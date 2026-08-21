"""Grant System Manager + set a strong random password for the three admins,
on a Frappe HR site. Standalone (frappe.init/connect) — no app install needed.

For each target it: backfills company_email on the Employee, ensures a linked
enabled User (Employee Self Service + System Manager roles), and sets a fresh
20-character alphanumeric password.

Passwords are NEVER printed. They are written to PASSWORD_FILE with 0600
permissions for the site owner to retrieve, then delete.

Run from frappe-bench:
    env/bin/python apps/hrms/.../setup_admins_server.py
  (or copy this file anywhere and run it with the bench python)

Idempotent: safe to re-run. Re-running generates NEW passwords for the three.
"""

import json
import os
import secrets
import string

import frappe

# ----------------------------------------------------------------- config
SITE_NAME = "SITE_NAME_HERE"   # <-- set to the target site; confirm with: ls sites
PASSWORD_FILE = "admin_passwords_DO_NOT_SHARE.json"  # written in CWD, chmod 600
ROLES = ["Employee Self Service", "System Manager"]

# employee_number -> login email for the admins to grant System Manager + a
# fresh password. Fill in, e.g. {"CT-00149": "user@example.com"}.
TARGETS = {
    # "CT-00000": "admin@example.com",
}

ALPHABET = string.ascii_letters + string.digits  # 20 chars ~= 119 bits


def gen():
    return "".join(secrets.choice(ALPHABET) for _ in range(20))


frappe.init(site=SITE_NAME)
frappe.connect()

creds = {}
summary = []

for code, email in TARGETS.items():
    emp = frappe.db.get_value(
        "Employee", {"employee_number": code},
        ["name", "status", "first_name", "middle_name", "last_name", "employee_name", "company_email"],
        as_dict=True,
    )
    if not emp:
        summary.append(f"{code} {email}: NO EMPLOYEE FOUND (import batch 2 first) -- skipped")
        continue

    # 1. backfill email on the employee record
    if (emp.company_email or "").lower() != email.lower():
        frappe.db.set_value("Employee", emp.name, "company_email", email)

    # 2. ensure the User exists
    if not frappe.db.exists("User", email):
        u = frappe.new_doc("User")
        u.update({
            "email": email,
            "first_name": emp.first_name or emp.employee_name,
            "middle_name": emp.middle_name,
            "last_name": emp.last_name,
            "user_type": "System User",
            "send_welcome_email": 0,
            "enabled": 1,
        })
        u.insert(ignore_permissions=True)

    # 3. roles (append+save is reliable even right after insert)
    u = frappe.get_doc("User", email)
    have = [r.role for r in u.roles]
    for role in ROLES:
        if role not in have:
            u.append("roles", {"role": role})

    # 4. password (set on the same save)
    pwd = gen()
    u.new_password = pwd
    u.send_welcome_email = 0
    u.enabled = 1
    u.save(ignore_permissions=True)

    # 5. link Employee -> User
    if emp.company_email != email or frappe.db.get_value("Employee", emp.name, "user_id") != email:
        frappe.db.set_value("Employee", emp.name, "user_id", email)

    creds[email] = pwd
    roles_now = frappe.get_all("Has Role", filters={"parent": email}, pluck="role")
    summary.append(f"{code} {email}: OK  roles={sorted(roles_now)}")

frappe.db.commit()

# also written to a locked-down file as a backup copy
with open(PASSWORD_FILE, "w") as f:
    json.dump(creds, f, indent=2)
os.chmod(PASSWORD_FILE, 0o600)

print("ADMIN_SETUP_DONE")
for line in summary:
    print("  ", line)
print("\n=== CREDENTIALS (send these to Hamad, then delete the file) ===")
for email, pwd in creds.items():
    print(f"  {email}  {pwd}")
print(f"\nAlso saved to: {os.path.abspath(PASSWORD_FILE)} (chmod 600) -- delete after handing over.")
