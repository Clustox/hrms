# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.kanban_board.kanban_board import get_kanban_column_counts, merge_kanban_filters
from frappe.tests import IntegrationTestCase

from hrms.ats.board import (
	BOARD_NAME,
	STAGE_FIELD,
	default_columns,
	get_job_board,
	job_board_name,
	upgrade_hiring_pipeline_board,
)
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
		stages = ["New Candidates", "Technical Assessment", "Final Interview", "Hired", "On Hold"]
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


class TestJobBoard(IntegrationTestCase):
	def custom_job(self, title, stages=("Applied", "Screen", "Offer", "Joined")):
		job = make_job(title)
		for i, stage in enumerate(stages):
			job.append("pipeline_stages", {"stage_name": stage, "stage_type": "Hired" if i == len(stages) - 1 else "Active"})
		return job.insert()

	def test_job_on_the_default_pipeline_uses_the_shared_board(self):
		job = make_job("_Test Job Board Default").insert()
		self.assertEqual(get_job_board(job.name), BOARD_NAME)
		self.assertFalse(frappe.db.exists("Kanban Board", job_board_name(job.name)))

	def test_job_with_its_own_stages_gets_its_own_board(self):
		job = self.custom_job("_Test Job Board Custom")
		name = get_job_board(job.name)
		self.assertEqual(name, job_board_name(job.name))
		board = frappe.get_doc("Kanban Board", name)
		self.assertEqual(board.field_name, STAGE_FIELD)
		self.assertEqual([c.column_name for c in board.columns], ["Applied", "Screen", "Offer", "Joined"])
		self.assertEqual(
			json.loads(board.filters),
			[["Job Applicant", "job_title", "=", job.name], ["Job Applicant", "is_dropped", "=", 0]],
		)

	def test_the_own_board_shows_only_this_jobs_candidates(self):
		job, other = self.custom_job("_Test Job Board Only"), self.custom_job("_Test Job Board Other")
		mine = new_applicant(job, "jobboard.mine@example.com").name
		new_applicant(other, "jobboard.other@example.com")
		move_stage(mine, "Screen")
		name = get_job_board(job.name)
		board = frappe.get_doc("Kanban Board", name)
		filters = merge_kanban_filters(board, [])
		counts = get_kanban_column_counts("Job Applicant", STAGE_FIELD, filters, [c.column_name for c in board.columns])
		self.assertEqual(counts, {"Applied": 0, "Screen": 1, "Offer": 0, "Joined": 0})

	def test_opening_the_board_twice_does_not_duplicate_it(self):
		job = self.custom_job("_Test Job Board Twice")
		get_job_board(job.name)
		get_job_board(job.name)
		self.assertEqual(frappe.db.count("Kanban Board", {"name": job_board_name(job.name)}), 1)

	def test_the_board_follows_later_stage_edits(self):
		job = self.custom_job("_Test Job Board Follow")
		name = get_job_board(job.name)
		job.append("pipeline_stages", {"stage_name": "Onboarding", "stage_type": "Active"})
		next(r for r in job.pipeline_stages if r.stage_name == "Applied").stage_name = "New Applicants"
		job.save()
		columns = [c.column_name for c in frappe.get_doc("Kanban Board", name).columns]
		self.assertEqual(columns, ["New Applicants", "Screen", "Offer", "Joined", "Onboarding"])

	def test_a_job_without_its_board_gets_none_created_on_save(self):
		job = self.custom_job("_Test Job Board Lazy")
		self.assertFalse(frappe.db.exists("Kanban Board", job_board_name(job.name)))

	def test_a_user_who_cannot_read_the_job_cannot_open_its_board(self):
		job = self.custom_job("_Test Job Board Perm")
		user = frappe.get_doc(
			{"doctype": "User", "email": "board.noperm@example.com", "first_name": "No Perm", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				get_job_board(job.name)
		finally:
			frappe.set_user("Administrator")

	def test_the_shared_board_drops_columns_the_default_pipeline_no_longer_has(self):
		from hrms.ats.board import BOARD_NAME, default_columns, sync_hiring_pipeline_columns

		create_kanban_board(BOARD_NAME)
		board = frappe.get_doc("Kanban Board", BOARD_NAME)
		board.append("columns", {"column_name": "Rejected after Final Interview", "status": "Active"})
		board.save(ignore_permissions=True)
		self.assertTrue(sync_hiring_pipeline_columns())
		self.assertEqual([c.column_name for c in frappe.get_doc("Kanban Board", BOARD_NAME).columns], default_columns())
		self.assertFalse(sync_hiring_pipeline_columns())  # nothing left to do
