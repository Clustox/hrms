"""ATS: read the resumes of existing candidates so they can be searched by their words."""

import frappe

from hrms.ats.resume import extract_missing_resume_text


def execute():
	count = extract_missing_resume_text()
	frappe.db.commit()
	print(f"ATS resume text extracted for {count} candidate(s)")
