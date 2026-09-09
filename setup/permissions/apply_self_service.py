"""Phase 5: employee self-service — let each employee see their OWN full
profile (personal + bank details) in the /hrms PWA, WITHOUT exposing any
colleague's confidential fields.

Background
----------
apply_field_levels.py moved sensitive fields to permlevel 1 (personal) and
permlevel 2 (bank) and granted those levels only to HR/CEO/Accounts. As a
side effect an employee could not see those fields on their OWN profile
either — the /hrms Profile page showed blank DOB / phone / bank.

The catch: permlevels are ROLE-based, not record-based, so we cannot natively
say "see permlevel-1 on your own record only". Granting the Employee Self
Service (ESS) role permlevel-1 read would let anyone read every colleague's
CNIC/DOB via the API — because the Employee directory is otherwise open.

Fix (airtight): record-scope Employee for pure-ESS logins so an employee can
only READ their own Employee record, THEN grant ESS permlevel 1 & 2 read.
Now the grant can only ever reveal the employee's own data. The company
directory keeps working because hrms.api.get_all_employees is patched to run
with ignore_permissions (it returns only 9 non-sensitive fields — see
hrms/api/__init__.py). No colleague full-doc is fetched anywhere in the PWA.

Result:
  * Own profile  -> DOB, phone, personal email, address, CNIC, bank visible
  * Colleagues   -> name / designation / department / image only (directory)
  * API path to a colleague's confidential field -> blocked (record-scoped)

Read-only for now: employees VIEW their own profile. Editing needs a PWA edit
feature and is best done as an approval-based change request (phase 6) so an
employee cannot alter their own designation / salary / joining date.

Idempotent: safe to re-run. Run AFTER apply_field_levels.py and scope_employees.py:
    bench --site <site> execute hrms.apply_self_service.run
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

ESS_ROLE = "Employee Self Service"

# permlevels the employee may READ on their own record (write stays HR-only)
SELF_READ_LEVELS = [1, 2]

# roles that must keep company-wide visibility — never record-scoped on Employee
BROAD_ROLES = {
    "System Manager", "Administrator", "HR User", "HR Manager",
    "Accounts Manager", "Accounts User", "CEO/COO", "IT User", "Department Head",
}


def grant_self_read():
    """ESS may read (not write) the confidential permlevels — own record only,
    because Employee is record-scoped below."""
    for level in SELF_READ_LEVELS:
        add_permission("Employee", ESS_ROLE, level)
        update_permission_property("Employee", ESS_ROLE, level, "read", 1)
        update_permission_property("Employee", ESS_ROLE, level, "write", 0)


def scope_employee_to_own():
    """For every login that has ONLY employee-level roles, restrict the
    Employee doctype to their own record. Broad roles are skipped."""
    created, scoped, skipped = 0, [], []
    emps = frappe.get_all(
        "Employee", filters={"user_id": ["is", "set"]},
        fields=["name", "user_id"],
    )
    for e in emps:
        if not frappe.db.exists("User", e.user_id):
            continue
        roles = set(frappe.get_all("Has Role", filters={"parent": e.user_id}, pluck="role"))
        if roles & BROAD_ROLES:
            skipped.append(e.user_id)
            continue
        exists = frappe.db.exists("User Permission", {
            "user": e.user_id, "allow": "Employee",
            "for_value": e.name, "applicable_for": "Employee",
        })
        if exists:
            scoped.append(e.user_id)
            continue
        frappe.get_doc({
            "doctype": "User Permission",
            "user": e.user_id,
            "allow": "Employee",
            "for_value": e.name,
            "applicable_for": "Employee",
            "apply_to_all_doctypes": 0,
        }).insert(ignore_permissions=True)
        created += 1
        scoped.append(e.user_id)
    return created, scoped, skipped


def run():
    grant_self_read()
    created, scoped, skipped = scope_employee_to_own()
    frappe.clear_cache(doctype="Employee")
    frappe.db.commit()

    print("SELFSERVICE_START")
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": "Employee", "role": ESS_ROLE, "permlevel": [">", 0]},
        fields=["permlevel", "read", "write"], order_by="permlevel",
    )
    print(f"{ESS_ROLE} confidential-level perms:")
    for r in rows:
        print(f"  L{r.permlevel}  read={r.read}  write={r.write}")
    print(f"Employee record-scoped logins: {len(scoped)} "
          f"(new permissions: {created}) | broad-role skipped: {len(skipped)}")
    print("REMINDER: hrms.api.get_all_employees must run ignore_permissions "
          "so the directory still lists everyone (9 safe fields).")
    print("SELFSERVICE_END")
