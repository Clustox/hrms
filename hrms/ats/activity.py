"""The guest activity log.

Only guests are logged here: what staff do to jobs and candidates is already in the change
history (Version) and the stage history. Looking at the same record again within a few minutes
is logged once, so opening a form does not flood the log. Direct file downloads are not logged
separately; opening the candidate (and so their resume) is.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

from hrms.ats.permissions import is_restricted_guest

VIEW_WINDOW_MINUTES = 10
TRACKED = ("Job Opening", "Job Applicant", "Candidate")


def job_of(doctype: str, name: str) -> str | None:
	if doctype == "Job Opening":
		return name
	if doctype == "Job Applicant":
		return frappe.db.get_value("Job Applicant", name, "job_title")
	if doctype == "Interview Feedback":
		interview = frappe.db.get_value("Interview Feedback", name, "interview")
		return frappe.db.get_value("Interview", interview, "job_opening") if interview else None
	return None


def log_activity(action: str, doctype: str, name: str, job: str | None = None, window_minutes: int = 0) -> str | None:
	"""Record what the current user did. With a window, the same action on the same record by the
	same user inside it is not recorded again."""
	user = frappe.session.user
	if window_minutes and frappe.db.exists(
		"ATS Activity",
		{
			"user": user,
			"action": action,
			"reference_doctype": doctype,
			"reference_name": name,
			"occurred_on": [">=", add_to_date(now_datetime(), minutes=-window_minutes)],
		},
	):
		return None
	return (
		frappe.get_doc(
			{
				"doctype": "ATS Activity",
				"user": user,
				"action": action,
				"reference_doctype": doctype,
				"reference_name": name,
				"job_opening": job if job is not None else job_of(doctype, name),
				"occurred_on": now_datetime(),
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


# ---- hooks


def log_guest_view(doc, method=None):
	"""onload of a job, applicant or candidate: a guest opened it."""
	if is_restricted_guest():
		log_activity("Viewed", doc.doctype, doc.name, window_minutes=VIEW_WINDOW_MINUTES)


def log_guest_note(doc, method=None):
	"""Comment after_insert: a guest added a note to a job, applicant or candidate."""
	if doc.comment_type == "Comment" and doc.reference_doctype in TRACKED and is_restricted_guest():
		log_activity("Added Note", doc.reference_doctype, doc.reference_name)


def log_guest_feedback(doc, method=None):
	"""Interview Feedback after_insert: a guest gave feedback."""
	if is_restricted_guest():
		log_activity("Gave Feedback", doc.doctype, doc.name)
