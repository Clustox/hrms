"""Team-lead visibility scoping for employee request doctypes.

Leave Application, Attendance Request, Shift Request and Expense Claim are
visible to:
  - HR / admin roles (ALL_ACCESS_ROLES): every record, and
  - everyone else: the owning employee's own records plus the records of that
    employee's DIRECT reports (reports_to == them). A team lead therefore sees
    their direct team; a regular employee (no reports) sees only their own.

Implemented as `permission_query_conditions` (list/report filtering) +
`has_permission` (single-document access) hooks. The `employee` link field on
these four doctypes is set to `ignore_user_permissions` (property setters added
at deploy time) so the old own-record User Permission no longer AND-restricts
them and this scoping is authoritative.
"""

import frappe

ALL_ACCESS_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}


def _visible_employees(user):
	"""Employee names this user may see, or None for unrestricted (HR/admin)."""
	if ALL_ACCESS_ROLES & set(frappe.get_roles(user)):
		return None
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		return []
	reports = frappe.get_all("Employee", filters={"reports_to": emp}, pluck="name")
	return [emp, *reports]


def _conditions(user, doctype):
	emps = _visible_employees(user or frappe.session.user)
	if emps is None:
		return ""
	if not emps:
		return "1=0"
	values = ", ".join(frappe.db.escape(e) for e in emps)
	return f"`tab{doctype}`.`employee` in ({values})"


def leave_application_query(user=None):
	return _conditions(user, "Leave Application")


def attendance_request_query(user=None):
	return _conditions(user, "Attendance Request")


def shift_request_query(user=None):
	return _conditions(user, "Shift Request")


def expense_claim_query(user=None):
	return _conditions(user, "Expense Claim")


def has_permission(doc, ptype=None, user=None, **kwargs):
	# Scope read visibility only; allow create/write/submit (the role perms
	# govern those -- an employee still raises their own requests, e.g. a WFH
	# Attendance Request, and an approver still acts).
	#
	# A has_permission hook must return True/False, never None: Frappe treats a
	# None return (when a doc is passed) as a DENY, which would block even an
	# employee reading or creating their own record.
	if ptype not in (None, "read", "select"):
		return True
	emps = _visible_employees(user or frappe.session.user)
	if emps is None:
		return True  # HR/admin -- see everything
	return getattr(doc, "employee", None) in emps  # True in-scope, False out-of-scope
