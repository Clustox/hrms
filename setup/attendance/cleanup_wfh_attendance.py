"""Cancel "Work From Home" attendance that was pre-created at WFH approval for
days the employee never checked in.

Approving a WFH request used to create attendance for every day in range, so an
approved-but-unworked day showed Present. WFH attendance is now created at the
employee's first check-in instead; this one-off clears the old pre-created
records (only ones from a Work From Home request that have NO Employee Checkin
that day). Days with a check-in are left alone.

Run (copy to hrms/hrms/ first, like backfill_august; dry-run by default):
  bench --site <site> execute hrms.cleanup_wfh_attendance.run
Apply:
  bench --site <site> execute hrms.cleanup_wfh_attendance.run --kwargs "{'apply': 1}"
Optional kwarg: from_date='2026-11-01'.
Idempotent: a second run finds nothing.
"""

import frappe


def run(apply=0, from_date=None):
	filters = {"status": "Work From Home", "docstatus": 1, "attendance_request": ["is", "set"]}
	if from_date:
		filters["attendance_date"] = [">=", from_date]
	rows = frappe.get_all(
		"Attendance", filters=filters, fields=["name", "employee", "attendance_date", "attendance_request"],
		order_by="employee asc, attendance_date asc",
	)
	stale = []
	for r in rows:
		if frappe.db.get_value("Attendance Request", r.attendance_request, "reason") != "Work From Home":
			continue
		d = r.attendance_date
		if not frappe.db.exists(
			"Employee Checkin",
			{"employee": r.employee, "time": ["between", [f"{d} 00:00:00", f"{d} 23:59:59"]]},
		):
			stale.append(r)

	print(f"{len(rows)} WFH attendance records; {len(stale)} have no check-in")
	for r in stale[:30]:
		print(f"  {r.name}  {r.employee}  {r.attendance_date}  ({r.attendance_request})")
	if not apply:
		print("dry-run: nothing changed (pass --kwargs \"{'apply': 1}\" to apply)")
		return
	for r in stale:
		doc = frappe.get_doc("Attendance", r.name)
		doc.flags.ignore_permissions = True
		doc.cancel()
	frappe.db.commit()
	print(f"cancelled {len(stale)}")
