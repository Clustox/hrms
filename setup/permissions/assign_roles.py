"""Assign RBAC roles to employees' login accounts (additive; keeps existing roles).

Reads an employee_number -> [roles] mapping from a JSON file so no employee PII
lives in the repo. Copy role_assignments.example.json to a private, git-ignored
location, fill in real employee codes + roles, and pass its path:

  bench --site <site> execute hrms.assign_roles.run \
      --kwargs "{'mapping_file': '/tmp/role_assignments.json'}"

Each code is resolved to a User via Employee.user_id (falling back to a User
matching company/personal email). Roles are only added to an existing User;
employees without a login are reported as PENDING — create the account, then
re-run (idempotent).
"""

import json

import frappe

DEFAULT_MAPPING = "/tmp/role_assignments.json"


def _resolve_user(emp):
    if emp.user_id and frappe.db.exists("User", emp.user_id):
        return emp.user_id
    for em in (emp.company_email, emp.personal_email):
        if em and frappe.db.exists("User", em):
            return em
    return None


def run(mapping_file=None):
    emp_roles = json.load(open(mapping_file or DEFAULT_MAPPING))

    applied, pending = [], []
    for code, roles in emp_roles.items():
        emp = frappe.db.get_value(
            "Employee", {"employee_number": code},
            ["name", "employee_name", "user_id", "company_email", "personal_email"],
            as_dict=True,
        )
        if not emp:
            pending.append((code, "NO EMPLOYEE RECORD", roles))
            continue
        user = _resolve_user(emp)
        if not user:
            pending.append((code, emp.employee_name, roles))
            continue
        u = frappe.get_doc("User", user)
        have = {r.role for r in u.roles}
        added = [r for r in roles if r not in have and frappe.db.exists("Role", r)]
        for r in added:
            u.append("roles", {"role": r})
        if added:
            u.save(ignore_permissions=True)
        applied.append((code, emp.employee_name, user, added))
    frappe.db.commit()

    print("ASSIGN_START")
    print(f"APPLIED ({len(applied)}):")
    for code, nm, user, added in applied:
        print(f"  {code} {nm:26} {user:32} +{added or '-'}")
    print(f"\nPENDING — need a login account first ({len(pending)}):")
    for code, nm, roles in pending:
        print(f"  {code} {nm:26} would-get={roles}")
    print("ASSIGN_END")
