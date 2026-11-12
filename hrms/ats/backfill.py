"""Bring existing recruitment data into the ATS pipeline. Safe to run again.

- every Job Opening without stages gets a copy of the default pipeline template
- every Job Applicant without a stage is placed in the stage that matches its old status
- every Job Applicant without a Candidate is linked to a Candidate (matched or created)
"""

import frappe

from hrms.ats.candidates import get_or_create_candidate
from hrms.ats.pipeline import (
	DEFAULT_TEMPLATE_NAME,
	STAGE_COPY_FIELDS,
	copy_template_stages,
	log_stage_change,
	stage_for_status,
)

LEGACY_REJECTED_REASON = "Rejected before pipeline stages existed"


def backfill_pipeline() -> dict:
	"""Run every backfill step and return how many records each one changed."""
	from hrms.ats.setup import apply_custom_fields, enable_change_history, seed_defaults, seed_drop_reasons

	# migrate runs patches before after_migrate hooks, so make sure the schema and defaults exist
	# no commits here: the caller (patch or test) decides, so a test never leaks data
	apply_custom_fields(commit=False)
	seed_defaults(commit=False)
	seed_drop_reasons(commit=False)
	enable_change_history(commit=False)

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
			"stage_entered_date": frappe.utils.getdate(applicant.modified or applicant.creation),
			"applied_on": frappe.utils.getdate(applicant.creation),
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
		log_stage_change(applicant.name, None, stage.stage_name)
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
		candidate = get_or_create_candidate(
			applicant.email_id,
			applicant.phone_number,
			applicant.applicant_name,
			applicant.source,
			applicant.resume_attachment,
		)
		if not candidate:
			continue
		frappe.db.set_value("Job Applicant", applicant.name, "candidate", candidate, update_modified=False)
		count += 1
	return count


OLD_DEFAULT_STAGE_NAMES = [
	"New Candidates",
	"Technical Profile Review",
	"Shortlisted (Phone Screening)",
	"Technical Assessment",
	"1st Technical Interview",
	"2nd Technical Interview",
	"Final Interview",
	"Rejected after Technical Interview",
	"Rejected after Final Interview",
	"Ready to Offer",
	"Offer Placed",
	"Offer Accepted",
	"Offer Rejected",
]

# (parent doctype, child doctype, child field on the parent)
STAGE_TABLES = (
	("ATS Pipeline Template", "ATS Template Stage", "stages"),
	("Job Opening", "Job Pipeline Stage", "pipeline_stages"),
)


def upgrade_default_pipeline() -> int:
	"""Give pipelines that still match the first default (13 stages) the stages added since:
	Offer Accepted becomes an ordinary stage, Hired follows it as its own stage, and On Hold is
	added at the end. Pipelines that were edited are left alone. Safe to run again."""
	count = 0
	for parent_doctype, child_doctype, fieldname in STAGE_TABLES:
		parents = frappe.get_all(child_doctype, filters={"parenttype": parent_doctype}, pluck="parent", distinct=True)
		for parent in parents:
			rows = frappe.get_all(
				child_doctype,
				filters={"parent": parent, "parenttype": parent_doctype},
				fields=["name", "stage_name"],
				order_by="idx asc",
			)
			if [r.stage_name for r in rows] != OLD_DEFAULT_STAGE_NAMES:
				continue

			by_name = {r.stage_name: r.name for r in rows}
			frappe.db.set_value(child_doctype, by_name["Offer Accepted"], "stage_type", "Active", update_modified=False)
			frappe.db.set_value(child_doctype, by_name["Offer Rejected"], "idx", 14, update_modified=False)
			for idx, (name, stage_type, status) in ((13, ("Hired", "Hired", "Accepted")), (15, ("On Hold", "Active", "Hold"))):
				frappe.get_doc(
					{
						"doctype": child_doctype,
						"parent": parent,
						"parenttype": parent_doctype,
						"parentfield": fieldname,
						"idx": idx,
						"stage_name": name,
						"stage_type": stage_type,
						"maps_to_status": status,
					}
				).insert(ignore_permissions=True)
			count += 1
	return count


