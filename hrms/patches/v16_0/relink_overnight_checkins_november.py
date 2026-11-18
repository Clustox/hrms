import frappe
from frappe.utils import flt, get_datetime, getdate

from hrms.api import SESSION_MAX_HOURS
from hrms.hr.doctype.employee_checkin.employee_checkin import update_attendance_in_checkins

# Open month only (Nov 2026 onward); closed months are never touched.
CUTOFF = "2026-11-01"
EDITABLE_STATUSES = ("Present", "Absent", "Half Day")


def execute():
	"""Fix overnight-shift check-ins that were read as a new day's check-in.

	1. Walk each employee's punches in time order and group them into sessions (a
	   punch within SESSION_MAX_HOURS of the session's shift start belongs to it).
	2. Re-link post-midnight punches to the session's shift.
	3. Recompute the session's existing Attendance (status / hours / in / out) and
	   cancel a stray Attendance that only existed because of the misread punch.

	Skips attendance created from leave or a request, and anything not
	Present/Absent/Half Day. Every change is recorded as a comment on the
	Attendance. Idempotent; does not commit."""
	frappe.flags.mute_emails = True

	logs = frappe.get_all(
		"Employee Checkin",
		filters={"time": [">=", CUTOFF]},
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
			current = open_session[emp] = {"start": start, "anchor": log, "logs": [], "changed": False}
			sessions.append(current)
		current["logs"].append(log)

	for session in sessions:
		anchor = session["anchor"]
		if not anchor.shift:
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
				log.update(shift=anchor.shift, shift_start=anchor.shift_start, shift_end=anchor.shift_end, offshift=0)
				session["changed"] = True
		if session["changed"]:
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

	if existing and existing.status in EDITABLE_STATUSES and not (
		existing.attendance_request or existing.leave_application
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
	"""Cancel an Attendance that was created only from a misread post-midnight punch."""
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
	others = frappe.db.exists(
		"Employee Checkin", {"attendance": attendance_name, "name": ["not in", moved_logs]}
	)
	if others:
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
