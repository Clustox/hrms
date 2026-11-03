"""Re-type already-synced biometric punches: first punch of the day = IN, every
later punch = OUT (so a day's check-out is its last punch).

The machine sync used to alternate IN/OUT, so a day with 3+ punches ended with a
stray IN and the check-out stuck on the 2nd punch. The sync now types punches the
new way, but it only sends NEW punches, so history already in Frappe needs this
one-off correction.

Run (copy to hrms/hrms/ first, like backfill_august; dry-run by default):
  bench --site <site> execute hrms.retype_device_checkins.run
Apply:
  bench --site <site> execute hrms.retype_device_checkins.run --kwargs "{'apply': 1}"
Optional kwargs: device_ids=['uface800'] (the sync's device_label values),
from_date='2026-08-01'.
Idempotent: a second run changes nothing.
"""

from collections import defaultdict

import frappe


def run(apply=0, device_ids=None, from_date=None):
	filters = {"device_id": ["in", device_ids or ["uface800"]]}
	if from_date:
		filters["time"] = [">=", from_date]
	rows = frappe.get_all(
		"Employee Checkin", filters=filters, fields=["name", "employee", "time", "log_type"],
		order_by="employee asc, time asc",
	)
	days = defaultdict(list)
	for r in rows:
		days[(r.employee, r.time.date())].append(r)

	changes = []
	for punches in days.values():
		for i, r in enumerate(punches):
			want = "IN" if i == 0 else "OUT"
			if r.log_type != want:
				changes.append((r, want))

	print(f"{len(rows)} device punches over {len(days)} days; {len(changes)} to re-type")
	for r, want in changes[:20]:
		print(f"  {r.employee} {r.time}  {r.log_type} -> {want}")
	if not apply:
		print("dry-run: nothing changed (pass --kwargs \"{'apply': 1}\" to apply)")
		return
	for r, want in changes:
		frappe.db.set_value("Employee Checkin", r.name, "log_type", want, update_modified=False)
	frappe.db.commit()
	print("applied")
