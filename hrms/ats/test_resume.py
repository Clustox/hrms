# Copyright (c) 2026, Clustox and contributors
# See license.txt

import io
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.resume import (
	MAX_TEXT_CHARS,
	extract_missing_resume_text,
	extract_text,
	refresh_resume_text,
	search_candidates,
	search_words,
)


def make_pdf(text: str) -> bytes:
	"""A one-page PDF containing the text (built by hand so the test needs no PDF library)."""
	stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
	objects = [
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
		b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
	]
	out = io.BytesIO()
	out.write(b"%PDF-1.4\n")
	offsets = []
	for number, body in enumerate(objects, start=1):
		offsets.append(out.tell())
		out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
	xref = out.tell()
	out.write(f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n")
	for offset in offsets:
		out.write(f"{offset:010d} 00000 n \n".encode())
	out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
	return out.getvalue()


def make_docx(*paragraphs: str) -> bytes:
	ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
	body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
	document = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
	out = io.BytesIO()
	with zipfile.ZipFile(out, "w") as archive:
		archive.writestr("word/document.xml", document)
	return out.getvalue()


def make_file(name: str, content: bytes) -> str:
	return frappe.get_doc({"doctype": "File", "file_name": name, "content": content, "is_private": 1}).insert(ignore_permissions=True).file_url


def make_candidate(resume_url=None, **kwargs):
	return frappe.get_doc(
		{"doctype": "Candidate", "full_name": "Resume Person", "email": f"resume.{frappe.generate_hash(length=8)}@example.com", "resume": resume_url, **kwargs}
	).insert()


class TestExtractText(IntegrationTestCase):
	def test_pdf(self):
		self.assertIn("Python developer", extract_text(make_pdf("Senior Python developer at Arbisoft"), "cv.pdf"))

	def test_docx_joins_paragraphs(self):
		text = extract_text(make_docx("Jane Doe", "QA Engineer", "Selenium and Cypress"), "cv.docx")
		self.assertEqual(text, "Jane Doe QA Engineer Selenium and Cypress")

	def test_plain_text_and_whitespace_is_tidied(self):
		self.assertEqual(extract_text(b"  Business   Analyst \n\n  SQL  ", "cv.txt"), "Business Analyst SQL")

	def test_text_that_is_already_decoded_is_accepted(self):
		self.assertEqual(extract_text("Decoded text résumé", "cv.txt"), "Decoded text résumé")

	def test_extension_is_not_case_sensitive(self):
		self.assertEqual(extract_text(b"hello", "CV.TXT"), "hello")

	def test_unsupported_types_give_no_text_and_no_error(self):
		for name in ("scan.png", "old.doc", "notes.odt", "noextension"):
			self.assertEqual(extract_text(b"\x89PNG....", name), "", name)

	def test_a_corrupted_file_gives_no_text_and_no_error(self):
		self.assertEqual(extract_text(b"this is not a pdf", "broken.pdf"), "")
		self.assertEqual(extract_text(b"this is not a zip", "broken.docx"), "")

	def test_empty_and_oversized_files_are_skipped(self):
		self.assertEqual(extract_text(b"", "empty.txt"), "")
		with patch("hrms.ats.resume.MAX_FILE_BYTES", 10):
			self.assertEqual(extract_text(b"x" * 11, "big.txt"), "")

	def test_very_long_text_is_cut(self):
		self.assertEqual(len(extract_text(b"a" * (MAX_TEXT_CHARS + 500), "long.txt")), MAX_TEXT_CHARS)


class TestRefreshResumeText(IntegrationTestCase):
	def test_stores_the_text_of_the_resume_file(self):
		url = make_file("cv.txt", b"Flutter and Dart mobile developer")
		candidate = make_candidate(url)
		self.assertEqual(refresh_resume_text(candidate.name), "Flutter and Dart mobile developer")
		self.assertEqual(frappe.db.get_value("Candidate", candidate.name, "resume_text"), "Flutter and Dart mobile developer")

	def test_a_new_resume_replaces_the_old_text(self):
		candidate = make_candidate(make_file("old.txt", b"Old resume words"))
		refresh_resume_text(candidate.name)
		frappe.db.set_value("Candidate", candidate.name, "resume", make_file("new.txt", b"Brand new resume"))
		self.assertEqual(refresh_resume_text(candidate.name), "Brand new resume")

	def test_removing_the_resume_clears_the_text(self):
		candidate = make_candidate(make_file("gone.txt", b"to be removed"))
		refresh_resume_text(candidate.name)
		frappe.db.set_value("Candidate", candidate.name, "resume", None)
		self.assertEqual(refresh_resume_text(candidate.name), "")

	def test_a_missing_file_is_not_an_error(self):
		candidate = make_candidate("/private/files/does-not-exist.pdf")
		self.assertEqual(refresh_resume_text(candidate.name), "")

	def test_candidate_without_resume(self):
		self.assertEqual(refresh_resume_text(make_candidate().name), "")


class TestQueueing(IntegrationTestCase):
	def test_a_new_resume_is_read_in_the_background(self):
		url = make_file("queue.txt", b"queued words")
		with patch("hrms.ats.resume.frappe.enqueue") as enqueue:
			candidate = make_candidate(url)
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.args[0], "hrms.ats.resume.refresh_resume_text")
		self.assertEqual(enqueue.call_args.kwargs["candidate"], candidate.name)

	def test_other_edits_do_not_read_the_resume_again(self):
		url = make_file("same.txt", b"same words")
		with patch("hrms.ats.resume.frappe.enqueue"):
			candidate = make_candidate(url)
		with patch("hrms.ats.resume.frappe.enqueue") as enqueue:
			candidate.current_title = "Engineer"
			candidate.save()
		enqueue.assert_not_called()

	def test_changing_the_resume_reads_it_again(self):
		with patch("hrms.ats.resume.frappe.enqueue"):
			candidate = make_candidate(make_file("first.txt", b"first"))
		with patch("hrms.ats.resume.frappe.enqueue") as enqueue:
			candidate.resume = make_file("second.txt", b"second")
			candidate.save()
		enqueue.assert_called_once()

	def test_a_candidate_without_a_resume_queues_nothing(self):
		with patch("hrms.ats.resume.frappe.enqueue") as enqueue:
			make_candidate()
		enqueue.assert_not_called()


