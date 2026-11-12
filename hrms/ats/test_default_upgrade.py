# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.backfill import OLD_DEFAULT_STAGE_NAMES, remove_default_rejected_stages, upgrade_default_pipeline
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import new_applicant


def stage_rows(job):
	return frappe.get_all(
		"Job Pipeline Stage",
		filters={"parent": job},
		fields=["stage_name", "stage_type", "maps_to_status", "idx"],
		order_by="idx asc",
	)


def job_on_old_default(title):
	"""A job whose pipeline is the first 13-stage default."""
	job = make_job(title).insert()
	frappe.db.delete("Job Pipeline Stage", {"parent": job.name})
	types = {"Rejected after Technical Interview": "Rejected", "Rejected after Final Interview": "Rejected", "Offer Accepted": "Hired", "Offer Rejected": "Rejected"}
	for idx, name in enumerate(OLD_DEFAULT_STAGE_NAMES, start=1):
		frappe.get_doc(
			{
				"doctype": "Job Pipeline Stage",
				"parent": job.name,
				"parenttype": "Job Opening",
				"parentfield": "pipeline_stages",
				"idx": idx,
				"stage_name": name,
				"stage_type": types.get(name, "Active"),
				"maps_to_status": "Accepted" if types.get(name) == "Hired" else "Open",
			}
		).insert()
	return job


class TestDefaultPipelineUpgrade(IntegrationTestCase):
	def test_old_default_gets_hired_and_on_hold(self):
		job = job_on_old_default("_Test Upgrade A")
		upgrade_default_pipeline()
		rows = stage_rows(job.name)
		names = [r.stage_name for r in rows]
		self.assertEqual(len(names), 15)
		self.assertEqual(names[11:], ["Offer Accepted", "Hired", "Offer Rejected", "On Hold"])
		by_name = {r.stage_name: r for r in rows}
		self.assertEqual(by_name["Offer Accepted"].stage_type, "Active")
		self.assertEqual((by_name["Hired"].stage_type, by_name["Hired"].maps_to_status), ("Hired", "Accepted"))
		self.assertEqual(by_name["On Hold"].maps_to_status, "Hold")
		self.assertEqual([r.idx for r in rows], list(range(1, 16)))

	def test_running_twice_changes_nothing(self):
		job = job_on_old_default("_Test Upgrade B")
		upgrade_default_pipeline()
		self.assertEqual(upgrade_default_pipeline(), 0)
		self.assertEqual(len(stage_rows(job.name)), 15)

	def test_edited_pipelines_are_left_alone(self):
		job = make_job("_Test Upgrade C")
		job.append("pipeline_stages", {"stage_name": "Applied", "stage_type": "Active"})
		job.append("pipeline_stages", {"stage_name": "Offer Accepted", "stage_type": "Hired"})
		job.insert()
		upgrade_default_pipeline()
		self.assertEqual([r.stage_name for r in stage_rows(job.name)], ["Applied", "Offer Accepted"])

	def test_new_jobs_already_have_the_new_default(self):
		job = make_job("_Test Upgrade D").insert()
		names = [r.stage_name for r in stage_rows(job.name)]
		self.assertEqual(names[7:], ["Ready to Offer", "Offer Placed", "Offer Accepted", "Hired", "On Hold"])
		self.assertFalse([n for n in names if "Reject" in n])  # rejected people are dropped with a reason instead
		self.assertEqual(upgrade_default_pipeline(), 0)


