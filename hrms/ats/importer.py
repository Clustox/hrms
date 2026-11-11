"""Bring the candidates of the old system in: one CSV, one row per application.

Columns (header names are matched without regard to case or spaces):
  job_title (required)  name (required)  email (required)  phone  stage  applied_on  source
  resume_url  cover_letter  legacy_id  dropped_reason  department  designation  positions

A job is matched by its exact title; one that does not exist yet is created from the default
pipeline. The stage must be one of the job's stages (blank means the first). A dropped_reason
puts the candidate in the dropped state with that reason. legacy_id makes the import repeatable:
a row whose legacy_id was imported before is skipped, and so is an email that already applied to
the same job. Nobody is notified and no stage email is sent while importing.

Always run it as a dry run first: every row is checked and the real work is undone at the end.
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import getdate

MAX_ROWS = 2000
REQUIRED = ("job_title", "name", "email")
ALIASES = {"full_name": "name", "candidate": "name", "email_id": "email", "phone_number": "phone", "job": "job_title"}


def normalize_header(header: str) -> str:
	key = (header or "").strip().lower().replace(" ", "_")
	return ALIASES.get(key, key)


def parse_csv(text: str) -> list[dict]:
	"""Rows of a CSV as dicts with normalised keys and trimmed values."""
	if text.startswith("﻿"):  # the byte-order mark Excel adds
		text = text[1:]
	reader = csv.DictReader(io.StringIO(text))
	return [
		{normalize_header(k): (v or "").strip() for k, v in row.items() if k is not None}
		for row in reader
		if any((v or "").strip() for v in row.values())
	]


def find_job(title: str) -> str | None:
	return frappe.db.get_value("Job Opening", {"job_title": title}, "name")


def create_job(row: dict) -> str:
	company = frappe.db.get_value("Company", {}, "name")
	designation = row.get("designation") or None
	if designation and not frappe.db.exists("Designation", designation):
		frappe.get_doc({"doctype": "Designation", "designation_name": designation}).insert(ignore_permissions=True)
	doc = frappe.get_doc(
		{
			"doctype": "Job Opening",
			"job_title": row["job_title"],
			"company": company,
			"designation": designation or _any_designation(),
			"department": row.get("department") or None,
			"status": "Open",
			"vacancies": int(row["positions"]) if (row.get("positions") or "").isdigit() else 1,
		}
	)
	return doc.insert(ignore_permissions=True).name


def _any_designation() -> str:
	name = frappe.db.get_value("Designation", {}, "name")
	if name:
		return name
	return frappe.get_doc({"doctype": "Designation", "designation_name": "Imported"}).insert(ignore_permissions=True).name


def _stages(job: str):
	from hrms.ats.pipeline import get_job_stages

	return get_job_stages(job)


def stage_name(job: str, wanted: str | None) -> str | None:
	if not wanted:
		return None
	return next((s.stage_name for s in _stages(job) if s.stage_name.lower() == wanted.lower()), None)


def check_row(row: dict, job: str | None) -> str | None:
	"""Why this row cannot be imported, or None."""
	for column in REQUIRED:
		if not row.get(column):
			return _("{0} is missing").format(column)
	if "@" not in row["email"]:
		return _("{0} is not an email address").format(row["email"])
	if row.get("applied_on"):
		try:
			getdate(row["applied_on"])
		except Exception:
			return _("applied_on {0} is not a date (use YYYY-MM-DD)").format(row["applied_on"])
	if row.get("dropped_reason") and not frappe.db.exists("Drop Reason", row["dropped_reason"]):
		return _("dropped_reason {0} is not a Drop Reason").format(row["dropped_reason"])
	if job and row.get("stage") and not stage_name(job, row["stage"]):
		return _("stage {0} is not a stage of this job").format(row["stage"])
	return None


def import_applicant(row: dict, job: str) -> str:
	source = row.get("source")
	doc = frappe.get_doc(
		{
			"doctype": "Job Applicant",
			"job_title": job,
			"applicant_name": row["name"],
			"email_id": row["email"],
			"phone_number": row.get("phone") or None,
			"source": source if source and frappe.db.exists("Job Applicant Source", source) else None,
			"resume_link": row.get("resume_url") or None,
			"cover_letter": row.get("cover_letter") or None,
			"legacy_id": row.get("legacy_id") or None,
			"applied_on": getdate(row["applied_on"]) if row.get("applied_on") else None,
		}
	)
	stage = stage_name(job, row.get("stage"))
	if stage:
		doc.pipeline_stage = stage
	doc.flags.ats_skip_email = True
	doc.flags.ats_skip_required_fields = True
	doc.insert(ignore_permissions=True)
	if row.get("dropped_reason"):
		doc.is_dropped = 1
		doc.drop_reason = row["dropped_reason"]
		doc.dropped_at_stage = doc.pipeline_stage
		doc.save(ignore_permissions=True)
	return doc.name


def already_imported(row: dict, job: str | None) -> bool:
	if row.get("legacy_id") and frappe.db.exists("Job Applicant", {"legacy_id": row["legacy_id"]}):
		return True
	if job:
		from hrms.ats.candidates import normalize_email

		wanted = normalize_email(row["email"])
		for email in frappe.get_all("Job Applicant", filters={"job_title": job}, pluck="email_id"):
			if normalize_email(email) == wanted:
				return True
	return False


def import_rows(rows: list[dict], dry_run: bool = True) -> dict:
	"""Import the rows. With dry_run everything is checked and then undone."""
	if len(rows) > MAX_ROWS:
		frappe.throw(_("Import at most {0} rows at a time; split the file.").format(MAX_ROWS))

	report = {"dry_run": bool(dry_run), "rows": len(rows), "jobs_created": 0, "created": 0, "skipped": 0, "errors": []}
	frappe.flags.ats_silent = True
	frappe.db.savepoint("ats_import")
	try:
		seen_legacy: set[str] = set()
		for number, row in enumerate(rows, start=2):  # row 1 is the header
			frappe.db.savepoint("ats_import_row")
			try:
				job = find_job(row["job_title"]) if row.get("job_title") else None
				problem = check_row(row, job)
				if problem:
					report["errors"].append({"row": number, "reason": problem})
					continue
				if row.get("legacy_id") in seen_legacy or already_imported(row, job):
					report["skipped"] += 1
					continue
				if not job:
					job = create_job(row)
					problem = check_row(row, job)  # now the stage can be checked against the new pipeline
					if problem:
						frappe.db.rollback(save_point="ats_import_row")
						report["errors"].append({"row": number, "reason": problem})
						continue
					report["jobs_created"] += 1
				import_applicant(row, job)
				if row.get("legacy_id"):
					seen_legacy.add(row["legacy_id"])
				report["created"] += 1
			except Exception as e:
				frappe.db.rollback(save_point="ats_import_row")
				report["errors"].append({"row": number, "reason": str(e)[:200]})
		if dry_run:
			frappe.db.rollback(save_point="ats_import")
	finally:
		frappe.flags.ats_silent = False
	return report


@frappe.whitelist()
def import_csv_file(file_url: str, dry_run: int = 1) -> dict:
	"""Import a CSV that was uploaded to this site. HR Managers and System Managers only."""
	if not {"System Manager", "HR Manager"} & set(frappe.get_roles()):
		frappe.throw(_("Only an HR Manager or System Manager can import."), frappe.PermissionError)
	content = frappe.get_doc("File", {"file_url": file_url}).get_content()
	text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
	return import_rows(parse_csv(text), dry_run=bool(int(dry_run)))
