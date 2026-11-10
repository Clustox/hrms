"""Matching helpers for Candidate: normalise email and phone, find an existing person."""

import re

import frappe

GMAIL_DOMAINS = ("gmail.com", "googlemail.com")


def normalize_email(email: str | None) -> str:
	"""Lower-case, trim and drop a +tag. Dots are ignored only for Gmail addresses."""
	email = (email or "").strip().lower()
	if "@" not in email:
		return email
	local, domain = email.rsplit("@", 1)
	local = local.split("+", 1)[0]
	if domain in GMAIL_DOMAINS:
		local = local.replace(".", "")
		domain = "gmail.com"
	return f"{local}@{domain}"


def normalize_phone(phone: str | None) -> str:
	"""Digits only, with Pakistani numbers brought to 92XXXXXXXXXX.

	+92 300 1234567, 0300-1234567, 00923001234567 and 3001234567 all become 923001234567.
	Numbers shorter than 7 digits are treated as missing.
	"""
	digits = re.sub(r"\D", "", phone or "")
	if digits.startswith("00"):
		digits = digits[2:]
	if digits.startswith("92") and len(digits) == 12:
		return digits
	if digits.startswith("0") and len(digits) == 11:
		return "92" + digits[1:]
	if digits.startswith("3") and len(digits) == 10:
		return "92" + digits
	return digits if len(digits) >= 7 else ""


def find_duplicate(email: str | None, phone: str | None, exclude: str | None = None) -> str | None:
	"""Name of an existing Candidate with the same email, else the same phone."""
	candidates = []
	email_key = normalize_email(email)
	phone_key = normalize_phone(phone)
	if email_key:
		candidates.append({"email_normalized": email_key})
	if phone_key:
		candidates.append({"phone_normalized": phone_key})

	for filters in candidates:
		if exclude:
			filters = {**filters, "name": ["!=", exclude]}
		name = frappe.db.get_value("Candidate", filters, "name")
		if name:
			return name
	return None


def sync_applicant_card_fields(doc, method=None):
	"""Candidate on_update: the current title and employer shown on the board cards follow the
	candidate. Applicants copy them when they are saved; this covers later edits."""
	frappe.db.sql(
		"""update `tabJob Applicant` set candidate_title = %s, candidate_employer = %s
		where candidate = %s""",
		(doc.current_title, doc.current_employer, doc.name),
	)
