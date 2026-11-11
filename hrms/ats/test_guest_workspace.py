# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json

import frappe
from frappe.boot import get_module_sidebars
from frappe.tests import IntegrationTestCase

from hrms.ats.guest_access import (
	ALLOWED_GUEST_MODULES,
	grant_access,
	guest_blocked_modules,
	invite_guest,
	revoke_all_access,
)
from hrms.ats.roles import GUEST, RECRUITER
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def unique_email():
	return f"ws.{frappe.generate_hash(length=8)}@example.com"


def make_user(*roles):
	return frappe.get_doc(
		{"doctype": "User", "email": unique_email(), "first_name": "WS", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": r} for r in roles]}
	).insert(ignore_permissions=True).name


def blocked(user):
	return {b.module for b in frappe.get_doc("User", user).block_modules}


def shells(user):
	frappe.set_user(user)
	try:
		return get_module_sidebars()
	finally:
		frappe.set_user("Administrator")


class TestGuestWorkspace(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Workspace").insert()
		self.guest = unique_email()
		invite_guest(self.guest, "G", [self.job.name], send_invite=0)

	def test_every_module_except_the_recruitment_ones_is_blocked(self):
		self.assertEqual(blocked(self.guest), guest_blocked_modules())
		for module in ALLOWED_GUEST_MODULES:
			self.assertNotIn(module, blocked(self.guest))
		self.assertIn("Accounts", blocked(self.guest))
		self.assertIn("Users", blocked(self.guest))

	def test_the_menu_only_has_the_recruitment_screens(self):
		menu = shells(self.guest)
		self.assertTrue(set(menu) <= {"HR", "Recruitment"}, sorted(menu))
		self.assertIn("Recruitment", menu)

	def test_the_menu_offers_only_what_the_guest_can_use(self):
		labels = {item["label"] for shell in shells(self.guest).values() for item in shell["items"]}
		for label in ("Job Opening", "Job Applicant", "Candidate", "Interview"):
			self.assertIn(label, labels)
		for label in ("Job Offer", "Staffing Plan", "Job Requisition", "Employee", "Leave Application", "Pipeline Template", "Drop Reason", "Inbox"):
			self.assertNotIn(label, labels, label)

	def test_staff_keep_their_full_menu(self):
		menu = shells(make_user(RECRUITER))
		self.assertGreater(len(menu), 2)
		self.assertEqual(blocked(make_user(RECRUITER)), set())

	def test_a_guest_who_also_has_a_staff_role_is_not_restricted(self):
		user = make_user("HR User")
		grant_access(user, self.job.name)  # adds the guest role to an HR user
		self.assertIn(GUEST, frappe.get_roles(user))
		self.assertEqual(blocked(user), set())

	def test_a_staff_members_own_blocked_modules_are_kept(self):
		user = make_user("HR User")
		doc = frappe.get_doc("User", user)
		doc.append("block_modules", {"module": "Accounts"})
		doc.save(ignore_permissions=True)
		grant_access(user, self.job.name)
		revoke_all_access(user)
		self.assertEqual(blocked(user), {"Accounts"})

	def test_revoking_everything_gives_the_blocks_back(self):
		revoke_all_access(self.guest)
		self.assertEqual(blocked(self.guest), set())

	def test_a_guest_with_one_job_left_stays_restricted(self):
		other = make_job("_Test Workspace 2").insert()
		grant_access(self.guest, other.name)
		from hrms.ats.guest_access import revoke_access

		revoke_access(self.guest, self.job.name)
		self.assertEqual(blocked(self.guest), guest_blocked_modules())

	def test_inviting_an_existing_guest_again_does_not_change_the_blocks(self):
		before = blocked(self.guest)
		invite_guest(self.guest, "G", [self.job.name], send_invite=0)
		self.assertEqual(blocked(self.guest), before)


class TestDashboardsDoNotLeak(IntegrationTestCase):
	"""The Recruitment dashboard is still part of a guest's menu, so its totals must only count what they may see."""

	def setUp(self):
		self.job = make_job("_Test Dashboard Leak").insert()
		self.guest = unique_email()
		invite_guest(self.guest, "G", [self.job.name], send_invite=0)
		visible = new_applicant(self.job, unique_email()).name
		move_stage(visible, "Technical Assessment")  # the only one in a stage guests may see
		for _ in range(4):
			new_applicant(self.job, unique_email())  # four more in a hidden stage

	def test_the_applicants_chart_counts_only_visible_applicants(self):
		from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as chart_get

		frappe.set_user(self.guest)
		try:
			values = chart_get(chart_name="Job Application Status")["datasets"][0]["values"]
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(sum(values), 1)

	def test_a_number_card_counts_only_visible_applicants(self):
		from frappe.desk.doctype.number_card.number_card import get_result

		card = frappe.get_doc("Number Card", "Total Applicants (This Month)")
		frappe.set_user(self.guest)
		try:
			result = get_result(json.dumps(card.as_dict(), default=str), card.filters_json or "[]")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(result, 1)