class TestSearch(IntegrationTestCase):
	def setUp(self):
		self.token = f"zq{frappe.generate_hash(length=8)}"  # a word no other resume contains

	def candidate_with(self, text):
		candidate = make_candidate(make_file("search.txt", text.encode()))
		refresh_resume_text(candidate.name)
		return candidate.name

	def test_finds_a_candidate_by_a_word_in_the_resume(self):
		name = self.candidate_with(f"Backend developer {self.token} Django")
		self.assertEqual(search_candidates(self.token), [name])

	def test_every_word_must_match(self):
		name = self.candidate_with(f"{self.token} Django REST")
		self.assertEqual(search_candidates(f"{self.token} django"), [name])
		self.assertEqual(search_candidates(f"{self.token} kubernetes"), [])

	def test_search_ignores_case_and_matches_part_of_a_word(self):
		name = self.candidate_with(f"Experienced {self.token}Engineer")
		self.assertEqual(search_candidates(self.token.upper()), [name])

	def test_only_candidates_with_the_word_are_returned(self):
		mine = self.candidate_with(f"{self.token} analyst")
		self.candidate_with("someone else entirely")
		self.assertEqual(search_candidates(self.token), [mine])

	def test_nothing_to_search_for_gives_nothing(self):
		self.candidate_with("anything at all")
		for text in ("", "   ", "a", "% _ %"):
			self.assertEqual(search_candidates(text), [], repr(text))

	def test_wildcard_characters_do_not_match_everything(self):
		self.candidate_with("plain words")
		self.assertEqual(search_candidates("%%"), [])

	def test_a_user_without_candidate_access_cannot_search(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "resume.noperm@example.com", "first_name": "No Perm", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				search_candidates("anything")
		finally:
			frappe.set_user("Administrator")

	def test_search_words(self):
		self.assertEqual(search_words("  Django, REST-API  a  c# "), ["django", "rest", "api"])


class TestExtractMissing(IntegrationTestCase):
	def test_only_candidates_with_a_resume_and_no_text_are_read(self):
		todo = make_candidate(make_file("todo.txt", b"read me"))
		done = make_candidate(make_file("done.txt", b"already read"))
		frappe.db.set_value("Candidate", done.name, "resume_text", "already read")
		without = make_candidate()
		self.assertGreaterEqual(extract_missing_resume_text(), 1)
		self.assertEqual(frappe.db.get_value("Candidate", todo.name, "resume_text"), "read me")
		self.assertFalse(frappe.db.get_value("Candidate", without.name, "resume_text"))

	def test_running_twice_reads_nothing_new(self):
		make_candidate(make_file("once.txt", b"only once"))
		extract_missing_resume_text()
		self.assertEqual(extract_missing_resume_text(), 0)
