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
# A card shows the candidate's current title and employer, the rating, the date they applied
# and the date they entered the current stage (dates only: a date and time does not fit a card).
CARD_FIELDS = [
	"candidate_title",
	"candidate_employer",
	"designation",
	"applicant_rating",
	"applied_on",
	"stage_entered_date",
]
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


def sync_hiring_pipeline_columns() -> bool:
	"""Make the shared Hiring Pipeline board's columns the stages of the default pipeline again (after the
	default changed). Only the columns are touched, not the board's filters or card fields. Returns True
	when something changed."""
	if not frappe.db.exists("Kanban Board", BOARD_NAME):
		return False
	board = frappe.get_doc("Kanban Board", BOARD_NAME)
	if board.field_name != STAGE_FIELD:
		return False
	wanted = default_columns()
	if [c.column_name for c in board.columns] == wanted:
		return False
	board.set("columns", [])
	for column_name in wanted:
		board.append("columns", {"column_name": column_name, "status": "Active"})
	board.save(ignore_permissions=True)
	return True


def job_board_name(job: str) -> str:
	return f"Pipeline - {job}"


def uses_default_pipeline(job: str) -> bool:
	"""True when the job's stages are exactly the default stages, in the default order."""
	from hrms.ats.pipeline import get_job_stages

	return [s.stage_name for s in get_job_stages(job)] == default_columns()


@frappe.whitelist()
def get_job_board(job: str) -> str:
	"""Name of the Kanban board to open for a job.

	A job on the default pipeline uses the shared Hiring Pipeline board (filtered to the job by
	the caller). A job with its own stages gets a board of its own, kept in step with its stages.
	"""
	frappe.has_permission("Job Opening", "read", job, throw=True)
	if uses_default_pipeline(job):
		if not frappe.db.exists("Kanban Board", BOARD_NAME):
			from hrms.hr.doctype.job_applicant.job_applicant import create_kanban_board

			create_kanban_board(BOARD_NAME)
		return BOARD_NAME
	return sync_job_board(job)


def sync_job_board(job: str) -> str:
	"""Create or update the job's own board: its stages as columns, only this job, no dropped."""
	from hrms.ats.pipeline import get_job_stages

	name = job_board_name(job)
	board = frappe.get_doc("Kanban Board", name) if frappe.db.exists("Kanban Board", name) else frappe.new_doc("Kanban Board")
	board.kanban_board_name = name
	board.private = 0
	board.reference_doctype = "Job Applicant"
	board.field_name = STAGE_FIELD
	board.filters = json.dumps([["Job Applicant", "job_title", "=", job], *HIDE_DROPPED_FILTER])
	board.fields = json.dumps(CARD_FIELDS)
	board.show_labels = 1

	existing = {c.column_name: c for c in board.get("columns") or []}
	wanted = [s.stage_name for s in get_job_stages(job)]
	board.set("columns", [])
	for column_name in wanted:  # keep the saved card order of columns that stay
		old = existing.get(column_name)
		board.append("columns", {"column_name": column_name, "status": "Active", "order": old.order if old else None})
	if board.is_new():
		board.insert(ignore_permissions=True)
	else:
		board.save(ignore_permissions=True)
	return name


def sync_job_board_on_save(doc, method=None):
	"""Job Opening on_update hook: keep an existing own board in step with the job's stages."""
	if frappe.db.exists("Kanban Board", job_board_name(doc.name)):
		sync_job_board(doc.name)


def refresh_board_cards() -> int:
	"""Give every pipeline board (the shared one and the per-job ones) the current card fields.
	Returns how many boards changed. Safe to run again."""
	wanted = json.dumps(CARD_FIELDS)
	changed = 0
	for name in frappe.get_all(
		"Kanban Board", filters={"reference_doctype": "Job Applicant", "field_name": STAGE_FIELD}, pluck="name"
	):
		if frappe.db.get_value("Kanban Board", name, "fields") != wanted:
			frappe.db.set_value("Kanban Board", name, "fields", wanted)
			changed += 1
	return changed
