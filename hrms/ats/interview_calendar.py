"""Interviews on the calendar.

Every interview gets one Frappe Event (linked back to it). When the recruiter has connected a Google
Calendar, the Event is synced to it by Frappe's own Google Calendar integration, which adds a Google
Meet link and sends the invitation to the interviewers and the candidate. Without a connected
calendar the Event still shows on the Frappe calendar. Rescheduling the interview moves the Event;
cancelling the interview removes it.
"""

import frappe
from frappe.utils import get_datetime

ACTIVE_STATUSES = ("Pending", "Under Review")


def get_interview_event(interview: str) -> str | None:
	return frappe.db.get_value("Event", {"reference_doctype": "Interview", "reference_docname": interview})


def google_calendar_for(user: str) -> str | None:
	"""The user's own enabled Google Calendar, if they connected one."""
	return frappe.db.get_value("Google Calendar", {"user": user, "enable": 1}, "name")


def event_times(interview) -> tuple:
	day = str(interview.scheduled_on)
	return get_datetime(f"{day} {interview.from_time}"), get_datetime(f"{day} {interview.to_time}")


def participants(interview) -> list[dict]:
	rows = [
		{"reference_doctype": "User", "reference_docname": d.interviewer, "email": d.interviewer}
		for d in interview.interview_details
		if d.interviewer
	]
	email = frappe.db.get_value("Job Applicant", interview.job_applicant, "email_id")
	if email:
		rows.append({"reference_doctype": "Job Applicant", "reference_docname": interview.job_applicant, "email": email})
	return rows


def sync_interview_event(interview, method=None) -> None:
	"""Interview hook: create the Event, or move it when the time or the people changed. A cancelled
	or discarded interview loses its Event."""
	if interview.docstatus == 2 or interview.status == "Cancelled":
		delete_interview_event(interview)
		return
	if not (interview.scheduled_on and interview.from_time and interview.to_time):
		return

	applicant_name = frappe.db.get_value("Job Applicant", interview.job_applicant, "applicant_name") or interview.job_applicant
	starts_on, ends_on = event_times(interview)

	name = get_interview_event(interview.name)
	if name:
		event = frappe.get_doc("Event", name)
	else:
		event = frappe.new_doc("Event")
		event.update({"event_type": "Private", "reference_doctype": "Interview", "reference_docname": interview.name})
		calendar = google_calendar_for(frappe.session.user)
		if calendar:
			event.update({"sync_with_google_calendar": 1, "google_calendar": calendar, "add_video_conferencing": 1})

	event.update(
		{
			"subject": f"Interview: {interview.interview_type} - {applicant_name}",
			"starts_on": starts_on,
			"ends_on": ends_on,
			"description": interview.job_opening or "",
		}
	)
	event.set("event_participants", participants(interview))
	event.flags.ignore_permissions = True
	event.save() if name else event.insert()


def delete_interview_event(interview) -> None:
	name = get_interview_event(interview.name)
	if name:
		frappe.delete_doc("Event", name, ignore_permissions=True)
