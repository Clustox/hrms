# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import DEFAULT_REJECT_REASON
from hrms.ats.test_pipeline import make_job


def new_applicant(job, email, **kwargs):
	return frappe.get_doc(
		{"doctype": "Job Applicant", "applicant_name": "Stage Tester", "email_id": email, "job_title": job.name, **kwargs}
	).insert()


def move_stage(name, stage):
	"""What a Kanban card move does: frappe.set_value on the stage field."""
	frappe.set_value("Job Applicant", name, "pipeline_stage", stage)
	return frappe.get_doc("Job Applicant", name)


def history(name):
	return [
		(r.from_stage, r.to_stage, r.trigger_source)
		for r in frappe.get_all(
			"Applicant Stage Log", filters={"job_applicant": name}, fields=["from_stage", "to_stage", "trigger_source"], order_by="creation asc"
		)
	]


class TestStagePlacementAndMoves(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Stage Logic").insert()

	def test_new_applicant_starts_in_the_first_stage(self):
		applicant = new_applicant(self.job, "place.first@example.com")
		self.assertEqual(applicant.pipeline_stage, "New Candidates")
		self.assertEqual(applicant.status, "Open")
		self.assertTrue(applicant.stage_entered_on)
		self.assertEqual(history(applicant.name), [(None, "New Candidates", "System")])

	def test_new_applicant_with_status_is_placed_by_status(self):
		applicant = new_applicant(self.job, "place.status@example.com", status="Shortlisted")
		self.assertEqual(applicant.pipeline_stage, "Shortlisted (Phone Screening)")

	def test_unknown_stage_is_rejected(self):
		applicant = new_applicant(self.job, "unknown.stage@example.com")
		with self.assertRaises(frappe.ValidationError):
			move_stage(applicant.name, "No Such Stage")

	def test_card_move_sets_status_time_and_history(self):
		applicant = new_applicant(self.job, "move.card@example.com")
		moved = move_stage(applicant.name, "Technical Assessment")
		self.assertEqual(moved.status, "Shortlisted")
		self.assertEqual(moved.pipeline_stage, "Technical Assessment")
		self.assertEqual(history(applicant.name)[-1], ("New Candidates", "Technical Assessment", "Manual"))

		self.assertEqual(move_stage(applicant.name, "Offer Accepted").status, "Accepted")
		self.assertEqual(move_stage(applicant.name, "Offer Rejected").status, "Rejected")

	def test_other_edits_do_not_touch_stage_time_or_history(self):
		applicant = new_applicant(self.job, "other.edit@example.com")
		entered = applicant.stage_entered_on
		applicant.applicant_rating = 0.8
		applicant.save()
		self.assertEqual(applicant.stage_entered_on, entered)
		self.assertEqual(len(history(applicant.name)), 1)

	def test_job_without_stages_is_left_alone(self):
		legacy = make_job("_Test Stage Legacy").insert()
		frappe.db.delete("Job Pipeline Stage", {"parent": legacy.name})
		applicant = new_applicant(legacy, "legacy.job@example.com")
		self.assertFalse(applicant.pipeline_stage)
		self.assertEqual(history(applicant.name), [])


class TestLegacyStatusWrites(IntegrationTestCase):
	"""Status written by older code (Desk buttons, Job Offer, Employee hook) must move the stage."""

	def setUp(self):
		self.job = make_job("_Test Legacy Status").insert()

	def set_status(self, name, status, source=None):
		doc = frappe.get_doc("Job Applicant", name)
		doc.status = status
		if source:
			doc.flags.ats_source = source
		doc.save()
		return doc

	def test_shortlist_moves_to_the_shortlisted_stage(self):
		name = new_applicant(self.job, "legacy.short@example.com").name
		doc = self.set_status(name, "Shortlisted")
		self.assertEqual(doc.pipeline_stage, "Shortlisted (Phone Screening)")
		self.assertEqual(history(name)[-1], ("New Candidates", "Shortlisted (Phone Screening)", "System"))

	def test_shortlist_when_already_in_a_shortlisted_stage_does_not_move(self):
		name = new_applicant(self.job, "legacy.stay@example.com").name
		move_stage(name, "Final Interview")
		doc = self.set_status(name, "Shortlisted")
		self.assertEqual(doc.pipeline_stage, "Final Interview")

	def test_accepted_moves_to_the_hired_stage(self):
		name = new_applicant(self.job, "legacy.hired@example.com").name
		move_stage(name, "Final Interview")
		doc = self.set_status(name, "Accepted")
		self.assertEqual(doc.pipeline_stage, "Hired")

	def test_accepted_while_in_an_offer_stage_does_not_move(self):
		name = new_applicant(self.job, "legacy.offer@example.com").name
		move_stage(name, "Ready to Offer")
		doc = self.set_status(name, "Accepted")
		self.assertEqual(doc.pipeline_stage, "Ready to Offer")

	def test_rejected_drops_the_candidate_in_place(self):
		name = new_applicant(self.job, "legacy.reject@example.com").name
		move_stage(name, "Technical Assessment")
		doc = self.set_status(name, "Rejected")
		self.assertEqual(doc.pipeline_stage, "Technical Assessment")
		self.assertEqual(doc.is_dropped, 1)
		self.assertEqual(doc.drop_reason, DEFAULT_REJECT_REASON)
		self.assertEqual(doc.dropped_at_stage, "Technical Assessment")

	def test_declined_offer_moves_to_the_last_rejected_stage(self):
		name = new_applicant(self.job, "legacy.declined@example.com").name
		move_stage(name, "Offer Placed")
		doc = self.set_status(name, "Rejected", source="Offer")
		self.assertEqual(doc.pipeline_stage, "Offer Rejected")
		self.assertEqual(doc.is_dropped, 0)
		self.assertEqual(history(name)[-1], ("Offer Placed", "Offer Rejected", "Offer"))

	def test_hold_and_replied_never_move_the_candidate(self):
		name = new_applicant(self.job, "legacy.hold@example.com").name
		move_stage(name, "Final Interview")
		for status in ("Hold", "Replied", "Open"):
			self.assertEqual(self.set_status(name, status).pipeline_stage, "Final Interview", status)
