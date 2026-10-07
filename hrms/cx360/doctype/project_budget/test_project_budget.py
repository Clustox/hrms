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

    def test_engine_reads_budget(self):
        _designation()
        proj = _project("Budget Engine Project")
        _budget(proj)
        self.assertEqual(ce.project_budget_values(proj),
                         {"value": 50000.0, "cost": 23400.0, "profit": 26600.0})

    def test_commission_on_profit(self):
        _designation()
        proj = _project("Budget Comm Project")
        if not frappe.db.exists("Customer", "Budget Client"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "Budget Client",
                            "customer_type": "Company", "customer_group": "Commercial",
                            "territory": "Rest Of The World"}).insert()
        emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        sow = frappe.get_doc({"doctype": "SOW", "title": "Budget SOW", "customer": "Budget Client",
                              "sow_type": "Sale", "billing_model": "Deliverable", "status": "Active",
                              "team": [{"employee": emp, "role": "Delivery Lead"}]}).insert()
        frappe.db.set_value("Project", proj, "custom_sow", sow.name)
        _budget(proj)
        frappe.get_doc({"doctype": "Commission Rule", "rule_name": "Lead 10% profit",
                        "role": "Delivery Lead", "base": "Project profit", "rate_type": "Percent",
                        "rate_value": 10, "trigger": "On project completion",
                        "effective_from": "2026-01-01", "project_scope": proj}).insert()
        run = frappe.get_doc({"doctype": "Commission Run", "run_type": "On project completion",
                              "project": proj})
        run.generate()
        mine = [e for e in run.entries if e.employee == emp]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].commission_amount, 2660.0)  # 10% of 26600 profit
