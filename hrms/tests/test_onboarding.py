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
	def tearDown(self):
		frappe.set_user("Administrator")

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

	def test_requires_hr_role(self):
		from hrms.onboarding import onboard_employee

		# The target hire being onboarded (not the caller).
		target_email = "test.hire.onb.target@example.com"
		frappe.db.delete("User", {"name": target_email})
		target = frappe.get_doc({
			"doctype": "Employee", "first_name": "Target", "last_name": "Hire",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "company_email": target_email,
		}).insert(ignore_permissions=True)

		# A non-HR caller: an ESS user linked to their OWN, unrelated Employee record.
		# NOTE: onboard_employee/submit_onboarding commit the DB transaction on
		# their success paths, which can flatten earlier tests' rollback within
		# the same run -- so leftovers from a prior run must be cleared by
		# identity, not assumed away, exactly like TestSaveOnboardingFields.setUp.
		caller_email = "test.hire.onb.caller@example.com"
		frappe.db.delete("Employee", {"user_id": caller_email})
		frappe.db.delete("User", {"name": caller_email})
		frappe.db.commit()
		caller_user = frappe.get_doc({
			"doctype": "User", "email": caller_email, "first_name": "Caller", "last_name": "Ess",
			"send_welcome_email": 0, "user_type": "System User",
		})
		caller_user.flags.no_welcome_mail = True
		caller_user.insert(ignore_permissions=True)
		# Link Employee.user_id BEFORE granting the ESS role: erpnext's
		# validate_employee_role (User.validate hook) strips Employee/ESS
		# roles from a user with no matching Employee record yet.
		frappe.get_doc({
			"doctype": "Employee", "first_name": "Caller", "last_name": "Ess",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "user_id": caller_email,
		}).insert(ignore_permissions=True)
		caller_user.reload()
		caller_user.add_roles("Employee Self Service")
		self.assertIn("Employee Self Service", frappe.get_roles(caller_email))

		frappe.set_user(caller_email)
		with self.assertRaises(frappe.PermissionError):
			onboard_employee(target.name, send_invite=0)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("User", target_email))
		self.assertIsNone(frappe.db.get_value("Employee", target.name, "user_id") or None)

	def test_rerun_does_not_revert_approved_status(self):
		from hrms.onboarding import onboard_employee
		email = "test.hire.onb.approved@example.com"
		# onboard_employee commits on success (see NOTE in test_requires_hr_role
		# above), so leftovers from a prior run must be cleared by identity.
		frappe.db.delete("Employee", {"user_id": email})
		frappe.db.delete("Employee", {"company_email": email})
		frappe.db.delete("User", {"name": email})
		frappe.db.commit()
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Already", "last_name": "Approved",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "company_email": email,
			"custom_onboarding_status": "Approved",
		}).insert(ignore_permissions=True)

		# Re-running (e.g. to resend an invite) must not revert Approved -> Invited.
		res = onboard_employee(emp.name, send_invite=0)
		self.assertEqual(res["status"], "Approved")
		self.assertEqual(
			frappe.db.get_value("Employee", emp.name, "custom_onboarding_status"), "Approved"
		)


