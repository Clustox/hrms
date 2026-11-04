# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe

from hrms.request_visibility import expense_request_has_permission, expense_request_query
from hrms.tests.utils import HRMSTestSuite


class TestExpenseRequestVisibility(HRMSTestSuite):
	def _as(self, user):
		frappe.set_user(user)
		self.addCleanup(lambda: frappe.set_user("Administrator"))

	def test_accounts_user_sees_all(self):
		accounts_user = frappe.db.get_value(
			"Has Role", {"role": "Accounts Manager", "parenttype": "User"}, "parent"
		)
		self._as(accounts_user)
		self.assertEqual(expense_request_query(), "")
		doc = frappe._dict(doctype="Expense Request", employee="any-employee")
		self.assertTrue(expense_request_has_permission(doc, "read"))

	def test_plain_employee_scoped_to_self(self):
		emp = frappe.db.get_value("Employee", {"status": "Active"}, ["name", "user_id"], as_dict=True)
		self._as(emp.user_id)
		q = expense_request_query()
		self.assertIn(emp.name, q)
		self.assertTrue(expense_request_has_permission(frappe._dict(doctype="Expense Request", employee=emp.name), "read"))
		stranger = frappe.db.get_value("Employee", {"name": ["!=", emp.name], "status": "Active"}, "name")
		self.assertFalse(expense_request_has_permission(frappe._dict(doctype="Expense Request", employee=stranger), "read"))
		self.assertFalse(expense_request_has_permission(frappe._dict(doctype="Expense Request", employee=stranger), "submit"))
		self.assertTrue(expense_request_has_permission(frappe._dict(doctype="Expense Request", employee=None), "create"))
