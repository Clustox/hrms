import frappe
from frappe.tests.utils import FrappeTestCase


class TestCommissionRun(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        if not frappe.db.exists("Customer", "CRun Client"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "CRun Client",
                            "customer_type": "Company", "customer_group": "Commercial",
                            "territory": "Rest Of The World"}).insert()
        self.sow = frappe.get_doc({
            "doctype": "SOW", "title": "CRun SOW", "customer": "CRun Client",
            "sow_type": "Sale", "billing_model": "Time & Material", "status": "Active",
        }).insert()
        self.project = frappe.db.get_value("Project", {"project_name": "CRun Project"}, "name")
        if not self.project:
            self.project = frappe.get_doc({
                "doctype": "Project", "project_name": "CRun Project",
                "custom_sow": self.sow.name,
            }).insert().name
        else:
            frappe.db.set_value("Project", self.project, "custom_sow", self.sow.name)
        frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.emp, "project": self.project,
            "allocation_percent": 50, "start_date": "2026-03-01", "end_date": "2026-03-31",
            "status": "Active",
        }).insert()
        # 1000 of billable revenue in March
        frappe.get_doc({
            "doctype": "Timesheet", "employee": self.emp,
            "time_logs": [{"activity_type": "Execution", "hours": 10, "is_billable": 1,
                           "billing_hours": 10, "billing_rate": 100,
                           "from_time": "2026-03-10 09:00:00",
                           "to_time": "2026-03-10 19:00:00", "project": self.project}],
        }).insert()
        frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "CRun Resource 10pct",
            "role": "Working Resource", "base": "Resource revenue", "rate_type": "Percent",
            "rate_value": 10, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
        }).insert()

    def test_generate_produces_entry(self):
        run = frappe.get_doc({
            "doctype": "Commission Run", "run_type": "Monthly recurring",
            "period_start": "2026-03-01", "period_end": "2026-03-31",
        })
        run.generate()
        mine = [e for e in run.entries if e.employee == self.emp]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].commission_amount, 100.0)  # 10% of 1000
