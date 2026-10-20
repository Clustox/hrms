import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, get_last_day


def check_hours_cap(doc, method=None):
    """Reconcile logged time against the planned Resource Allocation.

    Billable time must sit inside an active allocation and within its capacity
    (blocked otherwise); internal / bench time only raises a soft warning when it
    runs over capacity. Rules apply per (project, month)."""
    if not doc.employee:
        return
    # group logged hours — and whether any of it is billable — by (project, month)
    buckets = {}
    for row in (doc.time_logs or []):
        if not row.project or not row.from_time:
            continue
        month_key = getdate(row.from_time).strftime("%Y-%m")
        bucket = buckets.setdefault((row.project, month_key), {"hours": 0.0, "billable": False})
        bucket["hours"] += flt(row.hours)
        if flt(row.get("is_billable")):
            bucket["billable"] = True

    for (project, month_key), info in buckets.items():
        month_start = get_first_day(getdate(month_key + "-01"))
        month_end = get_last_day(month_start)
        billable = info["billable"]
        alloc = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": doc.employee, "project": project, "status": "Active",
                "start_date": ["<=", month_end],
            },
            or_filters=[["end_date", ">=", month_start], ["end_date", "is", "not set"]],
            fields=["name", "monthly_capacity_hours"], limit=1,
        )
        if not alloc:
            if billable:
                frappe.throw(
                    _("{0} has billable time on {1} in {2} with no active Resource Allocation. "
                      "Allocate the resource to this project first.").format(
                        doc.employee, project, month_key),
                    title=_("No allocation"),
                )
            continue
        cap = flt(alloc[0].monthly_capacity_hours)
        existing = _logged_hours(doc.employee, project, month_start, month_end, exclude=doc.name)
        total = existing + info["hours"]
        if cap and total > cap:
            msg = _("{0} has {1} hrs on {2} in {3} vs capacity {4} hrs.").format(
                doc.employee, total, project, month_key, cap)
            if billable:
                frappe.throw(msg, title=_("Over capacity"))
            else:
                frappe.msgprint(msg, title=_("Over capacity"), indicator="orange")


def _logged_hours(employee, project, start, end, exclude=None):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.hours), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE ts.employee=%s AND td.project=%s
          AND td.from_time BETWEEN %s AND %s
          AND ts.docstatus < 2 AND ts.name != %s
        """,
        (employee, project, start, f"{end} 23:59:59", exclude or ""),
    )
    return flt(rows[0][0]) if rows else 0.0
