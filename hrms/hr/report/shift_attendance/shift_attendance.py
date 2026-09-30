# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
#
# Clustox: this report is repurposed as a per-employee daily timesheet driven by
# Employee Checkins (the same source the /hrms PWA timesheet uses), because this
# instance does not run auto-attendance, so Attendance records barely exist and
# the stock Attendance-based version showed "Nothing to show". Each row is one
# employee-day derived from the day's check-in/out, with the punctuality Status
# (Early / On Time / Late) against the shift start, a 10-minute buffer either way.

import frappe
from frappe import _
from frappe.utils import cint, flt, format_datetime, format_duration, getdate

# A single in->out span longer than this is a missed punch, not real hours.
MAX_SHIFT_HOURS = 16
# Early / On Time / Late buffer (minutes) around the scheduled shift start.
PUNCTUALITY_BUFFER_MIN = 10


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	report_summary = get_report_summary(data)
	return columns, data, None, chart, report_summary


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 200,
		},
		{
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"label": _("Employee Name"),
			"width": 150,
		},
		{
			"label": _("Attendance Date"),
			"fieldname": "attendance_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": _("Shift"),
			"fieldname": "shift",
			"fieldtype": "Link",
			"options": "Shift Type",
			"width": 120,
		},
		{
			"label": _("Check-in"),
			"fieldname": "in_time",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Check-out"),
			"fieldname": "out_time",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"label": _("Working Hours"),
			"fieldname": "working_hours",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Shift Start"),
			"fieldname": "shift_start",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Shift End"),
			"fieldname": "shift_end",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Late Entry By"),
			"fieldname": "late_entry_hrs",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Early Exit By"),
			"fieldname": "early_exit_hrs",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 150,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 130,
		},
	]


def get_data(filters):
	if not (filters.get("from_date") and filters.get("to_date")):
		frappe.throw(_("Please select a From Date and To Date."))

	employees = _employees_in_scope(filters)
	if not employees:
		return []

	checkin_filters = {
		"employee": ["in", list(employees)],
		"time": ["between", [filters.from_date, f"{filters.to_date} 23:59:59"]],
	}
	if filters.get("shift"):
		checkin_filters["shift"] = filters.shift

	checkins = frappe.get_all(
		"Employee Checkin",
		filters=checkin_filters,
		fields=["employee", "log_type", "time", "shift", "shift_start", "shift_end"],
		order_by="employee asc, time asc",
	)

	rows = _group_by_employee_day(checkins)

	result = []
	for row in rows:
		emp = employees[row["employee"]]
		row["employee_name"] = emp.get("employee_name")
		row["department"] = emp.get("department")
		row["company"] = emp.get("company")
		_finalize_row(row)

		# Optional late-entry / early-exit filters.
		if filters.get("late_entry") and row.get("status") != "Late":
			continue
		if filters.get("early_exit") and not row.get("early_exit_hrs"):
			continue

		result.append(row)

	result.sort(key=lambda r: (r["employee_name"] or "", str(r["attendance_date"])))
	return result


def _employees_in_scope(filters):
	emp_filters = {}
	for field in ("employee", "department", "company"):
		if filters.get(field):
			emp_filters["name" if field == "employee" else field] = filters[field]

	employees = frappe.get_all(
		"Employee",
		filters=emp_filters,
		fields=["name", "employee_name", "department", "company"],
	)
	return {e["name"]: e for e in employees}


def _group_by_employee_day(checkins):
	"""One row per (employee, day): pair each check-IN with the next check-OUT
	(across midnight), capping a single span at MAX_SHIFT_HOURS so a missed punch
	doesn't glue an IN to an OUT days later. A new IN supersedes an unclosed one.
	"""
	rows = {}
	pending = {}  # employee -> open IN log

	def row_for(emp, when):
		key = (emp, getdate(when).isoformat())
		return rows.setdefault(
			key,
			{
				"employee": emp,
				"attendance_date": getdate(when).isoformat(),
				"shift": None,
				"shift_start": None,
				"shift_end": None,
				"in_time": None,
				"out_time": None,
				"working_hours": None,
			},
		)

	for log in checkins:
		emp = log.employee
		if log.log_type == "IN":
			pending[emp] = log
			row = row_for(emp, log.time)
			if row["in_time"] is None:
				row["in_time"] = log.time
				row["shift"] = log.shift
				row["shift_start"] = log.shift_start
				row["shift_end"] = log.shift_end
		elif log.log_type == "OUT":
			open_in = pending.pop(emp, None)
			hours = (log.time - open_in.time).total_seconds() / 3600 if open_in else None
			if hours is not None and 0 <= hours <= MAX_SHIFT_HOURS:
				row = row_for(emp, open_in.time)
				row["out_time"] = log.time
				row["working_hours"] = round((row["working_hours"] or 0) + hours, 2)
			else:
				# no open IN, or an implausibly long span (missed punch)
				row_for(emp, log.time)["out_time"] = log.time

	return list(rows.values())


def _finalize_row(row):
	in_t = row["in_time"]
	out_t = row["out_time"]
	ss = row["shift_start"]
	se = row["shift_end"]

	# Punctuality vs the scheduled shift start, with a buffer either side.
	if in_t and ss:
		diff_min = (in_t - ss).total_seconds() / 60
		if diff_min > PUNCTUALITY_BUFFER_MIN:
			row["status"] = "Late"
		elif diff_min < -PUNCTUALITY_BUFFER_MIN:
			row["status"] = "Early"
		else:
			row["status"] = "On Time"
	else:
		row["status"] = None

	row["late_entry_hrs"] = (
		format_duration((in_t - ss).total_seconds()) if (in_t and ss and in_t > ss) else None
	)
	row["early_exit_hrs"] = (
		format_duration((se - out_t).total_seconds()) if (out_t and se and out_t < se) else None
	)

	precision = cint(frappe.db.get_default("float_precision")) or 2
	row["working_hours"] = (
		flt(row["working_hours"], precision) if row["working_hours"] is not None else None
	)
	row["in_time"] = format_datetime(in_t) if in_t else None
	row["out_time"] = format_datetime(out_t) if out_t else None
	row["shift_start"] = format_datetime(ss) if ss else None
	row["shift_end"] = format_datetime(se) if se else None


def get_report_summary(data):
	if not data:
		return None

	on_time = sum(1 for d in data if d.get("status") == "On Time")
	late = sum(1 for d in data if d.get("status") == "Late")
	early = sum(1 for d in data if d.get("status") == "Early")
	total_hours = sum((d.get("working_hours") or 0) for d in data)

	return [
		{"value": len(data), "indicator": "Blue", "label": _("Days"), "datatype": "Int"},
		{"value": on_time, "indicator": "Green", "label": _("On Time"), "datatype": "Int"},
		{"value": late, "indicator": "Red", "label": _("Late"), "datatype": "Int"},
		{"value": early, "indicator": "Orange", "label": _("Early"), "datatype": "Int"},
		{
			"value": flt(total_hours, 1),
			"indicator": "Blue",
			"label": _("Total Hours"),
			"datatype": "Float",
		},
	]


def get_chart_data(data):
	if not data:
		return None

	buckets = {"On Time": 0, "Late": 0, "Early": 0}
	for d in data:
		if d.get("status") in buckets:
			buckets[d["status"]] += 1

	return {
		"data": {
			"labels": [_(k) for k in buckets],
			"datasets": [{"name": _("Status"), "values": list(buckets.values())}],
		},
		"type": "percentage",
	}
