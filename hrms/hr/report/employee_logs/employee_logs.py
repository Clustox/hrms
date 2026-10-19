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
from frappe.utils import add_days, cint, flt, get_datetime, getdate

from hrms.api import _get_shift_grace_periods, _late_early_flags
from hrms.hr.utils import get_checkin_location_labels


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
		{"label": _("Check-in"), "fieldname": "check_in", "fieldtype": "Data", "width": 210},
		{"label": _("Check-in Status"), "fieldname": "check_in_status", "fieldtype": "Data", "width": 150},
		{"label": _("Check-out"), "fieldname": "check_out", "fieldtype": "Data", "width": 210},
		{"label": _("Check-out Status"), "fieldname": "check_out_status", "fieldtype": "Data", "width": 150},
		{"label": _("Worked Hours"), "fieldname": "worked_hours", "fieldtype": "Data", "width": 150},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 220},
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
			) as shift_end,
			substring_index(
				group_concat(case when checkin.log_type = 'IN' then checkin.latitude end order by checkin.time asc),
				',', 1
			) as in_latitude,
			substring_index(
				group_concat(case when checkin.log_type = 'IN' then checkin.longitude end order by checkin.time asc),
				',', 1
			) as in_longitude,
			substring_index(
				group_concat(case when checkin.log_type = 'OUT' then checkin.latitude end order by checkin.time desc),
				',', 1
			) as out_latitude,
			substring_index(
				group_concat(case when checkin.log_type = 'OUT' then checkin.longitude end order by checkin.time desc),
				',', 1
			) as out_longitude
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

	# latitude/longitude come back as strings too (GROUP_CONCAT is always text
	# in MariaDB), hence the flt() below -- same reason shift_start/shift_end
	# need get_datetime() further down.
	in_locations = get_checkin_location_labels(
		[
			{
				"employee": row.employee,
				"shift": row.shift,
				"date": row.date,
				"latitude": flt(row.in_latitude) if row.in_latitude else None,
				"longitude": flt(row.in_longitude) if row.in_longitude else None,
			}
			for row in rows
		]
	)
	out_locations = get_checkin_location_labels(
		[
			{
				"employee": row.employee,
				"shift": row.shift,
				"date": row.date,
				"latitude": flt(row.out_latitude) if row.out_latitude else None,
				"longitude": flt(row.out_longitude) if row.out_longitude else None,
			}
			for row in rows
		]
	)

	precision = cint(frappe.db.get_default("float_precision")) or 2
	for row, in_location, out_location in zip(rows, in_locations, out_locations):
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

		# Formatted last, after the raw datetimes above are done with -- System
		# Settings' Time Format has no 12-hour option at all (just "HH:mm:ss" /
		# "HH:mm"), so this is spelled out explicitly rather than left to the
		# column's default Datetime rendering.
		row.check_in = _format_12h(row.check_in)
		row.check_out = _format_12h(row.check_out)
		row.location = _format_location(in_location, out_location)

		del row["shift"]
		del row["shift_start"]
		del row["shift_end"]
		del row["in_latitude"]
		del row["in_longitude"]
		del row["out_latitude"]
		del row["out_longitude"]

	# Nothing on this site auto-creates an Employee Checkin (or an Attendance
	# record) from an approved leave, so a leave day otherwise has no row at
	# all here (the main query above is keyed off Employee Checkin) and
	# silently vanishes from the report. Adds one explicitly for each
	# employee-day covered by an approved leave and nothing else.
	existing_days = {(row.employee, row.date) for row in rows}
	for leave_row in get_leave_rows(filters):
		if (leave_row.employee, leave_row.date) in existing_days:
			continue
		rows.append(
			{
				"employee": leave_row.employee,
				"employee_name": leave_row.employee_name,
				"company": leave_row.company,
				"date": leave_row.date,
				"check_in": "",
				"check_in_status": _("On Leave"),
				"check_out": "",
				"check_out_status": _("On Leave"),
				"worked_hours": "--",
				"location": "",
			}
		)

	rows.sort(key=lambda r: (str(r["date"]), r["employee_name"] or ""), reverse=True)
	return rows


def get_leave_rows(filters) -> list[dict]:
	"""One row per employee-day covered by an approved, submitted Leave
	Application within the report's date range/employee/company filters."""
	conditions, values = get_leave_conditions(filters)

	leaves = frappe.db.sql(
		f"""
		select
			la.employee as employee,
			employee.employee_name as employee_name,
			employee.company as company,
			la.from_date as from_date,
			la.to_date as to_date
		from `tabLeave Application` la
		inner join `tabEmployee` employee on employee.name = la.employee
		where la.status = 'Approved' and la.docstatus = 1 and {conditions}
		""",
		values,
		as_dict=True,
	)

	from_date = getdate(filters.from_date) if filters.from_date else None
	to_date = getdate(filters.to_date) if filters.to_date else None

	rows = []
	for leave in leaves:
		day = getdate(leave.from_date)
		leave_end = getdate(leave.to_date)
		if from_date and day < from_date:
			day = from_date
		if to_date and leave_end > to_date:
			leave_end = to_date

		while day <= leave_end:
			rows.append(
				frappe._dict(
					employee=leave.employee,
					employee_name=leave.employee_name,
					company=leave.company,
					date=day,
				)
			)
			day = add_days(day, 1)

	return rows


def _format_12h(dt) -> str:
	if not dt:
		return ""
	date_part = dt.strftime("%d-%m-%Y")
	time_part = dt.strftime("%I:%M %p").lstrip("0")  # "09:35 AM" -> "9:35 AM"
	return f"{date_part} {time_part}"


def _format_location(in_location, out_location) -> str:
	"""One short display string for the Location column. "Verified" means
	the punch fell inside an enforced Shift Location radius (so it can only
	ever be the configured place); everything else with coordinates is
	labelled "Remote" -- really "no enforced office reference point matched
	for that employee/shift/date", not a GPS-confirmed remote location, but
	shown as Remote since that's the practical reading in this org."""

	def _label(loc):
		if not loc:
			return None
		return _("Office") if loc["verified"] else _("Remote")

	in_label, out_label = _label(in_location), _label(out_location)
	if not in_label and not out_label:
		return ""
	if in_label == out_label:
		return in_label
	parts = []
	if in_label:
		parts.append(_("In: {0}").format(in_label))
	if out_label:
		parts.append(_("Out: {0}").format(out_label))
	return " · ".join(parts)


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


def get_leave_conditions(filters) -> tuple[str, dict]:
	"""Same employee/company/own-employee scoping as get_conditions, but for
	the Leave Application query: a date *range* overlap (la.from_date/to_date)
	rather than a single checkin timestamp falling between two dates."""
	conditions = ["1=1"]
	values = {}

	if filters.from_date:
		conditions.append("la.to_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.to_date:
		conditions.append("la.from_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.employee:
		conditions.append("la.employee = %(employee)s")
		values["employee"] = filters.employee
	if filters.company:
		conditions.append("employee.company = %(company)s")
		values["company"] = filters.company

	hr_roles = {"HR Manager", "HR User", "System Manager"}
	if not hr_roles & set(frappe.get_roles()):
		own_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		conditions.append("la.employee = %(own_employee)s")
		values["own_employee"] = own_employee or ""

	return " and ".join(conditions), values
