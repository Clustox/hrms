import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SOW(Document):
    def validate(self):
        if self.billing_model == "Deliverable":
            self.total_value = sum(flt(d.amount) for d in self.deliverables)
