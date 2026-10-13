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
from frappe.utils import cint, flt, get_datetime

from hrms.api import _get_shift_grace_periods, _late_early_flags


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

	# The two substring_index(group_concat(...)) columns pick the shift/shift_start
	# off the day's earliest IN log and shift_end off its latest OUT log, in the
	# same grouped query -- avoids an N+1 lookup per employee-day for the
	# late-entry/early-exit check below.
	rows = frappe.db.sql(
		f"""
		select
			checkin.employee as employee,
			employee.employee_name as employee_name,
			employee.company as company,
			date(checkin.time) as date,
			min(case when checkin.log_type = 'IN' then checkin.time end) as check_in,
			max(case when checkin.log_type = 'OUT' then checkin.time end) as check_out,
			substring_index(
				group_concat(case when checkin.log_type = 'IN' then checkin.shift end order by checkin.time asc),
				',', 1
			) as shift,
			substring_index(
				group_concat(case when checkin.log_type = 'IN' then checkin.shift_start end order by checkin.time asc),
				',', 1
			) as shift_start,
			substring_index(
				group_concat(case when checkin.log_type = 'OUT' then checkin.shift_end end order by checkin.time desc),
				',', 1
			) as shift_end
		from `tabEmployee Checkin` checkin
		inner join `tabEmployee` employee on employee.name = checkin.employee
		where {conditions}
		group by checkin.employee, date(checkin.time)
		order by date desc, employee.employee_name
		""",
		values,
		as_dict=True,
	)

	grace_periods = _get_shift_grace_periods({row.shift for row in rows if row.shift})

	precision = cint(frappe.db.get_default("float_precision")) or 2
	for row in rows:
		# shift_start/shift_end come back as strings from the group_concat +
		# substring_index trick above (GROUP_CONCAT is always text in MariaDB),
		# unlike check_in/check_out which MIN/MAX preserve as native datetimes.
		late_entry, early_exit = _late_early_flags(
			{
				"in_time": row.check_in,
				"out_time": row.check_out,
				"shift_start": get_datetime(row.shift_start) if row.shift_start else None,
				"shift_end": get_datetime(row.shift_end) if row.shift_end else None,
			},
			grace_periods.get(row.shift),
		)
		if not row.check_in:
			row.check_in_status = _("Missing")
		elif late_entry:
			row.check_in_status = _("Late")
		else:
			row.check_in_status = _("Present")

		if not row.check_out:
			row.check_out_status = _("Missing")
		elif early_exit:
			row.check_out_status = _("Early")
		else:
			row.check_out_status = _("Present")

		if row.check_in and row.check_out:
			hours = flt((row.check_out - row.check_in).total_seconds() / 3600, precision)
			h, m = int(hours), round((hours % 1) * 60)
			row.worked_hours = _("{0}h {1}m").format(h, str(m).zfill(2))
		else:
			row.worked_hours = "--"

		del row["shift"]
		del row["shift_start"]
		del row["shift_end"]

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
