"""Team-lead monthly CSV reports: hours logged + leaves taken.

A team lead downloads two reports for a chosen month, covering their DIRECT
reports only (employees whose `reports_to` is the lead) -- the same scope as the
rest of the team-visibility model (see request_visibility.py):

  * hours  -> one row per report: total worked hours + present/leave/absent days
  * leaves -> one row per report: days taken that month per leave type + total

Each endpoint returns ``{"columns": [...], "rows": [[...]]}`` so the frontend can
write a CSV generically. Scoped to the caller's own team, so there's nothing to
leak -- a lead only ever gets their own direct reports.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def _caller_employee():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def _direct_reports(emp):
	return frappe.get_all(
		"Employee",
		filters={"reports_to": emp, "status": "Active"},
		fields=["name", "employee_name"],
		order_by="employee_name",
	)


@frappe.whitelist()
def team_report(from_date: str, to_date: str, kind: str):
	"""Report over an arbitrary date range [from_date, to_date] (inclusive),
	`kind` = 'hours' | 'leaves'. Scoped to the caller's direct reports."""
	frm, to = getdate(from_date), getdate(to_date)
	if to < frm:
		frappe.throw(_("The end date can't be before the start date."))
	emp = _caller_employee()
	if not emp:
		frappe.throw(_("No employee record is linked to your account."))
	reports = _direct_reports(emp)
	if not reports:
		return {"columns": [], "rows": [], "empty": True}
	frm, to = str(frm), str(to)
	if kind == "hours":
		return _hours_report(reports, frm, to)
	if kind == "leaves":
		return _leaves_report(reports, frm, to)
	frappe.throw(_("Unknown report kind: {0}").format(kind))


def _attendance_counts(names, frm, to):
	rows = frappe.db.sql(
		"""SELECT employee, status, COUNT(*) c FROM `tabAttendance`
		   WHERE employee IN %(e)s AND attendance_date BETWEEN %(f)s AND %(t)s AND docstatus < 2
		   GROUP BY employee, status""",
		{"e": names, "f": frm, "t": to}, as_dict=True,
	)
	out = {}
	for r in rows:
		out.setdefault(r.employee, {})[r.status] = r.c
	return out


def _hours_report(reports, frm, to):
	from hrms.api import _get_employee_attendance_timesheet

	names = [r.name for r in reports]
	counts = _attendance_counts(names, frm, to)
	columns = ["Employee", "Name", "Total Hours", "Present Days", "Leave Days", "Absent Days"]
	rows = []
	for r in reports:
		ts = _get_employee_attendance_timesheet(r.name, frm, to)
		total = round(sum(flt(x.get("working_hours")) for x in ts), 2)
		cc = counts.get(r.name, {})
		leave_days = cc.get("On Leave", 0) + 0.5 * cc.get("Half Day", 0)
		rows.append([
			r.name, r.employee_name, total,
			cc.get("Present", 0), leave_days, cc.get("Absent", 0),
		])
	return {"columns": columns, "rows": rows}


def _leaves_report(reports, frm, to):
	names = [r.name for r in reports]
	# days on leave that month, per employee + leave type (On Leave = 1, Half Day = 0.5)
	data = frappe.db.sql(
		"""SELECT employee, leave_type,
		       SUM(CASE WHEN status = 'On Leave' THEN 1 WHEN status = 'Half Day' THEN 0.5 ELSE 0 END) days
		   FROM `tabAttendance`
		   WHERE employee IN %(e)s AND attendance_date BETWEEN %(f)s AND %(t)s AND docstatus < 2
		     AND leave_type IS NOT NULL AND leave_type != ''
		   GROUP BY employee, leave_type""",
		{"e": names, "f": frm, "t": to}, as_dict=True,
	)
	types = sorted({d.leave_type for d in data})
	per = {}
	for d in data:
		per.setdefault(d.employee, {})[d.leave_type] = flt(d.days)
	columns = ["Employee", "Name"] + types + ["Total"]
	rows = []
	for r in reports:
		vals = [per.get(r.name, {}).get(t, 0) for t in types]
		rows.append([r.name, r.employee_name] + vals + [round(sum(vals), 2)])
	return {"columns": columns, "rows": rows}
