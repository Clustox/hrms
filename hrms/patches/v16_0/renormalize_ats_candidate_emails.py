"""ATS: candidate emails now match exactly (case and spaces ignored only), so recompute the
normalised email of every Candidate. A stricter rule can only separate addresses, never merge
them, so this cannot create a clash. Idempotent."""

import frappe

from hrms.ats.candidates import normalize_email


def execute():
	changed = 0
	for name, email, current in frappe.db.sql("select name, email, email_normalized from `tabCandidate`"):
		wanted = normalize_email(email)
		if wanted != current:
			frappe.db.set_value("Candidate", name, "email_normalized", wanted, update_modified=False)
			changed += 1
	frappe.db.commit()
	print(f"ATS candidate emails re-normalised: {changed}")
