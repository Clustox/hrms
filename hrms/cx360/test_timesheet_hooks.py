import frappe
from frappe.tests.utils import FrappeTestCase
from hrms.cx360.timesheet_hooks import check_hours_cap


class TestTimesheetHoursCap(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        self.project = frappe.db.get_value("Project", {"project_name": "TS Cap Project"}, "name")
        if not self.project:
            self.project = frappe.get_doc(
                {"doctype": "Project", "project_name": "TS Cap Project"}
            ).insert().name
        frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.emp, "project": self.project,
            "allocation_percent": 25, "start_date": "2026-01-01", "end_date": "2026-12-31",
            "status": "Active",
        }).insert()

    def _ts(self, hours):
        return frappe.get_doc({
            "doctype": "Timesheet", "employee": self.emp,
            "time_logs": [{
                "hours": hours, "from_time": "2026-03-02 09:00:00",
                "to_time": "2026-03-02 17:00:00", "project": self.project,
            }],
        })

    def test_over_capacity_warns_not_raises(self):
        # 25% of 160 = 40 hrs cap; log 60 -> warning, no exception
        doc = self._ts(60)
        doc.flags.ignore_mandatory = True
        before = len(frappe.local.message_log or [])
        check_hours_cap(doc)
        self.assertGreater(len(frappe.local.message_log or []), before)

    def test_under_capacity_silent(self):
        doc = self._ts(10)
        doc.flags.ignore_mandatory = True
        frappe.clear_messages()
        check_hours_cap(doc)
        self.assertEqual(len(frappe.local.message_log or []), 0)