# the rejected stages the default pipeline used to have: the reason their candidates are dropped with,
# and the stage they are dropped at (when the job has it; else the nearest ordinary stage before)
REMOVED_REJECTED_STAGES = {
	"Rejected after Technical Interview": ("Rejected by recruiter", "2nd Technical Interview"),
	"Rejected after Final Interview": ("Rejected by recruiter", "Final Interview"),
	"Offer Rejected": ("Candidate withdrew", "Offer Placed"),
}


def remove_default_rejected_stages() -> int:
	"""Take the default "Rejected ..." stages out of every pipeline. The candidates in them are dropped
	(reason: rejected by recruiter, or withdrew for a declined offer) at the stage just before, and
	dropped candidates that were dropped at a removed stage are moved to that stage too. Stages with
	other names, or of another type, are left alone. Returns how many candidates were moved. Safe to
	run again."""
	moved = 0
	touched_jobs = set()
	for parent_doctype, child_doctype, _fieldname in STAGE_TABLES:
		parents = frappe.get_all(child_doctype, filters={"parenttype": parent_doctype}, pluck="parent", distinct=True)
		for parent in parents:
			rows = frappe.get_all(
				child_doctype,
				filters={"parent": parent, "parenttype": parent_doctype},
				fields=["name", "stage_name", "stage_type", "idx"],
				order_by="idx asc",
			)
			removable = [r for r in rows if r.stage_name in REMOVED_REJECTED_STAGES and r.stage_type == "Rejected"]
			if not removable:
				continue

			for row in removable:
				preferred = REMOVED_REJECTED_STAGES[row.stage_name][1]
				ordinary = [r for r in rows if r not in removable and r.stage_type == "Active"]
				before = [r for r in ordinary if r.idx < row.idx]
				target = preferred if any(r.stage_name == preferred for r in ordinary) else (before[-1] if before else rows[0]).stage_name
				if parent_doctype == "Job Opening":
					moved += _drop_candidates_of_stage(parent, row.stage_name, target)
					touched_jobs.add(parent)
				frappe.db.delete(child_doctype, {"name": row.name})

			keep = [r for r in rows if r not in removable]
			for position, row in enumerate(keep, start=1):
				if row.idx != position:
					frappe.db.set_value(child_doctype, row.name, "idx", position, update_modified=False)

	from hrms.ats.board import sync_hiring_pipeline_columns, sync_job_board
	from hrms.ats.counters import refresh_counters

	for job in touched_jobs:
		refresh_counters(job)
		sync_job_board(job)
	sync_hiring_pipeline_columns()  # the shared board keeps its own copy of the column list
	return moved


def _drop_candidates_of_stage(job: str, stage: str, target: str) -> int:
	reason = REMOVED_REJECTED_STAGES[stage][0]
	moved = 0
	for name, dropped in frappe.get_all(
		"Job Applicant", filters={"job_title": job, "pipeline_stage": stage}, fields=["name", "is_dropped"], as_list=True
	):
		values = {"pipeline_stage": target, "status": "Rejected"}
		if not dropped:
			values.update({"is_dropped": 1, "drop_reason": reason, "dropped_at_stage": target})
		else:
			values["dropped_at_stage"] = target
		frappe.db.set_value("Job Applicant", name, values, update_modified=False)
		moved += 1
	# people dropped at that stage while they were still in an earlier one: keep the history readable
	frappe.db.sql(
		"update `tabJob Applicant` set dropped_at_stage=%s where job_title=%s and dropped_at_stage=%s",
		(target, job, stage),
	)
	return moved


def fill_card_dates() -> int:
	"""Fill Applied On and In Stage Since for applicants that have not got them. Safe to run again."""
	before = frappe.db.count("Job Applicant", {"applied_on": ["is", "not set"]})
	frappe.db.sql(
		"""update `tabJob Applicant`
		set applied_on = date(creation)
		where applied_on is null"""
	)
	frappe.db.sql(
		"""update `tabJob Applicant`
		set stage_entered_date = date(stage_entered_on)
		where stage_entered_date is null and stage_entered_on is not null"""
	)
	return before
