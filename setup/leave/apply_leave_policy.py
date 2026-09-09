"""Clustox Leave Policy (v1.3) -> Frappe HR.

Builds the leave framework from the HR "Leaves Policy" document:
  * configures / creates all Leave Types with their rules,
  * a 2026 Leave Period (Jan-Dec) linked to the existing "Clustox 2026" holidays,
  * a "Clustox Leave Policy 2026" bundling the annually-allocated types,
  * a Leave Policy Assignment for every active employee (prorated by join date),
  * a standalone 3-year Religious Leave allocation per employee.

Quotas (from the policy's "Categories of Leaves" table):
  Annual 10 | Medical/Sick 7 | Casual 5 | Religious 5 (per 3 yrs) | Maternity 6 wks
  Marriage 5 | Bereavement 2 | Hajj 10 (once) | Paternity 3 | Long Service 5@5y/10@10y

Design notes / known limitations (see README):
  * Gender restriction (Maternity=F, Paternity=M) is NOT native — enforced by HR
    at allocation time since those are event-based (not in the annual policy).
  * Carry-forward is capped at 5 for Annual via `maximum_carry_forwarded_leaves`.
  * Religious "5 per 3 years" is modelled as one allocation valid 2026-2028.
  * Probation rules (Casual not in probation, Sick 2 for probationers) and the
    "sandwich"/notice rules are procedural — HR-enforced, not encoded.

Idempotent: leave types are upserted; period/policy/assignments/allocations are
skipped if already present. Re-run to onboard newly-added employees.

Run: bench --site <site> execute hrms.apply_leave_policy.run
"""

import json

import frappe
from frappe.utils import flt

COMPANY = "Clustox"
YEAR = 2026
PERIOD_NAME = f"Clustox {YEAR}"
POLICY_NAME = f"Clustox Leave Policy {YEAR}"
HOLIDAY_LIST = "Clustox 2026"  # already exists on the site
FROM_DATE = f"{YEAR}-01-01"
TO_DATE = f"{YEAR}-12-31"
RELIGIOUS_TO = f"{YEAR + 2}-12-31"  # 3-year window

# --- Leave Type config. Keys map straight to Leave Type fields. -------------
# Existing on site: Casual Leave, Sick Leave, Compensatory Off, Leave Without Pay.
LEAVE_TYPES = {
    "Annual Leave": dict(
        max_leaves_allowed=10, is_carry_forward=1, maximum_carry_forwarded_leaves=5,
        applicable_after=365, max_continuous_days_allowed=10, include_holiday=0,
    ),
    "Sick Leave": dict(max_leaves_allowed=7, is_carry_forward=0, include_holiday=0),
    "Casual Leave": dict(
        max_leaves_allowed=5, is_carry_forward=0, max_continuous_days_allowed=1,
        include_holiday=0,
    ),
    "Religious Leave": dict(max_leaves_allowed=5, is_carry_forward=0, include_holiday=0),
    "Maternity Leave": dict(
        max_leaves_allowed=30, is_carry_forward=0, applicable_after=182, include_holiday=0,
    ),  # 6 weeks working days; female (HR-enforced)
    "Paternity Leave": dict(max_leaves_allowed=3, is_carry_forward=0, include_holiday=0),
    "Marriage Leave": dict(max_leaves_allowed=5, is_carry_forward=0, include_holiday=0),
    "Bereavement Leave": dict(max_leaves_allowed=2, is_carry_forward=0, include_holiday=1),  # 2 calendar days
    "Hajj Umrah Leave": dict(
        max_leaves_allowed=10, is_carry_forward=0, applicable_after=365, include_holiday=0,
    ),
    "Long Service Leave": dict(
        max_leaves_allowed=10, is_carry_forward=0, applicable_after=1825, include_holiday=0,
    ),
    "Compensatory Off": dict(is_compensatory=1),
    "Leave Without Pay": dict(is_lwp=1),
}

# annually allocated to everyone via the Leave Policy
POLICY_ALLOCATION = {"Annual Leave": 10, "Sick Leave": 7, "Casual Leave": 5}


def ensure_leave_types():
    changed = []
    for name, props in LEAVE_TYPES.items():
        if frappe.db.exists("Leave Type", name):
            doc = frappe.get_doc("Leave Type", name)
        else:
            doc = frappe.new_doc("Leave Type")
            doc.leave_type_name = name
        for k, v in props.items():
            doc.set(k, v)
        doc.save(ignore_permissions=True)
        changed.append(name)
    frappe.db.commit()
    return changed


