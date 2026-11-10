"""The Hiring Pipeline Kanban board: the existing Frappe board on Job Applicant, extended.

Before the ATS it was a global board on the status field with four fixed columns. It is now a
board on the pipeline stage, with one column per stage of the default pipeline template, and a
saved filter that hides dropped candidates. It is still one board for every job: filter it to a
job (the "Pipeline Board" button on the job does this).
"""

import json

import frappe

BOARD_NAME = "Hiring Pipeline"
STAGE_FIELD = "pipeline_stage"
CARD_FIELDS = ["designation", "applicant_rating"]
HIDE_DROPPED_FILTER = [["Job Applicant", "is_dropped", "=", 0]]


def default_columns() -> list[str]:
	"""Column names: the stages of the default pipeline template, in order."""
	from hrms.ats.pipeline import DEFAULT_TEMPLATE_NAME, default_stage_rows

	if frappe.db.exists("ATS Pipeline Template", DEFAULT_TEMPLATE_NAME):
		return frappe.get_all(
			"ATS Template Stage",
			filters={"parent": DEFAULT_TEMPLATE_NAME},
			order_by="idx asc",
			pluck="stage_name",
		)
	return [row["stage_name"] for row in default_stage_rows()]


def apply_pipeline_definition(board) -> None:
	"""Point a Kanban Board document at the pipeline stage with the stage columns."""
	board.reference_doctype = "Job Applicant"
	board.field_name = STAGE_FIELD
	board.filters = json.dumps(HIDE_DROPPED_FILTER)
	board.fields = json.dumps(CARD_FIELDS)
	board.show_labels = 1
	board.set("columns", [])
	for column_name in default_columns():
		board.append("columns", {"column_name": column_name, "status": "Active"})


def upgrade_hiring_pipeline_board() -> bool:
	"""Move an existing status-based Hiring Pipeline board onto the pipeline stages.
	Returns True when a board was changed. A board that is already on the stage field is left alone."""
	if not frappe.db.exists("Kanban Board", BOARD_NAME):
		return False
	board = frappe.get_doc("Kanban Board", BOARD_NAME)
	if board.field_name == STAGE_FIELD:
		return False
	apply_pipeline_definition(board)
	board.save(ignore_permissions=True)
	return True
