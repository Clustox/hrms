"""ATS: rejected candidates are dropped with a reason, so the default "Rejected ..." stages go."""

import frappe

from hrms.ats.backfill import remove_default_rejected_stages


def execute():
	moved = remove_default_rejected_stages()
	frappe.db.commit()
	print(f"ATS rejected stages removed; {moved} candidate(s) moved to dropped")
