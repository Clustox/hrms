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


def create_interview_and_dependencies(applicant, scheduled_on, from_time, to_time, status=None, type_name="_Test Calendar Round"):
	for email in INTERVIEWERS:
		make_interviewer(email)
	if not frappe.db.exists("Interview Type", type_name):
		if not frappe.db.exists("Skill", "_Test Calendar Skill"):
			frappe.get_doc({"doctype": "Skill", "skill_name": "_Test Calendar Skill"}).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Interview Type",
				"interview_type_name": type_name,
				"expected_skill_set": [{"skill": "_Test Calendar Skill"}],
			}
		).insert(ignore_permissions=True)
	doc = frappe.get_doc(
		{
			"doctype": "Interview",
			"interview_type": type_name,
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


class TestGoogleChanges(IntegrationTestCase):
	"""What comes back from Google Calendar, simulated: no real Google account is touched."""

	def setUp(self):
		TestInterviewCalendar.setUp(self)

	interview = TestInterviewCalendar.interview
	event = TestInterviewCalendar.event

	def with_google_id(self, interview):
		event = self.event(interview)
		frappe.db.set_value(
			"Event",
			event.name,
			{"google_calendar_event_id": "g123", "google_calendar_id": "cal"},
		)
		return event.name

	def answer(self, who, status):
		return {"attendees": [{"email": who, "responseStatus": status}]}

	def test_the_candidates_answer_is_copied_to_the_event_and_the_interview(self):
		from hrms.ats.interview_calendar import apply_google_event

		interview = self.interview()
		name = self.with_google_id(interview)
		self.assertEqual(apply_google_event(name, self.answer(self.email.upper(), "accepted")), 1)
		self.assertEqual(frappe.db.get_value("Interview", interview.name, "candidate_response"), "Yes")
		rows = {p.email: p.attending for p in frappe.get_doc("Event", name).event_participants}
		self.assertEqual(rows[self.email], "Yes")

	def test_every_google_answer_maps_and_unanswered_stays_empty(self):
		from hrms.ats.interview_calendar import apply_google_event

		interview = self.interview()
		name = self.with_google_id(interview)
		for status, expected in (("declined", "No"), ("tentative", "Maybe")):
			apply_google_event(name, self.answer(self.email, status))
			self.assertEqual(frappe.db.get_value("Interview", interview.name, "candidate_response"), expected)
		apply_google_event(name, self.answer(self.email, "needsAction"))
		self.assertEqual(frappe.db.get_value("Interview", interview.name, "candidate_response"), "Maybe")  # no answer yet: unchanged

	def test_the_same_answer_twice_changes_nothing(self):
		from hrms.ats.interview_calendar import apply_google_event

		name = self.with_google_id(self.interview())
		apply_google_event(name, self.answer(self.email, "accepted"))
		self.assertEqual(apply_google_event(name, self.answer(self.email, "accepted")), 0)

	def test_a_time_change_pulled_from_google_moves_the_interview(self):
		interview = self.interview()
		event = frappe.get_doc("Event", self.event(interview).name)
		event.starts_on = f"{add_days(getdate(), 6)} 16:00:00"
		event.ends_on = f"{add_days(getdate(), 6)} 16:30:00"
		event.save(ignore_permissions=True)  # what Frappe's own Google sync does
		interview.reload()
		self.assertEqual((interview.scheduled_on, str(interview.from_time), str(interview.to_time)), (add_days(getdate(), 6), "16:00:00", "16:30:00"))

	def test_moving_the_interview_does_not_loop_back(self):
		interview = self.interview()
		interview.reschedule_interview(add_days(getdate(), 4), datetime.time(9, 0), datetime.time(9, 30))
		interview.reload()
		self.assertEqual(str(interview.from_time), "9:00:00")

	def test_the_poll_reads_each_event_and_survives_a_failure(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import poll_rsvps

		first = self.with_google_id(self.interview())
		other = new_applicant(self.job, f"cal.{frappe.generate_hash(length=8)}@example.com")
		second_interview = create_interview_and_dependencies(
			other.name, add_days(getdate(), 3), "11:00:00", "11:30:00", type_name="_Test Calendar Round 2"
		)
		second = self.with_google_id(second_interview)
		answers = {first: RuntimeError("google down"), second: self.answer(other.email_id, "accepted")}

		def fake_fetch(event):
			result = answers[event.name]
			if isinstance(result, Exception):
				raise result
			return result

		with patch("hrms.ats.interview_calendar.fetch_google_event", side_effect=fake_fetch):
			poll_rsvps()
		self.assertEqual(frappe.db.get_value("Interview", second_interview.name, "candidate_response"), "Yes")
