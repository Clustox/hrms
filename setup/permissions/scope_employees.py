"""Scope layer (part 1): restrict regular employees to their OWN transactional
records, while leaving the Employee directory / org chart visible to everyone.

Mechanism: for each employee login that has NO broad role, create a User
Permission (User -> own Employee) that is `applicable_for` each personal
doctype only. Because the permission is scoped per-doctype (never "apply to all"
and never for the Employee doctype itself), the employee directory and org chart
stay fully visible, but Leave/Attendance/Salary/Expense/etc. show only own rows.

Users holding a broad role (HR/Accounts/CEO/IT/System Manager) are SKIPPED — a
User Permission would wrongly restrict their company-wide access.

Managers' team visibility is intentionally NOT handled here: it depends on real
Reports-To lines (currently a flat placeholder) and ships with that change.

Idempotent: existing permissions are not duplicated. Re-run after new logins.

Run: bench --site <site> execute hrms.scope_employees.run
"""

import frappe

# roles that must keep company-wide (or matrix-wide) visibility — never scoped
BROAD_ROLES = {
    "System Manager", "Administrator", "HR User", "HR Manager",
    "Accounts Manager", "Accounts User", "CEO/COO", "IT User", "Department Head",
}

# personal/transactional doctypes an employee should see only their own of
SCOPED_DOCTYPES = [
    "Leave Application", "Leave Allocation", "Attendance", "Employee Checkin",
    "Salary Slip", "Salary Structure Assignment", "Expense Claim",
    "Employee Advance", "Additional Salary", "Employee Incentive",
    "Appraisal", "Employee Performance Feedback", "Goal", "Employee Separation",
]


def run():
    emps = frappe.get_all(
        "Employee", filters={"user_id": ["is", "set"]},
        fields=["name", "employee_name", "user_id"],
    )
    scoped, skipped, created = [], [], 0
    for e in emps:
        if not frappe.db.exists("User", e.user_id):
            continue
        roles = set(frappe.get_all("Has Role", filters={"parent": e.user_id}, pluck="role"))
        broad = roles & BROAD_ROLES
        if broad:
            skipped.append((e.user_id, sorted(broad)))
            continue
        for dt in SCOPED_DOCTYPES:
            if not frappe.db.exists("DocType", dt):
                continue
            if frappe.db.exists("User Permission", {
                "user": e.user_id, "allow": "Employee",
                "for_value": e.name, "applicable_for": dt,
            }):
                continue
            frappe.get_doc({
                "doctype": "User Permission",
                "user": e.user_id,
                "allow": "Employee",
                "for_value": e.name,
                "applicable_for": dt,
                "apply_to_all_doctypes": 0,
            }).insert(ignore_permissions=True)
            created += 1
        scoped.append(e.user_id)
    frappe.db.commit()

    print("SCOPE_START")
    print(f"scoped employees: {len(scoped)}  |  new permissions created: {created}")
    print(f"skipped (broad role, stay company-wide): {len(skipped)}")
    for u, br in skipped:
        print(f"  SKIP {u:34} {br}")
    print("SCOPE_END")
