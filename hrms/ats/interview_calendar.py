"""Interviews on the calendar.

Every interview gets one Frappe Event (linked back to it). When the recruiter has connected a Google
Calendar, the Event is synced to it by Frappe's own Google Calendar integration, which adds a Google
Meet link and sends the invitation to the interviewers and the candidate. Without a connected
calendar the Event still shows on the Frappe calendar. Rescheduling the interview moves the Event;
cancelling the interview removes it.
"""

import frappe
from frappe.utils import add_days, get_datetime, now_datetime

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
	event.flags.ats_from_interview = True  # so follow_event_time does not echo this back
	event.save() if name else event.insert()


def delete_interview_event(interview) -> None:
	name = get_interview_event(interview.name)
	if name:
		frappe.delete_doc("Event", name, ignore_permissions=True)


# ---- changes made in Google Calendar

GOOGLE_RESPONSE = {"accepted": "Yes", "declined": "No", "tentative": "Maybe"}


def follow_event_time(event, method=None) -> None:
	"""Event hook: when the time of an interview's Event changes (Frappe's Google sync pulled a
	reschedule made in Google Calendar), the interview follows it."""
	if event.reference_doctype != "Interview" or event.flags.get("ats_from_interview") or not event.starts_on:
		return
	if not frappe.db.exists("Interview", event.reference_docname):
		return

	interview = frappe.get_doc("Interview", event.reference_docname)
	starts_on = get_datetime(event.starts_on)
	ends_on = get_datetime(event.ends_on) if event.ends_on else starts_on
	if (starts_on, ends_on) == event_times(interview):
		return
	interview.db_set(
		{"scheduled_on": starts_on.date(), "from_time": starts_on.time(), "to_time": ends_on.time()}
	)
	interview.notify_update()


def apply_google_event(event_name: str, google_event: dict) -> int:
	"""Copy the attendees' answers from a Google Calendar event onto the Frappe Event and show the
	candidate's answer on the interview. Returns how many answers changed."""
	event = frappe.get_doc("Event", event_name)
	answers = {
		(a.get("email") or "").strip().lower(): GOOGLE_RESPONSE.get(a.get("responseStatus"))
		for a in google_event.get("attendees", [])
	}
	changed = 0
	for row in event.event_participants:
		answer = answers.get((row.email or "").strip().lower())
		if answer and row.attending != answer:
			row.attending = answer
			changed += 1

	if changed:
		event.flags.ignore_permissions = True
		event.flags.ats_from_interview = True
		event.save()

	if event.reference_doctype == "Interview":
		candidate = next((r for r in event.event_participants if r.reference_doctype == "Job Applicant"), None)
		if candidate and frappe.db.exists("Interview", event.reference_docname):
			frappe.db.set_value("Interview", event.reference_docname, "candidate_response", candidate.attending or "", update_modified=False)
	return changed


def fetch_google_event(event) -> dict | None:
	"""The event as Google has it (this is the only call out to Google)."""
	from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object

	service, _account = get_google_calendar_object(event.google_calendar)
	return (
		service.events()
		.get(calendarId=event.google_calendar_id, eventId=event.google_calendar_event_id)
		.execute()
	)


def poll_rsvps() -> None:
	"""Scheduled: read the answers to interview invitations. Only interviews from yesterday on are
	asked about. One failing event does not stop the rest."""
	events = frappe.get_all(
		"Event",
		filters={
			"reference_doctype": "Interview",
			"google_calendar_event_id": ["is", "set"],
			"starts_on": [">=", add_days(now_datetime(), -1)],
		},
		fields=["name", "google_calendar", "google_calendar_id", "google_calendar_event_id"],
	)
	for event in events:
		try:
			google_event = fetch_google_event(frappe._dict(event))
			if google_event:
				apply_google_event(event.name, google_event)
		except Exception:
			frappe.log_error(title=f"ATS RSVP poll failed ({event.name})")
