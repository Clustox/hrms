"""ATS: add the Hired and On Hold stages to pipelines still on the first 13-stage default."""

import frappe

from hrms.ats.backfill import upgrade_default_pipeline


def execute():
	count = upgrade_default_pipeline()
	frappe.db.commit()
	print(f"ATS default pipeline upgraded on {count} pipeline(s)")
