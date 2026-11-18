# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

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

	def test_beneficiary_field_installed(self):
		meta = frappe.get_meta("Expense Request")
		self.assertTrue(meta.has_field("beneficiary"))
		f = meta.get_field("beneficiary")
		self.assertEqual({x for x in f.options.split("\n") if x}, {"Self", "Spouse", "Children"})
		self.assertEqual(f.default, "Self")

	def test_beneficiary_cleared_for_non_medical_kept_for_medical(self):
		emp = make_employee("exp-ben@example.com", company="_Test Company")
		non_medical = frappe.get_doc(
			{
				"doctype": "Expense Request",
				"employee": emp,
				"expense_type": "AI Tool",
				"amount": 500,
				"reason": "t",
				"beneficiary": "Spouse",
			}
		).insert()
		self.assertEqual(non_medical.beneficiary or "", "")
		medical = frappe.get_doc(
			{
				"doctype": "Expense Request",
				"employee": emp,
				"expense_type": "OPD",
				"amount": 500,
				"reason": "t",
				"beneficiary": "Spouse",
			}
		).insert()
		self.assertEqual(medical.beneficiary, "Spouse")

	# --- Task 2: controller validation ---

	def test_requires_manager_flag_and_manager_resolution(self):
		mgr = make_employee("exp-mgr@example.com", company="_Test Company")
		emp = make_employee("exp-staff@example.com", company="_Test Company", reports_to=mgr)
		mgr_user = frappe.db.get_value("Employee", mgr, "user_id")

		doc = make_expense_request(employee=emp, expense_type="AI Tool")
		self.assertEqual(doc.requires_manager, 1)
		self.assertEqual(doc.manager, mgr_user)

		doc2 = make_expense_request(employee=emp, expense_type="OPD")
		self.assertEqual(doc2.requires_manager, 0)

	def test_amount_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_expense_request, amount=0)

	def test_reimbursement_fields_cleared_before_accounts(self):
		# A paid amount set on a Draft (e.g. by the requester) must not survive.
		doc = make_expense_request(amount=1000, paid_amount=9999, payment_mode="Petty Cash")
		self.assertIsNone(doc.paid_amount)
		self.assertIsNone(doc.payment_mode)

	def test_reject_requires_reason(self):
		doc = make_expense_request()
		doc.workflow_state = "Rejected"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_complete_defaults_paid_amount_and_sets_paid_by(self):
		doc = make_expense_request(amount=5000)
		doc.workflow_state = "Completed"
		doc.payment_date = nowdate()
		doc.payment_mode = "Bank Transfer"
		doc.save()
		self.assertEqual(doc.paid_amount, 5000)
		self.assertEqual(doc.paid_by, frappe.session.user)


def make_expense_request(**kw):
	"""Insert a (by default valid) Draft Expense Request."""
	kw.setdefault("employee", frappe.db.get_value("Employee", {"status": "Active"}, "name"))
	kw.setdefault("expense_type", "AI Tool")
	kw.setdefault("amount", 1000)
	kw.setdefault("reason", "Test expense")
	doc = frappe.get_doc({"doctype": "Expense Request", **kw})
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc
