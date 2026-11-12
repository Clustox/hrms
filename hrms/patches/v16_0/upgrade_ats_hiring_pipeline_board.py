"""ATS: move the existing Hiring Pipeline Kanban board from the four fixed statuses to the
pipeline stages (and hide dropped candidates). Idempotent."""

import frappe

from hrms.ats.board import upgrade_hiring_pipeline_board


def execute():
	changed = upgrade_hiring_pipeline_board()
	frappe.db.commit()
	print(f"ATS Hiring Pipeline board upgraded: {changed}")
