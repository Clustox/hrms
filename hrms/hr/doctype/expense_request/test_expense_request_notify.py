# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import nowdate

from hrms.hr.doctype.expense_request.test_expense_request_workflow import _make_user_employee
from hrms.patches.v16_0.create_expense_request_workflow import execute as seed_workflow
from hrms.tests.utils import HRMSTestSuite


class TestExpenseRequestNotify(HRMSTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_workflow()

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Expense Request")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_stage_emails(self):
		mgr, mgr_user = _make_user_employee("exp-nt-mgr@example.com")
		emp, emp_user = _make_user_employee("exp-nt-emp@example.com", reports_to=mgr)
		hr, hr_user = _make_user_employee("exp-nt-hr@example.com", roles=["Expense HR Approver"])
		acc, acc_user = _make_user_employee("exp-nt-acc@example.com", roles=["Expense Accounts Approver"])

		sent = []
		with patch("frappe.sendmail", side_effect=lambda **kw: sent.append(tuple(kw.get("recipients") or []))):
			frappe.set_user(emp_user)
			doc = frappe.get_doc(
				{
					"doctype": "Expense Request",
					"employee": emp,
					"expense_type": "AI Tool",
					"amount": 1000,
					"reason": "t",
					"receipt": "/files/r.pdf",
				}
			).insert()
			n = len(sent)
			apply_workflow(doc, "Submit for Approval")
			self.assertIn((mgr_user,), sent[n:])

			frappe.set_user(mgr_user)
			n = len(sent)
			apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")
			self.assertIn(("hr@clustox.com",), sent[n:])

			frappe.set_user(hr_user)
			n = len(sent)
			apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")
			self.assertIn(("accounts@clustox.com",), sent[n:])

			frappe.set_user(acc_user)
			paid = frappe.get_doc("Expense Request", doc.name)
			paid.payment_date = nowdate()
			paid.payment_mode = "Bank Transfer"
			paid.save()
			n = len(sent)
			apply_workflow(frappe.get_doc("Expense Request", doc.name), "Complete")
			self.assertIn((emp_user,), sent[n:])
