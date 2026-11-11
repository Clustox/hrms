# Copyright (c) 2026, Clustox and contributors
# See license.txt

import datetime

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from hrms.ats.interview_calendar import get_interview_event
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import new_applicant


INTERVIEWERS = ["test_interviewer1@example.com", "test_interviewer2@example.com"]


def make_interviewer(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Int", "send_welcome_email": 0, "roles": [{"role": "Interviewer"}]}
		).insert(ignore_permissions=True)


def create_interview_and_dependencies(applicant, scheduled_on, from_time, to_time, status=None):
	for email in INTERVIEWERS:
		make_interviewer(email)
	if not frappe.db.exists("Interview Type", "_Test Calendar Round"):
		if not frappe.db.exists("Skill", "_Test Calendar Skill"):
			frappe.get_doc({"doctype": "Skill", "skill_name": "_Test Calendar Skill"}).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Interview Type",
				"interview_type_name": "_Test Calendar Round",
				"expected_skill_set": [{"skill": "_Test Calendar Skill"}],
			}
		).insert(ignore_permissions=True)
	doc = frappe.get_doc(
		{
			"doctype": "Interview",
			"interview_type": "_Test Calendar Round",
			"job_applicant": applicant,
			"scheduled_on": scheduled_on,
			"from_time": from_time,
			"to_time": to_time,
			"interview_details": [{"interviewer": e} for e in INTERVIEWERS],
			**({"status": status} if status else {}),
		}
	)
	return doc.insert(ignore_permissions=True)


class TestInterviewCalendar(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Calendar Job").insert()
		self.email = f"cal.{frappe.generate_hash(length=8)}@example.com"
		self.applicant = new_applicant(self.job, self.email)

	def interview(self, **kwargs):
		return create_interview_and_dependencies(
			self.applicant.name, scheduled_on=add_days(getdate(), 3), from_time="10:00:00", to_time="10:45:00", **kwargs
		)

	def event(self, interview):
		name = get_interview_event(interview.name)
		return frappe.get_doc("Event", name) if name else None

	def test_scheduling_creates_one_event_with_the_right_time_and_people(self):
		interview = self.interview()
		event = self.event(interview)
		self.assertTrue(event)
		self.assertEqual(event.starts_on.time(), datetime.time(10, 0))
		self.assertEqual(event.ends_on.time(), datetime.time(10, 45))
		self.assertIn(self.applicant.applicant_name, event.subject)
		emails = {p.email for p in event.event_participants}
		self.assertEqual(emails, {"test_interviewer1@example.com", "test_interviewer2@example.com", self.email})

	def test_saving_again_does_not_make_a_second_event(self):
		interview = self.interview()
		interview.reload()
		interview.save()
		self.assertEqual(frappe.db.count("Event", {"reference_doctype": "Interview", "reference_docname": interview.name}), 1)

	def test_rescheduling_moves_the_event(self):
		interview = self.interview()
		interview.reschedule_interview(add_days(getdate(), 5), datetime.time(14, 0), datetime.time(15, 0))
		event = self.event(interview)
		self.assertEqual(event.starts_on.date(), add_days(getdate(), 5))
		self.assertEqual(event.starts_on.time(), datetime.time(14, 0))

	def test_discarding_the_interview_removes_the_event(self):
		interview = self.interview(status="Pending")
		self.assertTrue(self.event(interview))
		interview.discard()
		self.assertFalse(self.event(interview))

	def test_without_a_google_calendar_the_event_stays_on_the_frappe_calendar(self):
		from unittest.mock import patch

		with patch("hrms.ats.interview_calendar.google_calendar_for", return_value=None):
			event = self.event(self.interview())
		self.assertFalse(event.sync_with_google_calendar)
		self.assertFalse(event.add_video_conferencing)

	def test_with_a_google_calendar_the_event_syncs_and_asks_for_a_meet_link(self):
		from unittest.mock import MagicMock, patch

		name = f"_Test Calendar {frappe.generate_hash(length=5)}"
		frappe.get_doc({"doctype": "Google Calendar", "name": name, "calendar_name": name, "user": "Administrator", "enable": 1}).db_insert()
		google = "frappe.integrations.doctype.google_calendar.google_calendar.get_google_calendar_object"
		with patch(google, return_value=(None, MagicMock(push_to_google_calendar=0))):
			interview = self.interview()
		event = self.event(interview)
		self.assertEqual((event.sync_with_google_calendar, event.add_video_conferencing), (1, 1))
		self.assertEqual(event.google_calendar, name)
		frappe.db.delete("Google Calendar", {"name": name})

	def test_an_interview_without_a_candidate_email_still_gets_an_event(self):
		frappe.db.set_value("Job Applicant", self.applicant.name, "email_id", "")
		from unittest.mock import patch

		with patch("hrms.ats.interview_calendar.google_calendar_for", return_value=None):
			event = self.event(self.interview())
		self.assertEqual({p.email for p in event.event_participants}, {"test_interviewer1@example.com", "test_interviewer2@example.com"})
