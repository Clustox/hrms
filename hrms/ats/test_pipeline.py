# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import DEFAULT_TEMPLATE_NAME, default_stage_rows


def make_job(title: str, **kwargs):
	company = frappe.db.get_value("Company", {}, "name")
	if not frappe.db.exists("Designation", "_Test ATS Designation"):
		frappe.get_doc({"doctype": "Designation", "designation_name": "_Test ATS Designation"}).insert()
	doc = frappe.get_doc(
		{
			"doctype": "Job Opening",
			"job_title": title,
			"company": company,
			"designation": "_Test ATS Designation",
			"status": "Open",
			**kwargs,
		}
	)
	return doc


def make_template(name: str, stage_names: list[str]):
	rows = [{"stage_name": n, "stage_type": "Active"} for n in stage_names]
	rows.append({"stage_name": f"{name} Hired", "stage_type": "Hired"})
	return frappe.get_doc({"doctype": "ATS Pipeline Template", "template_name": name, "stages": rows}).insert()


class TestJobPipeline(IntegrationTestCase):
	def test_new_job_gets_default_pipeline(self):
		job = make_job("_Test Job Default Pipeline").insert()
		self.assertEqual(len(job.pipeline_stages), len(default_stage_rows()))
		self.assertEqual(job.pipeline_stages[0].stage_name, "New Candidates")
		self.assertEqual(job.pipeline_stages[0].maps_to_status, "Open")

	def test_chosen_template_is_copied(self):
		template = make_template("_Test Template X", ["Applied", "Screen"])
		job = make_job("_Test Job Template X", pipeline_template=template.name).insert()
		self.assertEqual([s.stage_name for s in job.pipeline_stages], ["Applied", "Screen", "_Test Template X Hired"])

	def test_template_edit_does_not_change_live_job(self):
		template = make_template("_Test Template Y", ["Applied"])
		job = make_job("_Test Job Template Y", pipeline_template=template.name).insert()
		template.append("stages", {"stage_name": "Late Addition", "stage_type": "Active"})
		template.save()
		job.reload()
		self.assertNotIn("Late Addition", [s.stage_name for s in job.pipeline_stages])

	def test_existing_stages_are_kept(self):
		job = make_job("_Test Job Custom Stages")
		job.append("pipeline_stages", {"stage_name": "Only Stage", "stage_type": "Active"})
		job.insert()
		self.assertEqual([s.stage_name for s in job.pipeline_stages], ["Only Stage"])

	def test_invalid_job_stages_rejected(self):
		job = make_job("_Test Job Dup Stages")
		job.append("pipeline_stages", {"stage_name": "Same", "stage_type": "Active"})
		job.append("pipeline_stages", {"stage_name": "same", "stage_type": "Active"})
		self.assertRaises(frappe.ValidationError, job.insert)

	def test_saving_old_job_without_stages_backfills_default(self):
		job = make_job("_Test Job Old").insert()
		job.pipeline_stages = []
		job.save()
		self.assertEqual(len(job.pipeline_stages), len(default_stage_rows()))

	def test_default_template_exists(self):
		self.assertTrue(frappe.db.exists("ATS Pipeline Template", DEFAULT_TEMPLATE_NAME))
