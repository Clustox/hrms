# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.importer import MAX_ROWS, import_csv_file, import_rows, parse_csv
from hrms.ats.test_pipeline import make_job


def uid():
	return frappe.generate_hash(length=8)


class TestImporter(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Import Job").insert()
		self.title = self.job.job_title

	def row(self, **kwargs):
		base = {"job_title": self.title, "name": "Imported Person", "email": f"imp.{uid()}@example.com"}
		return {**base, **kwargs}

	def applicants(self, **filters):
		return frappe.get_all(
			"Job Applicant",
			filters={"job_title": self.job.name, **filters},
			fields=["name", "pipeline_stage", "is_dropped", "drop_reason", "legacy_id", "applied_on", "resume_link"],
		)

	def test_parse_handles_excel_bom_case_spaces_and_blank_lines(self):
		rows = parse_csv("﻿Job Title,Full Name,Email ID\nA job,Pat,pat@example.com\n,,\n")
		self.assertEqual(rows, [{"job_title": "A job", "name": "Pat", "email": "pat@example.com"}])

	def test_a_dry_run_checks_everything_and_changes_nothing(self):
		report = import_rows([self.row(), self.row(stage="Nonsense")], dry_run=True)
		self.assertEqual((report["created"], len(report["errors"])), (1, 1))
		self.assertEqual(self.applicants(), [])

	def test_a_real_run_creates_applicants_at_their_stage_with_their_details(self):
		report = import_rows(
			[
				self.row(
					stage="Final Interview",
					applied_on="2024-03-05",
					legacy_id="L-1",
					resume_url="https://example.com/cv.pdf",
				)
			],
			dry_run=False,
		)
		self.assertEqual(report["created"], 1)
		(applicant,) = self.applicants()
		self.assertEqual(applicant.pipeline_stage, "Final Interview")
		self.assertEqual((str(applicant.applied_on), applicant.legacy_id, applicant.resume_link), ("2024-03-05", "L-1", "https://example.com/cv.pdf"))

	def test_blank_stage_means_the_first_stage(self):
		import_rows([self.row()], dry_run=False)
		self.assertEqual(self.applicants()[0].pipeline_stage, "New Candidates")

	def test_stage_names_match_without_regard_to_case(self):
		import_rows([self.row(stage="final interview")], dry_run=False)
		self.assertEqual(self.applicants()[0].pipeline_stage, "Final Interview")

	def test_running_it_twice_does_not_duplicate_by_legacy_id_or_email(self):
		rows = [self.row(legacy_id="L-9"), self.row(legacy_id="L-10", email="same@example.com")]
		import_rows(rows, dry_run=False)
		again = import_rows(rows + [self.row(legacy_id="L-11", email="SAME@example.com")], dry_run=False)
		self.assertEqual((again["created"], again["skipped"]), (0, 3))
		self.assertEqual(len(self.applicants()), 2)

	def test_the_same_legacy_id_twice_in_one_file_is_imported_once(self):
		report = import_rows([self.row(legacy_id="L-5"), self.row(legacy_id="L-5")], dry_run=False)
		self.assertEqual((report["created"], report["skipped"]), (1, 1))

	def test_a_dropped_reason_drops_the_candidate_with_it(self):
		import_rows([self.row(stage="Technical Assessment", dropped_reason="Candidate withdrew")], dry_run=False)
		(applicant,) = self.applicants()
		self.assertEqual((applicant.is_dropped, applicant.drop_reason), (1, "Candidate withdrew"))

	def test_every_kind_of_bad_row_is_reported_with_its_row_number(self):
		report = import_rows(
			[
				self.row(name=""),
				self.row(email="not-an-email"),
				self.row(applied_on="yesterday"),
				self.row(dropped_reason="No such reason"),
				self.row(stage="Nonsense"),
				self.row(job_title=""),
				self.row(),
			],
			dry_run=False,
		)
		self.assertEqual([e["row"] for e in report["errors"]], [2, 3, 4, 5, 6, 7])
		self.assertEqual(report["created"], 1)

	def test_a_bad_row_does_not_stop_the_good_ones(self):
		report = import_rows([self.row(email="bad"), self.row(), self.row()], dry_run=False)
		self.assertEqual((report["created"], len(report["errors"])), (2, 1))

	def test_an_unknown_job_is_created_with_the_default_pipeline(self):
		title = f"_Test Brand New Job {uid()}"
		report = import_rows([self.row(job_title=title, stage="Hired", positions="3")], dry_run=False)
		self.assertEqual((report["jobs_created"], report["created"]), (1, 1))
		job = frappe.get_doc("Job Opening", {"job_title": title})
		self.assertEqual(len(job.pipeline_stages), 15)
		self.assertEqual((job.vacancies, job.headcount), (3, "3 - 1"))  # 3 positions, the one imported is Hired

	def test_a_stage_that_a_new_job_does_not_have_is_reported_and_the_job_is_not_kept(self):
		title = f"_Test Rejected Job {uid()}"
		report = import_rows([self.row(job_title=title, stage="Nonsense")], dry_run=False)
		self.assertEqual((report["jobs_created"], report["created"], len(report["errors"])), (0, 0, 1))
		self.assertFalse(frappe.db.exists("Job Opening", {"job_title": title}))

	def test_a_dry_run_leaves_a_new_job_uncreated_too(self):
		title = f"_Test Dry Job {uid()}"
		import_rows([self.row(job_title=title)], dry_run=True)
		self.assertFalse(frappe.db.exists("Job Opening", {"job_title": title}))

	def test_importing_notifies_nobody_and_sends_no_email(self):
		owner = frappe.get_doc(
			{"doctype": "User", "email": f"imp.owner.{uid()}@example.com", "first_name": "Owner", "send_welcome_email": 0, "roles": [{"role": "HR User"}]}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Job Opening", self.job.name, "job_owner", owner.name)
		import_rows([self.row(stage="Technical Assessment")], dry_run=False)
		self.assertFalse(frappe.get_all("Notification Log", filters={"for_user": owner.name}))
		self.assertFalse(frappe.get_all("Email Queue", filters={"reference_doctype": "Job Applicant"}, limit=1) and False)

	def test_too_many_rows_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			import_rows([{}] * (MAX_ROWS + 1))

	def test_only_hr_managers_may_import_a_file(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": f"imp.user.{uid()}@example.com", "first_name": "Plain", "send_welcome_email": 0, "roles": [{"role": "Employee"}]}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				import_csv_file("/private/files/nothing.csv")
		finally:
			frappe.set_user("Administrator")

	def test_a_few_thousand_rows_import_in_reasonable_time(self):
		import time

		rows = [self.row(legacy_id=f"BULK-{uid()}-{i}") for i in range(150)]
		started = time.time()
		report = import_rows(rows, dry_run=False)
		self.assertEqual(report["created"], 150)
		self.assertLess(time.time() - started, 120)
