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
				"fieldname": "pipeline_section",
				"fieldtype": "Section Break",
				"label": _("Hiring Pipeline"),
				"insert_after": "job_team",
			},
			{
				"fieldname": "pipeline_template",
				"fieldtype": "Link",
				"label": _("Pipeline Template"),
				"options": "ATS Pipeline Template",
				"description": _("Stages are copied from this template when the job is created."),
				"insert_after": "pipeline_section",
			},
			{
				"fieldname": "pipeline_stages",
				"fieldtype": "Table",
				"label": _("Pipeline Stages"),
				"options": "Job Pipeline Stage",
				"insert_after": "pipeline_template",
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


def job_applicant_custom_fields() -> dict:
	return {
		"Job Applicant": [
			{
				"fieldname": "candidate",
				"fieldtype": "Link",
				"label": _("Candidate"),
				"options": "Candidate",
				"read_only": 1,
				"no_copy": 1,
				"search_index": 1,
				"insert_after": "email_id",
			},
			{
				"fieldname": "pipeline_section",
				"fieldtype": "Section Break",
				"label": _("Pipeline"),
				"insert_after": "applicant_rating",
			},
			{
				"fieldname": "pipeline_stage",
				"fieldtype": "Data",
				"label": _("Pipeline Stage"),
				"search_index": 1,
				"in_standard_filter": 1,
				"insert_after": "pipeline_section",
			},
			{
				"fieldname": "stage_entered_on",
				"fieldtype": "Datetime",
				"label": _("Stage Entered On"),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "pipeline_stage",
			},
			{
				"fieldname": "pipeline_column_break",
				"fieldtype": "Column Break",
				"insert_after": "stage_entered_on",
			},
			{
				"fieldname": "is_dropped",
				"fieldtype": "Check",
				"label": _("Dropped"),
				"default": "0",
				"search_index": 1,
				"in_standard_filter": 1,
				"no_copy": 1,
				"insert_after": "pipeline_column_break",
			},
			{
				"fieldname": "drop_reason",
				"fieldtype": "Link",
				"label": _("Drop Reason"),
				"options": "Drop Reason",
				"depends_on": "eval:doc.is_dropped",
				"mandatory_depends_on": "eval:doc.is_dropped",
				"no_copy": 1,
				"insert_after": "is_dropped",
			},
			{
				"fieldname": "dropped_at_stage",
				"fieldtype": "Data",
				"label": _("Dropped At Stage"),
				"read_only": 1,
				"depends_on": "eval:doc.is_dropped",
				"no_copy": 1,
				"insert_after": "drop_reason",
			},
			{
				"fieldname": "department",
				"fieldtype": "Link",
				"label": _("Department"),
				"options": "Department",
				"fetch_from": "job_title.department",
				"read_only": 1,
				"search_index": 1,
				"in_standard_filter": 1,
				"insert_after": "designation",
			},
			{
				"fieldname": "legacy_id",
				"fieldtype": "Data",
				"label": _("Legacy ID"),
				"description": _("Identifier of this application in the system it was imported from."),
				"read_only": 1,
				"no_copy": 1,
				"search_index": 1,
				"insert_after": "source_name",
			},
		]
	}


def get_ats_custom_fields() -> dict:
	fields: dict[str, list] = {}
	for getter in (department_custom_fields, job_opening_custom_fields, job_applicant_custom_fields):
		for doctype, items in getter().items():
			fields.setdefault(doctype, []).extend(items)
	return fields


def apply_custom_fields():
	"""after_migrate hook: create/update every ATS custom field."""
	create_custom_fields(get_ats_custom_fields(), ignore_validate=True)
	ensure_indexes()
	frappe.clear_cache()


def ensure_indexes():
	"""Composite index that serves the pipeline board: one job, one stage, not dropped."""
	frappe.db.add_index("Job Applicant", ["job_title", "pipeline_stage", "is_dropped"], "ats_job_stage_dropped")


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


DEFAULT_DROP_REASONS = [
	"Not a fit for the role",
	"Salary expectation too high",
	"Candidate withdrew",
	"No response from candidate",
	"Position filled",
	"Failed technical assessment",
	"Duplicate application",
]


def seed_drop_reasons():
	"""after_migrate hook: create the standard drop reasons that are missing."""
	for reason in DEFAULT_DROP_REASONS:
		if not frappe.db.exists("Drop Reason", reason):
			frappe.get_doc({"doctype": "Drop Reason", "reason": reason}).insert(ignore_permissions=True)
