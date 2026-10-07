import frappe
from frappe.tests.utils import FrappeTestCase
from types import SimpleNamespace
from hrms.cx360 import commission_engine as ce


class TestComputeCommission(FrappeTestCase):
    def test_percent(self):
        rule = SimpleNamespace(rate_type="Percent", rate_value=10,
                               scale_by_allocation=0, min_amount=0, max_amount=0)
        self.assertEqual(ce.compute_commission(1000, rule, 100), 100.0)

    def test_flat_scaled_by_allocation(self):
        rule = SimpleNamespace(rate_type="Flat", rate_value=5000,
                               scale_by_allocation=1, min_amount=0, max_amount=0)
        self.assertEqual(ce.compute_commission(0, rule, 50), 2500.0)

    def test_max_cap(self):
        rule = SimpleNamespace(rate_type="Percent", rate_value=50,
                               scale_by_allocation=0, min_amount=0, max_amount=300)
        self.assertEqual(ce.compute_commission(1000, rule, 100), 300.0)

    def test_per_person_override_rate(self):
        rule = SimpleNamespace(rate_type="Percent", rate_value=5,
                               scale_by_allocation=0, min_amount=0, max_amount=0)
        # default 5% of 8000 = 400; override to 3% -> 240
        self.assertEqual(ce.compute_commission(8000, rule, 50), 400.0)
        self.assertEqual(ce.compute_commission(8000, rule, 50, override_rate=3), 240.0)


class TestScopeMatches(FrappeTestCase):
    def test_any_matches_all(self):
        rule = SimpleNamespace(sow_type_scope="Any", customer_scope=None, project_scope=None)
        self.assertTrue(ce.scope_matches(rule, "Internal", "Fixed Monthly"))

    def test_tm_scope(self):
        rule = SimpleNamespace(sow_type_scope="Sale - Time & Material",
                               customer_scope=None, project_scope=None)
        self.assertTrue(ce.scope_matches(rule, "Sale", "Time & Material"))
        self.assertFalse(ce.scope_matches(rule, "Sale", "Deliverable"))
