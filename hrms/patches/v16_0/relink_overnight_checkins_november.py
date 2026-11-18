import frappe
from frappe.utils import get_datetime

from hrms.api import SESSION_MAX_HOURS

# Re-link overnight-shift check-ins recorded in the open month (Nov 2026 onward)
# that were treated as a new day's check-in instead of the previous shift's
# check-out. Closed months are untouched.
CUTOFF = "2026-11-01"


def execute():
	"""Walk each employee's November punches in time order, group them into
	sessions (a punch within SESSION_MAX_HOURS of the session's shift start belongs
	to it) and, for post-midnight punches that were left off-shift / on a different
	shift day, copy the session's shift fields and clear a wrongly-linked
	attendance so the reconcile below can recompute it. Idempotent; no commit."""
	logs = frappe.get_all(
		"Employee Checkin",
		filters={"time": [">=", CUTOFF]},
		fields=["name", "employee", "time", "shift", "shift_start", "shift_end", "offshift", "attendance"],
		order_by="employee asc, time asc",
	)
	start = {}
	anchor = {}
	for log in logs:
		emp, when = log.employee, get_datetime(log.time)
		first = start.get(emp)
		if first is None or (when - first).total_seconds() > SESSION_MAX_HOURS * 3600:
			start[emp] = get_datetime(log.shift_start) if log.shift_start else when
			anchor[emp] = log
			continue
		a = anchor[emp]
		if not a.shift or (log.shift == a.shift and log.shift_start == a.shift_start):
			continue
		frappe.db.set_value(
			"Employee Checkin",
			log.name,
			{
				"shift": a.shift,
				"shift_start": a.shift_start,
				"shift_end": a.shift_end,
				"offshift": 0,
			},
			update_modified=False,
		)
