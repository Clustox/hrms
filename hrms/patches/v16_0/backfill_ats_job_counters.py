"""ATS: fill the Hired / In pipeline / Dropped counters and the headcount of every job."""

import frappe

from hrms.ats.counters import refresh_all_counters


def execute():
	from hrms.ats.setup import apply_custom_fields

	apply_custom_fields(commit=False)  # the counter fields must exist before they are filled
	count = refresh_all_counters()
	frappe.db.commit()
	print(f"ATS job counters refreshed for {count} job(s)")
