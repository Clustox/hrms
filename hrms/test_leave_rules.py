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


POLICY_LEAVE_TYPES = (
    "Annual Leave", "Casual Leave", "Sick Leave", "Marriage Leave", "Hajj Umrah Leave",
    "Maternity Leave", "Paternity Leave", "Compensatory Off", "Bereavement Leave", "Religious Leave",
    "Leave Without Pay",
)


class TestNoAdvanceNotice(FrappeTestCase):
    """No leave type needs advance notice: leave can be applied for any time before its start date, and
    up to 7 days after it. (Marriage Leave used to need 45 days' notice.)"""

    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        # the applicant is the session user, so the HR/Admin bypass does not apply
        frappe.db.set_value("Employee", self.emp, "user_id", frappe.session.user)
        # an ordinary employee: HR / Administrator are exempt from the backdate window
        from unittest.mock import patch

        patcher = patch("frappe.get_roles", return_value=["Employee"])
        patcher.start()
        self.addCleanup(patcher.stop)
        # every type in the policy, whether or not this site has them yet (rolled back after the test)
        for name in POLICY_LEAVE_TYPES:
            if not frappe.db.exists("Leave Type", name):
                frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name}).insert(ignore_permissions=True)

    def _app(self, leave_type, starts_in, days=1):
        from frappe.utils import add_days, today

        start = add_days(today(), starts_in)
        return frappe.get_doc({
            "doctype": "Leave Application", "employee": self.emp, "leave_type": leave_type,
            "from_date": start, "to_date": add_days(start, days - 1), "total_leave_days": days,
        })

    def _notice_error(self, leave_type, starts_in):
        """The notice error, if the policy rules raise it (other rules, such as gender or probation, may
        still apply to the type and are not what is tested here)."""
        from hrms.leave_rules import validate_backdate_limit

        doc = self._app(leave_type, starts_in)
        for check in (validate_leave_application, validate_backdate_limit):
            try:
                check(doc)
            except frappe.ValidationError as ex:
                if "notice" in str(ex).lower() and "resignation" not in str(ex).lower():
                    return str(ex)
        return None

    def test_no_leave_type_needs_notice(self):
        types = frappe.get_all("Leave Type", pluck="name")
        self.assertTrue(types)
        for leave_type in types:
            for starts_in in (0, 1, 3, 10, 44, 45, 60):
                self.assertIsNone(self._notice_error(leave_type, starts_in), f"{leave_type} +{starts_in}d")

    def test_marriage_leave_can_start_tomorrow(self):
        validate_leave_application(self._app("Marriage Leave", 1))

    def test_apply_up_to_7_days_after_the_start_date_for_every_type(self):
        from hrms.leave_rules import validate_backdate_limit

        for leave_type in frappe.get_all("Leave Type", pluck="name"):
            validate_backdate_limit(self._app(leave_type, -7))  # 7 days after the start: allowed
            validate_backdate_limit(self._app(leave_type, -1))
            validate_backdate_limit(self._app(leave_type, 5))  # before the start: allowed

    def test_more_than_7_days_after_the_start_date_is_still_blocked(self):
        from hrms.leave_rules import validate_backdate_limit

        for leave_type in frappe.get_all("Leave Type", pluck="name"):
            with self.assertRaises(frappe.ValidationError, msg=leave_type):
                validate_backdate_limit(self._app(leave_type, -8))
