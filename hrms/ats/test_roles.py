# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.desk.form.load import getdoc
from frappe.tests import IntegrationTestCase

from hrms.ats.roles import (
	GUEST,
	RECRUITER,
	ROLES,
	SALARY_VIEWER,
	apply_roles_and_permissions,
)
from hrms.ats.test_pipeline import make_job


def make_user(*roles):
	email = f"role.{frappe.generate_hash(length=8)}@example.com"
	return frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Role Test",
			"send_welcome_email": 0,
			"enabled": 1,
			"roles": [{"role": r} for r in roles],
		}
	).insert(ignore_permissions=True).name


def can(user, doctype, ptype, doc=None):
	return bool(frappe.has_permission(doctype, ptype, doc=doc, user=user))


def salary_seen_by(user, job):
	"""The salary range a user receives when they open a job."""
	frappe.set_user(user)
	try:
		frappe.response.docs = []
		getdoc("Job Opening", job)
		doc = frappe.response.docs[0].as_dict()
		return doc.get("lower_range"), doc.get("upper_range")
	finally:
		frappe.set_user("Administrator")


class TestRolesExist(IntegrationTestCase):
	def test_the_three_roles_exist_with_desk_access(self):
		for role in ROLES:
			self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), 1, role)

	def test_applying_twice_adds_no_duplicate_rules(self):
		def rows():
			return frappe.db.count("Custom DocPerm", {"role": ["in", list(ROLES)]})

		before = rows()
		apply_roles_and_permissions(commit=False)
		self.assertEqual(rows(), before)


class TestRecruiter(IntegrationTestCase):
	def setUp(self):
		self.user = make_user(RECRUITER)

	def test_works_the_pipeline_but_cannot_delete(self):
		for doctype in ("Job Opening", "Job Applicant", "Candidate", "Interview"):
			for ptype in ("read", "write", "create"):
				self.assertTrue(can(self.user, doctype, ptype), f"{doctype} {ptype}")
			self.assertFalse(can(self.user, doctype, "delete"), f"{doctype} delete")

	def test_cannot_reach_employee_leave_or_payroll_data(self):
		for doctype in ("Employee", "Leave Application", "Salary Slip", "Attendance", "Expense Claim"):
			self.assertFalse(can(self.user, doctype, "read"), doctype)

	def test_can_create_a_job_with_its_links(self):
		job = make_job("_Test Recruiter Job", department=frappe.db.get_value("Department", {"is_group": 0}, "name"))
		frappe.set_user(self.user)  # make_job also prepares the designation, so build it first
		try:
			job.insert()
			self.assertTrue(job.name)
		finally:
			frappe.set_user("Administrator")

	def test_sees_the_salary_range(self):
		job = make_job("_Test Salary Recruiter", lower_range=111000, upper_range=222000).insert()
		self.assertEqual(salary_seen_by(self.user, job.name), (111000, 222000))


class TestGuestRole(IntegrationTestCase):
	def setUp(self):
		self.user = make_user(GUEST)

	def test_can_read_but_never_change_recruitment_records(self):
		for doctype in ("Job Opening", "Job Applicant", "Candidate", "Interview"):
			self.assertTrue(can(self.user, doctype, "read"), f"{doctype} read")
			for ptype in ("write", "create", "delete", "submit"):
				self.assertFalse(can(self.user, doctype, ptype), f"{doctype} {ptype}")

	def test_cannot_read_anything_else_in_hr(self):
		for doctype in ("Job Offer", "Staffing Plan", "Job Requisition", "Employee", "Salary Slip", "Leave Application",
				"ATS Pipeline Template", "Drop Reason", "Applicant Stage Log", "Employee Referral", "Appointment Letter"):
			self.assertFalse(can(self.user, doctype, "read"), doctype)

	def test_can_write_feedback_of_their_own_only(self):
		self.assertTrue(can(self.user, "Interview Feedback", "create"))
		own = frappe.get_doc({"doctype": "Interview Feedback", "owner": self.user})
		theirs = frappe.get_doc({"doctype": "Interview Feedback", "owner": "Administrator"})
		self.assertTrue(can(self.user, "Interview Feedback", "write", doc=own))
		self.assertFalse(can(self.user, "Interview Feedback", "read", doc=theirs))
		self.assertFalse(can(self.user, "Interview Feedback", "write", doc=theirs))

	def test_does_not_see_the_salary_range(self):
		job = make_job("_Test Salary Guest", lower_range=111000, upper_range=222000).insert()
		self.assertEqual(salary_seen_by(self.user, job.name), (0, 0))

	def test_gets_the_salary_only_with_the_salary_viewer_role(self):
		viewer = make_user(GUEST, SALARY_VIEWER)
		job = make_job("_Test Salary Viewer", lower_range=111000, upper_range=222000).insert()
		self.assertEqual(salary_seen_by(viewer, job.name), (111000, 222000))


