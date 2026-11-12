# Copyright (c) 2026, Clustox and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import advance_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import history, move_stage, new_applicant


def interview_for(applicant, status):
	return frappe.get_doc({"doctype": "Interview", "job_applicant": applicant, "status": status})


class TestAdvanceApplicant(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Advance").insert()
		self.name = new_applicant(self.job, "advance@example.com").name

	def test_moves_to_the_next_stage(self):
		self.assertEqual(advance_applicant(self.name), "Technical Profile Review")
		self.assertEqual(frappe.db.get_value("Job Applicant", self.name, "pipeline_stage"), "Technical Profile Review")

	def test_skips_rejected_stages(self):
		move_stage(self.name, "Final Interview")
		self.assertEqual(advance_applicant(self.name), "Ready to Offer")

	def test_source_is_recorded_in_the_history(self):
		advance_applicant(self.name, source="Interview")
		self.assertEqual(history(self.name)[-1], ("New Candidates", "Technical Profile Review", "Interview"))

	def test_offer_placed_advances_to_offer_accepted_then_hired(self):
		move_stage(self.name, "Offer Placed")
		self.assertEqual(advance_applicant(self.name), "Offer Accepted")
		self.assertEqual(advance_applicant(self.name), "Hired")

	def test_never_advances_into_on_hold_or_out_of_hired(self):
		move_stage(self.name, "Hired")
		with self.assertRaises(frappe.ValidationError):
			advance_applicant(self.name)  # On Hold and Offer Rejected are not forward stages

	def test_dropped_candidate_cannot_advance(self):
		frappe.db.set_value("Job Applicant", self.name, {"is_dropped": 1, "drop_reason": "Position filled"})
		with self.assertRaises(frappe.ValidationError):
			advance_applicant(self.name)


class TestInterviewPrompt(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Interview Prompt").insert()
		self.name = new_applicant(self.job, "prompt@example.com").name

	def prompt(self, status, applicant=None):
		with patch("hrms.hr.doctype.interview.interview.frappe.msgprint") as msgprint:
			interview_for(applicant or self.name, status).show_job_applicant_update_dialog()
		return msgprint

	def test_cleared_offers_to_move_to_the_next_stage(self):
		action = self.prompt("Cleared").call_args.kwargs["primary_action"]
		self.assertEqual(action["server_action"], "hrms.ats.pipeline.advance_applicant")
		self.assertEqual(action["args"], {"job_applicant": self.name, "source": "Interview"})

	def test_rejected_keeps_the_original_prompt(self):
		action = self.prompt("Rejected").call_args.kwargs["primary_action"]
		self.assertEqual(action["server_action"], "hrms.hr.doctype.interview.interview.update_job_applicant_status")
		self.assertEqual(action["args"]["status"], "Rejected")

	def test_original_rejected_prompt_drops_a_pipeline_applicant_in_place(self):
		from hrms.hr.doctype.interview.interview import update_job_applicant_status

		move_stage(self.name, "Technical Assessment")
		update_job_applicant_status("Rejected", self.name)
		doc = frappe.get_doc("Job Applicant", self.name)
		self.assertEqual((doc.is_dropped, doc.pipeline_stage), (1, "Technical Assessment"))
		self.assertEqual(doc.drop_reason, "Rejected by recruiter")

	def test_cleared_never_offers_to_mark_a_pipeline_applicant_accepted(self):
		action = self.prompt("Cleared").call_args.kwargs["primary_action"]
		self.assertNotIn("update_job_applicant_status", action["server_action"])

	def test_dropped_applicant_gets_no_prompt(self):
		frappe.db.set_value("Job Applicant", self.name, {"is_dropped": 1, "drop_reason": "Position filled"})
		self.prompt("Cleared").assert_not_called()

	def test_applicant_outside_a_pipeline_keeps_the_original_prompt(self):
		legacy = make_job("_Test Interview Legacy").insert()
		frappe.db.delete("Job Pipeline Stage", {"parent": legacy.name})
		name = new_applicant(legacy, "prompt.legacy@example.com").name
		action = self.prompt("Cleared", applicant=name).call_args.kwargs["primary_action"]
		self.assertEqual(action["server_action"], "hrms.hr.doctype.interview.interview.update_job_applicant_status")
		self.assertEqual(action["args"]["status"], "Accepted")

	def test_pending_interview_shows_nothing(self):
		self.prompt("Pending").assert_not_called()
