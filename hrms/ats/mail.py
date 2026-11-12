"""Email to candidates, sent from the recruiter's own Gmail and recorded on the candidate's timeline.

Frappe already does the hard parts: Email Account and User Email hold the Google (OAuth) connection,
and communication.make sends a message and records it as a Communication on the document, with the
message id that lets a reply be matched back to it. This module adds the ATS part: four standard
templates with merge fields, picking the recruiter's own address as the sender, and a bulk send.

The recruiter connects their Gmail once (Email Account with Google sign-in, or User Email). Until
they do, mail goes out from the hiring sender in HR Settings, as it always has.
"""

import json

import frappe
from frappe import _
from frappe.core.doctype.communication.email import _make as make_system_communication
from frappe.core.doctype.communication.email import make as make_user_communication

MAX_BULK = 100  # per call; keeps one click well under Gmail's daily sending limit

TEMPLATES = {
	"ATS Acknowledgement": (
		"We received your application for {{ job_name }}",
		"<p>Dear {{ candidate_name }},</p>"
		"<p>Thank you for applying for the {{ job_name }} position at {{ company }}. "
		"We have received your application and our team will review it.</p>"
		"<p>We will be in touch about the next steps.</p>"
		"<p>Kind regards,<br>{{ recruiter_name }}</p>",
	),
	"ATS Interview Invitation": (
		"Interview invitation: {{ job_name }}",
		"<p>Dear {{ candidate_name }},</p>"
		"<p>We would like to invite you to an interview for the {{ job_name }} position.</p>"
		"<p><b>Date:</b> {{ interview_date }}<br><b>Time:</b> {{ interview_time }}"
		"{% if meet_link %}<br><b>Meeting link:</b> {{ meet_link }}{% endif %}</p>"
		"<p>Please reply to confirm that this time suits you.</p>"
		"<p>Kind regards,<br>{{ recruiter_name }}</p>",
	),
	"ATS Rejection": (
		"Your application for {{ job_name }}",
		"<p>Dear {{ candidate_name }},</p>"
		"<p>Thank you for your interest in the {{ job_name }} position at {{ company }} and for the time "
		"you spent with us. After careful consideration we will not be taking your application forward.</p>"
		"<p>We wish you every success.</p>"
		"<p>Kind regards,<br>{{ recruiter_name }}</p>",
	),
	"ATS Offer": (
		"Offer: {{ job_name }}",
		"<p>Dear {{ candidate_name }},</p>"
		"<p>We are pleased to offer you the {{ job_name }} position at {{ company }}. "
		"The details of the offer will follow.</p>"
		"<p>Kind regards,<br>{{ recruiter_name }}</p>",
	),
}


def seed_email_templates(commit: bool = True) -> None:
	"""after_migrate hook: create the standard templates that are missing. Templates HR has edited
	are never overwritten."""
	for name, (subject, response) in TEMPLATES.items():
		if not frappe.db.exists("Email Template", name):
			frappe.get_doc(
				{
					"doctype": "Email Template",
					"name": name,
					"subject": subject,
					"response": response,
					"reference_doctype": "Job Applicant",
				}
			).insert(ignore_permissions=True)
	if commit:
		frappe.db.commit()


# ---- building the message


def template_context(applicant, interview: str | None = None) -> dict:
	"""What a template can use: candidate_name, job_name, company, stage_name, recruiter_name, and for
	an interview the interview_date, interview_time, interview_type and meet_link."""
	job = frappe.db.get_value("Job Opening", applicant.job_title, ["job_title", "company"], as_dict=True) or {}
	context = {
		**applicant.as_dict(),
		"candidate_name": applicant.applicant_name,
		"job_name": job.get("job_title"),
		"company": job.get("company"),
		"stage_name": applicant.get("pipeline_stage"),
		"recruiter_name": frappe.utils.get_fullname(frappe.session.user),
		"interview_date": "",
		"interview_time": "",
		"interview_type": "",
		"meet_link": "",
	}
	if interview:
		doc = frappe.get_doc("Interview", interview)
		context.update(
			{
				"interview_date": frappe.utils.formatdate(doc.scheduled_on),
				"interview_time": f"{frappe.utils.format_time(doc.from_time)} - {frappe.utils.format_time(doc.to_time)}",
				"interview_type": doc.interview_type,
				"meet_link": frappe.db.get_value("Event", doc.get("event"), "google_meet_link") if doc.get("event") else "",
			}
		)
	return context


