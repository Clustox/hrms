# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import nowdate

from hrms.expense_request_notify import _article
from hrms.hr.doctype.expense_request.test_expense_request_workflow import (
	_make_user_employee,
	attach_receipt,
)
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

	def test_article_helper(self):
		# Each of the six current expense types resolves to the right article.
		self.assertEqual(_article("AI Tool"), "An")
		self.assertEqual(_article("Certifications"), "A")
		self.assertEqual(_article("Food"), "A")
		self.assertEqual(_article("OPD"), "An")
		self.assertEqual(_article("IPD"), "An")
		self.assertEqual(_article("Long Service Reward"), "A")
		# Empty / None must not crash and defaults to "A".
		self.assertEqual(_article(""), "A")
		self.assertEqual(_article(None), "A")
		# Lowercased form when requested.
		self.assertEqual(_article("OPD", capitalized=False), "an")

	def test_email_body_article_grammar(self):
		mgr, mgr_user = _make_user_employee("exp-art-mgr@example.com")
		emp, emp_user = _make_user_employee("exp-art-emp@example.com", reports_to=mgr)

		bodies = []
		with patch(
			"frappe.sendmail",
			side_effect=lambda **kw: bodies.append(kw.get("message") or ""),
		):
			frappe.set_user(emp_user)
			doc = frappe.get_doc(
				{
					"doctype": "Expense Request",
					"employee": emp,
					"expense_type": "AI Tool",
					"amount": 1000,
					"reason": "t",
				}
			).insert()
			attach_receipt(doc)
			apply_workflow(doc, "Submit for Approval")
			frappe.set_user(mgr_user)
			apply_workflow(frappe.get_doc("Expense Request", doc.name), "Approve")

		hr_bodies = [b for b in bodies if "<b>AI Tool</b>" in b]
		self.assertTrue(hr_bodies, "expected an email mentioning the AI Tool expense type")
		for b in hr_bodies:
			self.assertIn("An <b>AI Tool</b>", b)
			self.assertNotIn("A <b>AI Tool</b>", b)

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
				}
			).insert()
			attach_receipt(doc)
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
