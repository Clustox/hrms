# Copyright (c) 2026, Clustox and contributors
# See license.txt

from unittest.mock import patch

import random

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.candidates import default_full_name, get_or_create_candidate
from hrms.ats.test_pipeline import make_job


def apply(job, email, **kwargs):
	return frappe.get_doc(
		{"doctype": "Job Applicant", "applicant_name": kwargs.pop("name", "Link Tester"), "email_id": email, "job_title": job.name, **kwargs}
	).insert()


def candidate_of(applicant):
	return frappe.db.get_value("Job Applicant", applicant.name, "candidate")


class TestNewApplicantGetsACandidate(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Link Job").insert()

	def test_first_application_creates_a_candidate_with_the_applicants_details(self):
		applicant = apply(self.job, "first.time@example.com", phone_number="0300 1112233", source="Walk In")
		candidate = frappe.get_doc("Candidate", candidate_of(applicant))
		self.assertEqual(
			(candidate.full_name, candidate.email, candidate.phone, candidate.source),
			("Link Tester", "first.time@example.com", "0300 1112233", "Walk In"),
		)

	def test_same_person_on_a_second_job_shares_the_candidate(self):
		other = make_job("_Test Link Job 2").insert()
		first = apply(self.job, "twice.apply@example.com")
		second = apply(other, "Twice.Apply@Example.com")  # same email in another case
		self.assertEqual(candidate_of(first), candidate_of(second))
		self.assertEqual(frappe.db.count("Candidate", {"email_normalized": "twice.apply@example.com"}), 1)

	def test_same_phone_with_another_email_shares_the_candidate(self):
		other = make_job("_Test Link Job 3").insert()
		first = apply(self.job, "phone.one@example.com", phone_number="+92 300 5550101")
		second = apply(other, "phone.two@example.com", phone_number="0300-5550101")
		self.assertEqual(candidate_of(first), candidate_of(second))

	def test_applicant_that_already_names_a_candidate_is_left_alone(self):
		chosen = frappe.get_doc({"doctype": "Candidate", "full_name": "Chosen", "email": "chosen@example.com"}).insert()
		applicant = apply(self.job, "someone.else@example.com", candidate=chosen.name)
		self.assertEqual(candidate_of(applicant), chosen.name)
		self.assertFalse(frappe.db.exists("Candidate", {"email_normalized": "someone.else@example.com"}))

	def test_missing_name_is_guessed_from_the_email(self):
		applicant = apply(self.job, "hira.khan@example.com", name="")
		self.assertEqual(frappe.db.get_value("Candidate", candidate_of(applicant), "full_name"), "Hira Khan")

	def test_the_web_form_application_records_the_website_source(self):
		frappe.flags.in_web_form = True
		try:
			applicant = apply(self.job, "web.form@example.com")
		finally:
			frappe.flags.in_web_form = False
		self.assertEqual(frappe.db.get_value("Candidate", candidate_of(applicant), "source"), "Website Listing")


class TestExistingCandidateIsNeverOverwritten(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Link Keep").insert()
		self.email = f"keep.{frappe.generate_hash(length=6)}@example.com"  # tests share one transaction
		self.phone = f"030{random.randint(1000000, 9999999)}"
		self.candidate = frappe.get_doc(
			{
				"doctype": "Candidate",
				"full_name": "Original Name",
				"email": self.email,
				"phone": self.phone,
				"current_title": "Lead",
				"current_employer": "Arbisoft",
				"source": "Campaign",
			}
		).insert()

	def test_nothing_the_candidate_already_has_is_replaced(self):
		apply(self.job, self.email, name="Different Name", phone_number="0399 8887776", source="Walk In")
		self.candidate.reload()
		self.assertEqual(
			(self.candidate.full_name, self.candidate.phone, self.candidate.source, self.candidate.current_title),
			("Original Name", self.phone, "Campaign", "Lead"),
		)

	def test_blanks_are_filled_from_the_new_application(self):
		new_phone = f"031{random.randint(1000000, 9999999)}"
		blank_email = f"blank.{frappe.generate_hash(length=6)}@example.com"
		blank = frappe.get_doc({"doctype": "Candidate", "full_name": "Blank One", "email": blank_email}).insert()
		apply(self.job, blank_email, phone_number=new_phone, source="Walk In")
		blank.reload()
		self.assertEqual((blank.phone, blank.source), (new_phone, "Walk In"))

	def test_a_phone_that_belongs_to_another_candidate_is_not_copied(self):
		other = frappe.get_doc({"doctype": "Candidate", "full_name": "Phone Owner", "email": "phone.owner@example.com", "phone": "0302 1110001"}).insert()
		blank = frappe.get_doc({"doctype": "Candidate", "full_name": "No Phone", "email": "no.phone.cand@example.com"}).insert()
		apply(self.job, "no.phone.cand@example.com", phone_number="0302 1110001")  # matches by email first
		blank.reload()
		self.assertFalse(blank.phone)
		self.assertEqual(other.phone, "0302 1110001")


class TestGetOrCreateCandidate(IntegrationTestCase):
	def test_nothing_to_go_on_gives_no_candidate(self):
		self.assertIsNone(get_or_create_candidate(None, None))
		self.assertIsNone(get_or_create_candidate("", "123"))

	def test_a_simultaneous_duplicate_uses_the_winner(self):
		winner = frappe.get_doc({"doctype": "Candidate", "full_name": "Winner", "email": "race@example.com"}).insert()
		# the first look finds nobody (the other request has not committed yet), the second finds the winner
		with patch("hrms.ats.candidates.find_duplicate", side_effect=[None, winner.name]):
			self.assertEqual(get_or_create_candidate("race@example.com", None, "Loser"), winner.name)

	def test_a_real_error_is_not_swallowed(self):
		with patch("hrms.ats.candidates.find_duplicate", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				get_or_create_candidate("not-an-email", None, "Bad")

	def test_default_name(self):
		self.assertEqual(default_full_name("  Sana Ali ", "x@y.com"), "Sana Ali")
		self.assertEqual(default_full_name(None, "usman_raza@example.com"), "Usman Raza")
		self.assertEqual(default_full_name("", "plain@example.com"), "Plain")
