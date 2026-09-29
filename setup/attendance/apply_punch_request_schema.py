"""Idempotent schema for repurposing Attendance Request as an employee
"punch request" (a missed check-in / check-out that a manager approves).

Run:
  bench --site <site> execute setup.attendance.apply_punch_request_schema.run

Adds custom fields for the punch (type + time), a hidden marker + a link to the
Employee Checkin created on approval, and a "Missed Punch" option on the native
`reason` Select. The behaviour (create the checkin on submit, skip the native
attendance-range creation) lives in
hrms.overrides.attendance_request.PunchAttendanceRequest. Re-runnable.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def run():
	print("PUNCH_REQUEST_SCHEMA_START")
	fields = {
		"Attendance Request": [
			{
				"fieldname": "custom_is_punch_request",
				"label": "Is Punch Request",
				"fieldtype": "Check",
				"default": "0",
				"hidden": 1,
				"insert_after": "reason",
			},
			{
				"fieldname": "custom_log_type",
				"label": "Punch Type",
				"fieldtype": "Select",
				"options": "\nCheck-in\nCheck-out",
				"insert_after": "custom_is_punch_request",
				"depends_on": "custom_is_punch_request",
				"mandatory_depends_on": "custom_is_punch_request",
			},
			{
				"fieldname": "custom_punch_time",
				"label": "Punch Time",
				"fieldtype": "Time",
				"insert_after": "custom_log_type",
				"depends_on": "custom_is_punch_request",
				"mandatory_depends_on": "custom_is_punch_request",
			},
			{
				"fieldname": "custom_created_checkin",
				"label": "Created Employee Checkin",
				"fieldtype": "Link",
				"options": "Employee Checkin",
				"read_only": 1,
				"hidden": 1,
				"insert_after": "custom_punch_time",
			},
		],
	}
	create_custom_fields(fields, update=True)

	# Add a "Missed Punch" reason (append; existing options preserved) so punch
	# requests satisfy the required native `reason` Select with a sensible value.
	frappe.make_property_setter(
		{
			"doctype": "Attendance Request",
			"fieldname": "reason",
			"property": "options",
			"value": "Work From Home\nOn Duty\nMissed Punch",
			"property_type": "Text",
		},
		is_system_generated=False,
	)
	frappe.db.commit()
	print("PUNCH_REQUEST_SCHEMA_DONE")
