import frappe
from frappe.utils import flt

SCOPE_MAP = {
    "Sale - Time & Material": ("Sale", "Time & Material"),
    "Sale - Deliverable": ("Sale", "Deliverable"),
    "Internal": ("Internal", None),
}


def resource_revenue(employee, project, start, end):
    return _sum_timesheet("billing_amount", employee, project, start, end)


def resource_cost(employee, project, start, end):
    return _sum_timesheet("costing_amount", employee, project, start, end)


def margin(employee, project, start, end):
    return resource_revenue(employee, project, start, end) - resource_cost(
        employee, project, start, end
    )


def _sum_timesheet(column, employee, project, start, end):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.{col}), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE ts.employee=%s AND td.project=%s
          AND td.from_time BETWEEN %s AND %s AND ts.docstatus < 2
        """.format(col=column),
        (employee, project, start, f"{end} 23:59:59"),
    )
    return flt(rows[0][0]) if rows else 0.0


def project_timesheet_revenue(project, start, end):
    """Total billable revenue on the project in the period, across ALL resources
    (document currency). This is the base for project-level roles (Sales, PM,
    Team Lead, Referrer) on a T&M project before it has been invoiced."""
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.billing_amount), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE td.project=%s AND td.from_time BETWEEN %s AND %s AND ts.docstatus < 2
        """,
        (project, start, f"{end} 23:59:59"),
    )
    return flt(rows[0][0]) if rows else 0.0


def project_invoiced(project, start, end):
    # net_amount (document currency, e.g. USD) — commissions are computed in the
    # client-billing currency, not the company base currency.
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sii.net_amount), 0)
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.project=%s AND si.docstatus=1
          AND si.posting_date BETWEEN %s AND %s
        """,
        (project, start, end),
    )
    return flt(rows[0][0]) if rows else 0.0


def project_timesheet_cost(project, start, end):
    """Total costing on the project in the period, across ALL resources (document
    currency, USD) — fed by native Activity Cost rates on the timesheets."""
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.costing_amount), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE td.project=%s AND td.from_time BETWEEN %s AND %s AND ts.docstatus < 2
        """,
        (project, start, f"{end} 23:59:59"),
    )
    return flt(rows[0][0]) if rows else 0.0


def project_sales_order_value(project):
    """Engagement value (USD) from the Project's linked Sales Order (net total,
    document currency). Zero for Internal projects with no order."""
    if not project:
        return 0.0
    so = frappe.db.get_value("Project", project, "custom_sales_order")
    if not so:
        return 0.0
    return flt(frappe.db.get_value("Sales Order", so, "net_total"))


def scope_matches(rule, sow_type, billing_model):
    scope = rule.sow_type_scope or "Any"
    if scope != "Any":
        want_type, want_model = SCOPE_MAP[scope]
        if sow_type != want_type:
            return False
        if want_model and billing_model != want_model:
            return False
    return True


def compute_commission(base_amount, rule, allocation_percent, override_rate=None):
    rate = override_rate if override_rate is not None else rule.rate_value
    if (rule.rate_type or "Percent") == "Percent":
        amt = flt(base_amount) * flt(rate) / 100.0
    else:
        amt = flt(rate)
    if getattr(rule, "scale_by_allocation", 0) and allocation_percent:
        amt = amt * (flt(allocation_percent) / 100.0)
    if flt(rule.min_amount) and amt < flt(rule.min_amount):
        amt = flt(rule.min_amount)
    if flt(rule.max_amount) and amt > flt(rule.max_amount):
        amt = flt(rule.max_amount)
    return flt(amt, 2)
