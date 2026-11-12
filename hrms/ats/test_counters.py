# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.counters import compute_counters, headcount_text, refresh_all_counters
from hrms.ats.pipeline import drop_applicant, restore_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def counters(job):
	return frappe.db.get_value("Job Opening", job, ["hired_count", "in_pipeline_count", "dropped_count", "headcount"], as_dict=True)


class TestJobCounters(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Counters", vacancies=3).insert()

	def test_a_new_job_starts_at_zero_with_its_positions(self):
		c = counters(self.job.name)
		self.assertEqual((c.hired_count, c.in_pipeline_count, c.dropped_count), (0, 0, 0))
		self.assertEqual(c.headcount, "3 - 0")

	def test_new_candidates_count_as_in_pipeline(self):
		new_applicant(self.job, "count.a@example.com")
		new_applicant(self.job, "count.b@example.com")
		self.assertEqual(counters(self.job.name).in_pipeline_count, 2)

	def test_hired_counts_people_in_the_hired_stage_not_offer_accepted(self):
		a = new_applicant(self.job, "count.hired@example.com").name
		b = new_applicant(self.job, "count.offer@example.com").name
		move_stage(a, "Hired")
		move_stage(b, "Offer Accepted")
		c = counters(self.job.name)
		self.assertEqual((c.hired_count, c.in_pipeline_count), (1, 1))
		self.assertEqual(c.headcount, "3 - 1")

	def test_dropped_counts_flagged_and_rejected_stage_candidates(self):
		flagged = new_applicant(self.job, "count.flagged@example.com").name
		rejected = new_applicant(self.job, "count.rejected@example.com").name
		new_applicant(self.job, "count.live@example.com")
		drop_applicant(flagged, "Candidate withdrew")
		move_stage(rejected, "Rejected after Final Interview")
		c = counters(self.job.name)
		self.assertEqual((c.dropped_count, c.in_pipeline_count), (2, 1))

	def test_restoring_returns_a_candidate_to_the_pipeline(self):
		name = new_applicant(self.job, "count.restore@example.com").name
		drop_applicant(name, "Candidate withdrew")
		self.assertEqual(counters(self.job.name).dropped_count, 1)
		restore_applicant(name)
		c = counters(self.job.name)
		self.assertEqual((c.dropped_count, c.in_pipeline_count), (0, 1))

	def test_on_hold_counts_as_in_pipeline(self):
		name = new_applicant(self.job, "count.hold@example.com").name
		move_stage(name, "On Hold")
		self.assertEqual(counters(self.job.name).in_pipeline_count, 1)

	def test_deleting_an_applicant_updates_the_counts(self):
		name = new_applicant(self.job, "count.delete@example.com").name
		self.assertEqual(counters(self.job.name).in_pipeline_count, 1)
		frappe.delete_doc("Job Applicant", name, force=True)
		self.assertEqual(counters(self.job.name).in_pipeline_count, 0)

	def test_moving_an_applicant_to_another_job_updates_both_jobs(self):
		other = make_job("_Test Counters Other", vacancies=1).insert()
		name = new_applicant(self.job, "count.switch@example.com").name
		doc = frappe.get_doc("Job Applicant", name)
		doc.job_title = other.name
		doc.pipeline_stage = "New Candidates"
		doc.save()
		self.assertEqual(counters(self.job.name).in_pipeline_count, 0)
		self.assertEqual(counters(other.name).in_pipeline_count, 1)

	def test_changing_positions_updates_the_headcount(self):
		move_stage(new_applicant(self.job, "count.positions@example.com").name, "Hired")
		self.job.vacancies = 5
		self.job.save()
		self.assertEqual(counters(self.job.name).headcount, "5 - 1")

	def test_changing_a_stage_type_recounts_the_job(self):
		name = new_applicant(self.job, "count.type@example.com").name
		move_stage(name, "Offer Accepted")
		self.assertEqual(counters(self.job.name).hired_count, 0)
		next(r for r in self.job.pipeline_stages if r.stage_name == "Offer Accepted").stage_type = "Hired"
		self.job.save()
		self.assertEqual(counters(self.job.name).hired_count, 1)

	def test_other_jobs_are_not_counted(self):
		other = make_job("_Test Counters Isolated").insert()
		new_applicant(other, "count.isolated@example.com")
		self.assertEqual(counters(self.job.name).in_pipeline_count, 0)

	def test_a_job_without_stages_counts_everyone_as_in_pipeline(self):
		legacy = make_job("_Test Counters Legacy").insert()
		frappe.db.delete("Job Pipeline Stage", {"parent": legacy.name})
		new_applicant(legacy, "count.legacy@example.com")
		self.assertEqual(compute_counters(legacy.name), {"hired_count": 0, "in_pipeline_count": 1, "dropped_count": 0})

	def test_refreshing_everything_repairs_the_numbers(self):
		new_applicant(self.job, "count.repair@example.com")
		frappe.db.set_value("Job Opening", self.job.name, {"in_pipeline_count": 99, "headcount": "wrong"})
		refresh_all_counters()
		c = counters(self.job.name)
		self.assertEqual((c.in_pipeline_count, c.headcount), (1, "3 - 0"))

	def test_headcount_text(self):
		self.assertEqual(headcount_text(3, 1), "3 - 1")
		self.assertEqual(headcount_text(None, 0), "0 - 0")