class TestRemoveRejectedStages(IntegrationTestCase):
	def old_job_with_people(self, title):
		job = job_on_old_default(title)
		upgrade_default_pipeline()
		people = {}
		for key, stage in (
			("tech", "Rejected after Technical Interview"),
			("final", "Rejected after Final Interview"),
			("offer", "Offer Rejected"),
			("live", "Final Interview"),
		):
			people[key] = new_applicant(job, f"rej.{key}.{frappe.generate_hash(length=6)}@example.com").name
			frappe.db.set_value("Job Applicant", people[key], "pipeline_stage", stage)
		people["old_drop"] = new_applicant(job, f"rej.old.{frappe.generate_hash(length=6)}@example.com").name
		frappe.db.set_value(
			"Job Applicant",
			people["old_drop"],
			{"is_dropped": 1, "drop_reason": "Position filled", "dropped_at_stage": "Rejected after Final Interview", "pipeline_stage": "Rejected after Final Interview"},
		)
		return job, people

	def applicant(self, name):
		return frappe.db.get_value(
			"Job Applicant", name, ["pipeline_stage", "status", "is_dropped", "drop_reason", "dropped_at_stage"], as_dict=True
		)

	def test_the_stages_go_and_the_rest_keep_their_order(self):
		job, _ = self.old_job_with_people("_Test Remove A")
		remove_default_rejected_stages()
		rows = stage_rows(job.name)
		names = [r.stage_name for r in rows]
		self.assertFalse([n for n in names if "Reject" in n])
		self.assertEqual(len(names), 12)
		self.assertEqual([r.idx for r in rows], list(range(1, 13)))
		self.assertEqual(names[-2:], ["Hired", "On Hold"])

	def test_people_in_them_are_dropped_with_a_reason_at_a_sensible_stage(self):
		job, people = self.old_job_with_people("_Test Remove B")
		moved = remove_default_rejected_stages()
		self.assertGreaterEqual(moved, 4)
		tech = self.applicant(people["tech"])
		self.assertEqual((tech.pipeline_stage, tech.is_dropped, tech.drop_reason, tech.dropped_at_stage), ("2nd Technical Interview", 1, "Rejected by recruiter", "2nd Technical Interview"))
		final = self.applicant(people["final"])
		self.assertEqual((final.pipeline_stage, final.is_dropped, final.drop_reason), ("Final Interview", 1, "Rejected by recruiter"))
		offer = self.applicant(people["offer"])
		self.assertEqual((offer.pipeline_stage, offer.is_dropped, offer.drop_reason, offer.status), ("Offer Placed", 1, "Candidate withdrew", "Rejected"))

	def test_someone_already_dropped_there_keeps_their_own_reason_and_moves_with_the_stage(self):
		job, people = self.old_job_with_people("_Test Remove C")
		remove_default_rejected_stages()
		old = self.applicant(people["old_drop"])
		self.assertEqual((old.is_dropped, old.drop_reason, old.pipeline_stage, old.dropped_at_stage), (1, "Position filled", "Final Interview", "Final Interview"))

	def test_people_in_other_stages_are_untouched(self):
		job, people = self.old_job_with_people("_Test Remove D")
		remove_default_rejected_stages()
		live = self.applicant(people["live"])
		self.assertEqual((live.pipeline_stage, live.is_dropped), ("Final Interview", 0))

	def test_running_it_again_changes_nothing(self):
		self.old_job_with_people("_Test Remove E")
		remove_default_rejected_stages()
		self.assertEqual(remove_default_rejected_stages(), 0)

	def test_a_custom_stage_with_a_default_name_but_another_type_is_left_alone(self):
		job = make_job("_Test Remove F")
		job.set("pipeline_stages", [])
		job.append("pipeline_stages", {"stage_name": "Applied", "stage_type": "Active"})
		job.append("pipeline_stages", {"stage_name": "Offer Rejected", "stage_type": "Active"})
		job.insert()
		remove_default_rejected_stages()
		self.assertEqual([r.stage_name for r in stage_rows(job.name)], ["Applied", "Offer Rejected"])

	def test_the_counters_and_the_board_follow(self):
		job, people = self.old_job_with_people("_Test Remove G")
		remove_default_rejected_stages()
		counters = frappe.db.get_value("Job Opening", job.name, ["dropped_count", "in_pipeline_count"], as_dict=True)
		self.assertEqual((counters.dropped_count, counters.in_pipeline_count), (4, 1))