class TestTransitions(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

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

	def test_submit_blocked_for_non_owner_non_hr(self):
		from hrms.onboarding import submit_onboarding
		name = self._hire(complete=True)

		# Link the employee's owner (an ESS user) -- not the caller in this test,
		# just establishes that the hire has a real owner distinct from HR.
		# NOTE: leftovers from a prior run must be cleared by identity (same
		# reasoning as TestSaveOnboardingFields.setUp / test_requires_hr_role above).
		owner_email = "trans.owner@example.com"
		frappe.db.delete("Employee", {"user_id": owner_email})
		frappe.db.delete("User", {"name": owner_email})
		frappe.db.commit()
		owner_user = frappe.get_doc({
			"doctype": "User", "email": owner_email, "first_name": "Trans", "last_name": "Owner",
			"send_welcome_email": 0, "user_type": "System User",
		})
		owner_user.flags.no_welcome_mail = True
		owner_user.insert(ignore_permissions=True)
		# Link Employee.user_id BEFORE granting the ESS role -- see the ordering
		# lesson noted on TestEssPerms/TestSaveOnboardingFields above.
		frappe.db.set_value("Employee", name, "user_id", owner_email)
		owner_user.reload()
		owner_user.add_roles("Employee Self Service")
		self.assertIn("Employee Self Service", frappe.get_roles(owner_email))

		# The stranger: neither the employee's owner nor HR, linked to their own
		# unrelated Employee record so erpnext doesn't strip their ESS role.
		stranger_email = "trans.stranger@example.com"
		frappe.db.delete("Employee", {"user_id": stranger_email})
		frappe.db.delete("User", {"name": stranger_email})
		frappe.db.commit()
		stranger_user = frappe.get_doc({
			"doctype": "User", "email": stranger_email, "first_name": "Trans", "last_name": "Stranger",
			"send_welcome_email": 0, "user_type": "System User",
		})
		stranger_user.flags.no_welcome_mail = True
		stranger_user.insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Employee", "first_name": "Trans", "last_name": "Stranger",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01", "user_id": stranger_email,
		}).insert(ignore_permissions=True)
		stranger_user.reload()
		stranger_user.add_roles("Employee Self Service")
		self.assertIn("Employee Self Service", frappe.get_roles(stranger_email))

		frappe.set_user(stranger_email)
		with self.assertRaises(frappe.PermissionError):
			submit_onboarding(name)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_status"), "Invited")


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


