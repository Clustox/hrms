"""ATS: give existing jobs a pipeline, place existing applicants in a stage and link them to
Candidates. Idempotent (see hrms.ats.backfill)."""

import frappe

from hrms.ats.backfill import backfill_pipeline


def execute():
	result = backfill_pipeline()
	frappe.db.commit()
	print(f"ATS backfill: {result}")
