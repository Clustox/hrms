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


class TestFreeBusy(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Busy Job").insert()
		self.first = new_applicant(self.job, f"busy.{frappe.generate_hash(length=8)}@example.com")
		self.second = new_applicant(self.job, f"busy.{frappe.generate_hash(length=8)}@example.com")
		self.day = add_days(getdate(), 30 + int(frappe.generate_hash(length=4), 16) % 3000)  # tests share a transaction: own day each

	def book(self, applicant, start, end, type_name):
		return create_interview_and_dependencies(applicant.name, self.day, start, end, type_name=type_name)

	def test_an_interviewer_with_another_interview_at_that_time_is_busy(self):
		from hrms.ats.interview_calendar import check_interviewers_free

		self.book(self.first, "10:00:00", "11:00:00", "_Test Busy Round 1")
		busy = check_interviewers_free(INTERVIEWERS, str(self.day), "10:30:00", "11:30:00")
		self.assertEqual(set(busy), set(INTERVIEWERS))

	def test_back_to_back_is_not_a_clash(self):
		from hrms.ats.interview_calendar import check_interviewers_free

		self.book(self.first, "10:00:00", "11:00:00", "_Test Busy Round 2")
		self.assertEqual(check_interviewers_free(INTERVIEWERS, str(self.day), "11:00:00", "12:00:00"), {})

	def test_an_interview_does_not_clash_with_itself(self):
		from hrms.ats.interview_calendar import check_interviewers_free

		interview = self.book(self.first, "10:00:00", "11:00:00", "_Test Busy Round 3")
		self.assertEqual(check_interviewers_free(INTERVIEWERS, str(self.day), "10:00:00", "11:00:00", interview.name), {})

	def test_a_clash_warns_but_does_not_block_saving(self):
		self.book(self.first, "10:00:00", "11:00:00", "_Test Busy Round 4")
		frappe.clear_messages()
		second = self.book(self.second, "10:15:00", "10:45:00", "_Test Busy Round 5")
		self.assertTrue(second.name)
		self.assertIn("Interviewer not free", str(frappe.message_log))

	def test_nobody_listed_means_nobody_busy(self):
		from hrms.ats.interview_calendar import check_interviewers_free

		self.assertEqual(check_interviewers_free([], str(self.day), "10:00:00", "11:00:00"), {})


GOOGLE = "hrms.ats.interview_calendar.google_freebusy"


def at(day, hhmm):
	import datetime as dt

	hour, minute = map(int, hhmm.split(":"))
	return dt.datetime.combine(day, dt.time(hour, minute))


class TestGoogleFreeBusy(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test GFB Job").insert()
		self.applicant = new_applicant(self.job, f"gfb.{frappe.generate_hash(length=8)}@example.com")
		self.day = add_days(getdate(), 50 + int(frappe.generate_hash(length=4), 16) % 3000)  # tests share a transaction

	def test_google_busy_time_is_part_of_the_conflicts(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import check_interviewers_free

		busy = {"busy": {"test_interviewer1@example.com": [(at(self.day, "10:15"), at(self.day, "10:45"))]}, "hidden": []}
		with patch(GOOGLE, return_value=busy):
			result = check_interviewers_free(INTERVIEWERS, str(self.day), "10:00:00", "11:00:00")
		self.assertEqual(list(result), ["test_interviewer1@example.com"])
		self.assertIn("Google Calendar", result["test_interviewer1@example.com"][0])
		self.assertIn("10:15-10:45", result["test_interviewer1@example.com"][0])

	def test_the_day_view_lists_both_sources_in_time_order_and_names_hidden_calendars(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import get_availability

		create_interview_and_dependencies(self.applicant.name, self.day, "09:00:00", "09:30:00", type_name="_Test GFB Round")
		google = {
			"busy": {"test_interviewer1@example.com": [(at(self.day, "13:00"), at(self.day, "14:00"))]},
			"hidden": ["test_interviewer2@example.com"],
		}
		with patch(GOOGLE, return_value=google):
			result = get_availability(INTERVIEWERS, str(self.day))
		mine = [s for s in result["slots"] if s["who"] == "test_interviewer1@example.com"]
		self.assertEqual([(s["source"], s["from"], s["to"]) for s in mine], [("ATS", "09:00", "09:30"), ("Google Calendar", "13:00", "14:00")])
		self.assertEqual(result["hidden"], ["test_interviewer2@example.com"])

	def test_the_interviews_own_google_event_does_not_count_against_it(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import get_availability

		interview = create_interview_and_dependencies(self.applicant.name, self.day, "11:00:00", "11:30:00", type_name="_Test GFB Round 2")
		own = {"busy": {"test_interviewer1@example.com": [(at(self.day, "11:00"), at(self.day, "11:30"))]}, "hidden": []}
		with patch(GOOGLE, return_value=own):
			result = get_availability(INTERVIEWERS, str(self.day), interview.name)
		self.assertEqual([s for s in result["slots"] if s["source"] == "Google Calendar"], [])

	def test_without_a_connected_google_calendar_only_frappe_events_show(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import get_availability, google_freebusy

		with patch("hrms.ats.interview_calendar.google_calendar_for", return_value=None):
			self.assertEqual(google_freebusy(INTERVIEWERS, at(self.day, "00:00"), at(self.day, "23:59")), {"busy": {}, "hidden": []})
			self.assertFalse(get_availability(INTERVIEWERS, str(self.day))["google_connected"])

	def test_google_being_unreachable_never_breaks_scheduling(self):
		from unittest.mock import patch

		from hrms.ats.interview_calendar import google_freebusy

		with patch("hrms.ats.interview_calendar.google_calendar_for", return_value="Some Calendar"), patch(
			"frappe.integrations.doctype.google_calendar.google_calendar.get_google_calendar_object", side_effect=Exception("token expired")
		):
			self.assertEqual(google_freebusy(INTERVIEWERS, at(self.day, "00:00"), at(self.day, "23:59")), {"busy": {}, "hidden": []})
		interview = create_interview_and_dependencies(self.applicant.name, self.day, "15:00:00", "15:30:00", type_name="_Test GFB Round 3")
		self.assertTrue(interview.name)  # saving still works

	def test_google_times_are_converted_to_site_time_and_unseen_calendars_are_reported(self):
		from unittest.mock import MagicMock, patch
		from zoneinfo import ZoneInfo

		from frappe.utils import get_system_timezone

		from hrms.ats.interview_calendar import google_freebusy

		tz = ZoneInfo(get_system_timezone())
		start_utc = at(self.day, "09:30").replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
		end_utc = at(self.day, "10:00").replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
		service = MagicMock()
		service.freebusy.return_value.query.return_value.execute.return_value = {
			"calendars": {
				"test_interviewer1@example.com": {"busy": [{"start": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")}]},
				"test_interviewer2@example.com": {"errors": [{"reason": "notFound"}]},
			}
		}
		with patch("hrms.ats.interview_calendar.google_calendar_for", return_value="Some Calendar"), patch(
			"frappe.integrations.doctype.google_calendar.google_calendar.get_google_calendar_object", return_value=(service, MagicMock())
		):
			result = google_freebusy(INTERVIEWERS, at(self.day, "00:00"), at(self.day, "23:59"))
		self.assertEqual(result["busy"], {"test_interviewer1@example.com": [(at(self.day, "09:30"), at(self.day, "10:00"))]})
		self.assertEqual(result["hidden"], ["test_interviewer2@example.com"])
		asked = service.freebusy.return_value.query.call_args.kwargs["body"]
		self.assertEqual([i["id"] for i in asked["items"]], INTERVIEWERS)

	def test_only_someone_who_can_read_interviews_may_ask(self):
		from hrms.ats.interview_calendar import get_availability

		user = frappe.get_doc(
			{"doctype": "User", "email": f"gfb.noperm.{frappe.generate_hash(length=6)}@example.com", "first_name": "N", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_availability(INTERVIEWERS, str(self.day))
		finally:
			frappe.set_user("Administrator")
