import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, get_last_day


def check_hours_cap(doc, method=None):
    """Soft alert (never blocks) when an employee's monthly hours on a project
    exceed their Resource Allocation capacity."""
    if not doc.employee:
        return
    # group logged hours by (project, month)
    buckets = {}
    for row in (doc.time_logs or []):
        if not row.project or not row.from_time:
            continue
        month_key = getdate(row.from_time).strftime("%Y-%m")
        buckets.setdefault((row.project, month_key), 0)
        buckets[(row.project, month_key)] += flt(row.hours)

    for (project, month_key), ts_hours in buckets.items():
        month_start = get_first_day(getdate(month_key + "-01"))
        month_end = get_last_day(month_start)
        alloc = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": doc.employee, "project": project, "status": "Active",
                "start_date": ["<=", month_end], "end_date": [">=", month_start],
            },
            fields=["name", "monthly_capacity_hours"], limit=1,
        )
        if not alloc:
            continue
        cap = flt(alloc[0].monthly_capacity_hours)
        existing = _logged_hours(doc.employee, project, month_start, month_end, exclude=doc.name)
        total = existing + ts_hours
        if cap and total > cap:
            frappe.msgprint(
                _("{0} has {1} hrs on {2} in {3} vs capacity {4} hrs.").format(
                    doc.employee, total, project, month_key, cap
                ),
                title=_("Over capacity"), indicator="orange",
            )


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
