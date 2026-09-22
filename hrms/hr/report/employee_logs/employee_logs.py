# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Employee Checkin, grouped one row per employee per day (earliest IN,
latest OUT), instead of the doctype list's one row per individual log --
mirrors the same grouping hrms.api.get_employee_checkin_history does for the
ESS Timesheet, just across employees/with filters for Desk.

Doesn't reuse the existing "Shift Attendance" report: that one requires each
Attendance to already be linked to a Shift Type and to its originating
Employee Checkin (via Employee Checkin.attendance), which only happens
through the shift-based auto-attendance job. This works directly off raw
Employee Checkin rows, so it has data regardless of whether that's set up.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 130},
		{"label": _("Check-in"), "fieldname": "check_in", "fieldtype": "Datetime", "width": 200},
		{"label": _("Check-in Status"), "fieldname": "check_in_status", "fieldtype": "Data", "width": 150},
		{"label": _("Check-out"), "fieldname": "check_out", "fieldtype": "Datetime", "width": 200},
		{"label": _("Check-out Status"), "fieldname": "check_out_status", "fieldtype": "Data", "width": 150},
		{"label": _("Worked Hours"), "fieldname": "worked_hours", "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			checkin.employee as employee,
			employee.employee_name as employee_name,
			employee.company as company,
			date(checkin.time) as date,
			min(case when checkin.log_type = 'IN' then checkin.time end) as check_in,
			max(case when checkin.log_type = 'OUT' then checkin.time end) as check_out
		from `tabEmployee Checkin` checkin
		inner join `tabEmployee` employee on employee.name = checkin.employee
		where {conditions}
		group by checkin.employee, date(checkin.time)
		order by date desc, employee.employee_name
		""",
		values,
		as_dict=True,
	)

	precision = cint(frappe.db.get_default("float_precision")) or 2
	for row in rows:
		row.check_in_status = _("Present") if row.check_in else _("Missing")
		row.check_out_status = _("Present") if row.check_out else _("Missing")
		if row.check_in and row.check_out:
			hours = flt((row.check_out - row.check_in).total_seconds() / 3600, precision)
			h, m = int(hours), round((hours % 1) * 60)
			row.worked_hours = _("{0}h {1}m").format(h, str(m).zfill(2))
		else:
			row.worked_hours = "--"

	return rows


def get_conditions(filters) -> tuple[str, dict]:
	conditions = ["1=1"]
	values = {}

	if filters.from_date:
		conditions.append("date(checkin.time) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.to_date:
		conditions.append("date(checkin.time) <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.employee:
		conditions.append("checkin.employee = %(employee)s")
		values["employee"] = filters.employee
	if filters.company:
		conditions.append("employee.company = %(company)s")
		values["company"] = filters.company

	# Raw SQL bypasses frappe.get_list's automatic user-permission scoping --
	# an Employee/ESS-only user (no HR role) only ever sees their own record.
	hr_roles = {"HR Manager", "HR User", "System Manager"}
	if not hr_roles & set(frappe.get_roles()):
		own_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		conditions.append("checkin.employee = %(own_employee)s")
		values["own_employee"] = own_employee or ""

	return " and ".join(conditions), values
