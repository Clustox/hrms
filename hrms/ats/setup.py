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
				"in_list_view": 1,
			},
			{
				"fieldname": "department_location",
				"fieldtype": "Data",
				"label": _("Location"),
				"insert_after": "industry",
				"in_list_view": 1,
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
				"in_list_view": 1,
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
				"in_list_view": 1,
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
				"fieldname": "counters_column_break",
				"fieldtype": "Column Break",
				"insert_after": "pipeline_stages",
			},
			{
				"fieldname": "headcount",
				"fieldtype": "Data",
				"label": _("Headcount"),
				"description": _("Positions - filled, for example 3 - 1."),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "counters_column_break",
				"in_list_view": 1,
			},
			{
				"fieldname": "hired_count",
				"fieldtype": "Int",
				"label": _("Hired"),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "headcount",
			},
			{
				"fieldname": "in_pipeline_count",
				"fieldtype": "Int",
				"label": _("In Pipeline"),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "hired_count",
			},
			{
				"fieldname": "dropped_count",
				"fieldtype": "Int",
				"label": _("Dropped"),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "in_pipeline_count",
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
				"fieldname": "candidate_title",
				"fieldtype": "Data",
				"label": _("Current Job Title"),
				"fetch_from": "candidate.current_title",
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "candidate",
			},
			{
				"fieldname": "candidate_employer",
				"fieldtype": "Data",
				"label": _("Current Employer"),
				"fetch_from": "candidate.current_employer",
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "candidate_title",
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
				"in_list_view": 1,
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
				"fieldname": "stage_entered_date",
				"fieldtype": "Date",
				"label": _("In Stage Since"),
				"description": _("Date only, for the board card. The exact time is in Stage Entered On."),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "stage_entered_on",
			},
			{
				"fieldname": "applied_on",
				"fieldtype": "Date",
				"label": _("Applied On"),
				"read_only": 1,
				"no_copy": 1,
				"insert_after": "stage_entered_date",
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
				"in_list_view": 1,
			},
			{
				"fieldname": "dropped_at_stage",
				"fieldtype": "Data",
				"label": _("Dropped At Stage"),
				"read_only": 1,
				"depends_on": "eval:doc.is_dropped",
				"no_copy": 1,
				"insert_after": "drop_reason",
				"in_list_view": 1,
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


def interview_custom_fields() -> dict:
	return {
		"Interview": [
			{
				"fieldname": "candidate_response",
				"fieldtype": "Select",
				"label": _("Candidate Response"),
				"options": chr(10).join(["", "Yes", "No", "Maybe"]),
				"read_only": 1,
				"no_copy": 1,
				"allow_on_submit": 1,
				"insert_after": "job_applicant",
				"description": _("The candidate's answer to the calendar invitation."),
			}
		]
	}


def get_ats_custom_fields() -> dict:
	fields: dict[str, list] = {}
	for getter in (department_custom_fields, job_opening_custom_fields, job_applicant_custom_fields, interview_custom_fields):
		for doctype, items in getter().items():
			fields.setdefault(doctype, []).extend(items)
	return fields


def apply_custom_fields(commit: bool = True):
	"""after_migrate hook: create/update every ATS custom field."""
	create_custom_fields(get_ats_custom_fields(), ignore_validate=True)
	ensure_indexes()
	if commit:
		frappe.db.commit()  # keep our changes even if a later after_migrate hook fails
	frappe.clear_cache()


def ensure_indexes():
	"""Composite index that serves the pipeline board: one job, one stage, not dropped."""
	frappe.db.add_index("Job Applicant", ["job_title", "pipeline_stage", "is_dropped"], "ats_job_stage_dropped")


def seed_defaults(commit: bool = True):
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
	if commit:
		frappe.db.commit()


DEFAULT_DROP_REASONS = [
	"Not a fit for the role",
	"Salary expectation too high",
	"Candidate withdrew",
	"No response from candidate",
	"Position filled",
	"Failed technical assessment",
	"Duplicate application",
	"Rejected before pipeline stages existed",
	"Rejected by recruiter",
]


def seed_drop_reasons(commit: bool = True):
	"""after_migrate hook: create the standard drop reasons that are missing."""
	for reason in DEFAULT_DROP_REASONS:
		if not frappe.db.exists("Drop Reason", reason):
			frappe.get_doc({"doctype": "Drop Reason", "reason": reason}).insert(ignore_permissions=True)
	if commit:
		frappe.db.commit()


CHANGE_HISTORY_DOCTYPES = ("Job Opening", "Job Applicant", "Job Offer")


def enable_change_history(commit: bool = True):
	"""after_migrate hook: keep a version history for recruitment records (off by default).

	Done with property setters, so the standard doctypes are not edited.
	"""
	for doctype in CHANGE_HISTORY_DOCTYPES:
		frappe.make_property_setter(
			{
				"doctype": doctype,
				"doctype_or_field": "DocType",
				"property": "track_changes",
				"value": "1",
				"property_type": "Check",
			},
			is_system_generated=False,
		)
	if commit:
		frappe.db.commit()
	frappe.clear_cache()


# Standard Job Opening fields the ATS Jobs list also shows (salary range and location)
LIST_COLUMN_FIELDS = {"Job Opening": ("location", "lower_range", "upper_range")}


def set_list_columns(commit: bool = True):
	"""after_migrate hook: show location and salary range as columns of the Job Opening list.

	A property setter, so the standard doctype is not edited. The Department and the other
	Job Opening columns come from the custom field definitions above."""
	for doctype, fieldnames in LIST_COLUMN_FIELDS.items():
		for fieldname in fieldnames:
			frappe.make_property_setter(
				{
					"doctype": doctype,
					"doctype_or_field": "DocField",
					"fieldname": fieldname,
					"property": "in_list_view",
					"value": "1",
					"property_type": "Check",
				},
				is_system_generated=False,
			)
	if commit:
		frappe.db.commit()
	frappe.clear_cache()