class TestSaveOnboardingFields(FrappeTestCase):
	"""Covers hrms.onboarding.save_onboarding_fields: the status-gated,
	whitelisted bypass for the permlevel-1 fields that block a hire's own
	ESS writes on the live server (see setup/permissions/apply_field_levels.py
	+ apply_self_service.py).

	NOTE on the permlevel-1 assertion: frappe.client.set_value() does NOT
	raise when a field is above the caller's permlevel access -- Frappe's
	Document.validate_higher_perm_levels()/reset_values_if_no_permlevel_access
	silently resets disallowed field values instead of throwing (verified
	against this bench: frappe/model/document.py). So the direct-write case
	below asserts the write is a silent no-op (value stays unset), which is
	the actual bug this fix addresses -- not an exception. save_onboarding_fields
	bypasses that (ignore_permissions=True) and the value persists for real.
	"""

	FIELD = "current_address"

	def setUp(self):
		# Targeted, self-contained permlevel setup for one field, instead of
		# setup.permissions.apply_field_levels.run() -- that helper also grants
		# permlevel access to "CEO/COO" and other Phase-2/3 roles that
		# setup.permissions.apply_rights_matrix.run() has not created on this
		# test site, so it throws LinkValidationError here. This test site's
		# Employee Self Service role already carries permlevel-1 read=1/write=0
		# (from a prior apply_self_service.run()), which is exactly the
		# production condition we need -- only the field's own permlevel is
		# missing, so we add just that.
		self._permlevel_ps = frappe.get_all(
			"Property Setter",
			filters={"doc_type": "Employee", "field_name": self.FIELD, "property": "permlevel"},
			pluck="name",
		)
		for ps in self._permlevel_ps:
			frappe.delete_doc("Property Setter", ps, force=True, ignore_permissions=True)
		frappe.make_property_setter({
			"doctype": "Employee", "doctype_or_field": "DocField", "fieldname": self.FIELD,
			"property": "permlevel", "value": 1, "property_type": "Int",
		})
		frappe.clear_cache(doctype="Employee")

		self.email = "onb.save.perm@example.com"
		# save_onboarding_fields (and onboard_employee) commit the DB transaction,
		# which defeats FrappeTestCase's usual rollback-per-test isolation -- so
		# any Employee/User left over from a prior run of this test must be
		# cleared explicitly, not just re-deleted by name.
		frappe.db.delete("Employee", {"user_id": self.email})
		frappe.db.delete("User", {"name": self.email})
		frappe.db.commit()
		user = frappe.get_doc({
			"doctype": "User", "email": self.email, "first_name": "Save", "last_name": "Perm",
			"send_welcome_email": 0, "user_type": "System User",
		})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)

		# Link Employee.user_id BEFORE adding the ESS role: erpnext's
		# validate_employee_role (User.validate hook) strips Employee/ESS
		# roles from a user with no matching Employee record yet.
		self.emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Save", "last_name": "Perm",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "date_of_birth": "1995-01-01",
			"custom_onboarding_status": "Invited",
			"user_id": self.email,
		}).insert(ignore_permissions=True)

		user.reload()
		user.add_roles("Employee Self Service")
		self.assertIn("Employee Self Service", frappe.get_roles(self.email))

		if not frappe.db.exists("User Permission",
		                        {"user": self.email, "allow": "Employee", "for_value": self.emp.name}):
			frappe.get_doc({
				"doctype": "User Permission", "user": self.email, "allow": "Employee",
				"for_value": self.emp.name, "apply_to_all_doctypes": 1,
			}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		for ps in frappe.get_all(
			"Property Setter",
			filters={"doc_type": "Employee", "field_name": self.FIELD, "property": "permlevel"},
			pluck="name",
		):
			frappe.delete_doc("Property Setter", ps, force=True, ignore_permissions=True)
		frappe.clear_cache(doctype="Employee")
		# save_onboarding_fields/db_set calls commit the transaction, so these
		# must be deleted explicitly rather than relying on test rollback.
		frappe.db.delete("User Permission", {"user": self.email})
		frappe.db.delete("Employee", {"user_id": self.email})
		frappe.db.delete("User", {"name": self.email})
		frappe.db.commit()

	def test_bypasses_permlevel_1_where_direct_write_silently_no_ops(self):
		from hrms.onboarding import save_onboarding_fields

		frappe.set_user(self.email)
		# Direct write: does not raise, but permlevel-1 write=0 for ESS means
		# Frappe silently drops the change (validate_higher_perm_levels resets
		# it) -- the field is left exactly as it was (unset).
		frappe.client.set_value("Employee", self.emp.name, self.FIELD, "Direct-Write-Blocked")
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("Employee", self.emp.name, self.FIELD))

		# The whitelisted bypass: same field, same ESS user, and it persists.
		frappe.set_user(self.email)
		result = save_onboarding_fields(self.emp.name, {self.FIELD: "Bypassed-Write"})
		frappe.set_user("Administrator")
		self.assertEqual(result["status"], "Invited")
		self.assertEqual(frappe.db.get_value("Employee", self.emp.name, self.FIELD), "Bypassed-Write")

	def test_throws_when_status_approved(self):
		from hrms.onboarding import save_onboarding_fields

		self.emp.db_set("custom_onboarding_status", "Approved")
		frappe.set_user(self.email)
		with self.assertRaises(frappe.ValidationError):
			save_onboarding_fields(self.emp.name, {self.FIELD: "X"})
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("Employee", self.emp.name, self.FIELD))

	def test_throws_on_non_whitelisted_field(self):
		from hrms.onboarding import save_onboarding_fields

		frappe.set_user(self.email)
		with self.assertRaises(frappe.ValidationError):
			save_onboarding_fields(self.emp.name, {"custom_onboarding_status": "Approved"})
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Employee", self.emp.name, "custom_onboarding_status"), "Invited"
		)

	def test_throws_for_non_owner_non_hr_caller(self):
		from hrms.onboarding import save_onboarding_fields

		other_email = "onb.save.other@example.com"
		frappe.db.delete("User", {"name": other_email})
		other = frappe.get_doc({
			"doctype": "User", "email": other_email, "first_name": "Other", "last_name": "Hire",
			"send_welcome_email": 0, "user_type": "System User",
		})
		other.flags.no_welcome_mail = True
		other.insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("User", other_email, force=True, ignore_permissions=True))

		frappe.set_user(other_email)
		with self.assertRaises(frappe.PermissionError):
			save_onboarding_fields(self.emp.name, {self.FIELD: "X"})
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("Employee", self.emp.name, self.FIELD))
