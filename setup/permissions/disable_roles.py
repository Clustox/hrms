"""Declutter the role list: DISABLE (not delete) ERPNext business-module roles
that a software/services company doesn't use.

Disabling sets Role.disabled = 1 — the role disappears from the "add role"
picker and stops applying, but nothing is destroyed and it is reversible
(set disabled = 0). Deleting standard roles is avoided on purpose: many are
protected and app-defined ones are recreated by `bench migrate`.

By default a role that a real (non-Administrator) user still holds is SKIPPED
and reported — so an over-provisioned account doesn't get silently changed.
Pass strip_from_users=True to first REMOVE these roles from those accounts
(they don't need unused-module roles), then disable. Admin/HR/Accounts roles on
those same accounts are never touched — only the roles in DISABLE below.

Idempotent. Run:
  bench --site <site> execute hrms.disable_roles.run
  bench --site <site> execute hrms.disable_roles.run --kwargs "{'strip_from_users': True}"
"""

import frappe

DISABLE = [
    "Sales Manager", "Sales Master Manager", "Sales User",
    "Purchase Manager", "Purchase Master Manager", "Purchase User",
    "Stock Manager", "Stock User", "Item Manager",
    "Manufacturing Manager", "Manufacturing User",
    "Shop Floor Manager", "Shop Floor User",
    "Maintenance Manager", "Maintenance User",
    "Delivery Manager", "Delivery User", "Fulfillment User",
    "Quality Manager", "Fleet Manager", "Marketing Manager",
    "Academics User", "Customer", "Supplier", "Interviewer",
]


def run(strip_from_users=False):
    disabled, skipped_missing, skipped_inuse, stripped = [], [], [], []
    for name in DISABLE:
        if not frappe.db.exists("Role", name):
            skipped_missing.append(name)
            continue
        real = [u for u in frappe.get_all(
            "Has Role", filters={"role": name, "parenttype": "User"}, pluck="parent"
        ) if u != "Administrator"]
        if real and not strip_from_users:
            skipped_inuse.append((name, real))
            continue
        for u in real:
            frappe.db.delete("Has Role", {"parent": u, "parenttype": "User", "role": name})
            stripped.append((name, u))
        if real:
            frappe.clear_cache(user=None)
        if not frappe.db.get_value("Role", name, "disabled"):
            frappe.db.set_value("Role", name, "disabled", 1)
            disabled.append(name)
    frappe.db.commit()

    print("DISABLE_START")
    print(f"newly disabled ({len(disabled)}): {disabled}")
    print(f"roles stripped from users ({len(stripped)}): {stripped}")
    print(f"already-missing ({len(skipped_missing)}): {skipped_missing}")
    print(f"skipped — has real users ({len(skipped_inuse)}): {skipped_inuse}")
    enabled = frappe.get_all("Role", filters={"disabled": 0}, pluck="name")
    print(f"roles still ENABLED: {len(enabled)}")
    print("DISABLE_END")
