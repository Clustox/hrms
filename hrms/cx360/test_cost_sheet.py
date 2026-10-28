import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from hrms.cx360.cost_sheet import (
    employee_daily_cost,
    employee_monthly_cost,
    working_days_in_month,
)


class TestEmployeeRateCard(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        frappe.db.delete("Employee Rate Card", {"employee": self.emp})

    def _card(self, **kw):
        doc = {"doctype": "Employee Rate Card", "employee": self.emp,
               "effective_from": "2099-01-01", "monthly_cost": 3200}
        doc.update(kw)
        return frappe.get_doc(doc)

    def test_hourly_cost_derived(self):
        card = self._card(monthly_cost=3200).insert()
        self.assertEqual(flt(card.hourly_cost), 20.0)  # 3200 / 160

    def test_duplicate_effective_from_blocked(self):
        self._card(effective_from="2099-01-01").insert()
        with self.assertRaises(frappe.ValidationError):
            self._card(effective_from="2099-01-01", monthly_cost=5000).insert()


class TestCostHelpers(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        frappe.db.delete("Employee Rate Card", {"employee": self.emp})

    def test_monthly_cost_picks_latest_effective(self):
        frappe.get_doc({"doctype": "Employee Rate Card", "employee": self.emp,
                        "effective_from": "2099-01-01", "monthly_cost": 3000}).insert()
        frappe.get_doc({"doctype": "Employee Rate Card", "employee": self.emp,
                        "effective_from": "2099-06-01", "monthly_cost": 4000}).insert()
        self.assertEqual(employee_monthly_cost(self.emp, "2099-03-15"), 3000.0)
        self.assertEqual(employee_monthly_cost(self.emp, "2099-07-15"), 4000.0)
        self.assertEqual(employee_monthly_cost(self.emp, "2098-12-31"), 0.0)  # before any card

    def test_daily_cost_times_working_days_equals_monthly(self):
        frappe.get_doc({"doctype": "Employee Rate Card", "employee": self.emp,
                        "effective_from": "2099-01-01", "monthly_cost": 3000}).insert()
        wd = working_days_in_month("2099-01-15")
        self.assertAlmostEqual(employee_daily_cost(self.emp, "2099-01-15") * wd, 3000.0, places=2)

    def test_working_days_sane_range(self):
        self.assertTrue(19 <= working_days_in_month("2026-10-15") <= 23)
        # Feb 2026: 28 days, 1 Feb 2026 is a Sunday -> 20 weekdays
        self.assertEqual(working_days_in_month("2026-02-10"), 20)


class TestCostSheetReport(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        frappe.db.delete("Employee Rate Card", {"employee": self.emp})
        frappe.get_doc({"doctype": "Employee Rate Card", "employee": self.emp,
                        "effective_from": "2099-01-01", "monthly_cost": 3000}).insert()
        # clear any 2099 test allocations for this employee (keeps capacity checks clean)
        frappe.db.delete("Resource Allocation", {"employee": self.emp, "start_date": [">=", "2099-01-01"]})
        self.cos = self._project("CostSheet CoS", "Sale")
        self.internal = self._project("CostSheet Internal", "Internal")

    def _project(self, name, engagement):
        p = frappe.db.get_value("Project", {"project_name": name}, "name")
        if not p:
            p = frappe.get_doc({"doctype": "Project", "project_name": name}).insert().name
        frappe.db.set_value("Project", p, "custom_engagement_type", engagement)
        return p

    def _alloc(self, project, cost_category, percent=50):
        return frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.emp, "project": project,
            "allocation_percent": percent, "start_date": "2099-01-01", "end_date": "2099-01-31",
            "status": "Active", "cost_category": cost_category}).insert()

    def test_monthly_rollup_cost(self):
        self._alloc(self.cos, "Cost of Services", 50)
        from hrms.cx360.report.cost_sheet.cost_sheet import execute
        _, data = execute({"from_date": "2099-01-01", "to_date": "2099-01-31",
                           "period": "Monthly", "employee": self.emp, "project": self.cos})
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["period"], "2099-01")
        self.assertEqual(flt(data[0]["cost"]), 1500.0)  # 3000 monthly * 50%
        self.assertEqual(data[0]["utilization"], "Billable")

    def test_bench_utilized_vs_idle(self):
        self._alloc(self.internal, "Bench Cost", 50)  # bench on Internal project
        self._alloc(self.cos, "Bench Cost", 50)       # bench on Sale project
        from hrms.cx360.report.cost_sheet.cost_sheet import execute
        _, data = execute({"from_date": "2099-01-01", "to_date": "2099-01-31",
                           "period": "Monthly", "employee": self.emp})
        by_proj = {r["project"]: r["utilization"] for r in data}
        self.assertEqual(by_proj.get(self.internal), "Bench - Utilized")
        self.assertEqual(by_proj.get(self.cos), "Bench - Idle")

    def test_daily_period_has_row_per_working_day(self):
        self._alloc(self.cos, "Cost of Services", 50)
        from hrms.cx360.report.cost_sheet.cost_sheet import execute
        _, data = execute({"from_date": "2099-01-01", "to_date": "2099-01-07",
                           "period": "Daily", "employee": self.emp, "project": self.cos})
        # Jan 1-7 2099: count working days in that span
        from hrms.cx360.cost_sheet import is_working_day
        from frappe.utils import getdate, add_days
        expected = sum(1 for i in range(7) if is_working_day(add_days(getdate("2099-01-01"), i)))
        self.assertEqual(len(data), expected)
