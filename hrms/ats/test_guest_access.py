# Copyright (c) 2026, Clustox and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from hrms.ats.guest_access import (
	active_grants,
	grant_access,
	granted_jobs,
	invite_guest,
	revoke_access,
	revoke_all_access,
	sync_expired_grants,
)
from hrms.ats.roles import GUEST, RECRUITER, SALARY_VIEWER
from hrms.ats.test_pipeline import make_job


def email():
	return f"guest.{frappe.generate_hash(length=8)}@example.com"


def make_user(*roles):
	return frappe.get_doc(
		{"doctype": "User", "email": email(), "first_name": "Staff", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": r} for r in roles]}
	).insert(ignore_permissions=True).name


def roles_of(user):
	return set(frappe.get_roles(user)) - {"All", "Guest", "Desk User"}


def as_user(user, fn, *args, **kwargs):
	frappe.set_user(user)
	try:
		return fn(*args, **kwargs)
	finally:
		frappe.set_user("Administrator")


class TestInviteGuest(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Invite A").insert()
		self.job2 = make_job("_Test Invite B").insert()

	def test_creates_a_guest_with_the_role_and_a_grant_per_job(self):
		address = email()
		result = invite_guest(address, "Sana", [self.job.name, self.job2.name], last_name="Khan", send_invite=0)
		self.assertTrue(result["created"])
		self.assertEqual(roles_of(address), {GUEST})
		self.assertEqual(frappe.db.get_value("User", address, ["enabled", "user_type"], as_dict=True), {"enabled": 1, "user_type": "System User"})
		self.assertEqual(set(granted_jobs(address)), {self.job.name, self.job2.name})
		self.assertEqual(len(result["grants"]), 2)

	def test_the_invite_email_is_sent_unless_switched_off(self):
		with patch("frappe.core.doctype.user.user.User.send_welcome_mail_to_user") as sender:
			invite_guest(email(), "Invited", [self.job.name], send_invite=1)
		sender.assert_called_once()
		with patch("frappe.core.doctype.user.user.User.send_welcome_mail_to_user") as sender:
			invite_guest(email(), "Quiet", [self.job.name], send_invite=0)
		sender.assert_not_called()

	def test_an_existing_user_keeps_their_other_roles(self):
		staff = make_user("HR User")
		result = invite_guest(staff, "Staff", [self.job.name], send_invite=0)
		self.assertFalse(result["created"])
		self.assertEqual(roles_of(staff), {"HR User", GUEST})

	def test_inviting_twice_does_not_duplicate_the_grant(self):
		address = email()
		invite_guest(address, "Twice", [self.job.name], send_invite=0)
		invite_guest(address, "Twice", [self.job.name], send_invite=0)
		self.assertEqual(frappe.db.count("Job Guest Access", {"user": address, "job_opening": self.job.name}), 1)

	def test_jobs_can_be_given_as_text(self):
		address = email()
		invite_guest(address, "Text", f'["{self.job.name}"]', send_invite=0)
		self.assertEqual(granted_jobs(address), [self.job.name])
		other = email()
		invite_guest(other, "Comma", f"{self.job.name}, {self.job2.name}", send_invite=0)
		self.assertEqual(set(granted_jobs(other)), {self.job.name, self.job2.name})

	def test_needs_a_job_and_a_valid_email(self):
		with self.assertRaises(frappe.ValidationError):
			invite_guest(email(), "NoJobs", [], send_invite=0)
		with self.assertRaises(frappe.ValidationError):
			invite_guest("not-an-email", "Bad", [self.job.name], send_invite=0)

	def test_a_disabled_user_cannot_be_invited(self):
		user = make_user("HR User")
		frappe.db.set_value("User", user, "enabled", 0)
		with self.assertRaises(frappe.ValidationError):
			invite_guest(user, "Off", [self.job.name], send_invite=0)

	def test_flags_and_expiry_are_stored(self):
		address = email()
		invite_guest(address, "Flags", [self.job.name], can_move_stages=1, can_view_salary=1, expires_on=add_days(nowdate(), 30), send_invite=0)
		grant = frappe.get_doc("Job Guest Access", active_grants(address)[0].name)
		self.assertEqual((grant.can_move_stages, grant.can_view_salary), (1, 1))
		self.assertEqual(str(grant.expires_on), add_days(nowdate(), 30))
		self.assertEqual(grant.granted_by, "Administrator")
		self.assertTrue(grant.granted_on)

	def test_administrator_and_guest_users_cannot_be_given_access(self):
		for user in ("Administrator", "Guest"):
			with self.assertRaises(frappe.ValidationError):
				grant_access(user, self.job.name)


class TestWhoMayShare(IntegrationTestCase):
	def setUp(self):
		self.owner = make_user(RECRUITER)
		self.other_recruiter = make_user(RECRUITER)
		self.hr_manager = make_user("HR Manager")
		self.job = make_job("_Test Share Owner", job_owner=self.owner).insert()
		self.guest = email()
		invite_guest(self.guest, "G", [self.job.name], send_invite=0)
		revoke_all_access(self.guest)

	def test_hr_manager_and_administrator_may_share_any_job(self):
		self.assertTrue(as_user(self.hr_manager, grant_access, self.guest, self.job.name))
		revoke_all_access(self.guest)
		self.assertTrue(grant_access(self.guest, self.job.name))

	def test_the_job_owner_may_share_their_own_job(self):
		self.assertTrue(as_user(self.owner, grant_access, self.guest, self.job.name))

	def test_another_recruiter_may_not(self):
		with self.assertRaises(frappe.PermissionError):
			as_user(self.other_recruiter, grant_access, self.guest, self.job.name)
		with self.assertRaises(frappe.PermissionError):
			as_user(self.other_recruiter, invite_guest, email(), "X", [self.job.name], None, 0, 0, None, 0)

	def test_the_owner_cannot_share_a_job_that_is_not_theirs(self):
		other_job = make_job("_Test Share Not Mine").insert()
		with self.assertRaises(frappe.PermissionError):
			as_user(self.owner, grant_access, self.guest, other_job.name)

	def test_a_guest_cannot_share_anything(self):
		guest_user = make_user(GUEST)
		with self.assertRaises(frappe.PermissionError):
			as_user(guest_user, grant_access, self.guest, self.job.name)

	def test_one_bad_job_stops_the_whole_invite(self):
		not_mine = make_job("_Test Share Mixed").insert()
		address = email()
		with self.assertRaises(frappe.PermissionError):
			as_user(self.owner, invite_guest, address, "Mixed", [self.job.name, not_mine.name], None, 0, 0, None, 0)
		self.assertFalse(frappe.db.exists("User", address))  # nothing was created

	def test_only_the_owner_or_hr_can_revoke(self):
		grant_access(self.guest, self.job.name)
		with self.assertRaises(frappe.PermissionError):
			as_user(self.other_recruiter, revoke_access, self.guest, self.job.name)
		self.assertEqual(as_user(self.owner, revoke_access, self.guest, self.job.name), 1)


class TestRevoke(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Revoke A").insert()
		self.job2 = make_job("_Test Revoke B").insert()
		self.guest = email()
		invite_guest(self.guest, "R", [self.job.name, self.job2.name], send_invite=0)

	def test_revoking_one_job_keeps_the_other(self):
		self.assertEqual(revoke_access(self.guest, self.job.name), 1)
		self.assertEqual(granted_jobs(self.guest), [self.job2.name])
		self.assertIn(GUEST, roles_of(self.guest))

	def test_revoking_the_last_job_takes_the_guest_role_away(self):
		revoke_all_access(self.guest)
		self.assertEqual(granted_jobs(self.guest), [])
		self.assertNotIn(GUEST, roles_of(self.guest))

	def test_the_revoked_grant_is_kept_for_the_record(self):
		revoke_access(self.guest, self.job.name)
		grant = frappe.get_all("Job Guest Access", filters={"user": self.guest, "job_opening": self.job.name}, fields=["revoked_on", "revoked_by"])[0]
		self.assertTrue(grant.revoked_on)
		self.assertEqual(grant.revoked_by, "Administrator")

	def test_revoking_twice_is_harmless(self):
		revoke_access(self.guest, self.job.name)
		self.assertEqual(revoke_access(self.guest, self.job.name), 0)

	def test_sharing_again_after_a_revoke_brings_the_old_record_back(self):
		revoke_access(self.guest, self.job.name)
		grant_access(self.guest, self.job.name)
		self.assertEqual(frappe.db.count("Job Guest Access", {"user": self.guest, "job_opening": self.job.name}), 1)
		self.assertIn(self.job.name, granted_jobs(self.guest))
		self.assertIn(GUEST, roles_of(self.guest))

	def test_deleting_a_grant_also_takes_the_role_away(self):
		revoke_access(self.guest, self.job.name)
		for name in frappe.get_all("Job Guest Access", filters={"user": self.guest}, pluck="name"):
			frappe.delete_doc("Job Guest Access", name, force=True)
		self.assertNotIn(GUEST, roles_of(self.guest))


class TestSalaryRole(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Salary Grant").insert()
		self.job2 = make_job("_Test Salary Grant 2").insert()
		self.guest = email()

	def test_salary_viewer_follows_the_grants_that_allow_salary(self):
		invite_guest(self.guest, "S", [self.job.name], can_view_salary=1, send_invite=0)
		grant_access(self.guest, self.job2.name, can_view_salary=0)
		self.assertIn(SALARY_VIEWER, roles_of(self.guest))
		revoke_access(self.guest, self.job.name)
		self.assertNotIn(SALARY_VIEWER, roles_of(self.guest))  # the job that allowed it is gone
		self.assertIn(GUEST, roles_of(self.guest))

	def test_no_salary_role_when_salary_is_not_allowed(self):
		invite_guest(self.guest, "NoSalary", [self.job.name], send_invite=0)
		self.assertNotIn(SALARY_VIEWER, roles_of(self.guest))


class TestExpiry(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Expiry").insert()
		self.guest = email()

	def test_a_grant_is_active_until_its_expiry_date_inclusive(self):
		invite_guest(self.guest, "E", [self.job.name], expires_on=nowdate(), send_invite=0)
		self.assertEqual(granted_jobs(self.guest), [self.job.name])

	def test_an_expired_grant_is_not_active(self):
		invite_guest(self.guest, "E", [self.job.name], send_invite=0)
		frappe.db.set_value("Job Guest Access", active_grants(self.guest)[0].name, "expires_on", add_days(nowdate(), -1))
		self.assertEqual(granted_jobs(self.guest), [])

	def test_the_daily_job_takes_the_roles_from_a_guest_whose_access_ran_out(self):
		invite_guest(self.guest, "E", [self.job.name], can_view_salary=1, expires_on=add_days(nowdate(), 5), send_invite=0)
		frappe.db.set_value("Job Guest Access", active_grants(self.guest)[0].name, "expires_on", add_days(nowdate(), -1))
		sync_expired_grants()
		self.assertNotIn(GUEST, roles_of(self.guest))
		self.assertNotIn(SALARY_VIEWER, roles_of(self.guest))

	def test_a_past_expiry_cannot_be_set(self):
		with self.assertRaises(frappe.ValidationError):
			invite_guest(self.guest, "E", [self.job.name], expires_on=add_days(nowdate(), -1), send_invite=0)

	def test_the_daily_job_is_scheduled(self):
		self.assertIn("hrms.ats.guest_access.sync_expired_grants", frappe.get_hooks("scheduler_events")["daily"])
