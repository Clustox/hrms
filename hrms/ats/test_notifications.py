# Copyright (c) 2026, Clustox and contributors
# See license.txt

import datetime

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from hrms.ats.test_interview_calendar import create_interview_and_dependencies
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def make_user(prefix="notif"):
	email = f"{prefix}.{frappe.generate_hash(length=8)}@example.com"
	frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": prefix, "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "HR User"}]}
	).insert(ignore_permissions=True)
	return email


def bell(user, **filters):
	return frappe.get_all("Notification Log", filters={"for_user": user, **filters}, pluck="subject")


class TestNotifications(IntegrationTestCase):
	def setUp(self):
		self.owner, self.teammate, self.outsider = make_user("owner"), make_user("team"), make_user("outside")
		self.job = make_job("_Test Notify Job", job_owner=self.owner)
		self.job.append("job_team", {"user": self.teammate, "team_role": "Recruiter"})
		self.job.insert()

	def applicant(self):
		return new_applicant(self.job, f"n.{frappe.generate_hash(length=8)}@example.com")

	def test_a_new_candidate_alerts_the_owner_and_the_team_but_nobody_else(self):
		applicant = self.applicant()
		for user in (self.owner, self.teammate):
			self.assertTrue(any("New candidate" in s for s in bell(user, document_name=applicant.name)), user)
		self.assertFalse(bell(self.outsider, document_name=applicant.name))

	def test_a_stage_move_alerts_the_job_people_and_not_the_person_who_moved(self):
		applicant = self.applicant()
		frappe.set_user(self.teammate)
		try:
			move_stage(applicant.name, "Technical Assessment")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(any("Technical Assessment" in s for s in bell(self.owner, document_name=applicant.name)))
		self.assertFalse(any("Technical Assessment" in s for s in bell(self.teammate, document_name=applicant.name)))

	def test_the_alert_is_in_app_only_and_links_to_the_candidate(self):
		applicant = self.applicant()
		log = frappe.get_all("Notification Log", filters={"for_user": self.owner, "document_name": applicant.name}, fields=["type", "document_type"])[0]
		self.assertEqual((log.type, log.document_type), ("Alert", "Job Applicant"))

	def test_a_note_on_a_candidate_alerts_but_a_system_comment_does_not(self):
		applicant = self.applicant()
		before = len(bell(self.owner, document_name=applicant.name))
		frappe.get_doc(
			{"doctype": "Comment", "comment_type": "Edit", "reference_doctype": "Job Applicant", "reference_name": applicant.name, "content": "edited"}
		).insert(ignore_permissions=True)
		self.assertEqual(len(bell(self.owner, document_name=applicant.name)), before)
		frappe.set_user(self.teammate)
		try:
			applicant.add_comment("Comment", "Strong on Python")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(any("added a note" in s for s in bell(self.owner, document_name=applicant.name)))

	def test_interview_scheduled_moved_and_cancelled_each_alert(self):
		applicant = self.applicant()
		interview = create_interview_and_dependencies(applicant.name, add_days(getdate(), 40), "10:00:00", "10:30:00", type_name="_Test Notify Round")
		interview.reload()
		interview.reschedule_interview(add_days(getdate(), 41), datetime.time(11, 0), datetime.time(11, 30))
		interview.reload()
		interview.discard() if interview.docstatus == 0 else None
		texts = " | ".join(bell(self.owner, document_name=interview.name))
		for word in ("scheduled", "rescheduled", "cancelled"):
			self.assertIn(word, texts)

	def test_imports_can_be_silenced(self):
		frappe.flags.ats_silent = True
		try:
			applicant = self.applicant()
		finally:
			frappe.flags.ats_silent = False
		self.assertFalse(bell(self.owner, document_name=applicant.name))

	def test_a_disabled_user_is_not_notified(self):
		frappe.db.set_value("User", self.teammate, "enabled", 0)
		applicant = self.applicant()
		self.assertFalse(bell(self.teammate, document_name=applicant.name))

	def test_a_job_without_people_notifies_nobody_and_does_not_fail(self):
		job = make_job("_Test Notify Empty").insert()
		self.assertTrue(new_applicant(job, f"n.{frappe.generate_hash(length=8)}@example.com"))
