"""Job counters: Hired, In pipeline, Dropped and the headcount (positions - filled).

Stored on the Job Opening so the job list never counts thousands of applicants per row, and
refreshed whenever an applicant or the job changes.
"""

import frappe

from hrms.ats.pipeline import get_job_stages


def compute_counters(job: str) -> dict:
	"""Counts for one job.

	- Hired: candidates in a stage of type Hired.
	- Dropped: candidates flagged dropped, plus those in a stage of type Rejected.
	- In pipeline: everyone else.
	"""
	type_of = {s.stage_name: s.stage_type for s in get_job_stages(job)}
	rows = frappe.db.sql(
		"""select pipeline_stage, is_dropped, count(*) from `tabJob Applicant`
		where job_title = %s group by pipeline_stage, is_dropped""",
		job,
	)
	hired = dropped = in_pipeline = 0
	for stage, is_dropped, count in rows:
		stage_type = type_of.get(stage)
		if is_dropped or stage_type == "Rejected":
			dropped += count
		elif stage_type == "Hired":
			hired += count
		else:
			in_pipeline += count
	return {"hired_count": hired, "in_pipeline_count": in_pipeline, "dropped_count": dropped}


def headcount_text(vacancies, hired: int) -> str:
	"""Positions - filled, for example '3 - 1'."""
	return f"{vacancies or 0} - {hired}"


def refresh_counters(job: str | None) -> None:
	if not job or not frappe.db.exists("Job Opening", job):
		return
	counters = compute_counters(job)
	vacancies = frappe.db.get_value("Job Opening", job, "vacancies")
	counters["headcount"] = headcount_text(vacancies, counters["hired_count"])
	frappe.db.set_value("Job Opening", job, counters, update_modified=False)


def refresh_all_counters() -> int:
	jobs = frappe.get_all("Job Opening", pluck="name")
	for job in jobs:
		refresh_counters(job)
	return len(jobs)


# ---- hooks


def refresh_for_applicant(doc, method=None):
	"""Job Applicant on_update / after_delete: refresh this job, and the previous one if the
	applicant was moved to another job."""
	refresh_counters(doc.get("job_title"))
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if before and before.get("job_title") and before.job_title != doc.get("job_title"):
		refresh_counters(before.job_title)


def refresh_for_job(doc, method=None):
	"""Job Opening on_update: vacancies or stage types may have changed."""
	refresh_counters(doc.name)
