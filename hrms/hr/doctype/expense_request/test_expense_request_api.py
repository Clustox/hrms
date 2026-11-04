# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow

from hrms.api import get_expense_requests
from hrms.hr.doctype.expense_request.test_expense_request_workflow import (
	_make_user_employee,
	attach_receipt,
)
from hrms.patches.v16_0.create_expense_request_workflow import execute as seed_workflow
from hrms.tests.utils import HRMSTestSuite


class TestExpenseRequestAPI(HRMSTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_workflow()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Expense Request")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_owner_and_approval_queue(self):
		mgr, mgr_user = _make_user_employee("exp-api-mgr@example.com")
		emp, emp_user = _make_user_employee("exp-api-emp@example.com", reports_to=mgr)
		hr, hr_user = _make_user_employee("exp-api-hr@example.com", roles=["Expense HR Approver"])

		frappe.set_user(emp_user)
		doc = frappe.get_doc(
			{
				"doctype": "Expense Request",
				"employee": emp,
				"expense_type": "AI Tool",
				"amount": 1234,
				"reason": "t",
			}
		).insert()
		attach_receipt(doc)
		apply_workflow(doc, "Submit for Approval")
		frappe.set_user(mgr_user)
		apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")  # -> Pending HR

		frappe.set_user(emp_user)
		mine = get_expense_requests(employee=emp)
		self.assertTrue(any(r["name"] == doc.name for r in mine))
		self.assertIn("workflow_state", mine[0])
		self.assertEqual(mine[0]["workflow_state_field"], "workflow_state")

		frappe.set_user(hr_user)
		queue = get_expense_requests(employee=hr, approver_id=hr_user, for_approval=True)
		row = [r for r in queue if r["name"] == doc.name]
		self.assertTrue(row)
		self.assertEqual(row[0]["workflow_state"], "Pending HR")

		# owner never appears in their own approval queue
		frappe.set_user(emp_user)
		own_queue = get_expense_requests(employee=emp, approver_id=emp_user, for_approval=True)
		self.assertFalse(any(r["name"] == doc.name for r in own_queue))
