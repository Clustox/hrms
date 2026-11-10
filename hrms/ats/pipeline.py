"""Pipeline stage rules shared by pipeline templates and per-job pipelines."""

import frappe
from frappe import _

STAGE_TYPES = ("Active", "Hired", "Rejected")

# Applicant status (the legacy HRMS field) that a stage maps to unless set explicitly.
DEFAULT_STATUS_BY_TYPE = {"Hired": "Accepted", "Rejected": "Rejected"}

DEFAULT_TEMPLATE_NAME = "Default Hiring Pipeline"

# (name, type, status, visible_to_guests). Order follows the reference screenshots:
# the two "Rejected after ..." stages sit before "Ready to Offer".
DEFAULT_STAGES = [
	("New Candidates", "Active", "Open", 0),
	("Technical Profile Review", "Active", "Open", 0),
	("Shortlisted (Phone Screening)", "Active", "Shortlisted", 1),
	("Technical Assessment", "Active", "Shortlisted", 1),
	("1st Technical Interview", "Active", "Shortlisted", 1),
	("2nd Technical Interview", "Active", "Shortlisted", 1),
	("Final Interview", "Active", "Shortlisted", 1),
	("Rejected after Technical Interview", "Rejected", "Rejected", 0),
	("Rejected after Final Interview", "Rejected", "Rejected", 0),
	# Ready to Offer / Offer Placed map to Accepted so the existing Job Offer and
	# onboarding flow (gated on Accepted) keeps working before the offer is accepted.
	("Ready to Offer", "Active", "Accepted", 0),
	("Offer Placed", "Active", "Accepted", 0),
	("Offer Accepted", "Hired", "Accepted", 0),
	("Offer Rejected", "Rejected", "Rejected", 0),
]


def validate_stages(stages) -> None:
	"""Validate and normalise a list of stage rows (template or job pipeline)."""
	if not stages:
		frappe.throw(_("A pipeline needs at least one stage."))

	seen = set()
	for idx, row in enumerate(stages):
		name = (row.stage_name or "").strip()
		if not name:
			frappe.throw(_("Row {0}: Stage Name is required.").format(idx + 1))
		row.stage_name = name

		key = name.lower()
		if key in seen:
			frappe.throw(_("Row {0}: Stage {1} is listed more than once.").format(idx + 1, frappe.bold(name)))
		seen.add(key)

		if row.stage_type not in STAGE_TYPES:
			row.stage_type = "Active"

		if not row.maps_to_status:
			if row.stage_type in DEFAULT_STATUS_BY_TYPE:
				row.maps_to_status = DEFAULT_STATUS_BY_TYPE[row.stage_type]
			else:
				row.maps_to_status = "Open" if idx == 0 else "Shortlisted"

	if stages[0].stage_type != "Active":
		frappe.throw(_("The first stage must be an Active stage, because new candidates start there."))


def default_stage_rows() -> list[dict]:
	return [
		{
			"stage_name": name,
			"stage_type": stage_type,
			"maps_to_status": status,
			"visible_to_guests": visible,
		}
		for name, stage_type, status, visible in DEFAULT_STAGES
	]


STAGE_COPY_FIELDS = (
	"stage_name",
	"stage_type",
	"maps_to_status",
	"visible_to_guests",
	"color",
	"auto_email_template",
	"require_reason",
)


def copy_template_stages(template_name: str) -> list[dict]:
	"""Stage rows of a template, as plain dicts that can be appended to a job."""
	template = frappe.get_doc("ATS Pipeline Template", template_name)
	return [{field: row.get(field) for field in STAGE_COPY_FIELDS} for row in template.stages]


def setup_job_pipeline(doc, method=None):
	"""Job Opening validate hook.

	A job with no stages gets a copy of its pipeline template (or the default template).
	The copy is independent: editing the template later never changes a live job.
	A job that already has stages keeps them and they are validated.
	"""
	if not doc.get("pipeline_stages"):
		template = doc.get("pipeline_template") or DEFAULT_TEMPLATE_NAME
		if not frappe.db.exists("ATS Pipeline Template", template):
			return  # nothing to copy (e.g. before the default template is seeded)
		for row in copy_template_stages(template):
			doc.append("pipeline_stages", row)

	if doc.get("pipeline_stages"):
		validate_stages(doc.pipeline_stages)


def log_stage_change(applicant: str, from_stage: str | None, to_stage: str | None, source: str = "Manual", reason: str | None = None):
	"""Append one row to the applicant's stage history."""
	job_opening = frappe.db.get_value("Job Applicant", applicant, "job_title")
	return frappe.get_doc(
		{
			"doctype": "Applicant Stage Log",
			"job_applicant": applicant,
			"job_opening": job_opening,
			"from_stage": from_stage,
			"to_stage": to_stage,
			"trigger_source": source,
			"reason": reason,
		}
	).insert(ignore_permissions=True)


def delete_applicant_stage_log(doc, method=None):
	"""Job Applicant on_trash hook: the history is removed together with its applicant."""
	frappe.flags.ats_allow_log_delete = True
	try:
		for name in frappe.get_all("Applicant Stage Log", filters={"job_applicant": doc.name}, pluck="name"):
			frappe.delete_doc("Applicant Stage Log", name, force=True, ignore_permissions=True)
	finally:
		frappe.flags.ats_allow_log_delete = False
