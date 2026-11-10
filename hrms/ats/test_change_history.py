# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.setup import CHANGE_HISTORY_DOCTYPES, enable_change_history
from hrms.ats.test_pipeline import make_job


class TestChangeHistory(IntegrationTestCase):
	def test_history_is_on_for_recruitment_records(self):
		for doctype in CHANGE_HISTORY_DOCTYPES:
			self.assertEqual(frappe.get_meta(doctype).track_changes, 1, doctype)

	def test_enabling_twice_keeps_a_single_setting(self):
		enable_change_history(commit=False)
		count = frappe.db.count(
			"Property Setter", {"doc_type": "Job Opening", "property": "track_changes", "doctype_or_field": "DocType"}
		)
		self.assertEqual(count, 1)

	def test_a_change_is_recorded_as_a_version(self):
		job = make_job("_Test Job History").insert()
		job.vacancies = 7
		job.save()
		versions = frappe.get_all("Version", filters={"ref_doctype": "Job Opening", "docname": job.name})
		self.assertGreaterEqual(len(versions), 1)
