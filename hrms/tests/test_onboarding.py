import frappe
from frappe.tests.utils import FrappeTestCase


class TestOnboardingSchema(FrappeTestCase):
	def test_onboarding_fields_exist(self):
		from setup.onboarding.apply_onboarding_schema import run
		run()
		meta = frappe.get_meta("Employee")
		for fn in ("custom_onboarding_status", "custom_onboarding_submitted_on",
		           "custom_onboarding_notes", "custom_onboarding_documents"):
			self.assertTrue(meta.get_field(fn), f"missing Employee.{fn}")
		self.assertTrue(frappe.get_meta("Employee Education").get_field("custom_certificate"))
		self.assertTrue(frappe.get_meta("Employee External Work History").get_field("custom_experience_letter"))
		self.assertTrue(frappe.db.exists("DocType", "Employee Onboarding Document"))


class TestValidateSubmission(FrappeTestCase):
	def _emp(self, **kw):
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Test", "last_name": "Hire",
			"company": "Clustox", "status": "Active",
			"date_of_joining": "2026-01-01", "gender": "Male",
			"date_of_birth": "1995-01-01",
			**kw,
		}).insert(ignore_permissions=True)
		return emp.name

	def test_missing_fields_listed(self):
		from hrms.onboarding import validate_onboarding_submission
		name = self._emp()
		missing = validate_onboarding_submission(name)
		self.assertIn("CNIC", " ".join(missing))
		self.assertIn("Blood Group", " ".join(missing))

	def test_complete_returns_empty(self):
		from hrms.onboarding import validate_onboarding_submission
		name = self._emp(custom_cnic_no="1234512345671", custom_cnic_expiry_date="2030-01-01",
		                 current_address="A", permanent_address="B", blood_group="O+",
		                 person_to_be_contacted="X", emergency_phone_number="0300",
		                 relation="Father")
		self.assertEqual(validate_onboarding_submission(name), [])


class TestOnboardEmployee(FrappeTestCase):
	def test_provisions_login_and_status(self):
		from hrms.onboarding import onboard_employee
		email = "test.hire.onb@example.com"
		frappe.db.delete("User", {"name": email})
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Onb", "last_name": "Hire",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "company_email": email,
		}).insert(ignore_permissions=True)
		res = onboard_employee(emp.name, send_invite=0)
		self.assertEqual(res["status"], "Invited")
		self.assertTrue(frappe.db.exists("User", email))
		self.assertEqual(frappe.db.get_value("Employee", emp.name, "custom_onboarding_status"), "Invited")
		self.assertEqual(frappe.db.get_value("Employee", emp.name, "user_id"), email)
		self.assertIn("Employee Self Service", frappe.get_roles(email))


class TestTransitions(FrappeTestCase):
	def _hire(self, complete):
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Trans", "last_name": "Hire",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "custom_onboarding_status": "Invited",
		})
		if complete:
			emp.update({"custom_cnic_no": "1", "custom_cnic_expiry_date": "2030-01-01",
			            "current_address": "A", "permanent_address": "B", "blood_group": "O+",
			            "person_to_be_contacted": "X", "emergency_phone_number": "0300",
			            "relation": "Father"})
		return emp.insert(ignore_permissions=True).name

	def test_submit_blocked_when_incomplete(self):
		from hrms.onboarding import submit_onboarding
		name = self._hire(complete=False)
		with self.assertRaises(frappe.ValidationError):
			submit_onboarding(name)
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_status"), "Invited")

	def test_submit_then_approve(self):
		from hrms.onboarding import submit_onboarding, approve_onboarding
		name = self._hire(complete=True)
		self.assertEqual(submit_onboarding(name)["status"], "Submitted")
		self.assertEqual(approve_onboarding(name)["status"], "Approved")

	def test_request_changes_reverts(self):
		from hrms.onboarding import submit_onboarding, request_onboarding_changes
		name = self._hire(complete=True)
		submit_onboarding(name)
		request_onboarding_changes(name, "Fix your CNIC scan")
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_status"), "Invited")
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_notes"), "Fix your CNIC scan")


class TestEssPerms(FrappeTestCase):
	def test_ess_can_write_own_cnic(self):
		from setup.permissions.apply_self_service import run as apply_ess
		apply_ess()
		email = "ess.perm.onb@example.com"
		frappe.db.delete("User", {"name": email})
		# NOTE: order matters — erpnext's validate_employee_role (a User.validate
		# hook) strips the Employee/Employee Self Service role from any user not
		# yet linked to an Employee. Create the User, then the Employee with
		# user_id set (linking it), THEN add the role — otherwise it gets stripped.
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Ess",
		                       "send_welcome_email": 0, "user_type": "System User"})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		emp = frappe.get_doc({"doctype": "Employee", "first_name": "Ess", "last_name": "Perm",
		                      "company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
		                      "gender": "Male", "date_of_birth": "1995-01-01",
		                      "user_id": email}).insert(ignore_permissions=True)
		user.reload()  # Employee.insert (user_id link) may have updated the User doc
		user.add_roles("Employee Self Service")
		self.assertIn("Employee Self Service", frappe.get_roles(email))
		# Employee.create_user_permission defaults to 1, so linking user_id on insert
		# already auto-created the scoping User Permission (Employee.update_user_permissions).
		# Only add it ourselves if that did not happen.
		if not frappe.db.exists("User Permission", {"user": email, "allow": "Employee", "for_value": emp.name}):
			frappe.get_doc({"doctype": "User Permission", "user": email, "allow": "Employee",
			                "for_value": emp.name, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)
		self.assertTrue(frappe.has_permission("Employee", "write", doc=emp.name, user=email))
