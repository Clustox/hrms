from hrms.overnight_attendance import relink_and_reconcile

# Open month only (Nov 2026 onward); closed months are never touched.
CUTOFF = "2026-11-01"


def execute():
	"""Re-link November's post-midnight punches to their overnight shift and
	recompute the Attendance that was computed without them. See
	hrms.overnight_attendance. Idempotent; does not commit."""
	import frappe

	frappe.flags.mute_emails = True
	relink_and_reconcile(CUTOFF)