def ensure_leave_period():
    existing = frappe.db.get_value(
        "Leave Period",
        {"company": COMPANY, "from_date": FROM_DATE, "to_date": TO_DATE},
        "name",
    )
    if existing:
        return existing, False
    doc = frappe.new_doc("Leave Period")
    doc.from_date = FROM_DATE
    doc.to_date = TO_DATE
    doc.company = COMPANY
    doc.is_active = 1
    if "optional_holiday_list" in {f.fieldname for f in doc.meta.fields}:
        doc.optional_holiday_list = HOLIDAY_LIST
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name, True


def ensure_leave_policy():
    if frappe.db.exists("Leave Policy", {"title": POLICY_NAME}):
        return frappe.db.get_value("Leave Policy", {"title": POLICY_NAME}, "name"), False
    doc = frappe.new_doc("Leave Policy")
    doc.title = POLICY_NAME
    for lt, alloc in POLICY_ALLOCATION.items():
        doc.append("leave_policy_details", {"leave_type": lt, "annual_allocation": alloc})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name, True


def assign_policy_to_all(period, policy):
    from hrms.hr.doctype.leave_policy_assignment.leave_policy_assignment import (
        create_assignment_for_multiple_employees,
    )

    all_emps = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
    already = set(frappe.get_all(
        "Leave Policy Assignment",
        filters={"leave_policy": policy, "docstatus": ["!=", 2]},
        pluck="employee",
    ))
    todo = [e for e in all_emps if e not in already]
    created = []
    if todo:
        created = create_assignment_for_multiple_employees(
            json.dumps(todo),
            json.dumps({
                "assignment_based_on": "Leave Period",
                "leave_policy": policy,
                "leave_period": period,
                "effective_from": FROM_DATE,
                "effective_to": TO_DATE,
                "carry_forward": 1,
            }),
        )
    frappe.db.commit()
    return len(all_emps), len(already), len(created)


def allocate_religious_all():
    lt = "Religious Leave"
    all_emps = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")
    created, skipped, failed = 0, 0, 0
    for emp in all_emps:
        if frappe.db.exists("Leave Allocation", {
            "employee": emp, "leave_type": lt, "docstatus": ["!=", 2],
            "from_date": FROM_DATE,
        }):
            skipped += 1
            continue
        sp = "relig_alloc"
        try:
            frappe.db.savepoint(sp)
            la = frappe.new_doc("Leave Allocation")
            la.employee = emp
            la.leave_type = lt
            la.from_date = FROM_DATE
            la.to_date = RELIGIOUS_TO
            la.new_leaves_allocated = 5
            la.insert(ignore_permissions=True)
            la.submit()
            created += 1
        except Exception:
            frappe.db.rollback(save_point=sp)
            failed += 1
    frappe.db.commit()
    return created, skipped, failed


def run():
    print("LEAVEPOLICY_START")

    changed = ensure_leave_types()
    print(f"leave types configured: {len(changed)}")

    period, new_p = ensure_leave_period()
    print(f"leave period: {period} ({'created' if new_p else 'existing'}) {FROM_DATE}..{TO_DATE}")

    policy, new_pol = ensure_leave_policy()
    print(f"leave policy: {policy} ({'created' if new_pol else 'existing'}) -> {POLICY_ALLOCATION}")

    total, already, created = assign_policy_to_all(period, policy)
    print(f"policy assignment: {total} active | already assigned {already} | newly assigned {created}")

    rc, rs, rf = allocate_religious_all()
    print(f"religious 3-yr allocation ({FROM_DATE}..{RELIGIOUS_TO}): created {rc} | skipped {rs} | failed {rf}")

    # ---- verification snapshot
    print("\n=== VERIFY ===")
    for lt in LEAVE_TYPES:
        d = frappe.get_doc("Leave Type", lt)
        print(f"  {lt:20} max={d.max_leaves_allowed} cf={d.is_carry_forward} "
              f"maxcf={d.get('maximum_carry_forwarded_leaves')} after={d.applicable_after}")
    print(f"  Leave Allocations now : {frappe.db.count('Leave Allocation')}")
    print(f"  Policy Assignments now: {frappe.db.count('Leave Policy Assignment')}")
    # sample one employee's balances
    sample = frappe.get_all("Leave Allocation",
                            filters={"docstatus": 1}, fields=["employee", "leave_type",
                            "total_leaves_allocated", "from_date", "to_date"],
                            order_by="employee", limit=8)
    print("  sample allocations:")
    for a in sample:
        print(f"    {a.employee}  {a.leave_type:18} {flt(a.total_leaves_allocated)}  "
              f"{a.from_date}..{a.to_date}")
    print("LEAVEPOLICY_END")
