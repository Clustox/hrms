# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.setup import DEFAULT_DROP_REASONS, seed_drop_reasons


class TestDropReason(IntegrationTestCase):
	def test_defaults_are_seeded(self):
		for reason in DEFAULT_DROP_REASONS:
			self.assertTrue(frappe.db.exists("Drop Reason", reason), reason)

	def test_seeding_twice_changes_nothing(self):
		before = frappe.db.count("Drop Reason")
		seed_drop_reasons()
		self.assertEqual(frappe.db.count("Drop Reason"), before)

	def test_reason_is_unique(self):
		doc = frappe.get_doc({"doctype": "Drop Reason", "reason": DEFAULT_DROP_REASONS[0]})
		self.assertRaises(frappe.DuplicateEntryError, doc.insert)
