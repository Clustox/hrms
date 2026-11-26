# Copyright (c) 2026, Clustox and contributors
# License: see license.txt
"""Create the role the Job Requisition approval flow needs. Runs before the model
sync because the doctype's permission rows refer to it. Approvals use the standard
System Manager role, so only the requester role is created here. Idempotent."""

import frappe

ROLES = {
	"Requisition Requester": 0,
}


def execute():
	for role, desk_access in ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk_access}).insert(
				ignore_permissions=True
			)
	frappe.db.commit()
