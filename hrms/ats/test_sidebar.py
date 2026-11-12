# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json
import os

import frappe
from frappe.tests import IntegrationTestCase

SIDEBAR_FILE = os.path.join(os.path.dirname(__file__), "..", "hr", "sidebar", "recruitment", "recruitment.json")


def file_items():
	with open(SIDEBAR_FILE, encoding="utf-8") as f:
		return json.load(f)["items"]


class TestRecruitmentSidebar(IntegrationTestCase):
	def test_the_new_screens_are_in_the_sidebar_file(self):
		links = {item["label"]: item["link_to"] for item in file_items() if item.get("link_to")}
		self.assertEqual(links["Candidate"], "Candidate")
		self.assertEqual(links["Pipeline Template"], "ATS Pipeline Template")
		self.assertEqual(links["Drop Reason"], "Drop Reason")

	def test_the_new_links_point_at_real_doctypes(self):
		for item in file_items():
			if item.get("link_type") == "DocType" and item["label"] in ("Candidate", "Pipeline Template", "Drop Reason"):
				self.assertTrue(frappe.db.exists("DocType", item["link_to"]), item["link_to"])

	def test_candidate_follows_job_applicant_and_setup_items_stay_in_setup(self):
		labels = [item["label"] for item in file_items()]
		self.assertEqual(labels.index("Candidate"), labels.index("Job Applicant") + 1)
		setup = labels.index("Setup")
		for label in ("Pipeline Template", "Drop Reason"):
			self.assertGreater(labels.index(label), setup)
		self.assertTrue(all(item["child"] == 1 for item in file_items() if item["label"] in ("Pipeline Template", "Drop Reason")))

	def test_existing_recruitment_entries_are_all_kept(self):
		labels = {item["label"] for item in file_items()}
		for label in (
			"Home", "Dashboard", "Hiring Pipeline", "Job Opening", "Job Applicant", "Interview", "Job Offer",
			"Appointment Letter", "Job Requisition", "Staffing Plan", "Employee Referral", "Recruitment Analytics",
			"Interview Type", "Job Opening Template", "Appointment Letter Template", "Job Offer Term Template",
			"Job Portal", "Settings",
		):
			self.assertIn(label, labels, label)

	def test_the_site_sidebar_has_the_new_entries(self):
		labels = [item.label for item in frappe.get_doc("Sidebar", "Recruitment").items]
		for label in ("Candidate", "Pipeline Template", "Drop Reason"):
			self.assertIn(label, labels, label)

	def test_every_item_is_still_shown_to_an_administrator(self):
		from frappe.boot import get_module_sidebars

		shown = [item["label"] for item in get_module_sidebars()["Recruitment"]["items"]]
		for label in ("Candidate", "Pipeline Template", "Drop Reason", "Job Applicant"):
			self.assertIn(label, shown, label)
