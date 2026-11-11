# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import drop_applicant, restore_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import history, move_stage, new_applicant


class TestDropAndRestore(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Drop Restore").insert()
		self.name = new_applicant(self.job, "drop.restore@example.com").name
		move_stage(self.name, "Technical Assessment")

	def test_drop_keeps_the_stage_and_records_the_reason(self):
		drop_applicant(self.name, "Candidate withdrew")
		doc = frappe.get_doc("Job Applicant", self.name)
		self.assertEqual(doc.is_dropped, 1)
		self.assertEqual(doc.pipeline_stage, "Technical Assessment")
		self.assertEqual(doc.drop_reason, "Candidate withdrew")
		self.assertEqual(doc.dropped_at_stage, "Technical Assessment")

	def test_restore_returns_to_the_same_stage(self):
		drop_applicant(self.name, "No response from candidate")
		restore_applicant(self.name)
		doc = frappe.get_doc("Job Applicant", self.name)
		self.assertEqual((doc.is_dropped, doc.pipeline_stage), (0, "Technical Assessment"))
		self.assertFalse(doc.drop_reason)
		self.assertFalse(doc.dropped_at_stage)

	def test_dropping_needs_a_reason(self):
		with self.assertRaises(frappe.MandatoryError):
			drop_applicant(self.name, "")

	def test_cannot_drop_twice_or_restore_a_live_candidate(self):
		with self.assertRaises(frappe.ValidationError):
			restore_applicant(self.name)
		drop_applicant(self.name, "Position filled")
		with self.assertRaises(frappe.ValidationError):
			drop_applicant(self.name, "Position filled")

	def test_dropping_is_not_a_stage_move(self):
		before = frappe.db.get_value("Job Applicant", self.name, "stage_entered_on")
		moves_before = len(history(self.name))
		drop_applicant(self.name, "Position filled")
		restore_applicant(self.name)
		self.assertEqual(frappe.db.get_value("Job Applicant", self.name, "stage_entered_on"), before)
		self.assertEqual(len(history(self.name)), moves_before)  # the stage history only records moves

	def test_user_without_write_permission_cannot_drop(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "no.perm.drop@example.com", "first_name": "No Perm", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				drop_applicant(self.name, "Position filled")
		finally:
			frappe.set_user("Administrator")
