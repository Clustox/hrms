# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate

from hrms.tests.utils import HRMSTestSuite

EXPENSE_TYPES = {"AI Tool", "Certifications", "Food", "OPD", "IPD", "Long Service Reward"}


class TestExpenseRequest(HRMSTestSuite):
	def setUp(self):
		frappe.db.delete("Expense Request")

	def test_doctype_installed_with_fields(self):
		meta = frappe.get_meta("Expense Request")
		for f in [
			"employee",
			"expense_type",
			"amount",
			"currency",
			"reason",
			"receipt",
			"prescription",
			"workflow_state",
			"requires_manager",
			"manager",
			"rejection_reason",
			"rejection_note",
			"paid_amount",
			"payment_date",
			"payment_mode",
			"reference_no",
			"paid_by",
		]:
			self.assertTrue(meta.has_field(f), f)
		self.assertTrue(meta.is_submittable)
		self.assertEqual(set(meta.get_field("expense_type").options.split("\n")), EXPENSE_TYPES)
