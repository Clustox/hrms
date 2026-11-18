"""Clustox: cap an incomplete / forgotten-check-out attendance session.

With the overnight check-out buffer (shifts' allow_check_out_after_shift_end_time
extended so post-midnight punches link to the prior day), a *forgotten* check-out
can glue a much later punch onto a day and produce an implausible 18h+ "working
day". Nobody works more than 18 hours straight, so a session whose span exceeds
MAX_SESSION_HOURS is treated as incomplete and capped: working_hours is limited
to 18 and out_time is pulled back to in_time + 18h.

Registered on Attendance `validate` (hooks.py), so it applies to auto-attendance,
manual edits and the API alike. The PWA separately resets the check-in state
after 18h so the next day's check-in isn't blocked (see
frontend/src/composables/useCheckin.js).
"""
import frappe
from frappe.utils import add_to_date, get_datetime, time_diff_in_hours

MAX_SESSION_HOURS = 18


def cap_long_session(doc, method=None):
    if not (doc.get("in_time") and doc.get("out_time")):
        return
    in_t = get_datetime(doc.in_time)
    out_t = get_datetime(doc.out_time)
    if time_diff_in_hours(out_t, in_t) > MAX_SESSION_HOURS:
        doc.out_time = add_to_date(in_t, hours=MAX_SESSION_HOURS)
        doc.working_hours = MAX_SESSION_HOURS
