"""Bring existing recruitment data into the ATS pipeline. Safe to run again.

- every Job Opening without stages gets a copy of the default pipeline template
- every Job Applicant without a stage is placed in the stage that matches its old status
- every Job Applicant without a Candidate is linked to a Candidate (matched or created)
"""

import frappe

from hrms.ats.candidates import find_duplicate, normalize_email, normalize_phone
from hrms.ats.pipeline import DEFAULT_TEMPLATE_NAME, STAGE_COPY_FIELDS, copy_template_stages, log_stage_change

LEGACY_REJECTED_REASON = "Rejected before pipeline stages existed"


def backfill_pipeline() -> dict:
	"""Run every backfill step and return how many records each one changed."""
	from hrms.ats.setup import apply_custom_fields, enable_change_history, seed_defaults, seed_drop_reasons

	# migrate runs patches before after_migrate hooks, so make sure the schema and defaults exist
	apply_custom_fields()
	seed_defaults()
	seed_drop_reasons()
	enable_change_history()

	return {
		"jobs": backfill_job_stages(),
		"applicants": backfill_applicant_stages(),
		"candidates": backfill_candidates(),
	}


def backfill_job_stages() -> int:
	if not frappe.db.exists("ATS Pipeline Template", DEFAULT_TEMPLATE_NAME):
		return 0
	rows = copy_template_stages(DEFAULT_TEMPLATE_NAME)
	with_stages = set(frappe.get_all("Job Pipeline Stage", filters={"parenttype": "Job Opening"}, pluck="parent"))
	count = 0
	for job in frappe.get_all("Job Opening", pluck="name"):
		if job in with_stages:
			continue
		for idx, row in enumerate(rows, start=1):
			frappe.get_doc(
				{
					"doctype": "Job Pipeline Stage",
					"parent": job,
					"parenttype": "Job Opening",
					"parentfield": "pipeline_stages",
					"idx": idx,
					**{field: row.get(field) for field in STAGE_COPY_FIELDS},
				}
			).insert(ignore_permissions=True)
		count += 1
	return count


def stage_for_status(stages: list[dict], status: str | None) -> dict:
	"""The pipeline stage an applicant with this legacy status belongs in."""
	first = stages[0]
	if status == "Accepted":
		return next((s for s in stages if s.stage_type == "Hired"), first)
	if status == "Shortlisted":
		return next((s for s in stages if s.stage_type == "Active" and s.maps_to_status == "Shortlisted"), first)
	return first  # Open, Replied, Hold and Rejected start at the first stage


def backfill_applicant_stages() -> int:
	applicants = frappe.get_all(
		"Job Applicant",
		filters={"pipeline_stage": ["in", ["", None]]},
		fields=["name", "job_title", "status", "creation", "modified"],
	)
	stages_by_job: dict[str, list] = {}
	count = 0
	for applicant in applicants:
		job = applicant.job_title
		if not job:
			continue
		if job not in stages_by_job:
			stages_by_job[job] = frappe.get_all(
				"Job Pipeline Stage",
				filters={"parent": job, "parenttype": "Job Opening"},
				fields=["stage_name", "stage_type", "maps_to_status"],
				order_by="idx asc",
			)
		stages = stages_by_job[job]
		if not stages:
			continue

		stage = stage_for_status(stages, applicant.status)
		values = {
			"pipeline_stage": stage.stage_name,
			"stage_entered_on": applicant.modified or applicant.creation,
			"department": frappe.db.get_value("Job Opening", job, "department"),
		}
		if applicant.status == "Rejected":
			values.update(
				{
					"is_dropped": 1,
					"drop_reason": LEGACY_REJECTED_REASON,
					"dropped_at_stage": stage.stage_name,
				}
			)
		frappe.db.set_value("Job Applicant", applicant.name, values, update_modified=False)
		log_stage_change(applicant.name, None, stage.stage_name, source="Import", reason="Backfilled from legacy status")
		count += 1
	return count


def backfill_candidates() -> int:
	count = 0
	applicants = frappe.get_all(
		"Job Applicant",
		filters={"candidate": ["in", ["", None]]},
		fields=["name", "applicant_name", "email_id", "phone_number", "source", "resume_attachment"],
		order_by="creation asc",
	)
	for applicant in applicants:
		if not (normalize_email(applicant.email_id) or normalize_phone(applicant.phone_number)):
			continue
		candidate = find_duplicate(applicant.email_id, applicant.phone_number)
		if not candidate:
			candidate = (
				frappe.get_doc(
					{
						"doctype": "Candidate",
						"full_name": applicant.applicant_name or applicant.email_id,
						"email": applicant.email_id,
						"phone": applicant.phone_number,
						"source": applicant.source,
						"resume": applicant.resume_attachment,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		frappe.db.set_value("Job Applicant", applicant.name, "candidate", candidate, update_modified=False)
		count += 1
	return count
