# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json

import frappe
from frappe.model import default_fields
from frappe.tests import IntegrationTestCase

from hrms.ats.board import BOARD_NAME, CARD_FIELDS, refresh_board_cards
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import new_applicant
from hrms.hr.doctype.job_applicant.job_applicant import create_kanban_board


def make_candidate(email, title=None, employer=None):
	return frappe.get_doc(
		{"doctype": "Candidate", "full_name": "Card Person", "email": email, "current_title": title, "current_employer": employer}
	).insert()


class TestCardFields(IntegrationTestCase):
	def test_every_card_field_is_a_real_field(self):
		meta = frappe.get_meta("Job Applicant")
		for fieldname in CARD_FIELDS:
			self.assertTrue(meta.get_field(fieldname) or fieldname in default_fields, fieldname)

	def test_card_shows_what_the_ats_document_lists(self):
		for fieldname in ("candidate_title", "candidate_employer", "creation", "stage_entered_on"):
			self.assertIn(fieldname, CARD_FIELDS)

	def test_a_new_board_has_the_card_fields(self):
		board = create_kanban_board("_Test Card Board")
		self.assertEqual(json.loads(board["fields"]), CARD_FIELDS)


class TestCandidateOnTheCard(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Card Job").insert()

	def link(self, email, candidate):
		doc = new_applicant(self.job, email)
		doc.candidate = candidate.name
		doc.save()
		return doc.name

	def test_applicant_copies_title_and_employer_from_the_candidate(self):
		candidate = make_candidate("card.copy@example.com", "QA Engineer", "Arbisoft")
		name = self.link("card.copy.app@example.com", candidate)
		self.assertEqual(
			frappe.db.get_value("Job Applicant", name, ["candidate_title", "candidate_employer"], as_dict=True),
			{"candidate_title": "QA Engineer", "candidate_employer": "Arbisoft"},
		)

	def test_editing_the_candidate_updates_all_their_applications(self):
		candidate = make_candidate("card.edit@example.com", "Intern", "Devsinc")
		other_job = make_job("_Test Card Job 2").insert()
		first = self.link("card.edit.a@example.com", candidate)
		second_doc = new_applicant(other_job, "card.edit.b@example.com")
		second_doc.candidate = candidate.name
		second_doc.save()

		candidate.current_title = "Senior QA Engineer"
		candidate.current_employer = "Folio3"
		candidate.save()

		for name in (first, second_doc.name):
			values = frappe.db.get_value("Job Applicant", name, ["candidate_title", "candidate_employer"], as_dict=True)
			self.assertEqual(values, {"candidate_title": "Senior QA Engineer", "candidate_employer": "Folio3"})

	def test_other_candidates_applicants_are_not_changed(self):
		mine = make_candidate("card.mine@example.com", "Intern", "A Ltd")
		theirs = make_candidate("card.theirs@example.com", "Manager", "B Ltd")
		mine_app, theirs_app = self.link("card.mine.app@example.com", mine), self.link("card.theirs.app@example.com", theirs)
		mine.current_title = "Engineer"
		mine.save()
		self.assertEqual(frappe.db.get_value("Job Applicant", mine_app, "candidate_title"), "Engineer")
		self.assertEqual(frappe.db.get_value("Job Applicant", theirs_app, "candidate_title"), "Manager")

	def test_applicant_without_a_candidate_has_empty_card_fields(self):
		doc = new_applicant(self.job, "card.none@example.com")
		self.assertFalse(doc.candidate_title)
		self.assertFalse(doc.candidate_employer)


class TestRefreshBoardCards(IntegrationTestCase):
	def test_old_boards_get_the_new_card_fields_once(self):
		create_kanban_board(BOARD_NAME)
		frappe.db.set_value("Kanban Board", BOARD_NAME, "fields", json.dumps(["designation", "applicant_rating"]))
		self.assertGreaterEqual(refresh_board_cards(), 1)
		self.assertEqual(json.loads(frappe.db.get_value("Kanban Board", BOARD_NAME, "fields")), CARD_FIELDS)
		self.assertEqual(refresh_board_cards(), 0)

	def test_boards_on_other_fields_are_left_alone(self):
		other = frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": "_Test Other Board",
				"reference_doctype": "Job Applicant",
				"field_name": "status",
				"fields": json.dumps(["designation"]),
				"columns": [{"column_name": "Open"}],
			}
		).insert()
		refresh_board_cards()
		self.assertEqual(json.loads(frappe.db.get_value("Kanban Board", other.name, "fields")), ["designation"])
