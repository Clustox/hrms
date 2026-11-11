# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.desk.form.load import getdoc
from frappe.desk.form.utils import add_comment
from frappe.utils import add_to_date, now_datetime, nowdate

from hrms.ats.activity import VIEW_WINDOW_MINUTES, log_activity
from hrms.ats.guest_access import grant_access, move_stage
from hrms.ats.roles import RECRUITER
from hrms.ats.test_permissions import GuestFixture, as_user, make_interview, make_user


def logs(user=None, **filters):
	if user:
		filters["user"] = user
	return frappe.get_all(
		"ATS Activity",
		filters=filters,
		fields=["user", "action", "reference_doctype", "reference_name", "job_opening", "occurred_on"],
		order_by="creation asc",
	)


def open_form(user, doctype, name):
	frappe.set_user(user)
	try:
		frappe.response.docs = []
		getdoc(doctype, name)
	finally:
		frappe.set_user("Administrator")


class TestGuestViewsAreLogged(GuestFixture):
	def test_opening_an_applicant_is_logged_with_the_job(self):
		open_form(self.guest, "Job Applicant", self.visible)
		(row,) = logs(self.guest)
		self.assertEqual((row.action, row.reference_doctype, row.reference_name, row.job_opening), ("Viewed", "Job Applicant", self.visible, self.job_a.name))
		self.assertTrue(row.occurred_on)

	def test_opening_a_job_and_a_candidate_is_logged(self):
		open_form(self.guest, "Job Opening", self.job_a.name)
		open_form(self.guest, "Candidate", self.candidate(self.visible))
		self.assertEqual({(r.reference_doctype) for r in logs(self.guest)}, {"Job Opening", "Candidate"})

	def test_opening_the_same_record_again_soon_is_logged_once(self):
		for _ in range(3):
			open_form(self.guest, "Job Applicant", self.visible)
		self.assertEqual(len(logs(self.guest, reference_name=self.visible)), 1)

	def test_opening_it_again_after_the_window_is_logged_again(self):
		open_form(self.guest, "Job Applicant", self.visible)
		first = logs(self.guest)[0]
		frappe.db.set_value("ATS Activity", frappe.get_all("ATS Activity", filters={"user": self.guest}, pluck="name")[0], "occurred_on", add_to_date(now_datetime(), minutes=-(VIEW_WINDOW_MINUTES + 1)))
		open_form(self.guest, "Job Applicant", self.visible)
		self.assertEqual(len(logs(self.guest)), 2)
		self.assertEqual(first.reference_name, self.visible)

	def test_a_record_the_guest_may_not_open_is_not_logged(self):
		with self.assertRaises(frappe.PermissionError):
			open_form(self.guest, "Job Applicant", self.hidden_stage)
		self.assertEqual(logs(self.guest), [])

	def test_two_guests_are_logged_separately(self):
		other = make_user("ATS Guest")
		grant_access(other, self.job_a.name)
		open_form(self.guest, "Job Applicant", self.visible)
		open_form(other, "Job Applicant", self.visible)
		self.assertEqual({r.user for r in logs(reference_name=self.visible)}, {self.guest, other})

	def test_staff_are_not_logged(self):
		open_form(make_user(RECRUITER), "Job Applicant", self.visible)
		open_form("Administrator", "Job Applicant", self.visible)
		self.assertEqual(logs(reference_name=self.visible), [])


class TestGuestNotesFeedbackAndMoves(GuestFixture):
	def test_a_note_added_by_a_guest_is_logged(self):
		as_user(self.guest, add_comment, "Job Applicant", self.visible, "asked good questions", self.guest, "Guest")
		self.assertEqual([(r.action, r.reference_name) for r in logs(self.guest, action="Added Note")], [("Added Note", self.visible)])

	def test_a_note_added_by_staff_is_not_logged(self):
		as_user(make_user(RECRUITER), add_comment, "Job Applicant", self.visible, "internal", "recruiter@example.com", "Recruiter")
		self.assertEqual(logs(action="Added Note", reference_name=self.visible), [])

	def test_feedback_given_by_a_guest_is_logged(self):
		interview = make_interview(self.visible, self.job_a.name, self.guest)
		frappe.db.set_value("Interview", interview, "scheduled_on", nowdate())
		feedback = as_user(
			self.guest,
			lambda: frappe.get_doc(
				{
					"doctype": "Interview Feedback",
					"interview": interview,
					"interviewer": self.guest,
					"result": "Cleared",
					"feedback": "strong on testing",
					"skill_assessment": [{"skill": "_Test Perm Skill", "rating": 0.8}],
				}
			).insert().name,
		)
		(row,) = logs(self.guest, action="Gave Feedback")
		self.assertEqual((row.reference_doctype, row.reference_name, row.job_opening), ("Interview Feedback", feedback, self.job_a.name))

	def test_a_move_by_a_guest_is_logged(self):
		grant_access(self.guest, self.job_a.name, can_move_stages=1)
		as_user(self.guest, move_stage, self.visible, "Final Interview")
		(row,) = logs(self.guest, action="Moved Candidate")
		self.assertEqual((row.reference_name, row.job_opening), (self.visible, self.job_a.name))

	def test_a_move_by_staff_is_not_in_the_guest_log(self):
		as_user(make_user(RECRUITER), move_stage, self.hidden_stage, "Final Interview")
		self.assertEqual(logs(action="Moved Candidate", reference_name=self.hidden_stage), [])


class TestTheLogItself(GuestFixture):
	def test_the_log_survives_a_revoke_and_keeps_its_rows(self):
		open_form(self.guest, "Job Applicant", self.visible)
		from hrms.ats.guest_access import revoke_all_access

		revoke_all_access(self.guest)
		self.assertEqual(len(logs(self.guest)), 1)

	def test_only_hr_can_read_the_log(self):
		open_form(self.guest, "Job Applicant", self.visible)
		name = frappe.get_all("ATS Activity", pluck="name", limit=1)[0]
		self.assertTrue(frappe.has_permission("ATS Activity", "read", doc=name, user=make_user("HR Manager")))
		for user in (self.guest, make_user(RECRUITER), make_user("HR User")):
			self.assertFalse(frappe.has_permission("ATS Activity", "read", doc=name, user=user), user)

	def test_nobody_can_edit_or_delete_log_rows(self):
		open_form(self.guest, "Job Applicant", self.visible)
		name = frappe.get_all("ATS Activity", pluck="name", limit=1)[0]
		for user in (make_user("HR Manager"), make_user("System Manager")):
			for ptype in ("write", "create", "delete"):
				self.assertFalse(frappe.has_permission("ATS Activity", ptype, doc=name, user=user), f"{user} {ptype}")

	def test_log_activity_can_record_any_action_for_the_current_user(self):
		log_activity("Viewed", "Job Opening", self.job_a.name)
		self.assertEqual(logs(user="Administrator")[0].job_opening, self.job_a.name)
