import frappe
from frappe.tests.utils import FrappeTestCase


class TestHybridProjectFields(FrappeTestCase):
    def test_project_engagement_fields(self):
        emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        proj = frappe.get_doc({
            "doctype": "Project", "project_name": "Hybrid Test Project",
            "custom_engagement_type": "Sale", "custom_billing_model": "Time & Material",
            "custom_team": [{"employee": emp, "role": "Delivery Lead"}],
        }).insert()
        self.assertEqual(
            frappe.db.get_value("Project", proj.name, "custom_engagement_type"), "Sale")
        self.assertEqual(
            frappe.db.get_value("Project", proj.name, "custom_billing_model"), "Time & Material")
        self.assertEqual(proj.custom_team[0].role, "Delivery Lead")
        self.assertEqual(proj.custom_team[0].employee, emp)
