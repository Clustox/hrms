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


def job_opening_custom_fields() -> dict:
	return {
		"Job Opening": [
			{
				"fieldname": "ats_section",
				"fieldtype": "Section Break",
				"label": _("Hiring Team"),
				"insert_after": "location",
			},
			{
				"fieldname": "job_owner",
				"fieldtype": "Link",
				"label": _("Job Owner"),
				"options": "User",
				"insert_after": "ats_section",
			},
			{
				"fieldname": "job_team",
				"fieldtype": "Table",
				"label": _("Job Team"),
				"options": "ATS Team Member",
				"insert_after": "job_owner",
			},
			{
				"fieldname": "salary_negotiable",
				"fieldtype": "Check",
				"label": _("Salary Negotiable"),
				"description": _("Show 'Negotiable' instead of a salary range."),
				"insert_after": "upper_range",
			},
		]
	}


def get_ats_custom_fields() -> dict:
	fields: dict[str, list] = {}
	for getter in (department_custom_fields, job_opening_custom_fields):
		for doctype, items in getter().items():
			fields.setdefault(doctype, []).extend(items)
	return fields


def apply_custom_fields():
	"""after_migrate hook: create/update every ATS custom field."""
	create_custom_fields(get_ats_custom_fields(), ignore_validate=True)
	frappe.clear_cache()


def seed_defaults():
	"""after_migrate hook: create the default pipeline template if it is missing."""
	from hrms.ats.pipeline import DEFAULT_TEMPLATE_NAME, default_stage_rows

	if frappe.db.exists("ATS Pipeline Template", DEFAULT_TEMPLATE_NAME):
		return

	template = frappe.get_doc(
		{
			"doctype": "ATS Pipeline Template",
			"template_name": DEFAULT_TEMPLATE_NAME,
			"description": "Standard hiring flow with technical screening, interviews and offer.",
			"stages": default_stage_rows(),
		}
	)
	template.insert(ignore_permissions=True)
