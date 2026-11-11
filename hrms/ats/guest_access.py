"""Guests: interviewers from outside HR who see only the jobs shared with them.

A grant (Job Guest Access) ties one user to one job. It is active until it is revoked or
passes its expiry date. The record rules (hrms.ats.permissions) read this table on every
request, so a revoked guest loses access at once. Roles follow the grants: ATS Guest while the
user has any active grant, ATS Salary Viewer while any active grant allows salary.
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate, validate_email_address

from hrms.ats.roles import GUEST, SALARY_VIEWER

ADMIN_ROLES = ("System Manager", "HR Manager")


def active_grants(user: str, job: str | None = None) -> list[dict]:
	"""A user's grants that are in force today (not revoked, not expired)."""
	filters = {"user": user, "revoked_on": ["is", "not set"]}
	if job:
		filters["job_opening"] = job
	rows = frappe.get_all(
		"Job Guest Access", filters=filters, fields=["name", "job_opening", "can_move_stages", "can_view_salary", "expires_on"]
	)
	today = getdate(nowdate())
	return [r for r in rows if not r.expires_on or getdate(r.expires_on) >= today]


def granted_jobs(user: str) -> list[str]:
	return [g.job_opening for g in active_grants(user)]


def can_grant_for_job(job: str | None) -> bool:
	"""Administrators, HR Managers and the job's owner may share or unshare a job."""
	user = frappe.session.user
	if user == "Administrator" or set(ADMIN_ROLES) & set(frappe.get_roles(user)):
		return True
	return bool(job) and frappe.db.get_value("Job Opening", job, "job_owner") == user


def sync_guest_roles(user: str) -> None:
	"""Give or take away ATS Guest and ATS Salary Viewer to match the user's active grants."""
	if not frappe.db.exists("User", user) or user in ("Administrator", "Guest"):
		return
	grants = active_grants(user)
	doc = frappe.get_doc("User", user)
	doc.flags.ignore_permissions = True
	have = {r.role for r in doc.roles}

	for role, wanted in ((GUEST, bool(grants)), (SALARY_VIEWER, any(g.can_view_salary for g in grants))):
		if wanted and role not in have:
			doc.add_roles(role)
		elif not wanted and role in have:
			doc.remove_roles(role)


def sync_expired_grants() -> None:
	"""Daily: a grant that ran out of time stops working at once (the record rules check the date);
	this also takes the roles away from guests with nothing left."""
	users = frappe.get_all(
		"Job Guest Access", filters={"revoked_on": ["is", "not set"], "expires_on": ["is", "set"]}, pluck="user", distinct=True
	)
	for user in users:
		sync_guest_roles(user)


def _as_list(value) -> list:
	if isinstance(value, str):
		value = json.loads(value) if value.strip().startswith("[") else [v.strip() for v in value.split(",")]
	return [v for v in (value or []) if v]


@frappe.whitelist()
def grant_access(
	user: str, job_opening: str, can_move_stages: int = 0, can_view_salary: int = 0, expires_on: str | None = None
) -> str:
	"""Share a job with a guest. Sharing it again after it was revoked brings the old record back."""
	if not can_grant_for_job(job_opening):
		frappe.throw(_("Only an administrator, an HR Manager or the job owner can share this job."), frappe.PermissionError)

	existing = frappe.db.get_value(
		"Job Guest Access", {"user": user, "job_opening": job_opening}, "name", order_by="creation desc"
	)
	values = {
		"can_move_stages": int(can_move_stages or 0),
		"can_view_salary": int(can_view_salary or 0),
		"expires_on": expires_on or None,
		"revoked_on": None,
		"revoked_by": None,
	}
	if existing:
		doc = frappe.get_doc("Job Guest Access", existing)
		doc.update(values)
	else:
		doc = frappe.get_doc({"doctype": "Job Guest Access", "user": user, "job_opening": job_opening, **values})
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


