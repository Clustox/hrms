import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class CommissionRule(Document):
    def validate(self):
        self.currency = "USD"
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To cannot be before Effective From."))