def render_template(template: str, applicant, interview: str | None = None) -> tuple[str, str]:
	"""Subject and message of a template for one applicant."""
	email = frappe.get_doc("Email Template", template).get_formatted_email(template_context(applicant, interview))
	return email["subject"], email["message"]


def connected_sender(user: str) -> str | None:
	"""The address the user sends from: the outgoing Email Account they connected with their Google
	sign-in (its Connected User), else the one that carries their own address, else one they list under
	User Email."""
	mine = frappe.db.get_value("Email Account", {"connected_user": user, "enable_outgoing": 1}, "email_id")
	if mine:
		return mine
	address = frappe.db.get_value("User", user, "email")
	if address and frappe.db.exists("Email Account", {"email_id": address, "enable_outgoing": 1}):
		return address
	return frappe.db.get_value("User Email", {"parent": user, "enable_outgoing": 1}, "email_id")


def pick_sender(user: str) -> str | None:
	"""Who a message is sent as: the recruiter's own connected address, else the hiring sender in HR
	Settings, else None (the default outgoing account)."""
	return connected_sender(user) or frappe.db.get_single_value("HR Settings", "hiring_sender_email") or None


# ---- sending


def send_candidate_email(
	job_applicant: str,
	template: str | None = None,
	subject: str | None = None,
	content: str | None = None,
	interview: str | None = None,
	system: bool = False,
) -> dict:
	"""Send an email to a candidate and record it on their timeline.

	Give a template, or a subject and content. A user-initiated send needs the right to email the
	applicant; system=True is for mail the pipeline sends by itself (such as the email on entering a
	stage), which has no signed-in recruiter to check."""
	applicant = frappe.get_doc("Job Applicant", job_applicant)
	if not applicant.email_id:
		frappe.throw(_("{0} has no email address.").format(applicant.applicant_name or applicant.name))
	if template:
		subject, content = render_template(template, applicant, interview)
	if not (subject and content):
		frappe.throw(_("Give a template, or a subject and a message."))

	user = frappe.session.user
	sender = pick_sender(user)
	send = make_system_communication if system else make_user_communication
	result = send(
		doctype="Job Applicant",
		name=applicant.name,
		content=content,
		subject=subject,
		sender=sender,
		sender_full_name=frappe.utils.get_fullname(user) if sender else None,
		recipients=[applicant.email_id],
		send_email=True,
	)
	return {"communication": result.get("name"), "sender": sender, "recipient": applicant.email_id}


@frappe.whitelist()
def send_template_email(job_applicant: str, template: str, interview: str | None = None) -> dict:
	"""Send one template email to one candidate."""
	return send_candidate_email(job_applicant, template=template, interview=interview)


@frappe.whitelist()
def send_bulk_email(template: str, applicants: str | list) -> dict:
	"""Send a template email to many candidates, one message each (each recorded on that candidate's
	timeline). One that cannot be sent does not stop the rest. Returns how many went out and which
	were skipped, with the reason."""
	names = json.loads(applicants) if isinstance(applicants, str) else list(applicants or [])
	names = list(dict.fromkeys(names))  # the same candidate twice gets one email
	if len(names) > MAX_BULK:
		frappe.throw(_("Send to at most {0} candidates at a time.").format(MAX_BULK))

	sent, skipped = 0, []
	for name in names:
		try:
			send_candidate_email(name, template=template)
			sent += 1
		except Exception as e:
			skipped.append({"applicant": name, "reason": str(e)[:200]})
	return {"sent": sent, "skipped": skipped}
