# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""
Posts a branded birthday-card image to Slack for every employee whose
birthday is today, alongside (not replacing) the existing email-based
`hrms.controllers.employee_reminders.send_birthday_reminders`.

Config (kept out of the database, same convention as other outbound-secret
values in this app -- see frappe.conf.get usages elsewhere, e.g.
hrms/utils/__init__.py's "ip-api-key"):

	site_config.json
	{
		...
		"hr_birthday_slack_webhook_url": "https://hooks.slack.com/services/...",
		"hr_birthday_slack_bot_token": "xoxb-..."
	}

`hr_birthday_slack_bot_token` is optional (a Slack Bot User OAuth token with
the `users:read` scope). When set, it's used to look up each birthday
person's real Slack account by matching Employee.employee_name against the
workspace's member list (`users.list`), so the post can `<@mention>` them for
real instead of just bold-printing their name, and so their Slack profile
photo can stand in when Employee.image isn't set. Without it, both of those
quietly fall back to their old behaviour (plain bold name, cupcake icon) --
same fail-safe shape as everything else in this module.

Toggle (HR Settings > Reminders > "Birthdays on Slack", a Check field,
same pattern as the existing "send_birthday_reminders" email toggle):
	frappe.db.get_single_value("HR Settings", "send_birthday_slack_notification")

If either the webhook URL is unset or the toggle is off, the job is a no-op
-- same fail-safe shape as the email reminder functions in this module's
sibling, employee_reminders.py.
"""

import math
import os
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.utils import get_url

from hrms.controllers.employee_reminders import get_employees_who_are_born_today

DEFAULT_MESSAGE = _(
	"May this year ahead bring you all the success you deserve, and we hope "
	"that your special day is as enjoyable as it can be. Have a "
	"well-deserved, thoroughly enjoyable birthday!"
)


def send_birthday_slack_notifications():
	"""Post a birthday card to Slack for every employee born today.

	Scheduler entry point (see hooks.py). Mirrors the enable/no-op shape of
	`employee_reminders.send_birthday_reminders`, just for Slack instead of
	email, and reuses the same "who's born today" query rather than
	duplicating it.
	"""
	to_send = int(frappe.db.get_single_value("HR Settings", "send_birthday_slack_notification") or 0)
	if not to_send:
		return

	webhook_url = frappe.conf.get("hr_birthday_slack_webhook_url")
	if not webhook_url:
		frappe.log_error(
			title="Birthday Slack notification skipped",
			message="HR Settings > Birthdays on Slack is enabled, but "
			"'hr_birthday_slack_webhook_url' is not set in site_config.json.",
		)
		return

	employees_born_today = get_employees_who_are_born_today()

	# Fetched (at most) once per run and matched in-process below, rather than
	# from within each enqueued job -- there's one Slack workspace directory
	# to look up against regardless of how many people share a birthday
	# today, so one `users.list` call serves all of them.
	slack_directory = _fetch_slack_directory()

	for _company, birthday_persons in employees_born_today.items():
		for person in birthday_persons:
			slack_user = _match_slack_user(person.get("name"), slack_directory)

			# One Slack message per person, enqueued individually so a slow/failed
			# Slack call for one person never blocks or fails the others, and never
			# blocks the scheduler tick itself.
			frappe.enqueue(
				_send_one_birthday_card_to_slack,
				queue="short",
				employee_name=person.get("name"),
				image=person.get("image"),
				webhook_url=webhook_url,
				slack_mention=f"<@{slack_user['id']}>" if slack_user else None,
				slack_avatar_url=(slack_user or {}).get("avatar_url"),
			)


def _send_one_birthday_card_to_slack(
	employee_name: str,
	image: str | None,
	webhook_url: str,
	slack_mention: str | None = None,
	slack_avatar_url: str | None = None,
):
	png_path = None
	try:
		png_path = render_birthday_card(employee_name, image, slack_avatar_url=slack_avatar_url)
		image_url = save_card_as_public_file(png_path, employee_name)
		post_birthday_card_to_slack(webhook_url, employee_name, image_url, mention=slack_mention)
	except Exception:
		frappe.log_error(
			title="Failed to send birthday Slack notification",
			message=frappe.get_traceback(),
		)
	finally:
		if png_path and os.path.exists(png_path):
			os.remove(png_path)


def _fetch_slack_directory() -> list[dict]:
	"""Return every non-bot, non-deleted member of the Slack workspace as
	{"id", "names": [...], "avatar_url"} dicts, or [] if no bot token is
	configured or the lookup fails for any reason -- this is a nice-to-have
	(a real @mention and a nicer photo fallback), never a reason to stop the
	birthday post itself.
	"""
	import requests

	bot_token = frappe.conf.get("hr_birthday_slack_bot_token")
	if not bot_token:
		return []

	members = []
	cursor = None
	try:
		while True:
			response = requests.get(
				"https://slack.com/api/users.list",
				headers={"Authorization": f"Bearer {bot_token}"},
				params={"limit": 200, "cursor": cursor} if cursor else {"limit": 200},
				timeout=10,
			)
			response.raise_for_status()
			data = response.json()
			if not data.get("ok"):
				frappe.log_error(
					title="Birthday Slack mention lookup failed",
					message=f"users.list returned error: {data.get('error')}",
				)
				return []

			for member in data.get("members", []):
				if member.get("deleted") or member.get("is_bot") or member.get("id") == "USLACKBOT":
					continue
				profile = member.get("profile") or {}
				names = {
					n.strip()
					for n in (profile.get("real_name"), profile.get("display_name"), member.get("real_name"))
					if n and n.strip()
				}
				if not names:
					continue
				members.append(
					{
						"id": member["id"],
						"names": names,
						"avatar_url": profile.get("image_512") or profile.get("image_192"),
					}
				)

			cursor = (data.get("response_metadata") or {}).get("next_cursor")
			if not cursor:
				break
	except Exception:
		frappe.log_error(title="Birthday Slack mention lookup failed", message=frappe.get_traceback())
		return []

	return members


def _match_slack_user(employee_name: str | None, slack_directory: list[dict]) -> dict | None:
	"""Match an Employee's name against the Slack directory fetched above by
	exact, case/whitespace-insensitive comparison against any of a member's
	known names (real name or display name) -- deliberately not a fuzzy
	match: a wrong @mention pings a stranger, so an unmatched name should
	fall back to plain text rather than guess.
	"""
	if not employee_name or not slack_directory:
		return None

	normalized = " ".join(employee_name.split()).casefold()
	for member in slack_directory:
		if any(normalized == " ".join(name.split()).casefold() for name in member["names"]):
			return member

	return None


def render_birthday_card(employee_name: str, image: str | None, slack_avatar_url: str | None = None) -> str:
	"""Render the birthday-card HTML template to a PNG via wkhtmltoimage,
	then composite the circular photo (or initials) and the "HAPPY BIRTHDAY"
	ring text on top with Pillow -- see the comment on `.photo-placeholder`
	in birthday_card.html for why that part isn't done in CSS/SVG.

	Returns the local filesystem path of the generated PNG (caller is
	responsible for cleaning it up once it's been uploaded/attached).
	"""
	assets_dir = frappe.get_app_path("hrms", "templates", "slack", "assets")
	html = frappe.render_template(
		"templates/slack/birthday_card.html",
		{
			"employee_name": employee_name,
			"message": DEFAULT_MESSAGE,
			"logo_path": "file://" + os.path.join(assets_dir, "clustox_logo.png").replace(os.sep, "/"),
			"alex_brush_font_path": "file://"
			+ os.path.join(assets_dir, "AlexBrush-Regular.ttf").replace(os.sep, "/"),
			"footer_path": "file://" + os.path.join(assets_dir, "footer.png").replace(os.sep, "/"),
		},
	)

	html_fd, html_path = tempfile.mkstemp(suffix=".html", prefix="birthday_card_")
	png_fd, png_path = tempfile.mkstemp(suffix=".png", prefix="birthday_card_")
	os.close(png_fd)  # wkhtmltoimage writes this file itself; we only need the path

	try:
		with os.fdopen(html_fd, "w", encoding="utf-8") as f:
			f.write(html)

		subprocess.run(
			[
				"wkhtmltoimage",
				"--enable-local-file-access",
				"--width",
				"700",
				"--disable-smart-width",
				"--quality",
				"90",
				html_path,
				png_path,
			],
			check=True,
			capture_output=True,
			timeout=60,
		)
	finally:
		os.remove(html_path)

	_composite_photo_circle(png_path, employee_name, image, slack_avatar_url)

	return png_path


# Must match `.photo-placeholder`'s `background` in birthday_card.html --
# an unmistakable marker color so its exact rendered position/size can be
# found in the PNG regardless of how the layout above it reflows.
_PHOTO_MARKER_RGB = (255, 0, 255)

_RING_TEXT = "  •  HAPPY BIRTHDAY  •  HAPPY BIRTHDAY  •  HAPPY BIRTHDAY  "
_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _composite_photo_circle(
	png_path: str, employee_name: str, image: str | None, slack_avatar_url: str | None = None
) -> None:
	from PIL import Image, ImageChops, ImageDraw, ImageOps

	card = Image.open(png_path).convert("RGBA")

	# Find the placeholder's exact bounding box by diffing against a
	# same-size solid-marker-color image -- zero-diff pixels are the marker.
	marker_diff = ImageChops.difference(card.convert("RGB"), Image.new("RGB", card.size, _PHOTO_MARKER_RGB))
	marker_mask = marker_diff.convert("L").point(lambda p: 255 if p == 0 else 0)
	bbox = marker_mask.getbbox()
	if not bbox:
		# Template markup changed and the marker's gone -- nothing to composite onto.
		frappe.log_error(
			title="Birthday card photo placeholder not found",
			message=f"Expected a #{bytes(_PHOTO_MARKER_RGB).hex()} marker in the rendered card for "
			f"{employee_name!r} but none was found. Was `.photo-placeholder` removed/recolored?",
		)
		return

	diameter = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
	center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
	circle_box = (
		center[0] - diameter // 2,
		center[1] - diameter // 2,
		center[0] + diameter // 2,
		center[1] + diameter // 2,
	)

	# Erase the marker square first -- pasting the circle with its mask below
	# only overwrites the pixels *inside* the circle, so the square's corners
	# would otherwise stay magenta.
	card.paste(Image.new("RGB", (bbox[2] - bbox[0], bbox[3] - bbox[1]), (255, 255, 255)), bbox[:2])

	circle_mask = Image.new("L", (diameter, diameter), 0)
	ImageDraw.Draw(circle_mask).ellipse((0, 0, diameter, diameter), fill=255)

	# Employee.image first; the Slack profile photo (if a mention was matched)
	# is a nicer stand-in than the cupcake when HR just hasn't uploaded one.
	photo = _open_employee_photo(image) or _open_employee_photo(slack_avatar_url)
	if photo:
		photo_fit = ImageOps.fit(photo.convert("RGB"), (diameter, diameter), method=Image.LANCZOS)
		card.paste(photo_fit, circle_box[:2], circle_mask)
	else:
		fallback = _fallback_cupcake_image(diameter)
		card.paste(fallback, circle_box[:2], circle_mask)

	_draw_ring_text(card, center, diameter / 2 + 14, _RING_TEXT)

	card.convert("RGB").save(png_path, "PNG")


def _fallback_cupcake_image(diameter: int):
	"""A birthday cupcake icon, used in place of a photo when an employee has
	none set. Bundled as a static asset at
	hrms/templates/slack/assets/cupcake_fallback.png.
	"""
	from PIL import Image

	assets_dir = frappe.get_app_path("hrms", "templates", "slack", "assets")
	cupcake = Image.open(os.path.join(assets_dir, "cupcake_fallback.png")).convert("RGBA")

	canvas = Image.new("RGB", (diameter, diameter), (253, 248, 240))  # warm cream background
	# Fit within the circle with a margin, preserving aspect ratio -- unlike
	# the photo path (ImageOps.fit/cover-crop), this icon has empty space
	# around it (candle flame, sprinkles) that cropping would cut into.
	target = int(diameter * 0.82)
	cupcake.thumbnail((target, target), Image.LANCZOS)
	paste_at = ((diameter - cupcake.width) // 2, (diameter - cupcake.height) // 2)
	canvas.paste(cupcake, paste_at, cupcake)

	return canvas


def _open_employee_photo(image: str | None):
	"""Return a Pillow Image for an Employee.image value, or None if there
	isn't one / it can't be loaded. Local Frappe file paths are opened
	straight off disk; anything else is treated as an external URL and
	fetched over HTTP, best-effort.
	"""
	from io import BytesIO

	from PIL import Image

	if not image:
		return None

	try:
		if image.startswith("/private/files/"):
			local_path = frappe.get_site_path("private", "files", image[len("/private/files/") :])
			return Image.open(local_path) if os.path.exists(local_path) else None
		elif image.startswith("/files/"):
			local_path = frappe.get_site_path("public", "files", image[len("/files/") :])
			return Image.open(local_path) if os.path.exists(local_path) else None
		else:
			import requests

			response = requests.get(image, timeout=10)
			response.raise_for_status()
			return Image.open(BytesIO(response.content))
	except Exception:
		# Any failure here (missing file, corrupt image, network error) just
		# means the initials fallback is used instead -- never let a bad
		# photo block the whole birthday card.
		return None


def _draw_ring_text(card, center: tuple, radius: float, text: str) -> None:
	"""Draw `text` running clockwise around a circle of `radius` centered on
	`center`, one rotated glyph at a time -- Pillow has no built-in
	curved-text primitive, so each character is rendered to its own small
	transparent tile, rotated to be tangent to the circle, and pasted at its
	computed position along the circumference.
	"""
	from PIL import Image, ImageDraw, ImageFont

	font = ImageFont.truetype(_FONT_PATH, size=13)
	n = len(text)
	if n == 0:
		return
	angle_step = 360 / n

	for i, ch in enumerate(text):
		if ch == " ":
			continue
		angle_deg = -90 + i * angle_step  # start at the top, go clockwise
		angle_rad = math.radians(angle_deg)
		x = center[0] + radius * math.cos(angle_rad)
		y = center[1] + radius * math.sin(angle_rad)

		fill = (63, 174, 74, 255) if ch == "•" else (27, 42, 74, 255)  # green dot separators, navy letters
		tile = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
		ImageDraw.Draw(tile).text((24, 24), ch, font=font, fill=fill, anchor="mm")
		# Rotate so the glyph reads upright as you walk clockwise around the ring.
		rotated = tile.rotate(-(angle_deg + 90), resample=Image.BICUBIC, expand=True)
		rw, rh = rotated.size
		card.paste(rotated, (int(x - rw / 2), int(y - rh / 2)), rotated)


def save_card_as_public_file(png_path: str, employee_name: str) -> str:
	"""Save the rendered PNG as a public Frappe File and return its absolute,
	internet-reachable URL -- Slack fetches `image_url` itself, so it has to
	be public, not just locally readable (unlike the photo embed above).
	"""
	with open(png_path, "rb") as f:
		content = f.read()

	safe_name = frappe.scrub(employee_name)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"birthday_card_{safe_name}_{frappe.utils.now_datetime().strftime('%Y%m%d')}.png",
			"content": content,
			"is_private": 0,
		}
	).insert(ignore_permissions=True)

	# frappe.utils.get_url() appends frappe.conf.webserver_port (our local dev
	# port, 8000) onto whatever host_name it's given -- correct for a bare
	# "hrms.localhost"-style dev hostname, but wrong once host_name is a
	# complete external URL already serving on its own standard port (e.g. a
	# reverse proxy or, for local testing, a Cloudflare tunnel -- see the
	# hr_birthday_slack_webhook_url comment above). When host_name is set
	# explicitly, trust it verbatim instead of letting get_url() rewrite it.
	host_name = frappe.conf.get("host_name")
	if host_name:
		return host_name.rstrip("/") + file_doc.file_url

	return get_url(file_doc.file_url)


def post_birthday_card_to_slack(webhook_url: str, employee_name: str, image_url: str, mention: str | None = None):
	import requests

	# `mention` is a ready-made "<@SLACKID>" (see _match_slack_user) -- Slack
	# renders that as a real, notifying @mention in mrkdwn text. Falls back to
	# the plain bold name when no Slack account was matched for this person.
	who = mention or f"*{employee_name}*"

	payload = {
		"text": _("🎉 It's {0}'s birthday today!").format(employee_name),
		"blocks": [
			{
				"type": "section",
				"text": {
					"type": "mrkdwn",
					"text": _("🎂 Happy Birthday {0}! 🎉").format(who),
				},
			},
			{
				"type": "image",
				"image_url": image_url,
				"alt_text": _("Happy Birthday {0}").format(employee_name),
			},
		],
	}

	response = requests.post(webhook_url, json=payload, timeout=15)
	response.raise_for_status()
