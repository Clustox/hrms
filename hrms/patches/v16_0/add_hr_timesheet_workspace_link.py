import json
import re

import frappe

WORKSPACE = "Shift & Attendance"
LINK_TO = "hr-timesheet"
CARD = "Reports"

# Known-good, sanitizer-safe content for this workspace, used if the stored
# content can no longer be parsed (see below).
FALLBACK_CONTENT = [
	{"id": "r0a57m9-Yx", "type": "chart", "data": {"chart_name": "Attendance Count", "col": 12}},
	{"id": "9_DQbkhJgn", "type": "spacer", "data": {"col": 12}},
	{"id": "mYz7o2zWVf", "type": "header", "data": {"text": "<b>Masters &amp; Reports</b>", "col": 12}},
	{"id": "iBvYqY6Ul6", "type": "card", "data": {"card_name": "Shifts", "col": 4}},
	{"id": "aCKU8VAUu8", "type": "card", "data": {"card_name": "Attendance", "col": 4}},
	{"id": "CMPmxSUFjB", "type": "card", "data": {"card_name": "Time", "col": 4}},
	{"id": "v61fwPM9fG", "type": "card", "data": {"card_name": "Overtime", "col": 4}},
	{"id": "WAO9X_IrfP", "type": "card", "data": {"card_name": "Reports", "col": 4}},
]


def execute():
	"""Add a "HR Timesheet" link (to the hr-timesheet Page) under the Reports
	card of the Shift & Attendance workspace, so HR can reach the per-employee
	timesheet overview from the desk.

	Frappe's Workspace save/import sanitizes header HTML and, on some versions,
	mangles inline style attributes into unescaped quotes that break the
	workspace's embedded-JSON content (blanking the whole desk). So we also
	strip style/class attributes from header blocks here, making the content
	robust to any future save. Idempotent and safe to re-run.
	"""
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	if not frappe.db.exists("Page", LINK_TO):
		# The Page ships with the app; if it isn't synced yet, skip quietly.
		return

	doc = frappe.get_doc("Workspace", WORKSPACE)

	_sanitize_content(doc)
	_ensure_link(doc)

	doc.save(ignore_permissions=True)


def _sanitize_content(doc):
	"""Strip style/class attributes from header blocks so the content survives
	frappe's HTML sanitizer without corrupting its escaping."""
	try:
		blocks = json.loads(doc.content or "[]")
	except (ValueError, TypeError):
		# Stored content is already corrupt/unparseable -> reset to known-good.
		doc.content = json.dumps(FALLBACK_CONTENT)
		return

	for block in blocks:
		if block.get("type") in ("header", "paragraph"):
			text = (block.get("data") or {}).get("text", "")
			text = re.sub(r'\s*style="[^"]*"', "", text)
			text = re.sub(r'\s*class="[^"]*"', "", text)
			block["data"]["text"] = text
	doc.content = json.dumps(blocks)


def _ensure_link(doc):
	if any((link.link_to or "") == LINK_TO for link in doc.links):
		return

	new_link = {
		"type": "Link",
		"label": "HR Timesheet",
		"link_type": "Page",
		"link_to": LINK_TO,
		"hidden": 0,
		"is_query_report": 0,
		"onboard": 0,
	}

	# Insert right after the Reports Card Break (fall back to the end) and bump
	# that card's link_count so the new link is grouped under it.
	rows = [link.as_dict() for link in doc.links]
	insert_at = len(rows)
	reports_idx = None
	for i, row in enumerate(rows):
		if row.get("type") == "Card Break" and (row.get("label") or "").strip() == CARD:
			reports_idx = i
			insert_at = i + 1
			break

	rows.insert(insert_at, new_link)

	doc.set("links", [])
	for row in rows:
		doc.append("links", row)

	if reports_idx is not None:
		for link in doc.links:
			if link.type == "Card Break" and (link.label or "").strip() == CARD:
				link.link_count = (link.link_count or 0) + 1
				break
