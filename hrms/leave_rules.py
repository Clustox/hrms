"""Clustox Leave Policy (v1.3) enforcement — server-side validations on Leave
Application / Leave Allocation, applied everywhere (/hrms PWA, desk, API).

Registered via hooks.py `doc_events`. Rules that the policy states but Frappe
does not enforce natively are implemented here:

  * advance-notice periods (Annual 3/30, Religious 15, Marriage 45, Hajj 60)
  * gender restriction (Maternity = Female, Paternity = Male)
  * "once in employment" (Hajj/Umrah)
  * probation (first 90 days): Casual blocked, Sick capped at 2
  * no leave during the notice/resignation period
  * Casual cannot be combined with another leave or an adjacent holiday
  * sandwich leave (leave immediately before AND after a holiday) not allowed
  * medical proof (attachment) required for Sick Leave over 2 days
  * Compensatory Off expires 1 month after it is earned

Enforcement = HARD BLOCK, but users holding an HR/override role bypass it
(for approved exceptions / emergencies). Emergencies applied on/for the same
day or a past date are exempt from the advance-notice rule.
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, today

OVERRIDE_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}
PROBATION_DAYS = 90

ANNUAL = "Annual Leave"
SICK = "Sick Leave"
CASUAL = "Casual Leave"
COMP_OFF = "Compensatory Off"

GENDER_REQUIRED = {"Maternity Leave": "Female", "Paternity Leave": "Male"}
FIXED_NOTICE_DAYS = {"Religious Leave": 15, "Marriage Leave": 45, "Hajj Umrah Leave": 60}
ONCE_TYPES = {"Hajj Umrah Leave"}


def _has_override() -> bool:
    return bool(set(frappe.get_roles()) & OVERRIDE_ROLES)


def _holiday_list(employee: str):
    try:
        from hrms.hr.utils import get_holiday_list_for_employee
        return get_holiday_list_for_employee(employee, raise_exception=False)
    except Exception:
        return None


def _is_holiday(hl, d) -> bool:
    return bool(hl) and bool(
        frappe.db.exists("Holiday", {"parent": hl, "holiday_date": getdate(d)})
    )


def _other_leave_on(doc, d) -> bool:
    """True if the employee has another (non-cancelled) leave covering day d."""
    return bool(frappe.db.exists("Leave Application", {
        "employee": doc.employee,
        "docstatus": ["<", 2],
        "name": ["!=", doc.name or "new"],
        "from_date": ["<=", getdate(d)],
        "to_date": [">=", getdate(d)],
    }))


def _sick_days_in_probation(doc, doj, prob_end) -> float:
    rows = frappe.get_all(
        "Leave Application",
        filters={
            "employee": doc.employee, "leave_type": SICK, "docstatus": ["<", 2],
            "name": ["!=", doc.name or "new"],
            "from_date": [">=", doj], "to_date": ["<", prob_end],
        },
        fields=["total_leave_days"],
    )
    return sum((r.total_leave_days or 0) for r in rows)


def _sandwiched_on(doc, hl, boundary_day) -> bool:
    """Skip a run of holidays outward from boundary_day; if the first working day
    reached is another leave day, this application sandwiches that holiday run."""
    if not _is_holiday(hl, boundary_day):
        return False  # no holiday immediately adjacent -> no sandwich on this side
    step = -1 if getdate(boundary_day) <= getdate(doc.from_date) else 1
    cur = boundary_day
    for _i in range(10):  # skip the run of holidays outward
        if not _is_holiday(hl, cur):
            break
        cur = add_days(cur, step)
    return _other_leave_on(doc, cur)


def validate_leave_application(doc, method=None):
    if _has_override():
        return

    lt = doc.leave_type
    frm = getdate(doc.from_date)
    to = getdate(doc.to_date)
    days = doc.total_leave_days or (date_diff(to, frm) + 1)
    emp = frappe.get_doc("Employee", doc.employee)

    # 1) gender
    req_gender = GENDER_REQUIRED.get(lt)
    if req_gender and (emp.get("gender") or "") != req_gender:
        frappe.throw(_("{0} is only available to {1} employees.").format(lt, req_gender))

    # 2) once in employment
    if lt in ONCE_TYPES and frappe.db.exists("Leave Application", {
        "employee": doc.employee, "leave_type": lt,
        "docstatus": ["<", 2], "name": ["!=", doc.name or "new"],
    }):
        frappe.throw(_("{0} can be availed only once during employment.").format(lt))

    # 3) advance notice — only for planned (future) leaves; same-day/backdated = emergency
    if frm > getdate(today()):
        needed = (3 if days <= 2 else 30) if lt == ANNUAL else FIXED_NOTICE_DAYS.get(lt)
        if needed:
            earliest = add_days(getdate(today()), needed)
            if frm < earliest:
                frappe.throw(_("{0} requires at least {1} days notice. "
                               "Earliest start date is {2}.").format(lt, needed, earliest))

    # 4) probation (first 90 days from joining, unless confirmed earlier)
    doj = getdate(emp.date_of_joining) if emp.get("date_of_joining") else None
    if doj:
        conf = getdate(emp.get("final_confirmation_date")) if emp.get("final_confirmation_date") else None
        prob_end = conf or add_days(doj, PROBATION_DAYS)
        if frm < prob_end:
            if lt == CASUAL:
                frappe.throw(_("Casual Leave is not permitted during probation "
                               "(until {0}).").format(prob_end))
            if lt == SICK and _sick_days_in_probation(doc, doj, prob_end) + days > 2:
                frappe.throw(_("During probation, Sick Leave is capped at 2 days."))

    # 5) no leave during notice / resignation period
    rel = getdate(emp.get("relieving_date")) if emp.get("relieving_date") else None
    if rel and getdate(today()) <= frm <= rel:
        frappe.throw(_("Leave cannot be availed during the notice / resignation period."))

    # 6) casual cannot combine with another leave or an adjacent holiday
    hl = _holiday_list(doc.employee)
    if lt == CASUAL:
        if _is_holiday(hl, add_days(frm, -1)) or _is_holiday(hl, add_days(to, 1)):
            frappe.throw(_("Casual Leave cannot be combined with a holiday or weekend."))
        if _other_leave_on(doc, add_days(frm, -1)) or _other_leave_on(doc, add_days(to, 1)):
            frappe.throw(_("Casual Leave cannot be combined with another leave."))

    # 7) sandwich leave (leave immediately before AND after a holiday run)
    if hl and (_sandwiched_on(doc, hl, add_days(frm, -1))
               or _sandwiched_on(doc, hl, add_days(to, 1))):
        frappe.throw(_("Sandwich leave is not allowed — you cannot take leave "
                       "immediately before and after a holiday/weekend."))


def validate_leave_application_on_submit(doc, method=None):
    """Medical proof required for Sick Leave over 2 days (checked at submit,
    once attachments can exist)."""
    if _has_override():
        return
    days = doc.total_leave_days or 0
    if doc.leave_type == SICK and days > 2:
        has_file = frappe.db.exists("File", {
            "attached_to_doctype": "Leave Application",
            "attached_to_name": doc.name,
        })
        if not has_file:
            frappe.throw(_("Sick Leave over 2 days requires a medical document "
                           "to be attached."))


def cap_compensatory_off_expiry(doc, method=None):
    """Compensatory Off must be availed within 1 month of being earned."""
    if doc.leave_type != COMP_OFF or not doc.get("from_date"):
        return
    limit = add_days(getdate(doc.from_date), 30)
    if doc.get("to_date") and getdate(doc.to_date) > limit:
        doc.to_date = limit
