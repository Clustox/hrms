# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def job_with_rule(title, stage="Technical Assessment", fields="phone_number, applicant_rating"):
	job = make_job(title).insert()
	for row in job.pipeline_stages:
		if row.stage_name == stage:
			row.required_fields = fields
	job.save()
	return job


class TestRequiredFields(IntegrationTestCase):
	def test_move_is_blocked_until_fields_are_filled(self):
		job = job_with_rule("_Test Req Fields A")
		applicant = new_applicant(job, "req.a@example.com")
		with self.assertRaises(frappe.ValidationError) as ctx:
			move_stage(applicant.name, "Technical Assessment")
		self.assertIn("Phone", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Job Applicant", applicant.name, "pipeline_stage"), "New Candidates")

	def test_move_is_allowed_once_filled(self):
		job = job_with_rule("_Test Req Fields B")
		applicant = new_applicant(job, "req.b@example.com")
		frappe.db.set_value("Job Applicant", applicant.name, {"phone_number": "0300 1234567", "applicant_rating": 0.6})
		moved = move_stage(applicant.name, "Technical Assessment")
		self.assertEqual(moved.pipeline_stage, "Technical Assessment")

	def test_other_stages_are_not_affected(self):
		job = job_with_rule("_Test Req Fields C")
		applicant = new_applicant(job, "req.c@example.com")
		self.assertEqual(move_stage(applicant.name, "Final Interview").pipeline_stage, "Final Interview")

	def test_new_applicants_are_never_blocked(self):
		job = job_with_rule("_Test Req Fields D", stage="New Candidates", fields="phone_number")
		applicant = new_applicant(job, "req.d@example.com")  # no phone, still placed
		self.assertEqual(applicant.pipeline_stage, "New Candidates")

	def test_status_write_that_would_move_is_also_blocked(self):
		job = job_with_rule("_Test Req Fields E", stage="Shortlisted (Phone Screening)", fields="phone_number")
		applicant = new_applicant(job, "req.e@example.com")
		doc = frappe.get_doc("Job Applicant", applicant.name)
		doc.status = "Shortlisted"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_unknown_field_name_is_rejected(self):
		job = make_job("_Test Req Fields F")
		job.append("pipeline_stages", {"stage_name": "Applied", "stage_type": "Active", "required_fields": "not_a_field"})
		with self.assertRaises(frappe.ValidationError):
			job.insert()

	def test_field_list_tolerates_spaces_and_new_lines(self):
		job = job_with_rule("_Test Req Fields G", fields=" phone_number ,\n applicant_rating ")
		applicant = new_applicant(job, "req.g@example.com")
		with self.assertRaises(frappe.ValidationError):
			move_stage(applicant.name, "Technical Assessment")
