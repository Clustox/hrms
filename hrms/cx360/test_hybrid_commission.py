import frappe
from frappe.tests.utils import FrappeTestCase


class TestHybridCommission(FrappeTestCase):
    """Phase 2: commission sourced from stock ERPNext — team from Project.custom_team,
    profit/cost from USD timesheet amounts (not the custom Project Budget)."""

    def setUp(self):
        emps = frappe.get_all("Employee", filters={"status": "Active"}, limit=2)
        self.worker, self.lead = emps[0].name, emps[1].name
        self.project = frappe.db.get_value("Project", {"project_name": "Hybrid Comm Project"}, "name") \
            or frappe.get_doc({"doctype": "Project", "project_name": "Hybrid Comm Project"}).insert().name
        proj = frappe.get_doc("Project", self.project)
        proj.custom_engagement_type = "Sale"
        proj.custom_billing_model = "Time & Material"
        proj.set("custom_team", [{"employee": self.lead, "role": "Delivery Lead"}])
        proj.save()
        frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.worker, "project": self.project,
            "allocation_percent": 50, "start_date": "2026-03-01", "end_date": "2026-03-31",
            "status": "Active",
        }).insert()
        # 80h billable @ $100 = $8,000 revenue; costing @ $40 = $3,200 cost -> $4,800 profit
        frappe.get_doc({
            "doctype": "Timesheet", "employee": self.worker,
            "time_logs": [{"activity_type": "Execution", "hours": 80, "is_billable": 1,
                           "billing_hours": 80, "billing_rate": 100, "costing_rate": 40,
                           "from_time": "2026-03-10 09:00:00", "to_time": "2026-03-13 17:00:00",
                           "project": self.project}],
        }).insert()
        frappe.get_doc({"doctype": "Commission Rule", "rule_name": "H Worker rev 5%",
                        "role": "Working Resource", "base": "Resource revenue", "rate_type": "Percent",
                        "rate_value": 5, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
                        "project_scope": self.project}).insert()
        frappe.get_doc({"doctype": "Commission Rule", "rule_name": "H Lead profit 10%",
                        "role": "Delivery Lead", "base": "Project profit", "rate_type": "Percent",
                        "rate_value": 10, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
                        "project_scope": self.project}).insert()

    def test_native_sourced_run(self):
        run = frappe.get_doc({
            "doctype": "Commission Run", "run_type": "Monthly recurring",
            "period_start": "2026-03-01", "period_end": "2026-03-31", "project": self.project,
        })
        run.generate()
        by_emp = {e.employee: e.commission_amount for e in run.entries}
        self.assertEqual(by_emp[self.worker], 400.0)   # 5% of own $8,000 revenue
        self.assertEqual(by_emp[self.lead], 480.0)     # 10% of project profit ($8,000-$3,200)
