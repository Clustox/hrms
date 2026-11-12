# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from hrms.ats.backfill import backfill_pipeline, fill_card_dates
from hrms.ats.test_backfill import legacy_applicant, legacy_job
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def dates(name):
	return frappe.db.get_value("Job Applicant", name, ["applied_on", "stage_entered_date", "stage_entered_on"], as_dict=True)


class TestCardDates(IntegrationTestCase):
	def setUp(self):
		self.job = make_job("_Test Card Dates").insert()

	def test_the_card_dates_are_plain_dates(self):
		meta = frappe.get_meta("Job Applicant")
		self.assertEqual(meta.get_field("applied_on").fieldtype, "Date")
		self.assertEqual(meta.get_field("stage_entered_date").fieldtype, "Date")

	def test_new_applicant_gets_both_dates_set_to_today(self):
		name = new_applicant(self.job, "dates.new@example.com").name
		d = dates(name)
		self.assertEqual((d.applied_on, d.stage_entered_date), (getdate(nowdate()), getdate(nowdate())))
		self.assertTrue(d.stage_entered_on)  # the exact time is still kept

	def test_a_stage_move_updates_the_stage_date_but_not_the_applied_date(self):
		name = new_applicant(self.job, "dates.move@example.com").name
		frappe.db.set_value("Job Applicant", name, {"applied_on": add_days(nowdate(), -20), "stage_entered_date": add_days(nowdate(), -20)})
		move_stage(name, "Technical Assessment")
		d = dates(name)
		self.assertEqual(d.stage_entered_date, getdate(nowdate()))
		self.assertEqual(d.applied_on, getdate(add_days(nowdate(), -20)))

	def test_other_edits_leave_the_dates_alone(self):
		name = new_applicant(self.job, "dates.edit@example.com").name
		frappe.db.set_value("Job Applicant", name, "stage_entered_date", add_days(nowdate(), -5))
		doc = frappe.get_doc("Job Applicant", name)
		doc.applicant_rating = 0.6
		doc.save()
		self.assertEqual(dates(name).stage_entered_date, getdate(add_days(nowdate(), -5)))

	def test_a_status_driven_move_also_updates_the_stage_date(self):
		name = new_applicant(self.job, "dates.status@example.com").name
		frappe.db.set_value("Job Applicant", name, "stage_entered_date", add_days(nowdate(), -9))
		doc = frappe.get_doc("Job Applicant", name)
		doc.status = "Shortlisted"  # an older status write that moves the stage
		doc.save()
		self.assertEqual(dates(name).stage_entered_date, getdate(nowdate()))


class TestFillCardDates(IntegrationTestCase):
	def test_existing_applicants_get_their_dates_from_creation_and_stage_time(self):
		job = make_job("_Test Fill Dates").insert()
		name = new_applicant(job, "fill.dates@example.com").name
		frappe.db.set_value("Job Applicant", name, {"applied_on": None, "stage_entered_date": None})
		self.assertGreaterEqual(fill_card_dates(), 1)
		d = dates(name)
		self.assertEqual(d.applied_on, getdate(frappe.db.get_value("Job Applicant", name, "creation")))
		self.assertEqual(d.stage_entered_date, getdate(d.stage_entered_on))

	def test_running_twice_changes_nothing(self):
		fill_card_dates()
		self.assertEqual(fill_card_dates(), 0)

	def test_the_backfill_sets_both_dates_for_older_applicants(self):
		job = legacy_job("_Test Fill Dates Legacy")
		name = legacy_applicant(job, "fill.legacy@example.com", "Open")
		backfill_pipeline()
		d = dates(name)
		self.assertTrue(d.applied_on and d.stage_entered_date)
