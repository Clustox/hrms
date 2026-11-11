"""Record-level rules for guests (interviewers from outside HR).

Staff (System Manager, HR Manager, HR User, ATS Recruiter) are not affected. A guest, meaning a
user with ATS Guest and none of the staff roles, can only see:

- jobs shared with them (an active Job Guest Access),
- in those jobs, applicants who are in a stage marked "Visible to Guests" and are not dropped
  (so a person disappears from the guest as soon as they leave a visible stage),
- candidates that have at least one such application,
- interviews they are assigned to, in a shared job, and the feedback on those,
- no Kanban boards (their card counts are not permission-filtered).

Each rule exists twice, because Frappe asks in two ways: a SQL condition for lists, reports and
searches (permission_query_conditions), and a yes/no for one record (has_permission). Both read
the grants on every request, so revoking access takes effect at once. The role-level rights are
in hrms.ats.roles; this is the part that narrows them to the right records.
"""

import frappe

from hrms.ats.guest_access import granted_jobs
from hrms.ats.roles import GUEST, RECRUITER

STAFF_ROLES = {"System Manager", "HR Manager", "HR User", RECRUITER}


def is_restricted_guest(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user in ("Administrator", "Guest"):
		return False
	roles = set(frappe.get_roles(user))
	return GUEST in roles and not (STAFF_ROLES & roles)


def _in(values) -> str:
	return ", ".join(frappe.db.escape(v) for v in values)


# ---- SQL conditions (lists, reports, searches)


def _visible_applicant_sql(user: str, alias: str) -> str:
	jobs = granted_jobs(user)
	if not jobs:
		return "1=0"
	return (
		f"({alias}.is_dropped = 0 and {alias}.job_title in ({_in(jobs)}) and exists ("
		"select 1 from `tabJob Pipeline Stage` stage where stage.parenttype = 'Job Opening' "
		f"and stage.parent = {alias}.job_title and stage.stage_name = {alias}.pipeline_stage "
		"and stage.visible_to_guests = 1))"
	)


def job_opening_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return ""
	jobs = granted_jobs(user)
	return f"`tabJob Opening`.name in ({_in(jobs)})" if jobs else "1=0"


def job_applicant_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return ""
	return _visible_applicant_sql(user, "`tabJob Applicant`")


def candidate_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return ""
	visible = _visible_applicant_sql(user, "ja")
	return f"exists (select 1 from `tabJob Applicant` ja where ja.candidate = `tabCandidate`.name and {visible})"


def interview_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return ""
	jobs = granted_jobs(user)
	if not jobs:
		return "1=0"
	return (
		f"(`tabInterview`.job_opening in ({_in(jobs)}) and exists (select 1 from `tabInterview Detail` d "
		f"where d.parenttype = 'Interview' and d.parent = `tabInterview`.name and d.interviewer = {frappe.db.escape(user)}))"
	)


def interview_feedback_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return ""
	jobs = granted_jobs(user)
	if not jobs:
		return "1=0"
	return (
		"exists (select 1 from `tabInterview` i where i.name = `tabInterview Feedback`.interview "
		f"and i.job_opening in ({_in(jobs)}))"
	)


def kanban_board_query(user=None):
	user = user or frappe.session.user
	return "1=0" if is_restricted_guest(user) else ""


# ---- yes/no for one record


def job_opening_has_permission(doc, ptype=None, user=None, **kwargs):
	# Returns True/False only: Frappe reads None as a denial.
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return True
	return doc.get("name") in granted_jobs(user)


def applicant_is_visible(job: str | None, stage: str | None, is_dropped, user: str) -> bool:
	if is_dropped or not job or not stage or job not in granted_jobs(user):
		return False
	return bool(
		frappe.db.exists(
			"Job Pipeline Stage",
			{"parenttype": "Job Opening", "parent": job, "stage_name": stage, "visible_to_guests": 1},
		)
	)


def job_applicant_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return True
	return applicant_is_visible(doc.get("job_title"), doc.get("pipeline_stage"), doc.get("is_dropped"), user)


def candidate_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return True
	if not doc.get("name"):
		return False
	rows = frappe.get_all(
		"Job Applicant", filters={"candidate": doc.name}, fields=["job_title", "pipeline_stage", "is_dropped"]
	)
	return any(applicant_is_visible(r.job_title, r.pipeline_stage, r.is_dropped, user) for r in rows)


def interview_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return True
	if doc.get("job_opening") not in granted_jobs(user):
		return False
	return any(row.get("interviewer") == user for row in doc.get("interview_details") or [])


def interview_feedback_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if not is_restricted_guest(user):
		return True
	job = frappe.db.get_value("Interview", doc.get("interview"), "job_opening") if doc.get("interview") else None
	return bool(job) and job in granted_jobs(user)


def kanban_board_has_permission(doc, ptype=None, user=None, **kwargs):
	return not is_restricted_guest(user or frappe.session.user)
