# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.setup import set_list_columns


def list_columns(doctype):
	return {f.fieldname for f in frappe.get_meta(doctype).fields if f.in_list_view}


class TestListColumns(IntegrationTestCase):
	def test_jobs_list_shows_the_columns_the_ats_document_asks_for(self):
		columns = list_columns("Job Opening")
		# position name, department, location, headcount, salary min and max, owner, status
		for fieldname in ("job_title", "department", "location", "headcount", "lower_range", "upper_range", "job_owner", "status"):
			self.assertIn(fieldname, columns, fieldname)

	def test_existing_job_columns_are_kept(self):
		columns = list_columns("Job Opening")
		for fieldname in ("designation", "company", "employment_type", "publish"):
			self.assertIn(fieldname, columns, fieldname)

	def test_departments_list_shows_industry_location_and_owner(self):
		columns = list_columns("Department")
		for fieldname in ("department_name", "industry", "department_location", "department_owner"):
			self.assertIn(fieldname, columns, fieldname)

	def test_existing_department_columns_are_kept(self):
		self.assertIn("parent_department", list_columns("Department"))

	def test_setting_the_columns_twice_keeps_a_single_setting(self):
		set_list_columns(commit=False)
		count = frappe.db.count(
			"Property Setter", {"doc_type": "Job Opening", "field_name": "location", "property": "in_list_view"}
		)
		self.assertEqual(count, 1)

	def test_columns_are_only_added_on_the_ats_doctypes(self):
		# Job Applicant keeps exactly its own list columns (job, rating, status)
		self.assertEqual(list_columns("Job Applicant"), {"job_title", "applicant_rating", "status"})
