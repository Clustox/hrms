# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_log import make_applicant


class TestApplicantPipelineFields(IntegrationTestCase):
	def test_fields_exist_with_expected_types(self):
		meta = frappe.get_meta("Job Applicant")
		expected = {
			"pipeline_stage": "Data",
			"stage_entered_on": "Datetime",
			"is_dropped": "Check",
			"drop_reason": "Link",
			"dropped_at_stage": "Data",
			"department": "Link",
			"legacy_id": "Data",
		}
		for fieldname, fieldtype in expected.items():
			field = meta.get_field(fieldname)
			self.assertIsNotNone(field, fieldname)
			self.assertEqual(field.fieldtype, fieldtype, fieldname)

	def test_new_applicant_defaults(self):
		job = make_job("_Test Job Fields").insert()
		applicant = make_applicant(job, "fields.test@example.com")
		self.assertEqual(applicant.is_dropped, 0)
		self.assertFalse(applicant.drop_reason)

	def test_department_is_taken_from_the_job(self):
		department = frappe.db.get_value("Department", {"is_group": 0}, "name")
		job = make_job("_Test Job Dept", department=department).insert()
		applicant = make_applicant(job, "dept.test@example.com")
		self.assertEqual(applicant.department, department)

	def test_drop_requires_a_reason(self):
		job = make_job("_Test Job Drop").insert()
		applicant = make_applicant(job, "drop.test@example.com")
		applicant.is_dropped = 1
		self.assertRaises(frappe.MandatoryError, applicant.save)

	def test_board_index_exists(self):
		indexes = frappe.db.sql("show index from `tabJob Applicant` where Key_name = 'ats_job_stage_dropped'")
		self.assertEqual(len(indexes), 3)  # job_title, pipeline_stage, is_dropped

	def test_drop_records_stage_and_restore_clears_it(self):
		job = make_job("_Test Job Restore").insert()
		applicant = make_applicant(job, "restore.test@example.com")
		applicant.pipeline_stage = "Technical Assessment"
		applicant.is_dropped = 1
		applicant.drop_reason = "Candidate withdrew"
		applicant.save()
		self.assertEqual(applicant.dropped_at_stage, "Technical Assessment")

		applicant.is_dropped = 0
		applicant.save()
		self.assertFalse(applicant.drop_reason)
		self.assertFalse(applicant.dropped_at_stage)
