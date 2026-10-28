import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

STANDARD_MONTHLY_HOURS = 160
OPEN_END = getdate("2999-12-31")  # sentinel for an open-ended allocation (no end_date)


class ResourceAllocation(Document):
    def validate(self):
        self.currency = "USD"
        self.monthly_capacity_hours = flt(self.allocation_percent) / 100.0 * STANDARD_MONTHLY_HOURS
        self._populate_rates()
        self._check_dates()
        self._check_total_allocation()

    def _populate_rates(self):
        """Fill blank rates from the authoritative sources (see get_suggested_rates).
        A rate typed by hand is left untouched."""
        rates = get_suggested_rates(self.employee, self.project, self.start_date)
        if not flt(self.project_cost_rate):
            self.project_cost_rate = rates["cost_rate"]
        if not flt(self.project_billing_rate):
            self.project_billing_rate = rates["billing_rate"]

    def _check_dates(self):
        if self.end_date and getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(_("End Date cannot be before Start Date."))

    def _check_total_allocation(self):
        if self.status != "Active":
            return
        my_start = getdate(self.start_date)
        my_end = getdate(self.end_date) if self.end_date else OPEN_END
        others = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": self.employee, "status": "Active",
                "name": ["!=", self.name or ""],
            },
            fields=["allocation_percent", "start_date", "end_date"],
        )
        total = flt(self.allocation_percent)
        for o in others:
            o_start = getdate(o.start_date)
            o_end = getdate(o.end_date) if o.end_date else OPEN_END
            if o_start <= my_end and o_end >= my_start:  # periods overlap
                total += flt(o.allocation_percent)
        if total > 100:
            frappe.throw(
                _("{0} would be allocated {1}% over this period (max 100%).").format(
                    self.employee_name or self.employee, total
                )
            )


@frappe.whitelist()
def get_suggested_rates(
    employee: str | None = None, project: str | None = None, on_date: str | None = None
) -> dict:
    """Suggested allocation rates: cost from the employee's Rate Card (hourly), billing
    from the project's Sales Order. Shared by the form (live prefill) and the controller
    (fill-if-blank on save)."""
    from hrms.cx360 import cost_sheet

    on_date = on_date or frappe.utils.today()
    return {
        "cost_rate": cost_sheet.employee_hourly_cost(employee, on_date) if employee else 0,
        "billing_rate": _sales_order_rate(project),
    }


def _sales_order_rate(project):
    so = frappe.db.get_value("Project", project, "custom_sales_order") if project else None
    if not so:
        return 0
    item = frappe.get_all(
        "Sales Order Item", filters={"parent": so},
        fields=["rate"], order_by="idx", limit=1,
    )
    return flt(item[0].rate) if item else 0
