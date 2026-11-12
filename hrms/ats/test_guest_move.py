# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe

from hrms.ats.guest_access import get_move_options, grant_access, move_stage, revoke_access
from hrms.ats.roles import RECRUITER
from hrms.ats.test_permissions import GuestFixture, as_user, make_user, names_or_denied, unique_email
from hrms.ats.guest_access import invite_guest


def stage_of(name):
	return frappe.db.get_value("Job Applicant", name, "pipeline_stage")


def moves(name):
	return frappe.get_all(
		"Applicant Stage Log", filters={"job_applicant": name}, fields=["from_stage", "to_stage", "moved_by"], order_by="creation desc", limit=1
	)[0]


class TestGuestMovesCandidates(GuestFixture):
	def allow_moving(self):
		grant_access(self.guest, self.job_a.name, can_move_stages=1)

	def test_a_guest_with_the_right_moves_a_visible_candidate(self):
		self.allow_moving()
		self.assertEqual(as_user(self.guest, move_stage, self.visible, "Final Interview"), "Final Interview")
		self.assertEqual(stage_of(self.visible), "Final Interview")

	def test_the_move_is_recorded_under_the_guests_name(self):
		self.allow_moving()
		as_user(self.guest, move_stage, self.visible, "Final Interview")
		self.assertEqual(
			(moves(self.visible).from_stage, moves(self.visible).to_stage, moves(self.visible).moved_by),
			("Technical Assessment", "Final Interview", self.guest),
		)

	def test_a_guest_without_the_right_cannot_move_anyone(self):
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, move_stage, self.visible, "Final Interview")
		self.assertEqual(stage_of(self.visible), "Technical Assessment")

	def test_the_right_is_per_job(self):
		self.allow_moving()
		grant_access(self.guest, self.job_b.name, can_move_stages=0)
		# a visible candidate of job B, where moving is not allowed
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, move_stage, self.other_job, "Technical Assessment")

	def test_a_hidden_candidate_cannot_be_moved_even_with_the_right(self):
		self.allow_moving()
		for hidden in (self.hidden_stage, self.rejected, self.dropped, self.other_job):
			with self.assertRaises(frappe.PermissionError):
				as_user(self.guest, move_stage, hidden, "Final Interview")

	def test_revoking_takes_the_right_away_at_once(self):
		self.allow_moving()
		revoke_access(self.guest, self.job_a.name)
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, move_stage, self.visible, "Final Interview")

	def test_an_unknown_stage_is_refused(self):
		self.allow_moving()
		with self.assertRaises(frappe.ValidationError):
			as_user(self.guest, move_stage, self.visible, "No Such Stage")

	def test_moving_out_of_the_visible_stages_makes_the_candidate_disappear_for_the_guest(self):
		self.allow_moving()
		as_user(self.guest, move_stage, self.visible, "On Hold")  # a stage that is not ticked for guests
		self.assertEqual(names_or_denied(self.guest, "Job Applicant"), [])

	def test_stage_rules_still_apply_to_a_guest(self):
		row = next(r for r in self.job_a.pipeline_stages if r.stage_name == "Final Interview")
		row.required_fields = "phone_number"
		self.job_a.save()
		self.allow_moving()
		with self.assertRaises(frappe.ValidationError):
			as_user(self.guest, move_stage, self.visible, "Final Interview")  # the applicant has no phone

	def test_a_guest_still_cannot_edit_anything_else_on_the_applicant(self):
		self.allow_moving()
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, frappe.set_value, "Job Applicant", self.visible, "applicant_rating", 1)


class TestMoveOptions(GuestFixture):
	def test_a_guest_with_the_right_is_offered_the_other_stages(self):
		grant_access(self.guest, self.job_a.name, can_move_stages=1)
		options = as_user(self.guest, get_move_options, self.visible)
		self.assertNotIn("Technical Assessment", options)  # where they already are
		self.assertIn("Final Interview", options)
		self.assertEqual(len(options), 14)  # 15 stages, minus the current one

	def test_a_guest_without_the_right_is_offered_nothing(self):
		self.assertEqual(as_user(self.guest, get_move_options, self.visible), [])

	def test_a_hidden_candidate_is_refused(self):
		grant_access(self.guest, self.job_a.name, can_move_stages=1)
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, get_move_options, self.hidden_stage)

	def test_staff_are_offered_nothing_because_they_use_the_board(self):
		self.assertEqual(as_user(make_user(RECRUITER), get_move_options, self.visible), [])


class TestStaffMoveThroughTheSameAction(GuestFixture):
	def test_a_recruiter_can_move_a_candidate(self):
		self.assertEqual(as_user(make_user(RECRUITER), move_stage, self.hidden_stage, "Final Interview"), "Final Interview")

	def test_a_user_without_write_access_cannot(self):
		reader = make_user("Interviewer")  # can read interviews, never applicants
		with self.assertRaises(frappe.PermissionError):
			as_user(reader, move_stage, self.hidden_stage, "Final Interview")

	def test_inviting_with_the_right_gives_it_straight_away(self):
		address = unique_email("mover")
		invite_guest(address, "Mover", [self.job_a.name], can_move_stages=1, send_invite=0)
		self.assertEqual(as_user(address, move_stage, self.visible, "Final Interview"), "Final Interview")
