"""ATS roles and what they may do.

- ATS Recruiter: works the pipeline (jobs, applicants, candidates, interviews).
- ATS Guest: an interviewer from outside HR. Read-only, and only what the record rules in
  hrms.ats.guest_access allow; can add interview feedback of their own.
- ATS Salary Viewer: may read the salary fields (given to a guest only when HR allows it).

Salary fields are moved to permission level 1. HR User, HR Manager, System Manager and ATS
Recruiter are given that level explicitly, so they keep seeing them.
"""

import frappe
from frappe.permissions import setup_custom_perms

RECRUITER = "ATS Recruiter"
GUEST = "ATS Guest"
SALARY_VIEWER = "ATS Salary Viewer"
ROLES = (RECRUITER, GUEST, SALARY_VIEWER)

WORK = {"read": 1, "write": 1, "create": 1, "report": 1, "print": 1, "email": 1}
READ = {"read": 1}
SELECT = {"select": 1}

RECRUITER_PERMISSIONS = {
	"Job Opening": WORK,
	"Job Applicant": WORK,
	"Candidate": WORK,
	"Interview": WORK,
	"Interview Feedback": READ,
	"Job Offer": READ,
	"Job Requisition": READ,
	"Staffing Plan": READ,  # job validation checks the Staffing Plan, as it does for HR User
	"Drop Reason": READ,
	"ATS Pipeline Template": READ,
	"Applicant Stage Log": READ,
	"Job Guest Access": {"read": 1, "write": 1, "create": 1},  # limited to their own jobs by the document check
	"Interview Type": READ,
	"Email Template": READ,
	"Skill": READ,
	"Department": SELECT,
	"Designation": SELECT,
	"Company": SELECT,
	"Branch": SELECT,
	"Employment Type": SELECT,
	"Job Applicant Source": SELECT,
	"Currency": SELECT,
	"User": SELECT,
}

GUEST_PERMISSIONS = {
	"Job Opening": READ,
	"Job Applicant": READ,
	"Candidate": READ,
	"Interview": READ,
	"Interview Type": SELECT,
	"Skill": SELECT,
	"Department": SELECT,
	"Designation": SELECT,
	"Company": SELECT,
	"Branch": SELECT,
	"Employment Type": SELECT,
	"Job Applicant Source": SELECT,
	"User": SELECT,
}

# a guest writes feedback of their own only
GUEST_OWN_RECORDS = {"Interview Feedback": {"read": 1, "write": 1, "create": 1, "submit": 1}}

# salary fields: moved to level 1
SALARY_FIELDS = {"Job Opening": ("lower_range", "upper_range"), "Job Applicant": ("lower_range", "upper_range")}
SALARY_LEVEL = 1
SALARY_ROLES = ("System Manager", "HR Manager", "HR User", RECRUITER)

# job counters (Hired / In pipeline / Dropped / headcount) count every candidate, including the ones a
# guest may not see, so they sit on a staff-only level 2
COUNTER_FIELDS = ("hired_count", "in_pipeline_count", "dropped_count", "headcount")
COUNTER_LEVEL = 2
STAFF_ROLES = ("System Manager", "HR Manager", "HR User", RECRUITER)


def ensure_permission(doctype: str, role: str, ptypes: dict, permlevel: int = 0, if_owner: int = 0) -> None:
	"""Make sure the role has exactly these rights on the doctype at this level. Safe to repeat."""
	setup_custom_perms(doctype)  # copies the standard rules into editable ones the first time
	name = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": if_owner}, "name"
	)
	doc = (
		frappe.get_doc("Custom DocPerm", name)
		if name
		else frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": permlevel,
				"if_owner": if_owner,
			}
		)
	)
	for ptype, value in ptypes.items():
		doc.set(ptype, value)
	doc.save(ignore_permissions=True)


def create_roles() -> None:
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1}).insert(
				ignore_permissions=True
			)


def protect_salary_fields() -> None:
	"""Put the salary fields on permission level 1 and give that level to the roles that need it."""
	for doctype, fieldnames in SALARY_FIELDS.items():
		for fieldname in fieldnames:
			frappe.make_property_setter(
				{
					"doctype": doctype,
					"doctype_or_field": "DocField",
					"fieldname": fieldname,
					"property": "permlevel",
					"value": str(SALARY_LEVEL),
					"property_type": "Int",
				},
				is_system_generated=False,
			)
		for role in SALARY_ROLES:
			ensure_permission(doctype, role, {"read": 1, "write": 1}, permlevel=SALARY_LEVEL)
		ensure_permission(doctype, SALARY_VIEWER, READ, permlevel=SALARY_LEVEL)


def protect_counters() -> None:
	"""Put the job counters on permission level 2, readable by staff only."""
	for fieldname in COUNTER_FIELDS:
		frappe.make_property_setter(
			{
				"doctype": "Job Opening",
				"doctype_or_field": "DocField",
				"fieldname": fieldname,
				"property": "permlevel",
				"value": str(COUNTER_LEVEL),
				"property_type": "Int",
			},
			is_system_generated=False,
		)
	for role in STAFF_ROLES:
		ensure_permission("Job Opening", role, READ, permlevel=COUNTER_LEVEL)


def apply_roles_and_permissions(commit: bool = True) -> None:
	"""after_migrate hook: create the ATS roles and give them their permissions."""
	create_roles()
	for doctype, ptypes in RECRUITER_PERMISSIONS.items():
		ensure_permission(doctype, RECRUITER, ptypes)
	for doctype, ptypes in GUEST_PERMISSIONS.items():
		ensure_permission(doctype, GUEST, ptypes)
	for doctype, ptypes in GUEST_OWN_RECORDS.items():
		ensure_permission(doctype, GUEST, ptypes, if_owner=1)
	protect_salary_fields()
	protect_counters()
	if commit:
		frappe.db.commit()
	frappe.clear_cache()
