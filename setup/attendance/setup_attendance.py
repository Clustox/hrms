"""Create the Holiday List + Shift Type for biometric auto-attendance and
assign the shift to every Active employee that has an attendance_device_id.

- Shift "Clustox General": 09:00-18:00, auto-attendance on, backfill from 2026-01-01.
- Holiday List "Clustox 2026": Saturdays + Sundays as weekly off (ADJUST if the
  Clustox work-week differs).
- default_shift is set ONLY on employees with a device id, so employees not
  enrolled on the machine are never auto-marked absent.

Run: bench --site <site> execute hrms.setup_attendance.run
Idempotent: safe to re-run.
"""

import datetime

import frappe

COMPANY = "Clustox"
SHIFT = "Clustox General"
HOLIDAY_LIST = "Clustox 2026"
YEAR = 2026
WEEKLY_OFF_WEEKDAYS = {5, 6}  # 5=Sat, 6=Sun  (ADJUST if needed)
PROCESS_FROM = f"{YEAR}-01-01"


def run():
    log = {"created": [], "shift_assigned": [], "skipped": [], "warnings": []}

    # --- Holiday List: weekends across the whole year ---
    if not frappe.db.exists("Holiday List", HOLIDAY_LIST):
        hl = frappe.new_doc("Holiday List")
        hl.holiday_list_name = HOLIDAY_LIST
        hl.from_date = f"{YEAR}-01-01"
        hl.to_date = f"{YEAR}-12-31"
        d = datetime.date(YEAR, 1, 1)
        end = datetime.date(YEAR, 12, 31)
        while d <= end:
            if d.weekday() in WEEKLY_OFF_WEEKDAYS:
                hl.append("holidays", {
                    "holiday_date": d.isoformat(),
                    "description": "Weekend",
                    "weekly_off": 1,
                })
            d += datetime.timedelta(days=1)
        hl.insert(ignore_permissions=True)
        log["created"].append(f"Holiday List: {HOLIDAY_LIST} ({len(hl.holidays)} weekend days)")

    # --- Shift Type with auto-attendance ---
    if not frappe.db.exists("Shift Type", SHIFT):
        st = frappe.new_doc("Shift Type")
        st.name = SHIFT
        st.update({
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "holiday_list": HOLIDAY_LIST,
            "enable_auto_attendance": 1,
            # biometric punches don't reliably tag IN/OUT -> alternate them
            "determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
            "working_hours_calculation_based_on": "First Check-in and Last Check-out",
            "begin_check_in_before_shift_start_time": 60,
            "allow_check_out_after_shift_end_time": 60,
            "working_hours_threshold_for_half_day": 4,
            "working_hours_threshold_for_absent": 1,
            "late_entry_grace_period": 15,
            "early_exit_grace_period": 15,
            "mark_auto_attendance_on_holiday": 0,
            "process_attendance_after": PROCESS_FROM,
        })
        st.insert(ignore_permissions=True)
        log["created"].append(f"Shift Type: {SHIFT} (09:00-18:00, process from {PROCESS_FROM})")

    # --- assign shift to employees that have a device id ---
    emps = frappe.db.sql(
        """SELECT name, employee_number, default_shift, attendance_device_id
           FROM `tabEmployee`
           WHERE status='Active' AND attendance_device_id IS NOT NULL
             AND attendance_device_id != ''
           ORDER BY employee_number""",
        as_dict=True,
    )
    for e in emps:
        if e.default_shift == SHIFT:
            log["skipped"].append(f"{e.employee_number} already on {SHIFT}")
            continue
        frappe.db.set_value("Employee", e.name, "default_shift", SHIFT)
        log["shift_assigned"].append(f"{e.employee_number} (device {e.attendance_device_id})")

    frappe.db.commit()

    print("\n========== ATTENDANCE SETUP SUMMARY ==========")
    for k in ("created", "shift_assigned", "skipped", "warnings"):
        print(f"\n{k.upper()} ({len(log[k])}):")
        for i in log[k][:10]:
            print("  ", i)
        if len(log[k]) > 10:
            print(f"   ... (+{len(log[k]) - 10} more)")
    print(f"\nShift '{SHIFT}' assigned to {len(log['shift_assigned']) + len([s for s in log['skipped']])} employees total.")
