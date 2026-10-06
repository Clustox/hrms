import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

STANDARD_MONTHLY_HOURS = 160


class ResourceAllocation(Document):
    def validate(self):
        self.monthly_capacity_hours = flt(self.allocation_percent) / 100.0 * STANDARD_MONTHLY_HOURS
        self._check_total_allocation()

    def _check_total_allocation(self):
        if self.status != "Active":
            return
        others = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": self.employee, "status": "Active",
                "name": ["!=", self.name or ""],
                "start_date": ["<=", self.end_date],
                "end_date": [">=", self.start_date],
            },
            fields=["allocation_percent"],
        )
        total = flt(self.allocation_percent) + sum(flt(o.allocation_percent) for o in others)
        if total > 100:
            frappe.throw(
                _("{0} would be allocated {1}% over this period (max 100%).").format(
                    self.employee_name or self.employee, total
                )
            )
