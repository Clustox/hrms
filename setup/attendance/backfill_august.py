"""Backfill August 2026 attendance from the biometric punch export.

- Creates Employee Checkin records for every August punch that maps to an
  employee (via attendance_device_id).
- Restricts the shift's auto-attendance window to August only, then runs it,
  producing Attendance with real in/out times and working hours.

Run: bench --site <site> execute hrms.backfill_august.run \
        --kwargs "{'data_file': '/path/to/attendance_2026.json'}"
Idempotent: existing checkins for the same employee+time are skipped.
"""

import json

import frappe

SHIFT = "Clustox General"
MONTH = "2026-08"
DATA_FILE = "/workspace/.employee_import/attendance_2026.json"


def run(data_file=None):
    logs = [r for r in json.load(open(data_file or DATA_FILE)) if r["timestamp"][:7] == MONTH]

    # device_id -> employee
    dev_map = {
        d.attendance_device_id: d.name
        for d in frappe.get_all("Employee",
                                filters={"attendance_device_id": ["!=", ""]},
                                fields=["name", "attendance_device_id"])
    }

    # flexible-hours config FIRST (must happen before any unmarked checkins exist):
    # determine in/out from the log type, compute hours from first-in/last-out,
    # wide window so evening/night punches still map to the shift.
    st = frappe.get_doc("Shift Type", SHIFT)
    st.determine_check_in_and_check_out = "Strictly based on Log Type in Employee Checkin"
    st.working_hours_calculation_based_on = "First Check-in and Last Check-out"
    st.start_time = "12:00:00"
    st.end_time = "21:00:00"
    st.begin_check_in_before_shift_start_time = 360   # from 06:00
    st.allow_check_out_after_shift_end_time = 240      # until 01:00
    st.save(ignore_permissions=True)
    frappe.db.commit()

    # ZK punch codes: 0 = check-in, 1 = check-out (others -> leave unset)
    LOG_TYPE = {0: "IN", 1: "OUT"}

    made = 0
    skipped_no_emp = 0
    punched_emps = set()
    for r in logs:
        emp = dev_map.get(r["device_user_id"])
        if not emp:
            skipped_no_emp += 1
            continue
        punched_emps.add(emp)
        if frappe.db.exists("Employee Checkin", {"employee": emp, "time": r["timestamp"]}):
            continue
        ci = frappe.new_doc("Employee Checkin")
        ci.update({
            "employee": emp,
            "time": r["timestamp"],
            "device_id": r["device_user_id"],
            "log_type": LOG_TYPE.get(r.get("punch")),  # flexible: use device direction
        })
        ci.insert(ignore_permissions=True)
        made += 1
    frappe.db.commit()

    # WFH / non-biometric staff check in via the old system, not this device.
    # Anyone assigned to the shift with ZERO August punches would be falsely
    # marked absent -- unassign them so auto-attendance skips them for now.
    assigned = set(frappe.get_all("Employee",
                   filters={"status": "Active", "default_shift": SHIFT}, pluck="name"))
    zero_punch = sorted(assigned - punched_emps)
    for name in zero_punch:
        frappe.db.set_value("Employee", name, "default_shift", None)
    # clear any prior August records for them (idempotent re-runs)
    if zero_punch:
        frappe.db.delete("Attendance",
                         {"employee": ["in", zero_punch],
                          "attendance_date": ["between", ["2026-08-01", "2026-08-31"]]})
    frappe.db.commit()

    # restrict auto-attendance to August, then process (biometric staff only)
    st.db_set("process_attendance_after", "2026-07-31")
    st.db_set("last_sync_of_checkin", "2026-09-01 00:00:00")
    st.reload()
    st.process_auto_attendance()
    frappe.db.commit()

    by_status = frappe.db.sql(
        """SELECT status, COUNT(*) c FROM `tabAttendance`
           WHERE attendance_date BETWEEN '2026-08-01' AND '2026-08-31'
           GROUP BY status""", as_dict=True)

    print("\n========== AUGUST BACKFILL SUMMARY ==========")
    print(f"August punches in file:        {len(logs)}")
    print(f"Checkins created:              {made}")
    print(f"Punches with no employee map:  {skipped_no_emp}")
    print(f"Employees who punched in Aug:  {len(punched_emps)}")
    print(f"Excluded (WFH / zero punches): {len(zero_punch)}")
    print(f"Attendance by status:          {{{', '.join(f'{r.status}: {r.c}' for r in by_status)}}}")
