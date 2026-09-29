"""Clustox: make Employee.reports_to (the reporting manager) mandatory, so every
new employee is created with a manager. Applied as a property setter, re-runnable.
"""

import frappe


def execute():
	frappe.make_property_setter(
		{
			"doctype": "Employee",
			"fieldname": "reports_to",
			"property": "reqd",
			"value": "1",
			"property_type": "Check",
		},
		is_system_generated=False,
	)
	frappe.db.commit()
