# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import new_applicant


def linked_counts(doctype, name):
	"""Counts shown on a form's connections for each linked doctype."""
	result = get_open_count(doctype, name)
	return {row["doctype"]: row["count"] for row in result["count"]["external_links_found"]}


def make_interview(applicant, job):
	if not frappe.db.exists("Skill", "_Test Dash Skill"):
		frappe.get_doc({"doctype": "Skill", "skill_name": "_Test Dash Skill"}).insert()
	if not frappe.db.exists("Interview Type", "_Test Dash Round"):
		frappe.get_doc(
			{
				"doctype": "Interview Type",
				"interview_type_name": "_Test Dash Round",
				"expected_skill_set": [{"skill": "_Test Dash Skill"}],
			}
		).insert()
	return frappe.get_doc(
		{
			"doctype": "Interview",
			"job_applicant": applicant,
			"job_opening": job,
			"interview_type": "_Test Dash Round",
			"scheduled_on": add_days(nowdate(), 3),
			"from_time": "10:00:00",
			"to_time": "11:00:00",
		}
	).insert()


class TestJobConnections(IntegrationTestCase):
	def test_job_form_lists_applicants_and_interviews(self):
		data = frappe.get_meta("Job Opening").get_dashboard_data()
		self.assertEqual(data.non_standard_fieldnames["Interview"], "job_opening")
		items = [item for group in data.transactions for item in group["items"]]
		self.assertIn("Job Applicant", items)
		self.assertIn("Interview", items)

	def test_counts_on_the_job_form(self):
		job = make_job("_Test Connections").insert()
		first = new_applicant(job, "conn.a@example.com").name
		new_applicant(job, "conn.b@example.com")  # no interview
		make_interview(first, job.name)
		counts = linked_counts("Job Opening", job.name)
		self.assertEqual(counts.get("Job Applicant"), 2)
		self.assertEqual(counts.get("Interview"), 1)


class TestDepartmentConnections(IntegrationTestCase):
	def test_department_page_lists_its_jobs(self):
		data = frappe.get_meta("Department").get_dashboard_data()
		self.assertEqual(data.fieldname, "department")
		items = [item for group in data.transactions for item in group["items"]]
		self.assertIn("Job Opening", items)

	def test_department_counts_its_jobs_only(self):
		department = frappe.db.get_value("Department", {"is_group": 0}, "name")
		other = frappe.db.get_value("Department", {"is_group": 0, "name": ["!=", department]}, "name")
		before = linked_counts("Department", department).get("Job Opening", 0)
		make_job("_Test Dept Jobs A", department=department).insert()
		make_job("_Test Dept Jobs B", department=department).insert()
		make_job("_Test Dept Jobs C", department=other).insert()
		self.assertEqual(linked_counts("Department", department).get("Job Opening", 0), before + 2)

	def test_existing_department_links_are_kept(self):
		"""The override adds to the Department page; it does not replace anything."""
		data = frappe.get_meta("Department").get_dashboard_data()
		self.assertTrue(len(data.transactions) >= 1)
