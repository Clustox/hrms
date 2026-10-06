import frappe
from frappe.tests.utils import FrappeTestCase


class TestCommissionRule(FrappeTestCase):
    def test_rule_inserts_with_defaults(self):
        r = frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "Resource monthly T&M",
            "role": "Working Resource", "base": "Resource revenue",
            "rate_type": "Percent", "rate_value": 10, "trigger": "Monthly recurring",
            "effective_from": "2026-01-01",
        }).insert()
        self.assertEqual(r.active, 1)
        self.assertEqual(r.sow_type_scope, "Any")

    def test_bad_date_range_blocked(self):
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Commission Rule", "rule_name": "Bad dates",
                "role": "Sales", "base": "Project revenue", "rate_type": "Percent",
                "rate_value": 1, "trigger": "Monthly recurring",
                "effective_from": "2026-06-01", "effective_to": "2026-01-01",
            }).insert()
