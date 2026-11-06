"""ATS (applicant tracking) schema that is added on top of existing HRMS/ERPNext doctypes.

Custom fields are applied from `after_migrate`, so they land on fresh installs and on
existing sites alike. `create_custom_fields` is idempotent, which makes re-running safe.
Each ATS feature contributes its own `*_custom_fields()` function below.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def department_custom_fields() -> dict:
	return {
		"Department": [
			{
				"fieldname": "ats_section",
				"fieldtype": "Section Break",
				"label": _("Recruitment"),
				"insert_after": "disabled",
			},
			{
				"fieldname": "industry",
				"fieldtype": "Data",
				"label": _("Industry"),
				"insert_after": "ats_section",
			},
			{
				"fieldname": "department_location",
				"fieldtype": "Data",
				"label": _("Location"),
				"insert_after": "industry",
			},
			{
				"fieldname": "ats_column_break",
				"fieldtype": "Column Break",
				"insert_after": "department_location",
			},
			{
				"fieldname": "department_owner",
				"fieldtype": "Link",
				"label": _("Department Owner"),
				"options": "User",
				"insert_after": "ats_column_break",
			},
			{
				"fieldname": "department_team",
				"fieldtype": "Table",
				"label": _("Department Team"),
				"options": "ATS Team Member",
				"insert_after": "department_owner",
			},
		]
	}


def get_ats_custom_fields() -> dict:
	fields: dict[str, list] = {}
	for getter in (department_custom_fields,):
		for doctype, items in getter().items():
			fields.setdefault(doctype, []).extend(items)
	return fields


def apply_custom_fields():
	"""after_migrate hook: create/update every ATS custom field."""
	create_custom_fields(get_ats_custom_fields(), ignore_validate=True)
	frappe.clear_cache()
