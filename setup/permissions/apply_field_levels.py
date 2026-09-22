"""Phase 4: field-level confidentiality via Permission Levels on Employee.

Moves sensitive fields to permlevel 1 (personal-confidential) and permlevel 2
(payroll/bank), then grants those levels only to the HR/CEO/Accounts roles.
Anyone with plain Employee access (permlevel 0) can still open the record but
NO LONGER sees the protected fields. Administrator bypasses all levels.

Idempotent: safe to re-run (property setters are replaced, perms upserted).

Run: bench --site <site> execute hrms.apply_field_levels.run
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

LEVEL1_FIELDS = [
    "date_of_birth", "cell_number", "personal_email",
    "current_address", "permanent_address", "marital_status",
    "custom_cnic_no", "custom_cnic_expiry_date",
]
LEVEL2_FIELDS = ["bank_name", "bank_ac_no", "iban"]

# permlevel -> {role: [granted ptypes]}
LEVEL_PERMS = {
    1: {
        "HR User": ["read", "write"],
        "HR Manager": ["read", "write"],
        "CEO/COO": ["read"],
    },
    2: {
        "HR User": ["read", "write"],
        "HR Manager": ["read", "write"],
        "CEO/COO": ["read"],
        "Accounts Manager": ["read"],
    },
}

# ptypes that are meaningful at permlevel > 0
PTYPES = ["read", "write"]


def set_permlevel(fieldname, level):
    existing = frappe.get_all(
        "Property Setter",
        filters={"doc_type": "Employee", "field_name": fieldname, "property": "permlevel"},
        pluck="name",
    )
    for e in existing:
        frappe.delete_doc("Property Setter", e, force=True, ignore_permissions=True)
    frappe.make_property_setter({
        "doctype": "Employee",
        "doctype_or_field": "DocField",
        "fieldname": fieldname,
        "property": "permlevel",
        "value": level,
        "property_type": "Int",
    })


def run():
    for f in LEVEL1_FIELDS:
        set_permlevel(f, 1)
    for f in LEVEL2_FIELDS:
        set_permlevel(f, 2)

    for level, roles in LEVEL_PERMS.items():
        for role, granted in roles.items():
            add_permission("Employee", role, level)
            for p in PTYPES:
                update_permission_property("Employee", role, level, p, 1 if p in granted else 0)

    frappe.clear_cache(doctype="Employee")
    frappe.db.commit()

    # ---- report
    m = frappe.get_meta("Employee")
    print("FIELDLVL_START")
    print("field permlevels:")
    for f in LEVEL1_FIELDS + LEVEL2_FIELDS:
        fld = m.get_field(f)
        print(f"  {f:30} -> permlevel {fld.permlevel}")
    print("custom docperms (permlevel > 0):")
    rows = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": "Employee", "permlevel": [">", 0]},
        fields=["role", "permlevel", "read", "write"],
        order_by="permlevel, role",
    )
    for r in rows:
        print(f"  L{r.permlevel} {r.role:20} read={r.read} write={r.write}")
    print("FIELDLVL_END")
