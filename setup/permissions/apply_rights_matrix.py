"""Phase 2+3: create the new HR roles and apply the DocType rights matrix.

Because a Custom DocPerm on a DocType overrides ALL default perms for it,
every customized DocType also gets System Manager (full) so admins keep access.
Export/Print/Import are NOT granted (per the security rules) except to System Manager.

Run: bench --site <site> execute hrms.apply_rights_matrix.run
"""
import json
import frappe
from frappe.permissions import add_permission, update_permission_property

NEW_ROLES = ["Team Lead", "Department Head", "CEO/COO", "IT User", "Admin User"]
FULL = ["read", "write", "create", "submit", "cancel", "delete", "report", "export", "print", "email"]
ALL_PTYPES = ["read", "write", "create", "submit", "cancel", "delete", "report", "export", "print", "email", "import"]


def set_perm(dt, role, granted):
    add_permission(dt, role, 0)
    for p in ALL_PTYPES:
        update_permission_property(dt, role, 0, p, 1 if p in granted else 0)


def run(mapping_file=None):
    matrix = json.load(open(mapping_file or "/tmp/rights_matrix.json"))

    created = []
    for r in NEW_ROLES:
        if not frappe.db.exists("Role", r):
            d = frappe.new_doc("Role")
            d.role_name = r
            d.desk_access = 1
            d.insert(ignore_permissions=True)
            created.append(r)

    applied, missing = [], []
    for dt, roles in matrix.items():
        if not frappe.db.exists("DocType", dt):
            missing.append(dt)
            continue
        set_perm(dt, "System Manager", FULL)          # admins always retain access
        for role, ptypes in roles.items():
            granted = list(ptypes)
            if "read" in granted:
                granted.append("report")               # usable list/report view, but no export
            set_perm(dt, role, granted)
        applied.append(dt)

    frappe.db.commit()
    print("MATRIX_START")
    print("roles_created:", created)
    print("doctypes_applied:", len(applied))
    print("doctypes_MISSING:", missing)
    print("MATRIX_END")
