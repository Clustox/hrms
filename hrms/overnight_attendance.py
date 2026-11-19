"""Clustox: overnight / post-midnight attendance.

A shift's working session lasts SESSION_MAX_HOURS from its SHIFT START. A punch
inside that window belongs to the session, so a check-out after midnight is the
check-out of the previous day's shift, not a new day's check-in.

* `previous_session_shift`  -- used when a punch is stored: link it to the shift it
  belongs to when it falls outside every shift's own check-in/out window.
* `relink_and_reconcile`    -- repair already-stored punches and the Attendance
  that was computed from them (run once for November by a patch, and hourly for
  the last few days so a late check-out corrects an Absent made without it).
"""
import frappe
from frappe.utils import add_days, flt, get_datetime, getdate, today

from hrms.hr.doctype.employee_checkin.employee_checkin import update_attendance_in_checkins

SESSION_MAX_HOURS = 18
RECONCILE_DAYS = 3
EDITABLE_STATUSES = ("Present", "Absent", "Half Day")


def previous_session_shift(employee: str, timestamp):
	"""Shift details of the shift whose session (start .. start + 18h) contains
	`timestamp`, or {} when there is none."""
	from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

	timestamp = get_datetime(timestamp)
	# the shift that started on the punch's own date, then the previous date's
	for day in (timestamp, add_days(timestamp, -1)):
		shift = get_employee_shift(employee, day, True)
		if not shift:
			continue
		elapsed = (timestamp - get_datetime(shift.start_datetime)).total_seconds()
		if 0 <= elapsed <= SESSION_MAX_HOURS * 3600:
			return shift
	return {}


def reconcile_recent():
	"""Hourly: repair the last RECONCILE_DAYS days."""
	frappe.flags.mute_emails = True
	relink_and_reconcile(add_days(today(), -RECONCILE_DAYS))


def relink_and_reconcile(from_date):
	"""Group each employee's punches (from `from_date`) into sessions, re-link
	post-midnight punches to the session's shift, then recompute the session's
	Attendance when punches are not yet accounted for in it. Idempotent; does not
	commit. Skips Attendance from leave or a request, and any status other than
	Present / Absent / Half Day. Every change is commented on the Attendance."""
	logs = frappe.get_all(
		"Employee Checkin",
		filters={"time": [">=", str(from_date)]},
		fields=[
			"name",
			"employee",
			"time",
			"log_type",
			"shift",
			"shift_start",
			"shift_end",
			"offshift",
			"attendance",
		],
		order_by="employee asc, time asc",
	)

	sessions = []
	open_session = {}
	for log in logs:
		emp, when = log.employee, get_datetime(log.time)
		current = open_session.get(emp)
		if current is None or (when - current["start"]).total_seconds() > SESSION_MAX_HOURS * 3600:
			start = get_datetime(log.shift_start) if log.shift_start else when
			current = open_session[emp] = {"start": start, "anchor": log, "logs": []}
			sessions.append(current)
		current["logs"].append(log)

	for session in sessions:
		anchor = session["anchor"]
		if not anchor.shift or len(session["logs"]) < 2:
			continue
		for log in session["logs"][1:]:
			if log.shift != anchor.shift or log.shift_start != anchor.shift_start or log.offshift:
				frappe.db.set_value(
					"Employee Checkin",
					log.name,
					{
						"shift": anchor.shift,
						"shift_start": anchor.shift_start,
						"shift_end": anchor.shift_end,
						"offshift": 0,
					},
					update_modified=False,
				)
				log.update(
					shift=anchor.shift,
					shift_start=anchor.shift_start,
					shift_end=anchor.shift_end,
					offshift=0,
				)
				log["relinked"] = True
		reconcile_session(session)


def reconcile_session(session):
	anchor, logs = session["anchor"], session["logs"]
	att_date = getdate(anchor.shift_start)
	existing = frappe.db.get_value(
		"Attendance",
		{"employee": anchor.employee, "attendance_date": att_date, "docstatus": 1},
		["name", "status", "working_hours", "in_time", "out_time", "attendance_request", "leave_application"],
		as_dict=True,
	)
	stray = {l.attendance for l in logs if l.attendance and (not existing or l.attendance != existing.name)}

	# Only act when the day's Attendance was computed from this session's first punch
	# (it is linked to it) and a later punch is not yet accounted for. Once every
	# punch is linked this stops, and an Attendance that HR created or edited by
	# hand (its punches never linked to it) is never overwritten.
	unaccounted = bool(
		existing
		and anchor.attendance == existing.name
		and any(l.get("relinked") or l.attendance != existing.name for l in logs[1:])
	)

	if (
		unaccounted
		and existing.status in EDITABLE_STATUSES
		and not (existing.attendance_request or existing.leave_application)
	):
		shift_type = frappe.get_cached_doc("Shift Type", anchor.shift)
		half = flt(shift_type.working_hours_threshold_for_half_day)
		absent = flt(shift_type.working_hours_threshold_for_absent)
		if shift_type.is_half_holiday(anchor.employee, att_date):
			half, absent = half / 2, absent / 2
		status, hours, late, early, in_time, out_time = shift_type.get_attendance(
			[frappe._dict(l) for l in logs], absent, half
		)
		if (
			status != existing.status
			or round(flt(hours), 2) != round(flt(existing.working_hours), 2)
			or in_time != existing.in_time
			or out_time != existing.out_time
		):
			frappe.db.set_value(
				"Attendance",
				existing.name,
				{
					"status": status,
					"working_hours": hours,
					"in_time": in_time,
					"out_time": out_time,
					"late_entry": int(late),
					"early_exit": int(early),
				},
				update_modified=False,
			)
			frappe.get_doc("Attendance", existing.name).add_comment(
				text=(
					f"Corrected for overnight shift: was {existing.status} / {flt(existing.working_hours)}h, "
					f"now {status} / {flt(hours)}h."
				)
			)
		update_attendance_in_checkins([l.name for l in logs], existing.name)

	for name in stray:
		cancel_if_orphaned(name, [l.name for l in logs])


def cancel_if_orphaned(attendance_name, moved_logs):
	"""Cancel an Attendance created only from a misread post-midnight punch."""
	att = frappe.db.get_value(
		"Attendance",
		attendance_name,
		["docstatus", "status", "attendance_request", "leave_application"],
		as_dict=True,
	)
	if not att or att.docstatus != 1 or att.status not in EDITABLE_STATUSES:
		return
	if att.attendance_request or att.leave_application:
		return
	if frappe.db.exists("Employee Checkin", {"attendance": attendance_name, "name": ["not in", moved_logs]}):
		return
	frappe.db.set_value(
		"Employee Checkin", {"attendance": attendance_name}, "attendance", None, update_modified=False
	)
	doc = frappe.get_doc("Attendance", attendance_name)
	try:
		doc.cancel()
		doc.add_comment(text="Cancelled: created from a post-midnight check-out of the previous overnight shift.")
	except Exception:
		frappe.log_error(title=f"Overnight fix: could not cancel stray Attendance {attendance_name}")