class TestSalaryProtection(IntegrationTestCase):
	def test_hr_roles_keep_seeing_salary(self):
		job = make_job("_Test Salary HR", lower_range=111000, upper_range=222000).insert()
		for role in ("HR User", "HR Manager", "System Manager"):
			self.assertEqual(salary_seen_by(make_user(role), job.name), (111000, 222000), role)

	def test_salary_fields_are_on_the_protected_level(self):
		for doctype in ("Job Opening", "Job Applicant"):
			meta = frappe.get_meta(doctype)
			for fieldname in ("lower_range", "upper_range"):
				self.assertEqual(meta.get_field(fieldname).permlevel, 1, f"{doctype}.{fieldname}")

	def test_other_job_fields_stay_visible_to_a_guest(self):
		job = make_job("_Test Salary Other Fields").insert()
		frappe.set_user(make_user(GUEST))
		try:
			frappe.response.docs = []
			getdoc("Job Opening", job.name)
			doc = frappe.response.docs[0].as_dict()
			self.assertTrue(doc.job_title.startswith("_Test Salary Other Fields"))
			self.assertEqual(doc.status, "Open")
		finally:
			frappe.set_user("Administrator")


class TestExistingHrRolesKeepTheirRights(IntegrationTestCase):
	"""Giving the ATS roles permissions copies the standard rules into editable ones; nothing may be lost."""

	def test_hr_user_still_works_recruitment(self):
		user = make_user("HR User")
		for doctype in ("Job Opening", "Job Applicant", "Interview", "Job Offer", "Staffing Plan", "Job Requisition"):
			self.assertTrue(can(user, doctype, "read"), f"{doctype} read")
		for doctype in ("Job Opening", "Job Applicant", "Interview"):
			self.assertTrue(can(user, doctype, "write"), f"{doctype} write")
			self.assertTrue(can(user, doctype, "create"), f"{doctype} create")

	def test_hr_manager_can_still_delete_jobs_and_applicants(self):
		user = make_user("HR Manager")
		for doctype in ("Job Opening", "Job Applicant"):
			self.assertTrue(can(user, doctype, "delete"), doctype)

	def test_hr_user_still_cannot_delete_jobs(self):
		self.assertFalse(can(make_user("HR User"), "Job Opening", "delete"))

	def test_the_interviewer_role_is_unchanged(self):
		user = make_user("Interviewer")
		self.assertTrue(can(user, "Interview", "read"))
		self.assertFalse(can(user, "Job Applicant", "read"))  # it never could


class TestPublicSiteStillWorks(IntegrationTestCase):
	def test_the_public_apply_form_can_still_store_a_salary_expectation(self):
		job = make_job("_Test Public Apply").insert()
		doc = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"applicant_name": "Public Applicant",
				"email_id": f"public.{frappe.generate_hash(length=8)}@example.com",
				"job_title": job.name,
				"lower_range": 90000,
				"upper_range": 120000,
			}
		)
		frappe.set_user("Guest")
		try:
			doc.flags.ignore_permissions = True  # what the web form does
			doc.insert()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Job Applicant", doc.name, "lower_range"), 90000)

	def test_the_public_job_list_still_shows_a_published_salary_range(self):
		from hrms.www.jobs.index import get_job_openings

		job = make_job("_Test Public Salary", publish=1, publish_salary_range=1, lower_range=70000, upper_range=95000).insert()
		frappe.set_user("Guest")
		try:
			rows = get_job_openings({}, None, None, 100, 0)
		finally:
			frappe.set_user("Administrator")
		row = next(r for r in rows if r.name == job.name)
		self.assertEqual((row.lower_range, row.upper_range), (70000, 95000))
