# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.kanban_board.kanban_board import get_kanban_column_counts, merge_kanban_filters
from frappe.tests import IntegrationTestCase

from hrms.ats.board import BOARD_NAME, STAGE_FIELD, default_columns, upgrade_hiring_pipeline_board
from hrms.ats.pipeline import default_stage_rows, drop_applicant
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant
from hrms.hr.doctype.job_applicant.job_applicant import create_kanban_board


def board_counts(board_name, job):
	"""Cards per column when the board is filtered to one job, as the Kanban view loads them."""
	board = frappe.get_doc("Kanban Board", board_name)
	columns = [c.column_name for c in board.columns]
	filters = merge_kanban_filters(board, [["Job Applicant", "job_title", "=", job]])
	return get_kanban_column_counts("Job Applicant", board.field_name, filters, columns)


class TestHiringPipelineBoard(IntegrationTestCase):
	def test_new_board_uses_the_pipeline_stages(self):
		board = create_kanban_board("_Test Hiring Board")
		self.assertEqual(board["field_name"], STAGE_FIELD)
		self.assertEqual([c["column_name"] for c in board["columns"]], default_columns())
		self.assertEqual(len(board["columns"]), len(default_stage_rows()))

	def test_board_hides_dropped_candidates_by_a_saved_filter(self):
		board = create_kanban_board("_Test Hiring Board 2")
		self.assertEqual(json.loads(board["filters"]), [["Job Applicant", "is_dropped", "=", 0]])

	def test_every_active_candidate_of_a_job_appears_in_a_column(self):
		create_kanban_board("_Test Hiring Board 3")
		job = make_job("_Test Board Job").insert()
		stages = ["New Candidates", "Technical Assessment", "Final Interview", "Hired", "On Hold", "Rejected after Final Interview"]
		for i, stage in enumerate(stages):
			name = new_applicant(job, f"board.{i}@example.com").name
			move_stage(name, stage)
		counts = board_counts("_Test Hiring Board 3", job.name)
		self.assertEqual(sum(counts.values()), len(stages))  # nobody is hidden any more
		for stage in stages:
			self.assertEqual(counts[stage], 1, stage)

	def test_a_dropped_candidate_leaves_the_board(self):
		create_kanban_board("_Test Hiring Board 4")
		job = make_job("_Test Board Dropped").insert()
		keep = new_applicant(job, "board.keep@example.com").name
		gone = new_applicant(job, "board.gone@example.com").name
		self.assertEqual(sum(board_counts("_Test Hiring Board 4", job.name).values()), 2)
		drop_applicant(gone, "Candidate withdrew")
		counts = board_counts("_Test Hiring Board 4", job.name)
		self.assertEqual(sum(counts.values()), 1)
		self.assertEqual(frappe.db.get_value("Job Applicant", keep, "is_dropped"), 0)

	def test_the_board_follows_a_stage_move(self):
		create_kanban_board("_Test Hiring Board 5")
		job = make_job("_Test Board Move").insert()
		name = new_applicant(job, "board.move@example.com").name
		move_stage(name, "Technical Assessment")
		counts = board_counts("_Test Hiring Board 5", job.name)
		self.assertEqual((counts["New Candidates"], counts["Technical Assessment"]), (0, 1))


class TestBoardUpgrade(IntegrationTestCase):
	def make_old_board(self):
		"""The board as it was before the ATS: status field and four fixed columns."""
		board = frappe.get_doc("Kanban Board", BOARD_NAME)
		board.field_name = "status"
		board.filters = None
		board.set("columns", [])
		for name in ("Open", "Replied", "Shortlisted", "Accepted"):
			board.append("columns", {"column_name": name, "status": "Active"})
		board.save(ignore_permissions=True)

	def setUp(self):
		create_kanban_board(BOARD_NAME)  # first use creates it, as in the app

	def test_old_board_moves_onto_the_stages(self):
		self.make_old_board()
		self.assertTrue(upgrade_hiring_pipeline_board())
		board = frappe.get_doc("Kanban Board", BOARD_NAME)
		self.assertEqual(board.field_name, STAGE_FIELD)
		self.assertEqual([c.column_name for c in board.columns], default_columns())
		self.assertEqual(json.loads(board.filters), [["Job Applicant", "is_dropped", "=", 0]])

	def test_running_the_upgrade_twice_changes_nothing(self):
		self.make_old_board()
		upgrade_hiring_pipeline_board()
		self.assertFalse(upgrade_hiring_pipeline_board())

	def test_no_board_means_nothing_to_upgrade(self):
		if frappe.db.exists("Kanban Board", BOARD_NAME):
			frappe.delete_doc("Kanban Board", BOARD_NAME, force=True)
		self.assertFalse(upgrade_hiring_pipeline_board())
