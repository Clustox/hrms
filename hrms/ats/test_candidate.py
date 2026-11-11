# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.candidates import find_duplicate, normalize_email, normalize_phone


def make_candidate(email: str, phone: str | None = None, name: str = "Test Person"):
	return frappe.get_doc({"doctype": "Candidate", "full_name": name, "email": email, "phone": phone}).insert()


class TestCandidateNormalization(IntegrationTestCase):
	def test_email_normalization(self):
		self.assertEqual(normalize_email("  Ayesha.Khan@Example.COM "), "ayesha.khan@example.com")
		# only case and spaces are ignored: +tags and Gmail dots make a different address
		self.assertEqual(normalize_email("ayesha+jobs@example.com"), "ayesha+jobs@example.com")
		self.assertEqual(normalize_email("a.y.e.s.h.a@Gmail.com"), "a.y.e.s.h.a@gmail.com")
		self.assertEqual(normalize_email("a.y@googlemail.com"), "a.y@googlemail.com")
		self.assertEqual(normalize_email(None), "")

	def test_phone_normalization_pakistani_formats(self):
		for raw in ("+92 300 1234567", "0300-1234567", "00923001234567", "3001234567", "(92) 300 123 4567"):
			self.assertEqual(normalize_phone(raw), "923001234567", raw)

	def test_phone_other_and_missing(self):
		self.assertEqual(normalize_phone("+1 415 555 0100"), "14155550100")
		self.assertEqual(normalize_phone("12345"), "")
		self.assertEqual(normalize_phone(None), "")


class TestCandidate(IntegrationTestCase):
	def test_normalized_fields_are_stored(self):
		candidate = make_candidate("Fresh.Candidate@Example.com", "0300 1112223")
		self.assertEqual(candidate.email_normalized, "fresh.candidate@example.com")
		self.assertEqual(candidate.phone_normalized, "923001112223")

	def test_same_email_in_other_case_is_a_duplicate(self):
		make_candidate("dup.email@example.com")
		with self.assertRaises(frappe.ValidationError):
			make_candidate("  DUP.EMAIL@Example.com ", name="Same Person")

	def test_a_plus_tag_or_gmail_dots_make_a_different_person(self):
		first = make_candidate("tagged@example.com", name="One")
		self.assertNotEqual(make_candidate("tagged+jobs@example.com", name="Two").name, first.name)
		gmail = make_candidate("dotted.name@gmail.com", name="Three")
		self.assertNotEqual(make_candidate("dottedname@gmail.com", name="Four").name, gmail.name)

	def test_same_phone_in_other_format_is_a_duplicate(self):
		make_candidate("first.phone@example.com", "+92 301 5550001")
		with self.assertRaises(frappe.ValidationError):
			make_candidate("second.phone@example.com", "0301-5550001", name="Same Person")

	def test_missing_phone_never_matches(self):
		make_candidate("no.phone.a@example.com")
		make_candidate("no.phone.b@example.com")  # both without phone: not duplicates

	def test_find_duplicate_prefers_email_and_can_exclude_self(self):
		candidate = make_candidate("find.me@example.com", "0302 5550002")
		self.assertEqual(find_duplicate("FIND.ME@example.com", None), candidate.name)
		self.assertEqual(find_duplicate(None, "+92 302 5550002"), candidate.name)
		self.assertIsNone(find_duplicate("find.me@example.com", None, exclude=candidate.name))
		self.assertIsNone(find_duplicate("nobody@example.com", "0399 0000000"))

	def test_editing_a_candidate_is_not_a_duplicate_of_itself(self):
		candidate = make_candidate("edit.me@example.com", "0303 5550003")
		candidate.current_title = "QA Engineer"
		candidate.save()
		self.assertEqual(candidate.current_title, "QA Engineer")
