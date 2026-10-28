"""Cost Sheet — distributes each employee's cost (from their Rate Card) across their
planned Resource Allocations, per working day, then rolls up by the chosen period.

cost(day, allocation) = (monthly cost / working days in month) * allocation% """

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate

from hrms.cx360.cost_sheet import employee_monthly_cost, is_working_day, working_days_in_month

COST_CATEGORIES = [
    "", "Cost of Services", "Bench Cost", "Leadership Cost",
    "Training & Development Cost", "Pre-Sales", "Support", "Invest",
]
UTILIZATION_BUCKETS = ["Billable", "Bench - Utilized", "Bench - Idle", "Overhead"]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 110},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
        {"label": _("Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 130},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
        {"label": _("Cost Category"), "fieldname": "cost_category", "fieldtype": "Data", "width": 130},
        {"label": _("Utilization"), "fieldname": "utilization", "fieldtype": "Data", "width": 120},
        {"label": _("Alloc %"), "fieldname": "allocation_percent", "fieldtype": "Float", "width": 80},
        {"label": _("Days"), "fieldname": "days", "fieldtype": "Float", "width": 70},
        {"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "options": "currency", "width": 110},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 1, "hidden": 1},
    ]


def _utilization_bucket(cost_category, billable, project_is_internal):
    if cost_category == "Cost of Services" or billable:
        return "Billable"
    if cost_category == "Bench Cost":
        return "Bench - Utilized" if project_is_internal else "Bench - Idle"
    return "Overhead"


def _period_label(day, period):
    if period == "Weekly":
        iso = day.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if period == "Monthly":
        return day.strftime("%Y-%m")
    return day.strftime("%Y-%m-%d")


def get_data(filters):
    from_date, to_date = getdate(filters.from_date), getdate(filters.to_date)
    if from_date > to_date:
        return []
    period = filters.get("period") or "Daily"

    alloc_filters = {"status": "Active", "start_date": ["<=", to_date]}
    for f in ("project", "employee", "cost_category"):
        if filters.get(f):
            alloc_filters[f] = filters.get(f)
    allocations = frappe.get_all(
        "Resource Allocation",
        filters=alloc_filters,
        or_filters=[["end_date", ">=", from_date], ["end_date", "is", "not set"]],
        fields=["employee", "employee_name", "project", "allocation_percent",
                "cost_category", "billable", "start_date", "end_date"],
    )

    dept_cache, internal_cache, month_cost_cache, wd_cache = {}, {}, {}, {}
    groups = {}
    for a in allocations:
        if a.employee not in dept_cache:
            dept_cache[a.employee] = frappe.db.get_value("Employee", a.employee, "department") or ""
        dept = dept_cache[a.employee]
        if filters.get("department") and dept != filters.get("department"):
            continue
        if a.project not in internal_cache:
            internal_cache[a.project] = (
                frappe.db.get_value("Project", a.project, "custom_engagement_type") == "Internal")
        util = _utilization_bucket(a.cost_category, a.billable, internal_cache[a.project])
        if filters.get("utilization") and util != filters.get("utilization"):
            continue

        span_start = max(from_date, getdate(a.start_date))
        span_end = min(to_date, getdate(a.end_date) if a.end_date else to_date)
        day = span_start
        while day <= span_end:
            if is_working_day(day):
                ym = (day.year, day.month)
                mck = (a.employee, ym)
                if mck not in month_cost_cache:
                    month_cost_cache[mck] = employee_monthly_cost(a.employee, day)
                if ym not in wd_cache:
                    wd_cache[ym] = working_days_in_month(day)
                wd = wd_cache[ym]
                daily = (month_cost_cache[mck] / wd) if wd else 0.0
                cost = daily * flt(a.allocation_percent) / 100.0
                key = (_period_label(day, period), a.employee, a.employee_name, dept,
                       a.project, a.cost_category or "", util)
                g = groups.setdefault(
                    key, {"days": 0.0, "cost": 0.0, "allocation_percent": flt(a.allocation_percent)})
                g["days"] += 1
                g["cost"] += cost
            day += timedelta(days=1)

    rows = []
    for key, g in groups.items():
        period_label, emp, emp_name, dept, project, category, util = key
        rows.append({
            "period": period_label, "employee": emp, "employee_name": emp_name,
            "department": dept, "project": project, "cost_category": category,
            "utilization": util, "allocation_percent": g["allocation_percent"],
            "days": g["days"], "cost": flt(g["cost"], 2), "currency": "USD",
        })
    rows.sort(key=lambda r: (r["period"], r["employee_name"] or "", r["project"]))
    return rows
