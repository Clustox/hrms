# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.patches.v16_0.create_expense_request_workflow import execute as seed_workflow
from hrms.tests.utils import HRMSTestSuite


def _user_for(employee):
	return frappe.db.get_value("Employee", employee, "user_id")


def _make_user_employee(email, reports_to=None, roles=None):
	emp = make_employee(email, company="_Test Company", reports_to=reports_to)
	user = frappe.get_doc("User", _user_for(emp))
	user.add_roles("Employee", *(roles or []))
	return emp, user.name


class TestExpenseRequestWorkflow(HRMSTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_workflow()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Expense Request")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _raise(self, employee, user, expense_type="AI Tool", **extra):
		frappe.set_user(user)
		doc = frappe.get_doc(
			{
				"doctype": "Expense Request",
				"employee": employee,
				"expense_type": expense_type,
				"amount": 1000,
				"reason": "test",
				"receipt": "/files/r.pdf",
				**extra,
			}
		).insert()
		return doc

	def test_manager_first_routes_to_pending_manager(self):
		mgr, _ = _make_user_employee("exp-wf-mgr@example.com")
		emp, emp_user = _make_user_employee("exp-wf-emp@example.com", reports_to=mgr)
		doc = self._raise(emp, emp_user, "AI Tool")
		apply_workflow(doc, "Submit for Approval")
		self.assertEqual(doc.workflow_state, "Pending Manager")

	def test_no_manager_routes_to_pending_hr(self):
		emp, emp_user = _make_user_employee("exp-wf-solo@example.com")
		doc = self._raise(emp, emp_user, "Food")
		apply_workflow(doc, "Submit for Approval")
		self.assertEqual(doc.workflow_state, "Pending HR")

	def test_full_chain_to_completed(self):
		mgr, mgr_user = _make_user_employee("exp-wf-mgr2@example.com")
		emp, emp_user = _make_user_employee("exp-wf-emp2@example.com", reports_to=mgr)
		hr, hr_user = _make_user_employee("exp-wf-hr@example.com", roles=["Expense HR Approver"])
		acc, acc_user = _make_user_employee("exp-wf-acc@example.com", roles=["Expense Accounts Approver"])

		doc = self._raise(emp, emp_user, "AI Tool")
		apply_workflow(doc, "Submit for Approval")
		frappe.set_user(mgr_user)
		apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")
		frappe.set_user(hr_user)
		apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")
		frappe.set_user(acc_user)
		paid = frappe.get_doc("Expense Request", doc.name)
		paid.payment_date = nowdate()
		paid.payment_mode = "Bank Transfer"
		paid.save()
		apply_workflow(frappe.get_doc("Expense Request", doc.name), "Complete")

		final = frappe.get_doc("Expense Request", doc.name)
		self.assertEqual(final.workflow_state, "Completed")
		self.assertEqual(final.docstatus, 1)
		self.assertEqual(final.paid_amount, 1000)
		self.assertEqual(final.paid_by, acc_user)

	def test_hr_cannot_self_approve(self):
		hr, hr_user = _make_user_employee("exp-wf-hrself@example.com", roles=["Expense HR Approver"])
		doc = self._raise(hr, hr_user, "Long Service Reward")
		apply_workflow(doc, "Submit for Approval")
		self.assertEqual(doc.workflow_state, "Pending HR")
		frappe.set_user(hr_user)
		self.assertRaises(
			frappe.ValidationError, apply_workflow, frappe.get_doc("Expense Request", doc.name), "Approve"
		)

	def test_non_manager_cannot_approve(self):
		mgr, _ = _make_user_employee("exp-wf-mgr3@example.com")
		emp, emp_user = _make_user_employee("exp-wf-emp3@example.com", reports_to=mgr)
		other, other_user = _make_user_employee("exp-wf-other@example.com")
		doc = self._raise(emp, emp_user, "AI Tool")
		apply_workflow(doc, "Submit for Approval")
		frappe.set_user(other_user)
		self.assertRaises(
			Exception, apply_workflow, frappe.get_doc("Expense Request", doc.name), "Approve"
		)

	def test_requester_can_cancel(self):
		mgr, _ = _make_user_employee("exp-wf-mgr4@example.com")
		emp, emp_user = _make_user_employee("exp-wf-emp4@example.com", reports_to=mgr)
		doc = self._raise(emp, emp_user, "AI Tool")
		apply_workflow(doc, "Submit for Approval")
		frappe.set_user(emp_user)
		apply_workflow(frappe.get_doc("Expense Request", doc.name), "Cancel")
		self.assertEqual(frappe.db.get_value("Expense Request", doc.name, "workflow_state"), "Cancelled")
