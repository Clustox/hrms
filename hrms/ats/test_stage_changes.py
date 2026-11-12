# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import drop_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def row(job, stage_name):
	return next(r for r in job.pipeline_stages if r.stage_name == stage_name)


def stage_of(name):
	return frappe.db.get_value("Job Applicant", name, "pipeline_stage")


class TestRenameStage(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Stage Rename").insert()

	def test_candidates_follow_a_renamed_stage(self):
		a = new_applicant(self.job, "rename.a@example.com").name
		b = new_applicant(self.job, "rename.b@example.com").name
		move_stage(b, "Technical Assessment")

		row(self.job, "New Candidates").stage_name = "Applied"
		self.job.save()

		self.assertEqual(stage_of(a), "Applied")
		self.assertEqual(stage_of(b), "Technical Assessment")  # other stages untouched

	def test_other_jobs_are_not_affected(self):
		other = make_job("_Test Stage Rename Other").insert()
		mine = new_applicant(self.job, "rename.mine@example.com").name
		theirs = new_applicant(other, "rename.theirs@example.com").name

		row(self.job, "New Candidates").stage_name = "Applied"
		self.job.save()

		self.assertEqual(stage_of(mine), "Applied")
		self.assertEqual(stage_of(theirs), "New Candidates")

	def test_swapping_two_names_does_not_mix_candidates_up(self):
		a = new_applicant(self.job, "swap.a@example.com").name  # New Candidates
		b = new_applicant(self.job, "swap.b@example.com").name
		move_stage(b, "Technical Profile Review")

		first, second = row(self.job, "New Candidates"), row(self.job, "Technical Profile Review")
		first.stage_name, second.stage_name = "Technical Profile Review", "New Candidates"
		self.job.save()

		self.assertEqual(stage_of(a), "Technical Profile Review")
		self.assertEqual(stage_of(b), "New Candidates")

	def test_a_dropped_candidate_keeps_the_stage_they_were_dropped_from(self):
		name = new_applicant(self.job, "rename.dropped@example.com").name
		drop_applicant(name, "Candidate withdrew")

		row(self.job, "New Candidates").stage_name = "Applied"
		self.job.save()

		doc = frappe.get_doc("Job Applicant", name)
		self.assertEqual((doc.pipeline_stage, doc.dropped_at_stage), ("Applied", "Applied"))

	def test_renaming_to_an_existing_name_is_refused(self):
		row(self.job, "New Candidates").stage_name = "Final Interview"
		with self.assertRaises(frappe.ValidationError):
			self.job.save()

	def test_reordering_changes_nothing_for_candidates(self):
		name = new_applicant(self.job, "reorder@example.com").name
		moved = self.job.pipeline_stages.pop(0)  # take the first stage out and put it back at the end
		self.job.pipeline_stages.append(moved)
		for idx, stage in enumerate(self.job.pipeline_stages, start=1):
			stage.idx = idx
		self.job.save()
		self.assertEqual(stage_of(name), "New Candidates")


class TestDeleteStage(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Stage Delete").insert()

	def remove(self, stage_name):
		self.job.pipeline_stages = [r for r in self.job.pipeline_stages if r.stage_name != stage_name]

	def test_a_stage_with_candidates_cannot_be_deleted(self):
		name = new_applicant(self.job, "delete.full@example.com").name
		move_stage(name, "Technical Assessment")
		self.remove("Technical Assessment")
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.job.save()
		self.assertIn("Technical Assessment", str(ctx.exception))
		self.assertEqual(stage_of(name), "Technical Assessment")

	def test_an_empty_stage_can_be_deleted(self):
		self.remove("Technical Assessment")
		self.job.save()
		names = [r.stage_name for r in self.job.pipeline_stages]
		self.assertNotIn("Technical Assessment", names)

	def test_a_stage_can_be_deleted_once_its_candidates_have_moved(self):
		name = new_applicant(self.job, "delete.moved@example.com").name
		move_stage(name, "Technical Assessment")
		move_stage(name, "Final Interview")
		self.remove("Technical Assessment")
		self.job.save()
		self.assertEqual(stage_of(name), "Final Interview")

	def test_a_dropped_candidate_still_blocks_deleting_their_stage(self):
		name = new_applicant(self.job, "delete.dropped@example.com").name
		drop_applicant(name, "Candidate withdrew")
		self.remove("New Candidates")
		with self.assertRaises(frappe.ValidationError):
			self.job.save()

	def test_deleting_the_first_stage_must_keep_the_pipeline_valid(self):
		self.remove("New Candidates")  # the next stage (Active) becomes first: still valid
		self.job.save()
		self.assertEqual(self.job.pipeline_stages[0].stage_name, "Technical Profile Review")
