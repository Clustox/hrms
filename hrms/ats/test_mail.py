# Copyright (c) 2026, Clustox and contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.mail import TEMPLATES, pick_sender, send_bulk_email, send_candidate_email, seed_email_templates
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import new_applicant

SYSTEM = "hrms.ats.mail.make_system_communication"
USER = "hrms.ats.mail.make_user_communication"


def email():
	return f"mail.{frappe.generate_hash(length=8)}@example.com"


class TestCandidateMail(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Mail Job").insert()
		self.applicant = new_applicant(self.job, email())

	def test_the_four_templates_are_seeded_and_not_overwritten(self):
		seed_email_templates(commit=False)
		for name in TEMPLATES:
			self.assertTrue(frappe.db.exists("Email Template", name), name)
		frappe.db.set_value("Email Template", "ATS Offer", "subject", "Edited by HR")
		seed_email_templates(commit=False)
		self.assertEqual(frappe.db.get_value("Email Template", "ATS Offer", "subject"), "Edited by HR")

	def test_a_template_fills_in_the_candidate_and_job(self):
		seed_email_templates(commit=False)
		with patch(USER) as make:
			send_candidate_email(self.applicant.name, template="ATS Rejection")
		kwargs = make.call_args.kwargs
		self.assertIn(self.applicant.applicant_name, kwargs["content"])
		self.assertIn("_Test Mail Job", kwargs["subject"])
		self.assertEqual(kwargs["recipients"], [self.applicant.email_id])
		self.assertEqual((kwargs["doctype"], kwargs["name"]), ("Job Applicant", self.applicant.name))

	def test_no_address_means_a_clear_error(self):
		frappe.db.set_value("Job Applicant", self.applicant.name, "email_id", "")
		with self.assertRaises(frappe.ValidationError):
			send_candidate_email(self.applicant.name, subject="s", content="c")

	def test_nothing_to_send_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			send_candidate_email(self.applicant.name)

	def test_sender_is_the_recruiters_connected_address_else_hiring_sender(self):
		with patch("hrms.ats.mail.connected_sender", return_value="me@gmail.com"):
			self.assertEqual(pick_sender("Administrator"), "me@gmail.com")
		with patch("hrms.ats.mail.connected_sender", return_value=None):
			frappe.db.set_single_value("HR Settings", "hiring_sender_email", "hiring@example.com")
			self.assertEqual(pick_sender("Administrator"), "hiring@example.com")

	def test_the_account_connected_to_the_user_is_their_sender_even_with_another_address(self):
		from hrms.ats.mail import connected_sender

		user = frappe.get_doc(
			{"doctype": "User", "email": email(), "first_name": "Conn", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		account = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": "_Test Connected",
				"email_id": f"recruiter.{frappe.generate_hash(length=6)}@example.com",
				"enable_outgoing": 1,
				"smtp_server": "localhost",
				"password": "x",
				"connected_user": user.name,
			}
		)
		account.flags.ignore_validate = True
		account.insert(ignore_permissions=True)
		self.assertEqual(connected_sender(user.name), account.email_id)
		self.assertIsNone(connected_sender("Guest"))

	def test_a_real_send_lands_on_the_candidates_timeline(self):
		if not frappe.db.exists("Email Account", {"default_outgoing": 1}):  # the dev site has none
			account = frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": "_Test ATS Outgoing",
					"email_id": "ats.outgoing@example.com",
					"enable_outgoing": 1,
					"default_outgoing": 1,
					"smtp_server": "localhost",
					"password": "x",
				}
			)
			account.flags.ignore_validate = True
			account.insert(ignore_permissions=True)
		send_candidate_email(self.applicant.name, subject="Hello", content="<p>Hi</p>", system=True)
		self.assertTrue(
			frappe.db.exists(
				"Communication",
				{"reference_doctype": "Job Applicant", "reference_name": self.applicant.name, "subject": "Hello"},
			)
		)

	def test_bulk_sends_one_each_and_reports_the_ones_skipped(self):
		seed_email_templates(commit=False)
		other = new_applicant(self.job, email())
		frappe.db.set_value("Job Applicant", other.name, "email_id", "")
		third = new_applicant(self.job, email())
		with patch(USER) as make:
			result = send_bulk_email("ATS Acknowledgement", json.dumps([self.applicant.name, other.name, third.name, third.name]))
		self.assertEqual(result["sent"], 2)  # the duplicate is sent once
		self.assertEqual(make.call_count, 2)
		self.assertEqual([s["applicant"] for s in result["skipped"]], [other.name])

	def test_bulk_has_a_ceiling(self):
		with self.assertRaises(frappe.ValidationError):
			send_bulk_email("ATS Offer", [f"x{i}" for i in range(101)])

	def test_a_user_without_the_right_to_email_cannot_send(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": email(), "first_name": "NoMail", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				send_candidate_email(self.applicant.name, subject="s", content="c")
		finally:
			frappe.set_user("Administrator")
