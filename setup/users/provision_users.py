"""Provision User accounts for employees and link them (Employee.user_id).

Creates a System User with the "Employee Self Service" role for each target
employee and links it. Does NOT set a password or send email here — login is
enabled later via the invite / password step (needs working SMTP).

Idempotent: existing users are re-used, role + link ensured, never duplicated.

Run: bench --site <site> execute hrms.provision_users.run
"""

import frappe

ESS_ROLE = "Employee Self Service"

# Optional: employees that need a company_email set first, matched by
# employee_number. Fill in as needed, e.g. {"CT-00149": "user@example.com"}.
# Employees that already have a company_email don't need an entry here.
EMAIL_BACKFILL = {}


def run():
    log = {"email_set": [], "user_created": [], "user_linked": [], "already": [], "warnings": []}

    # 1. backfill the three requested emails onto their Employee records
    for code, email in EMAIL_BACKFILL.items():
        emp = frappe.db.get_value("Employee", {"employee_number": code}, ["name", "company_email"], as_dict=True)
        if not emp:
            log["warnings"].append(f"{code}: no Employee found")
            continue
        if (emp.company_email or "").lower() != email.lower():
            frappe.db.set_value("Employee", emp.name, "company_email", email)
            log["email_set"].append(f"{code} -> {email}")

    # 2. every Active employee with a company_email and no linked user
    targets = frappe.db.sql(
        """
        SELECT name, employee_number, employee_name, first_name, middle_name,
               last_name, company_email, user_id
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND company_email IS NOT NULL AND company_email != ''
        ORDER BY employee_number
        """,
        as_dict=True,
    )

    for e in targets:
        email = e.company_email.strip()

        # guard: is this email already linked to a DIFFERENT employee?
        other = frappe.db.get_value(
            "Employee", {"user_id": email, "name": ["!=", e.name]}, "employee_number"
        )
        if other:
            log["warnings"].append(f"{e.employee_number}: {email} already linked to {other}, skipped")
            continue

        # create the User if missing
        if not frappe.db.exists("User", email):
            u = frappe.new_doc("User")
            u.update({
                "email": email,
                "first_name": e.first_name or e.employee_name,
                "middle_name": e.middle_name,
                "last_name": e.last_name,
                "user_type": "System User",
                "send_welcome_email": 0,   # no email here; invite step handles delivery
                "enabled": 1,
            })
            u.insert(ignore_permissions=True)
            log["user_created"].append(f"{e.employee_number} {email}")
        else:
            log["already"].append(f"User exists: {email}")

        # ensure the ESS role (append+save is reliable even right after insert,
        # unlike add_roles() which can silently no-op on a fresh user)
        u = frappe.get_doc("User", email)
        if ESS_ROLE not in [r.role for r in u.roles]:
            u.append("roles", {"role": ESS_ROLE})
            u.save(ignore_permissions=True)

        # link Employee -> User
        if e.user_id != email:
            frappe.db.set_value("Employee", e.name, "user_id", email)
            log["user_linked"].append(f"{e.employee_number} -> {email}")

    frappe.db.commit()

    print("\n========== PROVISION SUMMARY ==========")
    for k, items in log.items():
        print(f"\n{k.upper()} ({len(items)}):")
        for i in items:
            print("  ", i)
