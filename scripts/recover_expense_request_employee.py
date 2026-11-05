"""Recover Expense Request records whose `employee` was overwritten with an
approver's own employee by the pre-fix PWA bug (validateForm stamped the current
user's employee on every save, including approver edits such as entering a
rejection reason).

The `employee` field is never user-editable in the normal flow -- it is set only
by the form on create -- so *any* change to it recorded in the Version log is the
bug. The earliest logged `old` value is therefore the true original requester.

Run inside `bench console`:

    import scripts.recover_expense_request_employee as r
    r.run()            # REPORT ONLY -- prints candidates, writes nothing
    r.run(apply=True)  # restores employee (+ employee_name) to the original

Idempotent: a record already matching its original is skipped.
"""

import json

import frappe

# Roles an overwriting approver would hold; a current employee carrying one is a
# strong signal the change was the bug (the approver stamped their own employee).
APPROVER_ROLES = ("Expense HR Approver", "Expense Accounts Approver")


def _is_approver(employee):
	user = frappe.db.get_value("Employee", employee, "user_id")
	if not user:
		return False
	roles = set(frappe.get_roles(user))
	return bool(roles.intersection(APPROVER_ROLES))


def _employee_changes(docname):
	"""(old, new, when) for every `employee` change in the Version log, oldest first."""
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Expense Request", "docname": docname},
		fields=["name", "creation", "data"],
		order_by="creation asc",
	)
	out = []
	for v in versions:
		try:
			data = json.loads(v.data or "{}")
		except Exception:
			continue
		for ch in data.get("changed", []):
			if ch and ch[0] == "employee":
				out.append((ch[1], ch[2], v.creation))
	return out


def _candidates():
	rows = frappe.get_all("Expense Request", fields=["name", "employee", "employee_name"])
	found = []
	for r in rows:
		changes = _employee_changes(r.name)
		if not changes:
			continue
		original = changes[0][0]  # value before the first overwrite == original requester
		if not original or original == r.employee:
			continue  # no original recorded, or already correct (idempotent)
		found.append(
			{
				"name": r.name,
				"current": r.employee,
				"current_name": r.employee_name,
				"original": original,
				"original_name": frappe.db.get_value("Employee", original, "employee_name"),
				"n_changes": len(changes),
				"current_is_approver": _is_approver(r.employee),
			}
		)
	return found


def run(apply=False):
	cands = _candidates()
	print(f"RES candidates: {len(cands)}")
	for c in cands:
		flag = "APPROVER (bug)" if c["current_is_approver"] else "not-approver (verify!)"
		print(
			f"  - {c['name']} | current: {c['current']} ({c['current_name']}) [{flag}]"
			f" -> original: {c['original']} ({c['original_name']}) | employee-changes: {c['n_changes']}"
		)
	if not apply:
		print("RES mode: REPORT-ONLY (no writes)")
		return cands

	fixed = 0
	for c in cands:
		try:
			frappe.db.set_value(
				"Expense Request",
				c["name"],
				{"employee": c["original"], "employee_name": c["original_name"]},
				update_modified=False,
			)
			frappe.db.commit()
			fixed += 1
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), f"recover_expense_employee:{c['name']}")
	print(f"RES fixed: {fixed}/{len(cands)}")
	return cands
