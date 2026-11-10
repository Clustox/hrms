# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.backfill import OLD_DEFAULT_STAGE_NAMES, upgrade_default_pipeline
from hrms.ats.test_pipeline import make_job


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
		self.assertEqual(names[11:], ["Offer Accepted", "Hired", "Offer Rejected", "On Hold"])
		self.assertEqual(upgrade_default_pipeline(), 0)
