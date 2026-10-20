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
        """Fill blank rates from the authoritative sources: cost from Activity Cost,
        billing from the project's Sales Order (falling back to Activity Cost). A rate
        typed by hand is left untouched."""
        if not flt(self.project_cost_rate):
            self.project_cost_rate = self._activity_cost_rate("costing_rate")
        if not flt(self.project_billing_rate):
            self.project_billing_rate = self._sales_order_rate() or self._activity_cost_rate("billing_rate")

    def _activity_cost_rate(self, field):
        if not (self.employee and self.activity_type):
            return 0
        return flt(frappe.db.get_value(
            "Activity Cost",
            {"employee": self.employee, "activity_type": self.activity_type},
            field,
        ))

    def _sales_order_rate(self):
        so = frappe.db.get_value("Project", self.project, "custom_sales_order")
        if not so:
            return 0
        item = frappe.get_all(
            "Sales Order Item", filters={"parent": so},
            fields=["rate"], order_by="idx", limit=1,
        )
        return flt(item[0].rate) if item else 0

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
