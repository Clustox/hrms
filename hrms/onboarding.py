# Copyright (c) 2026, Clustox and contributors
import frappe
from frappe import _

MANDATORY = [
	("custom_cnic_no", "CNIC"),
	("custom_cnic_expiry_date", "CNIC Expiry"),
	("current_address", "Current Address"),
	("permanent_address", "Permanent Address"),
	("blood_group", "Blood Group"),
	("person_to_be_contacted", "Emergency Contact Person"),
	("emergency_phone_number", "Emergency Contact Phone"),
	("relation", "Emergency Contact Relation"),
]


def validate_onboarding_submission(employee: str) -> list[str]:
	doc = frappe.get_doc("Employee", employee)
	return [label for fieldname, label in MANDATORY if not doc.get(fieldname)]
