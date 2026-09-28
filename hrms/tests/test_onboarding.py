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
