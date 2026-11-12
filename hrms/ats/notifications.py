"""In-app notifications for the people running a job: its owner and its team.

Four things are worth a bell alert: a candidate moved to another stage, a new candidate applied, a
note was added to a candidate, and an interview was scheduled, moved or cancelled. They are Frappe
Notification Log entries of type Alert, so they show in the bell and never turn into emails. The
person who did the thing is not told about their own action.

Imports and migrations set frappe.flags.ats_silent so that loading history does not notify anyone.
"""

import frappe
from frappe import _
from frappe.utils import get_fullname


def job_recipients(job: str | None, actor: str | None = None) -> list[str]:
	"""The job's owner and team (enabled users only), without the person who acted."""
	if not job or not frappe.db.exists("Job Opening", job):
		return []
	users = [frappe.db.get_value("Job Opening", job, "job_owner")]
	users += frappe.get_all("ATS Team Member", filters={"parent": job, "parenttype": "Job Opening"}, pluck="user")
	enabled = set(frappe.get_all("User", filters={"name": ["in", [u for u in users if u]], "enabled": 1}, pluck="name"))
	return [u for u in dict.fromkeys(users) if u in enabled and u != actor and u not in ("Administrator", "Guest")]


def notify(job: str | None, subject: str, doctype: str, name: str, include_actor: bool = False) -> int:
	"""Tell the job's people (not the person acting, unless include_actor). Returns how many."""
	if frappe.flags.get("ats_silent"):
		return 0
	actor = frappe.session.user
	recipients = job_recipients(job, actor=None if include_actor else actor)
	for user in recipients:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"from_user": actor,
				"type": "Alert",
				"subject": subject,
				"document_type": doctype,
				"document_name": name,
			}
		).insert(ignore_permissions=True)
	return len(recipients)


def _who() -> str:
	return frappe.bold(get_fullname(frappe.session.user))


def applicant_label(applicant: str) -> str:
	return frappe.db.get_value("Job Applicant", applicant, "applicant_name") or applicant


def stage_changed(applicant: str, from_stage: str | None, to_stage: str | None) -> int:
	job = frappe.db.get_value("Job Applicant", applicant, "job_title")
	if from_stage is None:  # first placement of a new applicant is the "new candidate" alert
		return 0
	subject = _("{0} moved {1} from {2} to {3}").format(
		_who(), frappe.bold(applicant_label(applicant)), from_stage, frappe.bold(to_stage or "")
	)
	return notify(job, subject, "Job Applicant", applicant)


def new_candidate(doc, method=None) -> int:
	subject = _("New candidate {0} applied").format(frappe.bold(doc.applicant_name or doc.name))
	# the applicant is often a website visitor, so everyone on the job hears, even whoever entered it
	return notify(doc.job_title, subject, "Job Applicant", doc.name, include_actor=True)


def new_note(doc, method=None) -> int:
	"""Comment hook: a note (not a system comment) on a candidate."""
	if doc.reference_doctype != "Job Applicant" or doc.comment_type != "Comment":
		return 0
	job = frappe.db.get_value("Job Applicant", doc.reference_name, "job_title")
	subject = _("{0} added a note on {1}").format(_who(), frappe.bold(applicant_label(doc.reference_name)))
	return notify(job, subject, "Job Applicant", doc.reference_name)


def interview_changed(interview, what: str) -> int:
	"""what: scheduled, rescheduled or cancelled."""
	job = interview.job_opening or frappe.db.get_value("Job Applicant", interview.job_applicant, "job_title")
	subject = _("Interview {0} {1} for {2}").format(
		frappe.bold(interview.name), what, frappe.bold(applicant_label(interview.job_applicant))
	)
	return notify(job, subject, "Interview", interview.name)
