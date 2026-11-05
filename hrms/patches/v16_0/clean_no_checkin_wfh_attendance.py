import frappe
from frappe.utils import getdate

# Clean up the fabricated, zero-work WFH/On Duty attendance created before the
# "require a check-in" rule shipped. October 2026 payroll is closed, so only the
# current open month (Nov 2026 onward) is touched.
CUTOFF = "2026-11-01"


def _has_checkin(employee: str, day) -> bool:
	day = getdate(day)
	return bool(
		frappe.db.exists(
			"Employee Checkin",
			{
				"employee": employee,
				"time": ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]],
			},
		)
	)


def execute():
	"""Cancel request-based (WFH/On Duty) attendance from the current open month
	for which the employee has no check-in that day. Idempotent; leaves
	check-in-backed days and closed months untouched. Does not commit -- the
	patch runner (or the console deploy step) owns the transaction."""
	frappe.flags.mute_emails = True

	rows = frappe.get_all(
		"Attendance",
		filters={
			"docstatus": 1,
			"attendance_request": ["is", "set"],
			"status": ["in", ["Work From Home", "Present", "Half Day"]],
			"attendance_date": [">=", CUTOFF],
		},
		fields=["name", "employee", "attendance_date"],
	)

	cancelled = 0
	for r in rows:
		if _has_checkin(r.employee, r.attendance_date):
			continue
		doc = frappe.get_doc("Attendance", r.name)
		doc.flags.ignore_permissions = True
		doc.cancel()
		cancelled += 1

	frappe.logger().info(
		f"clean_no_checkin_wfh_attendance: cancelled {cancelled} of {len(rows)} "
		f"request-based attendance rows dated >= {CUTOFF}"
	)
