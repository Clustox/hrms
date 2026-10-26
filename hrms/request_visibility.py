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
	# A has_permission hook must return True/False, never None: Frappe treats a
	# None return (when a doc is passed) as a DENY, which would block even an
	# employee reading or creating their own record.
	user = user or frappe.session.user
	if ALL_ACCESS_ROLES & set(frappe.get_roles(user)):
		return True  # HR/admin -- full access

	# Reversing an approval is an HR action: cancelling or deleting an approved
	# (submitted) or already-cancelled leave is limited to the HR roles above
	# (returned True just before). Approvers and team leads keep approving and
	# rejecting, and can still delete a leave that was never approved.
	if (
		getattr(doc, "doctype", None) == "Leave Application"
		and ptype in ("cancel", "delete")
		and getattr(doc, "docstatus", 0) in (1, 2)
	):
		return False

	target = getattr(doc, "employee", None)

	# Approval model: submit/cancel = the DIRECT manager approves their team's
	# requests. Not self-approval (an employee can't submit their own), and not
	# a skip-level manager. Role perms also gate this (only roles with submit=1
	# reach here), so a plain employee never approves.
	if ptype in ("submit", "cancel"):
		own = frappe.db.get_value("Employee", {"user_id": user}, "name")
		return bool(own and target and
			frappe.db.get_value("Employee", target, "reports_to") == own)

	# Create, and any doctype-level check (no specific doc -> target is None),
	# must pass -- otherwise the employee can't raise their own request at all
	# (the "need create permission on Attendance Request" regression). Per-doc
	# read/write/delete are scoped to own record + direct reports.
	if ptype == "create" or target is None:
		return True
	return target in _visible_employees(user)
