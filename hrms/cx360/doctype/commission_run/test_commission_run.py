import frappe
from frappe.tests.utils import FrappeTestCase


class TestCommissionRun(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        self.project = frappe.db.get_value("Project", {"project_name": "CRun Project"}, "name") \
            or frappe.get_doc({"doctype": "Project", "project_name": "CRun Project"}).insert().name
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


class TestMultiRoleStacking(FrappeTestCase):
    def setUp(self):
        emps = frappe.get_all("Employee", filters={"status": "Active"}, limit=3)
        self.wa, self.wb, self.sales = emps[0].name, emps[1].name, emps[2].name
        if not frappe.db.exists("Customer", "Acme Test"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "Acme Test",
                            "customer_type": "Company", "customer_group": "Commercial",
                            "territory": "Rest Of The World"}).insert()
        self.project = frappe.db.get_value("Project", {"project_name": "Acme Test Project"}, "name") \
            or frappe.get_doc({"doctype": "Project", "project_name": "Acme Test Project",
                               "customer": "Acme Test"}).insert().name
        proj = frappe.get_doc("Project", self.project)
        proj.custom_engagement_type = "Sale"
        proj.custom_billing_model = "Time & Material"
        proj.set("custom_team", [{"employee": self.sales, "role": "Sales"}])
        proj.save()
        for emp in (self.wa, self.wb):
            frappe.get_doc({
                "doctype": "Resource Allocation", "employee": emp, "project": self.project,
                "allocation_percent": 50, "start_date": "2026-03-01", "end_date": "2026-03-31",
                "status": "Active",
            }).insert()
            frappe.get_doc({
                "doctype": "Timesheet", "employee": emp,
                "time_logs": [{"activity_type": "Execution", "hours": 80, "is_billable": 1,
                               "billing_hours": 80, "billing_rate": 100,
                               "from_time": "2026-03-10 09:00:00",
                               "to_time": "2026-03-13 17:00:00", "project": self.project}],
            }).insert()
        # Worker rule 5%, with a per-person override of 3% for worker B
        frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "Acme Worker 5%",
            "role": "Working Resource", "base": "Resource revenue", "rate_type": "Percent",
            "rate_value": 5, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
            "project_scope": self.project,
            "overrides": [{"employee": self.wb, "rate_value": 3}],
        }).insert()
        # Sales rule 1% of total project revenue
        frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "Acme Sales 1%",
            "role": "Sales", "base": "Total project revenue", "rate_type": "Percent",
            "rate_value": 1, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
            "project_scope": self.project,
        }).insert()

    def test_three_people_three_amounts(self):
        run = frappe.get_doc({
            "doctype": "Commission Run", "run_type": "Monthly recurring",
            "period_start": "2026-03-01", "period_end": "2026-03-31", "project": self.project,
        })
        run.generate()
        by_emp = {e.employee: e.commission_amount for e in run.entries}
        self.assertEqual(by_emp[self.wa], 400.0)   # 5% of own 8000
        self.assertEqual(by_emp[self.wb], 240.0)   # 3% override of own 8000
        self.assertEqual(by_emp[self.sales], 160.0)  # 1% of total 16000
        self.assertEqual(run.total_commission, 800.0)
