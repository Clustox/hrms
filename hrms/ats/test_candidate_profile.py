# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import drop_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant
from hrms.hr.doctype.candidate.candidate import get_applications


class TestCandidateProfile(IntegrationTestCase):
	def setUp(self):
		self.email = f"profile.{frappe.generate_hash(length=6)}@example.com"
		self.jobs = [make_job("_Test Profile A").insert(), make_job("_Test Profile B").insert()]

	def apply_to_both(self):
		first = new_applicant(self.jobs[0], self.email).name
		second = new_applicant(self.jobs[1], self.email.replace("@", "+second@")).name  # same person
		return first, second

	def candidate(self, applicant):
		return frappe.db.get_value("Job Applicant", applicant, "candidate")

	def test_one_person_two_jobs_each_with_its_own_stage(self):
		first, second = self.apply_to_both()
		move_stage(first, "Technical Assessment")
		move_stage(second, "Final Interview")
		self.assertEqual(self.candidate(first), self.candidate(second))

		rows = {a.job_title: a for a in get_applications(self.candidate(first))}
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[self.jobs[0].name].pipeline_stage, "Technical Assessment")
		self.assertEqual(rows[self.jobs[1].name].pipeline_stage, "Final Interview")

	def test_each_application_carries_job_name_status_and_date(self):
		first, _second = self.apply_to_both()
		application = next(a for a in get_applications(self.candidate(first)) if a.name == first)
		self.assertTrue(application.job_name.startswith("_Test Profile A"))
		self.assertEqual(application.status, "Open")
		self.assertTrue(application.applied_on)

	def test_a_dropped_application_shows_its_reason(self):
		first, _second = self.apply_to_both()
		drop_applicant(first, "Candidate withdrew")
		application = next(a for a in get_applications(self.candidate(first)) if a.name == first)
		self.assertEqual((application.is_dropped, application.drop_reason), (1, "Candidate withdrew"))

	def test_the_form_receives_the_applications_on_load(self):
		first, _second = self.apply_to_both()
		doc = frappe.get_doc("Candidate", self.candidate(first))
		doc.run_method("onload")
		self.assertEqual(len(doc.get("__onload").applications), 2)

	def test_a_new_candidate_has_no_applications(self):
		doc = frappe.new_doc("Candidate")
		doc.run_method("onload")
		self.assertFalse(doc.get("__onload") and doc.get("__onload").get("applications"))

	def test_someone_elses_applications_are_not_listed(self):
		first, _second = self.apply_to_both()
		other = new_applicant(self.jobs[0], f"other.{frappe.generate_hash(length=6)}@example.com").name
		names = {a.name for a in get_applications(self.candidate(first))}
		self.assertNotIn(other, names)

	def test_the_candidate_page_counts_its_applications(self):
		first, _second = self.apply_to_both()
		counts = {r["doctype"]: r["count"] for r in get_open_count("Candidate", self.candidate(first))["count"]["external_links_found"]}
		self.assertEqual(counts.get("Job Applicant"), 2)

	def test_a_user_who_cannot_read_applicants_sees_none(self):
		first, _second = self.apply_to_both()
		candidate = self.candidate(first)
		user = frappe.get_doc(
			{"doctype": "User", "email": "profile.noperm@example.com", "first_name": "No Perm", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_applications(candidate)
		finally:
			frappe.set_user("Administrator")

	def test_the_applicant_list_shows_the_stage_of_each_application(self):
		columns = {f.fieldname for f in frappe.get_meta("Job Applicant").fields if f.in_list_view}
		self.assertIn("pipeline_stage", columns)
