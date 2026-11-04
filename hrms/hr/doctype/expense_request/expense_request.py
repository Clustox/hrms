# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from hrms.hr.utils import validate_active_employee

# Expense types that must be approved by the employee's manager first.
MANAGER_FIRST_TYPES = {"AI Tool", "Certifications", "Food"}
# Non-working states where attachments are not yet required.
PRE_SUBMIT_STATES = {None, "", "Draft", "Cancelled"}


def resolve_manager(employee: str) -> str | None:
	"""The User id of the employee's reports_to manager, or None when the
	employee has no reports_to (or that manager has no linked user)."""
	reports_to = frappe.db.get_value("Employee", employee, "reports_to")
	if not reports_to:
		return None
	return frappe.db.get_value("Employee", reports_to, "user_id") or None


class ExpenseRequest(Document):
	def validate(self):
		validate_active_employee(self.employee)
		self.set_routing_fields()
		self.set_currency()
		self.validate_amount()
		self.validate_attachments()
		self.validate_rejection()
		self.validate_completion()

	def set_routing_fields(self):
		self.requires_manager = 1 if self.expense_type in MANAGER_FIRST_TYPES else 0
		# Resolved here so the workflow's Draft routing condition
		# (`doc.requires_manager and doc.manager`) is accurate at submit time.
		self.manager = resolve_manager(self.employee)

	def set_currency(self):
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def validate_amount(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

	def validate_attachments(self):
		# Attachments are generic File records uploaded after insert (the PWA
		# pattern), so require them only once the request leaves Draft for
		# approval. At least one file (the receipt / invoice) is mandatory;
		# OPD / IPD should also include the prescription (reviewer-checked).
		if self.workflow_state in PRE_SUBMIT_STATES:
			return
		count = frappe.db.count(
			"File", {"attached_to_doctype": self.doctype, "attached_to_name": self.name}
		)
		if count < 1:
			frappe.throw(_("Please attach the receipt / invoice before submitting this request."))

	def validate_rejection(self):
		if self.workflow_state == "Rejected" and not self.rejection_reason:
			frappe.throw(_("A rejection reason is required to reject this request."))

	def validate_completion(self):
		if self.workflow_state != "Completed":
			return
		if not flt(self.paid_amount):
			self.paid_amount = self.amount
		if not self.payment_date:
			frappe.throw(_("Payment date is required to complete this request."))
		if not self.payment_mode:
			frappe.throw(_("Payment mode is required to complete this request."))
		self.paid_by = frappe.session.user
