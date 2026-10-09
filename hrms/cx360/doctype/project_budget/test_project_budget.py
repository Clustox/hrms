import frappe
from frappe.tests.utils import FrappeTestCase
from hrms.cx360 import commission_engine as ce

DESIG = "Principal Software Engineer"


def _designation():
    if not frappe.db.exists("Designation", DESIG):
        frappe.get_doc({"doctype": "Designation", "designation_name": DESIG}).insert()
    if not frappe.db.exists("Designation Rate", DESIG):
        frappe.get_doc({"doctype": "Designation Rate", "designation": DESIG,
                        "hourly_rate": 35, "monthly_rate": 5600}).insert()
    return DESIG


def _project(name):
    return frappe.db.get_value("Project", {"project_name": name}, "name") or \
        frappe.get_doc({"doctype": "Project", "project_name": name}).insert().name


def _budget(proj, value=50000):
    return frappe.get_doc({
        "doctype": "Project Budget", "project": proj, "project_value": value,
        "resource_lines": [{"designation": DESIG, "quantity": 2, "basis": "Hourly",
                            "duration": 320}],
        "other_costs": [{"description": "AI tools", "amount": 1000}],
    }).insert()


class TestProjectBudget(FrappeTestCase):
    def test_budget_math(self):
        _designation()
        b = _budget(_project("Budget Test Project"))
        self.assertEqual(b.resource_lines[0].rate, 35)        # fetched from rate card
        self.assertEqual(b.resource_lines[0].line_cost, 22400)  # 2 * 35 * 320
        self.assertEqual(b.budgeted_cost, 23400)                # 22400 + 1000
        self.assertEqual(b.budgeted_profit, 26600)              # 50000 - 23400
