import frappe
from frappe.tests.utils import FrappeTestCase
from hrms.leave_rules import validate_leave_application


class TestHalfDayRule(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        # make the applicant == session user so leave_rules._bypass returns False
        # (override roles only bypass when acting on ANOTHER employee's behalf)
        frappe.db.set_value("Employee", self.emp, "user_id", frappe.session.user)

    def _app(self, leave_type):
        return frappe.get_doc({
            "doctype": "Leave Application", "employee": self.emp, "leave_type": leave_type,
            "from_date": "2026-11-10", "to_date": "2026-11-10", "half_day": 1,
            "total_leave_days": 0.5,
        })

    def test_half_day_blocked_for_non_casual(self):
        with self.assertRaises(frappe.ValidationError) as cm:
            validate_leave_application(self._app("Annual Leave"))
        self.assertIn("Half-day", str(cm.exception))

    def test_half_day_allowed_for_casual(self):
        # Casual half-day must not raise the half-day error (other rules may still apply)
        try:
            validate_leave_application(self._app("Casual Leave"))
        except frappe.ValidationError as ex:
            self.assertNotIn("Half-day", str(ex))
