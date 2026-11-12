# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import log_stage_change
from hrms.ats.test_pipeline import make_job


def make_applicant(job, email):
	return frappe.get_doc(
		{"doctype": "Job Applicant", "applicant_name": "Log Tester", "email_id": email, "job_title": job.name}
	).insert()


class TestApplicantStageLog(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Job Stage Log").insert()
		self.applicant = make_applicant(self.job, "stage.log.test@example.com")

	def test_log_records_user_time_and_stages(self):
		log = log_stage_change(self.applicant.name, "New Candidates", "Final Interview")
		self.assertEqual(log.job_opening, self.job.name)
		self.assertEqual((log.from_stage, log.to_stage), ("New Candidates", "Final Interview"))
		self.assertEqual(log.moved_by, frappe.session.user)
		self.assertTrue(log.moved_on)

	def test_first_entry_has_no_from_stage(self):
		log = log_stage_change(self.applicant.name, None, "New Candidates")
		self.assertFalse(log.from_stage)

	def test_log_cannot_be_deleted_directly(self):
		log = log_stage_change(self.applicant.name, "A", "B")
		self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Applicant Stage Log", log.name, force=True)

	def test_log_is_removed_with_its_applicant(self):
		log_stage_change(self.applicant.name, "A", "B")
		log_stage_change(self.applicant.name, "B", "C")
		frappe.delete_doc("Job Applicant", self.applicant.name, force=True)
		self.assertFalse(frappe.db.exists("Applicant Stage Log", {"job_applicant": self.applicant.name}))
