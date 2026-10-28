"""Reset a stale attendance session.

An employee who forgets to check out stays "checked in" -- the portal keeps
offering Check Out, so they can't cleanly start the next day. A check-in with no
check-out for STALE_CHECKIN_HOURS is treated as a MISSED check-out and its
session is reset: the portal offers a fresh Check In (see `useCheckin.js`, which
uses the same window), and when that new check-in is recorded the abandoned one
is annotated here so HR can see why it has no matching check-out.

The abandoned log itself is left untouched (no deletion, no fabricated OUT):
attendance for that day is exactly what it was, and HR can correct it through
the usual Attendance / Employee Checkin screens.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, time_diff_in_hours

# Keep in sync with STALE_CHECKIN_HOURS in frontend/src/composables/useCheckin.js
STALE_CHECKIN_HOURS = 18


def reset_stale_session(doc, method=None):
	"""after_insert on Employee Checkin: a new IN that follows an earlier IN with
	no check-out in between, more than STALE_CHECKIN_HOURS earlier, closes out
	that earlier session as a missed check-out."""
	if doc.log_type != "IN":
		return

	previous = frappe.db.get_value(
		"Employee Checkin",
		{"employee": doc.employee, "time": ("<", doc.time), "name": ("!=", doc.name)},
		["name", "log_type", "time"],
		as_dict=True,
		order_by="time desc",
	)
	if not previous or previous.log_type != "IN":
		return

	hours = time_diff_in_hours(get_datetime(doc.time), get_datetime(previous.time))
	if hours < STALE_CHECKIN_HOURS:
		return

	comment = _(
		"Session reset: no check-out was recorded within {0} hours of this check-in, "
		"so it was treated as a missed check-out. A new session started at {1}."
	).format(STALE_CHECKIN_HOURS, frappe.utils.format_datetime(doc.time))
	frappe.get_doc("Employee Checkin", previous.name).add_comment("Info", comment)
