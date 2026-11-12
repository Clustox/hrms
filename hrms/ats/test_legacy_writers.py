# Copyright (c) 2026, Clustox and contributors
# See license.txt

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import set_applicant_status
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import history, move_stage, new_applicant
from hrms.hr.doctype.job_offer.job_offer import update_job_applicant
from hrms.overrides.employee_master import update_job_applicant_and_offer


def job_requiring_phone_at(stage, title):
	job = make_job(title).insert()
	for row in job.pipeline_stages:
		if row.stage_name == stage:
			row.required_fields = "phone_number"
	job.save()
	return job


class TestJobOfferWriter(IntegrationTestCase):
	def test_accepted_offer_moves_to_the_hired_stage(self):
		job = make_job("_Test Offer Accepted").insert()
		name = new_applicant(job, "offer.accept@example.com").name
		move_stage(name, "Offer Placed")
		update_job_applicant("Accepted", name)
		doc = frappe.get_doc("Job Applicant", name)
		self.assertEqual((doc.pipeline_stage, doc.status), ("Offer Accepted", "Accepted"))
		self.assertEqual(history(name)[-1], ("Offer Placed", "Offer Accepted"))

	def test_declined_offer_drops_the_candidate_at_the_offer_stage(self):
		job = make_job("_Test Offer Declined").insert()
		name = new_applicant(job, "offer.decline@example.com").name
		move_stage(name, "Offer Placed")
		update_job_applicant("Rejected", name)
		doc = frappe.get_doc("Job Applicant", name)
		self.assertEqual((doc.pipeline_stage, doc.status, doc.is_dropped), ("Offer Placed", "Rejected", 1))
		self.assertEqual((doc.drop_reason, doc.dropped_at_stage), ("Candidate withdrew", "Offer Placed"))

	def test_other_offer_statuses_do_nothing(self):
		job = make_job("_Test Offer Other").insert()
		name = new_applicant(job, "offer.other@example.com").name
		update_job_applicant("Awaiting Response", name)
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "New Candidates")

	def test_repeated_offer_update_changes_nothing(self):
		job = make_job("_Test Offer Repeat").insert()
		name = new_applicant(job, "offer.repeat@example.com").name
		move_stage(name, "Offer Placed")
		update_job_applicant("Accepted", name)
		count = len(history(name))
		update_job_applicant("Accepted", name)
		self.assertEqual(len(history(name)), count)

	def test_offer_result_ignores_required_fields(self):
		job = job_requiring_phone_at("Offer Accepted", "_Test Offer Required")
		name = new_applicant(job, "offer.required@example.com").name  # no phone
		move_stage(name, "Offer Placed")
		update_job_applicant("Accepted", name)
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Offer Accepted")


class TestEmployeeHookWriter(IntegrationTestCase):
	def test_creating_an_employee_moves_the_applicant_to_the_hired_stage(self):
		job = make_job("_Test Employee Hook").insert()
		name = new_applicant(job, "employee.hook@example.com").name
		move_stage(name, "Final Interview")
		update_job_applicant_and_offer(SimpleNamespace(job_applicant=name))
		doc = frappe.get_doc("Job Applicant", name)
		self.assertEqual((doc.pipeline_stage, doc.status), ("Hired", "Accepted"))
		self.assertEqual(history(name)[-1], ("Final Interview", "Hired"))

	def test_hook_without_an_applicant_does_nothing(self):
		update_job_applicant_and_offer(SimpleNamespace(job_applicant=None))

	def test_applicant_with_accepted_status_still_moves_on_to_hired(self):
		job = make_job("_Test Employee Hook 2").insert()
		name = new_applicant(job, "employee.hook2@example.com").name
		move_stage(name, "Ready to Offer")  # maps to Accepted already
		update_job_applicant_and_offer(SimpleNamespace(job_applicant=name))
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Hired")

	def test_already_hired_applicant_is_untouched(self):
		job = make_job("_Test Employee Hook 3").insert()
		name = new_applicant(job, "employee.hook3@example.com").name
		move_stage(name, "Hired")
		count = len(history(name))
		update_job_applicant_and_offer(SimpleNamespace(job_applicant=name))
		self.assertEqual(len(history(name)), count)


class TestSetApplicantStatus(IntegrationTestCase):
	def test_unchanged_status_is_a_no_op(self):
		job = make_job("_Test Set Status").insert()
		name = new_applicant(job, "set.status@example.com").name
		set_applicant_status(name, "Open")
		self.assertEqual(len(history(name)), 1)


class TestHiredAndOnHoldStages(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Hired Hold").insert()

	def test_offer_accepted_then_employee_created_ends_in_hired(self):
		name = new_applicant(self.job, "hired.flow@example.com").name
		move_stage(name, "Offer Placed")
		update_job_applicant("Accepted", name)
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Offer Accepted")
		update_job_applicant_and_offer(SimpleNamespace(job_applicant=name))
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Hired")
		self.assertEqual(history(name)[-1], ("Offer Accepted", "Hired"))

	def test_offer_accepted_never_moves_a_hired_candidate_backwards(self):
		name = new_applicant(self.job, "hired.back@example.com").name
		move_stage(name, "Hired")
		update_job_applicant("Accepted", name)
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Hired")

	def test_offer_accepted_from_an_early_stage_goes_to_offer_accepted(self):
		name = new_applicant(self.job, "hired.early@example.com").name
		move_stage(name, "Final Interview")
		update_job_applicant("Accepted", name)
		self.assertEqual(frappe.db.get_value("Job Applicant", name, "pipeline_stage"), "Offer Accepted")

	def test_on_hold_is_a_stage_that_sets_the_hold_status(self):
		name = new_applicant(self.job, "on.hold@example.com").name
		doc = move_stage(name, "On Hold")
		self.assertEqual((doc.pipeline_stage, doc.status), ("On Hold", "Hold"))

	def test_hired_stage_counts_as_accepted(self):
		name = new_applicant(self.job, "hired.status@example.com").name
		doc = move_stage(name, "Hired")
		self.assertEqual((doc.pipeline_stage, doc.status), ("Hired", "Accepted"))
