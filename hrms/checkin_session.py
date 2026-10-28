"""Reset a stale attendance session.

An employee who forgets to check out stays "checked in" -- the portal keeps
offering Check Out, so they can't cleanly start the next day. A check-in still
open STALE_CHECKIN_HOURS after its SHIFT START (e.g. a 12pm shift -> 6am the
next day; a check-in with no shift counts from its own time) is treated as a
MISSED check-out and its session is reset: the portal offers a fresh Check In
(see `useCheckin.js`, which uses the same window), and when that new check-in
is recorded the abandoned one is annotated here so HR can see why it has no
matching check-out.

The abandoned log itself is left untouched (no deletion, no fabricated OUT):
attendance for that day is exactly what it was, and HR can correct it through
the usual Attendance / Employee Checkin screens.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, format_datetime, get_datetime

# Keep in sync with STALE_CHECKIN_HOURS in frontend/src/composables/useCheckin.js
STALE_CHECKIN_HOURS = 18


def session_expires_at(shift_start, checkin_time):
	"""When a check-in's session lapses: STALE_CHECKIN_HOURS after the shift
	start, or after the check-in itself when it has no shift."""
	return add_to_date(get_datetime(shift_start or checkin_time), hours=STALE_CHECKIN_HOURS)


def reset_stale_session(doc, method=None):
	"""after_insert on Employee Checkin: a new IN that follows an earlier IN with
	no check-out in between, made after that earlier session lapsed, closes out
	that earlier session as a missed check-out."""
	if doc.log_type != "IN":
		return

	previous = frappe.db.get_value(
		"Employee Checkin",
		{"employee": doc.employee, "time": ("<", doc.time), "name": ("!=", doc.name)},
		["name", "log_type", "time", "shift_start"],
		as_dict=True,
		order_by="time desc",
	)
	if not previous or previous.log_type != "IN":
		return

	if get_datetime(doc.time) < session_expires_at(previous.shift_start, previous.time):
		return

	comment = _(
		"Session reset: no check-out was recorded within {0} hours of the shift start, "
		"so this check-in was treated as a missed check-out. A new session started at {1}."
	).format(STALE_CHECKIN_HOURS, format_datetime(doc.time))
	frappe.get_doc("Employee Checkin", previous.name).add_comment("Info", comment)
