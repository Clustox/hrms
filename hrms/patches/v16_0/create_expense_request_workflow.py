# Copyright (c) 2026, Clustox and contributors
# License: see license.txt
"""Seed the Expense Request approval workflow, its two dedicated approver roles,
and the doctype permissions those roles need. Idempotent: safe to re-run."""

import frappe
from frappe.permissions import add_permission, update_permission_property

DOCTYPE = "Expense Request"
WORKFLOW_NAME = "Expense Request Approval"

HR_APPROVER = "Expense HR Approver"
ACCOUNTS_APPROVER = "Expense Accounts Approver"
HR_SOURCE_ROLES = ["HR Manager", "HR User"]
ACCOUNTS_SOURCE_ROLES = ["Accounts Manager", "Accounts User"]

# (state, doc_status, allow_edit). allow_edit is mandatory; terminal states are
# limited to HR Manager (admin override only -- read-only for everyone else).
STATES = [
	("Draft", 0, "Employee"),
	("Pending Manager", 0, "Employee"),
	("Pending HR", 0, HR_APPROVER),
	("Pending Accounts", 0, ACCOUNTS_APPROVER),
	("Rejected", 0, "HR Manager"),
	("Cancelled", 0, "HR Manager"),
	("Completed", 1, "HR Manager"),
]

# (state, action, next_state, allowed, allow_self_approval, condition)
TRANSITIONS = [
	("Draft", "Submit for Approval", "Pending Manager", "Employee", 1, "doc.requires_manager and doc.manager"),
	("Draft", "Submit for Approval", "Pending HR", "Employee", 1, "not (doc.requires_manager and doc.manager)"),
	("Draft", "Cancel", "Cancelled", "Employee", 1, "doc.owner == frappe.session.user"),
	("Pending Manager", "Approve", "Pending HR", "Employee", 0, "doc.manager == frappe.session.user"),
	("Pending Manager", "Reject", "Rejected", "Employee", 0, "doc.manager == frappe.session.user"),
	("Pending Manager", "Cancel", "Cancelled", "Employee", 1, "doc.owner == frappe.session.user"),
	("Pending HR", "Approve", "Pending Accounts", HR_APPROVER, 0, ""),
	("Pending HR", "Reject", "Rejected", HR_APPROVER, 0, ""),
	("Pending HR", "Cancel", "Cancelled", "Employee", 1, "doc.owner == frappe.session.user"),
	("Pending Accounts", "Complete", "Completed", ACCOUNTS_APPROVER, 0, ""),
	("Pending Accounts", "Reject", "Rejected", ACCOUNTS_APPROVER, 0, ""),
	("Pending Accounts", "Cancel", "Cancelled", "Employee", 1, "doc.owner == frappe.session.user"),
]


def execute():
	_ensure_roles()
	_assign_roles()
	_grant_permissions()
	_ensure_states_and_actions()
	_create_workflow()
	frappe.db.commit()


def _ensure_roles():
	for role in (HR_APPROVER, ACCOUNTS_APPROVER):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def _assign_roles():
	_assign(HR_SOURCE_ROLES, HR_APPROVER)
	_assign(ACCOUNTS_SOURCE_ROLES, ACCOUNTS_APPROVER)


def _assign(source_roles, target_role):
	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", source_roles], "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	for user in set(users):
		if user in ("Administrator", "Guest") or not frappe.db.exists("User", user):
			continue
		if not frappe.db.exists("Has Role", {"parent": user, "role": target_role, "parenttype": "User"}):
			frappe.get_doc("User", user).add_roles(target_role)


def _grant_permissions():
	role_perms = {
		HR_APPROVER: {"read": 1, "write": 1},
		ACCOUNTS_APPROVER: {"read": 1, "write": 1, "submit": 1},
	}
	for role, ptypes in role_perms.items():
		add_permission(DOCTYPE, role)
		for ptype, value in ptypes.items():
			update_permission_property(DOCTYPE, role, permlevel=0, ptype=ptype, value=value)


def _ensure_states_and_actions():
	for state, _ds, _ae in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": ""}
			).insert(ignore_permissions=True)
	for _s, action, *_rest in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)


def _create_workflow():
	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
	else:
		wf = frappe.new_doc("Workflow")
	wf.workflow_name = WORKFLOW_NAME
	wf.document_type = DOCTYPE
	wf.is_active = 1
	wf.override_status = 0
	wf.send_email_alert = 0
	wf.workflow_state_field = "workflow_state"
	wf.set("states", [])
	wf.set("transitions", [])
	for state, doc_status, allow_edit in STATES:
		wf.append("states", {"state": state, "doc_status": str(doc_status), "allow_edit": allow_edit or None})
	for state, action, next_state, allowed, self_approval, condition in TRANSITIONS:
		wf.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
				"allow_self_approval": self_approval,
				"condition": condition or None,
			},
		)
	wf.flags.ignore_permissions = True
	wf.save()
