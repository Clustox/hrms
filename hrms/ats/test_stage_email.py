# Copyright (c) 2026, Clustox and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def make_template(name="_Test Stage Email"):
	if frappe.db.exists("Email Template", name):
		frappe.delete_doc("Email Template", name, force=True)
	return frappe.get_doc(
		{
			"doctype": "Email Template",
			"name": name,
			"subject": "Update on {{ job_name }}",
			"response": "<p>Hello {{ candidate_name }}, you are now at {{ stage_name }}.</p>",
		}
	).insert()


def job_with_email(title, stage, template):
	job = make_job(title).insert()
	for row in job.pipeline_stages:
		if row.stage_name == stage:
			row.auto_email_template = template
	job.save()
	return job


class TestStageEmail(IntegrationTestCase):
	def test_email_is_sent_when_a_stage_with_a_template_is_entered(self):
		template = make_template()
		job = job_with_email("_Test Email Job A", "Technical Assessment", template.name)
		applicant = new_applicant(job, "mail.a@example.com")
		with patch("hrms.ats.mail.make_system_communication") as sendmail:
			move_stage(applicant.name, "Technical Assessment")
		sendmail.assert_called_once()
		kwargs = sendmail.call_args.kwargs
		self.assertEqual(kwargs["recipients"], ["mail.a@example.com"])
		self.assertIn("Update on _Test Email Job A", kwargs["subject"])
		self.assertIn("Stage Tester", kwargs["content"])
		self.assertIn("Technical Assessment", kwargs["content"])
		self.assertEqual((kwargs["doctype"], kwargs["name"]), ("Job Applicant", applicant.name))

	def test_no_email_for_a_stage_without_a_template(self):
		template = make_template()
		job = job_with_email("_Test Email Job B", "Technical Assessment", template.name)
		applicant = new_applicant(job, "mail.b@example.com")
		with patch("hrms.ats.mail.make_system_communication") as sendmail:
			move_stage(applicant.name, "Final Interview")
		sendmail.assert_not_called()

	def test_new_applicant_gets_the_first_stage_email(self):
		template = make_template()
		job = job_with_email("_Test Email Job C", "New Candidates", template.name)
		with patch("hrms.ats.mail.make_system_communication") as sendmail:
			new_applicant(job, "mail.c@example.com")
		sendmail.assert_called_once()

	def test_a_failing_email_does_not_stop_the_move(self):
		template = make_template()
		job = job_with_email("_Test Email Job D", "Technical Assessment", template.name)
		applicant = new_applicant(job, "mail.d@example.com")
		with patch("hrms.ats.mail.make_system_communication", side_effect=Exception("smtp down")):
			moved = move_stage(applicant.name, "Technical Assessment")
		self.assertEqual(moved.pipeline_stage, "Technical Assessment")

	def test_skip_flag_suppresses_the_email(self):
		template = make_template()
		job = job_with_email("_Test Email Job E", "Technical Assessment", template.name)
		applicant = new_applicant(job, "mail.e@example.com")
		doc = frappe.get_doc("Job Applicant", applicant.name)
		doc.pipeline_stage = "Technical Assessment"
		doc.flags.ats_skip_email = True
		with patch("hrms.ats.mail.make_system_communication") as sendmail:
			doc.save()
		sendmail.assert_not_called()

	def test_no_email_when_stage_does_not_change(self):
		template = make_template()
		job = job_with_email("_Test Email Job F", "New Candidates", template.name)
		with patch("hrms.ats.mail.make_system_communication"):
			applicant = new_applicant(job, "mail.f@example.com")
		with patch("hrms.ats.mail.make_system_communication") as sendmail:
			applicant.reload()
			applicant.applicant_rating = 0.4
			applicant.save()
		sendmail.assert_not_called()
