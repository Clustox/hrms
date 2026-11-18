import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

from hrms.attendance_cap import cap_long_session


class TestAttendanceCap(FrappeTestCase):
    def test_caps_session_over_18h(self):
        # 20h span (forgotten check-out) -> capped to 18h, out_time pulled back
        doc = frappe._dict(
            in_time=get_datetime("2026-11-10 12:00:00"),
            out_time=get_datetime("2026-11-11 08:00:00"),
            working_hours=20,
        )
        cap_long_session(doc)
        self.assertEqual(doc.working_hours, 18)
        self.assertEqual(get_datetime(doc.out_time), get_datetime("2026-11-11 06:00:00"))

    def test_leaves_normal_long_day(self):
        # 14h late night (noon -> 2 AM) is real, must be untouched
        doc = frappe._dict(
            in_time=get_datetime("2026-11-10 12:00:00"),
            out_time=get_datetime("2026-11-11 02:00:00"),
            working_hours=14,
        )
        cap_long_session(doc)
        self.assertEqual(doc.working_hours, 14)
        self.assertEqual(get_datetime(doc.out_time), get_datetime("2026-11-11 02:00:00"))

    def test_ignores_single_punch(self):
        # no out_time (missing check-out) -> nothing to cap
        doc = frappe._dict(in_time=get_datetime("2026-11-10 12:00:00"), out_time=None, working_hours=0)
        cap_long_session(doc)
        self.assertEqual(doc.working_hours, 0)
