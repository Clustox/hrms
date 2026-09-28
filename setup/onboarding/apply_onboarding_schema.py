"""Idempotent creation of onboarding custom fields. Run:
  bench --site test_onboarding.localhost execute setup.onboarding.apply_onboarding_schema.run
Re-runnable. The Employee Onboarding Document child doctype is shipped as code
(hrms/hr/doctype/employee_onboarding_document) and installed by migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def run():
	print("ONBOARDING_SCHEMA_START")
	fields = {
		"Employee": [
			{
				"fieldname": "custom_onboarding_status",
				"label": "Onboarding Status",
				"fieldtype": "Select",
				"options": "\nInvited\nSubmitted\nApproved",
				"read_only": 1,
				"insert_after": "status",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "custom_onboarding_submitted_on",
				"label": "Onboarding Submitted On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"insert_after": "custom_onboarding_status",
			},
			{
				"fieldname": "custom_onboarding_notes",
				"label": "Onboarding Review Notes",
				"fieldtype": "Small Text",
				"read_only": 1,
				"insert_after": "custom_onboarding_submitted_on",
			},
			{
				"fieldname": "custom_onboarding_documents",
				"label": "Onboarding Documents",
				"fieldtype": "Table",
				"options": "Employee Onboarding Document",
				"insert_after": "custom_onboarding_notes",
			},
		],
		"Employee Education": [
			{
				"fieldname": "custom_certificate",
				"label": "Certificate",
				"fieldtype": "Attach",
				"insert_after": "grade",
			},
		],
		"Employee External Work History": [
			{
				"fieldname": "custom_experience_letter",
				"label": "Experience Letter",
				"fieldtype": "Attach",
				"insert_after": "total_experience",
			},
		],
	}
	create_custom_fields(fields, update=True)
	frappe.db.commit()
	print("ONBOARDING_SCHEMA_DONE")