@frappe.whitelist()
def revoke_access(user: str, job_opening: str) -> int:
	"""Take a job away from a guest, at once. Returns how many grants were revoked."""
	count = 0
	for grant in frappe.get_all(
		"Job Guest Access", filters={"user": user, "job_opening": job_opening, "revoked_on": ["is", "not set"]}, pluck="name"
	):
		doc = frappe.get_doc("Job Guest Access", grant)
		doc.revoked_on = now_datetime()
		doc.revoked_by = frappe.session.user
		doc.flags.ignore_permissions = True
		doc.save()
		count += 1
	return count


@frappe.whitelist()
def revoke_all_access(user: str) -> int:
	"""Take every job away from a guest."""
	return sum(revoke_access(user, job) for job in {g.job_opening for g in active_grants(user)})


@frappe.whitelist()
def invite_guest(
	email: str,
	first_name: str,
	jobs: str | list,
	last_name: str | None = None,
	can_move_stages: int = 0,
	can_view_salary: int = 0,
	expires_on: str | None = None,
	send_invite: int = 1,
) -> dict:
	"""Create a guest (or reuse an existing user), share the jobs with them and send the invite email."""
	job_list = _as_list(jobs)
	if not job_list:
		frappe.throw(_("Choose at least one job to share."))
	for job in job_list:
		if not can_grant_for_job(job):
			frappe.throw(
				_("Only an administrator, an HR Manager or the job owner can share {0}.").format(job), frappe.PermissionError
			)
	email = validate_email_address(email, throw=True).lower()

	created = False
	if frappe.db.exists("User", email):
		if not frappe.db.get_value("User", email, "enabled"):
			frappe.throw(_("{0} is disabled. Enable the user first.").format(email))
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"user_type": "System User",
				"enabled": 1,
				"send_welcome_email": int(send_invite or 0),
				"roles": [{"role": GUEST}],
			}
		)
		user.flags.ignore_permissions = True
		user.insert()
		created = True

	grants = [grant_access(email, job, can_move_stages, can_view_salary, expires_on) for job in job_list]
	return {"user": email, "created": created, "grants": grants}


# ---- moving candidates


def can_move_stages(user: str, job: str) -> bool:
	"""A guest may move candidates of a job only when their grant says so."""
	return any(g.can_move_stages for g in active_grants(user, job))


@frappe.whitelist()
def get_move_options(job_applicant: str) -> list[str]:
	"""The stages a guest may move this candidate to, or [] when they have no right to move them."""
	from hrms.ats.permissions import is_restricted_guest
	from hrms.ats.pipeline import get_job_stages

	doc = frappe.get_doc("Job Applicant", job_applicant)
	doc.check_permission("read")
	if not is_restricted_guest() or not can_move_stages(frappe.session.user, doc.job_title):
		return []
	return [s.stage_name for s in get_job_stages(doc.job_title) if s.stage_name != doc.pipeline_stage]


@frappe.whitelist()
def move_stage(job_applicant: str, stage: str) -> str:
	"""Move a candidate to another stage of their job.

	Staff need write access to the applicant. A guest needs a grant that allows moving, and can
	only move candidates they can see. The move is recorded under the guest's own name."""
	from hrms.ats.permissions import is_restricted_guest

	doc = frappe.get_doc("Job Applicant", job_applicant)
	if is_restricted_guest():
		doc.check_permission("read")  # the candidate must be visible to them
		if not can_move_stages(frappe.session.user, doc.job_title):
			frappe.throw(_("You are not allowed to move candidates of this job."), frappe.PermissionError)
	else:
		doc.check_permission("write")

	doc.pipeline_stage = stage
	doc.save(ignore_permissions=True)  # a guest has no write role; the checks above decide
	if is_restricted_guest():
		from hrms.ats.activity import log_activity

		log_activity("Moved Candidate", "Job Applicant", doc.name, doc.job_title)
	return doc.pipeline_stage
