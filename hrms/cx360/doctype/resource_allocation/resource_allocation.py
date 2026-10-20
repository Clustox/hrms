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
        self._check_dates()
        self._check_total_allocation()

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
