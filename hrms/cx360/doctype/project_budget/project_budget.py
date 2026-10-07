import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ProjectBudget(Document):
    def validate(self):
        self.currency = "USD"  # budgeting is always USD (see commission currency policy)
        resource_total = 0.0
        for line in self.resource_lines:
            if not line.rate and line.designation:
                dr = frappe.db.get_value(
                    "Designation Rate", line.designation,
                    ["hourly_rate", "monthly_rate"], as_dict=True,
                )
                if dr:
                    line.rate = dr.monthly_rate if line.basis == "Monthly" else dr.hourly_rate
            line.line_cost = flt(line.quantity) * flt(line.rate) * flt(line.duration)
            resource_total += flt(line.line_cost)
        other_total = sum(flt(c.amount) for c in self.other_costs)
        self.budgeted_cost = resource_total + other_total
        self.budgeted_profit = flt(self.project_value) - flt(self.budgeted_cost)
