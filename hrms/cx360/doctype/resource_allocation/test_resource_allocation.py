import frappe
from frappe.tests.utils import FrappeTestCase


def _emp(idx=0):
    rows = frappe.get_all("Employee", filters={"status": "Active"}, limit=5)
    return rows[idx].name


def _project(name):
    existing = frappe.db.get_value("Project", {"project_name": name}, "name")
    if existing:
        return existing
    return frappe.get_doc({"doctype": "Project", "project_name": name}).insert().name


def _alloc(emp, project, pct, start, end, status="Active"):
    return frappe.get_doc({
        "doctype": "Resource Allocation", "employee": emp, "project": project,
        "allocation_percent": pct, "start_date": start, "end_date": end, "status": status,
    })


class TestResourceAllocation(FrappeTestCase):
    def test_capacity_hours_computed(self):
        a = _alloc(_emp(), _project("RA Proj A"), 50, "2026-01-01", "2026-12-31").insert()
        self.assertEqual(a.monthly_capacity_hours, 80)

    def test_overlapping_over_100_blocked(self):
        emp = _emp(1)
        _alloc(emp, _project("RA Proj B"), 60, "2026-01-01", "2026-06-30").insert()
        with self.assertRaises(frappe.ValidationError):
            _alloc(emp, _project("RA Proj C"), 50, "2026-03-01", "2026-09-30").insert()

    def test_non_overlapping_allowed(self):
        emp = _emp(2)
        _alloc(emp, _project("RA Proj D"), 100, "2026-01-01", "2026-03-31").insert()
        a = _alloc(emp, _project("RA Proj E"), 100, "2026-04-01", "2026-06-30").insert()
        self.assertTrue(a.name)
