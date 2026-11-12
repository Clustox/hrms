# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.backfill import LEGACY_REJECTED_REASON, backfill_pipeline
from hrms.ats.test_pipeline import make_job


def legacy_job(title):
	"""A job as it looked before the ATS: no pipeline stages."""
	job = make_job(title).insert()
	frappe.db.delete("Job Pipeline Stage", {"parent": job.name})
	return job


def legacy_applicant(job, email, status, phone=None):
	doc = frappe.get_doc(
		{"doctype": "Job Applicant", "applicant_name": "Legacy Person", "email_id": email, "job_title": job.name, "phone_number": phone}
	).insert()
	frappe.db.set_value("Job Applicant", doc.name, {"status": status, "pipeline_stage": "", "candidate": None})
	return doc.name


class TestBackfill(IntegrationTestCase):
	def test_jobs_applicants_and_candidates_are_backfilled(self):
		job = legacy_job("_Test Backfill Job")
		names = {s: legacy_applicant(job, f"bf.{s.lower()}@example.com", s) for s in ("Open", "Replied", "Hold", "Shortlisted", "Accepted", "Rejected")}

		result = backfill_pipeline()
		self.assertGreaterEqual(result["jobs"], 1)

		get = lambda status, field: frappe.db.get_value("Job Applicant", names[status], field)
		self.assertEqual(get("Open", "pipeline_stage"), "New Candidates")
		self.assertEqual(get("Replied", "pipeline_stage"), "New Candidates")
		self.assertEqual(get("Hold", "pipeline_stage"), "New Candidates")
		self.assertEqual(get("Shortlisted", "pipeline_stage"), "Shortlisted (Phone Screening)")
		self.assertEqual(get("Accepted", "pipeline_stage"), "Hired")

		self.assertEqual(get("Rejected", "is_dropped"), 1)
		self.assertEqual(get("Rejected", "drop_reason"), LEGACY_REJECTED_REASON)
		self.assertEqual(get("Rejected", "dropped_at_stage"), "New Candidates")
		self.assertEqual(get("Open", "is_dropped"), 0)

		for status in names:
			self.assertTrue(get(status, "candidate"), status)
			self.assertTrue(get(status, "stage_entered_on"), status)
			self.assertEqual(frappe.db.count("Applicant Stage Log", {"job_applicant": names[status]}), 1, status)

	def test_job_stages_come_from_the_default_template(self):
		job = legacy_job("_Test Backfill Stages")
		backfill_pipeline()
		stages = frappe.get_all("Job Pipeline Stage", filters={"parent": job.name}, order_by="idx asc", pluck="stage_name")
		self.assertEqual(stages[0], "New Candidates")
		self.assertEqual(stages[-1], "On Hold")
		self.assertEqual(len(stages), 12)

	def test_same_person_on_two_jobs_shares_one_candidate(self):
		job_a, job_b = legacy_job("_Test Backfill A"), legacy_job("_Test Backfill B")
		first = legacy_applicant(job_a, "shared.person@example.com", "Open", "0300 7770001")
		second = legacy_applicant(job_b, "SHARED.Person@example.com", "Shortlisted", "+92 300 7770001")
		backfill_pipeline()
		self.assertEqual(
			frappe.db.get_value("Job Applicant", first, "candidate"),
			frappe.db.get_value("Job Applicant", second, "candidate"),
		)

	def test_running_twice_changes_nothing(self):
		job = legacy_job("_Test Backfill Twice")
		name = legacy_applicant(job, "twice@example.com", "Shortlisted")
		backfill_pipeline()
		logs = frappe.db.count("Applicant Stage Log", {"job_applicant": name})
		candidates = frappe.db.count("Candidate")
		again = backfill_pipeline()
		self.assertEqual(again, {"jobs": 0, "applicants": 0, "candidates": 0})
		self.assertEqual(frappe.db.count("Applicant Stage Log", {"job_applicant": name}), logs)
		self.assertEqual(frappe.db.count("Candidate"), candidates)

	def test_applicant_already_in_a_stage_is_left_alone(self):
		job = legacy_job("_Test Backfill Placed")
		name = legacy_applicant(job, "placed@example.com", "Open")
		frappe.db.set_value("Job Applicant", name, "pipeline_stage", "Final Interview")
		backfill_pipeline()
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Final Interview")
