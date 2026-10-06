import frappe
from frappe.tests.utils import FrappeTestCase


def _customer():
    if not frappe.db.exists("Customer", "CX360 Test Client"):
        frappe.get_doc({
            "doctype": "Customer", "customer_name": "CX360 Test Client",
            "customer_type": "Company", "customer_group": "Commercial",
            "territory": "Rest Of The World",
        }).insert()
    return "CX360 Test Client"


class TestSOW(FrappeTestCase):
    def test_deliverable_total_rolls_up(self):
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Deliverable SOW", "customer": _customer(),
            "sow_type": "Sale", "billing_model": "Deliverable", "status": "Active",
            "deliverables": [
                {"title": "Phase 1", "amount": 3000},
                {"title": "Phase 2", "amount": 2000},
            ],
        }).insert()
        self.assertEqual(sow.total_value, 5000)

    def test_team_and_type_persist(self):
        emp = frappe.get_all("Employee", limit=1)[0].name
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Internal SOW", "customer": _customer(),
            "sow_type": "Internal", "billing_model": "Fixed Monthly",
            "monthly_value": 8000, "status": "Active",
            "team": [{"employee": emp, "role": "Delivery Lead"}],
        }).insert()
        self.assertEqual(sow.sow_type, "Internal")
        self.assertEqual(sow.team[0].role, "Delivery Lead")

    def test_project_links_to_sow(self):
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Link SOW", "customer": _customer(),
            "sow_type": "Sale", "billing_model": "Time & Material", "status": "Active",
        }).insert()
        proj = frappe.get_doc({
            "doctype": "Project", "project_name": "CX360 Link Project",
            "custom_sow": sow.name,
        }).insert()
        self.assertEqual(frappe.db.get_value("Project", proj.name, "custom_sow"), sow.name)
