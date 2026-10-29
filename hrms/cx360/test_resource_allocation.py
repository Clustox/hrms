import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt


class TestResourceAllocationParity(FrappeTestCase):
    """Phase 0 — Resource Allocation carries the Project 360 project_allocations fields
    (resource_role, cost_category, billable, bench/training reasons, release & joining dates),
    references the project's billing model, and supports open-ended allocations."""

    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        self.project = frappe.db.get_value("Project", {"project_name": "RA Parity Test"}, "name")
        if not self.project:
            self.project = frappe.get_doc({
                "doctype": "Project", "project_name": "RA Parity Test",
                "custom_billing_model": "Fixed Monthly",
            }).insert().name
        else:
            frappe.db.set_value("Project", self.project, "custom_billing_model", "Fixed Monthly")
        # This bench's FrappeTestCase does not roll back per-test in the console harness,
        # so start each test from a clean slate for this project's allocations.
        frappe.db.delete("Resource Allocation", {"project": self.project})

    def _alloc(self, **kw):
        doc = {
            "doctype": "Resource Allocation", "employee": self.emp, "project": self.project,
            "allocation_percent": 50, "start_date": "2099-01-01", "end_date": "2099-03-31",
            "status": "Active",
        }
        doc.update(kw)
        return frappe.get_doc(doc)

    def test_new_fields_persist(self):
        ra = self._alloc(
            resource_role="Senior Developer", cost_category="Cost of Services",
            billable=1, bench_reason="Skill Upgrade", training_reason="Certification Pursuit",
        ).insert()
        got = frappe.db.get_value(
            "Resource Allocation", ra.name,
            ["resource_role", "cost_category", "billable", "bench_reason",
             "training_reason"], as_dict=True)
        self.assertEqual(got.resource_role, "Senior Developer")
        self.assertEqual(got.cost_category, "Cost of Services")
        self.assertEqual(got.billable, 1)
        self.assertEqual(got.bench_reason, "Skill Upgrade")
        self.assertEqual(got.training_reason, "Certification Pursuit")

    def test_billing_model_fetched_from_project(self):
        ra = self._alloc().insert()
        self.assertEqual(ra.billing_model, "Fixed Monthly")

    def test_open_ended_allocation_saves(self):
        ra = self._alloc(end_date=None, allocation_percent=40).insert()
        self.assertFalse(ra.end_date)
        self.assertAlmostEqual(ra.monthly_capacity_hours, 64.0)  # 40% * 160

    def test_capacity_block_counts_open_allocation(self):
        self._alloc(end_date=None, allocation_percent=70).insert()  # open, from 2099-01-01
        with self.assertRaises(frappe.ValidationError):
            self._alloc(start_date="2099-02-01", end_date="2099-02-28",
                        allocation_percent=40).insert()  # overlaps the open one -> 110%

    def test_capacity_ok_when_no_overlap(self):
        self._alloc(start_date="2099-01-01", end_date="2099-01-31", allocation_percent=80).insert()
        # different month, no overlap -> allowed even though both are 80%
        self._alloc(start_date="2099-06-01", end_date="2099-06-30", allocation_percent=80).insert()

    def test_end_before_start_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self._alloc(start_date="2099-03-01", end_date="2099-01-01").insert()


class TestResourceAllocationRates(FrappeTestCase):
    """Allocation rates auto-fill: cost from the employee's Rate Card, billing from the
    project's Sales Order, only when left blank."""

    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        frappe.db.delete("Employee Rate Card", {"employee": self.emp})
        frappe.get_doc({"doctype": "Employee Rate Card", "employee": self.emp,
                        "effective_from": "2099-01-01", "monthly_cost": 3200}).insert()  # hourly 20
        self.project = frappe.db.get_value("Project", {"project_name": "RA Rate Test"}, "name")
        if not self.project:
            self.project = frappe.get_doc(
                {"doctype": "Project", "project_name": "RA Rate Test"}).insert().name
        frappe.db.set_value("Project", self.project, "custom_sales_order", None)
        frappe.db.delete("Resource Allocation", {"project": self.project})

    def _ra(self, **kw):
        doc = {
            "doctype": "Resource Allocation", "employee": self.emp, "project": self.project,
            "allocation_percent": 50, "start_date": "2099-01-01", "end_date": "2099-03-31",
            "status": "Active",
        }
        doc.update(kw)
        return frappe.get_doc(doc)

    def test_cost_rate_from_rate_card(self):
        ra = self._ra().insert()
        self.assertEqual(flt(ra.project_cost_rate), 20.0)  # 3200 / 160

    def test_no_billing_without_sales_order(self):
        ra = self._ra().insert()  # project has no Sales Order
        self.assertEqual(flt(ra.project_billing_rate), 0.0)

    def test_billing_rate_from_sales_order(self):
        so = frappe.get_all("Sales Order", limit=1)
        if not so:
            self.skipTest("no Sales Order on this bench")
        item = frappe.get_all("Sales Order Item", filters={"parent": so[0].name},
                              fields=["rate"], order_by="idx", limit=1)
        if not item:
            self.skipTest("Sales Order has no items")
        frappe.db.set_value("Project", self.project, "custom_sales_order", so[0].name)
        ra = self._ra().insert()
        self.assertEqual(flt(ra.project_billing_rate), flt(item[0].rate))

    def test_manual_rate_not_overwritten(self):
        ra = self._ra(project_cost_rate=7, project_billing_rate=9).insert()
        self.assertEqual(flt(ra.project_cost_rate), 7.0)
        self.assertEqual(flt(ra.project_billing_rate), 9.0)

    def test_get_suggested_rates_endpoint(self):
        # the whitelisted method the form calls for live prefill
        from hrms.cx360.doctype.resource_allocation.resource_allocation import get_suggested_rates
        res = get_suggested_rates(self.emp, self.project, "2099-01-01")
        self.assertEqual(flt(res["cost_rate"]), 20.0)  # rate card hourly
        self.assertEqual(flt(res["billing_rate"]), 0.0)  # no SO
