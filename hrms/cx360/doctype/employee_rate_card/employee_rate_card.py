import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

STANDARD_MONTHLY_HOURS = 160


class EmployeeRateCard(Document):
    def validate(self):
        self.currency = "USD"
        self.hourly_cost = flt(self.monthly_cost) / STANDARD_MONTHLY_HOURS
        self._check_duplicate_effective_from()

    def _check_duplicate_effective_from(self):
        dupe = frappe.db.exists(
            "Employee Rate Card",
            {
                "employee": self.employee,
                "effective_from": getdate(self.effective_from),
                "name": ["!=", self.name or ""],
            },
        )
        if dupe:
            frappe.throw(
                _("{0} already has a rate card effective {1} ({2}).").format(
                    self.employee_name or self.employee, self.effective_from, dupe
                )
            )
