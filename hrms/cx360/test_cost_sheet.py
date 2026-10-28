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
