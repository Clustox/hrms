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


def default_full_name(applicant_name: str | None, email: str | None) -> str:
	"""The name to give a new Candidate: the applicant's name, else a guess from the email address."""
	if applicant_name and applicant_name.strip():
		return applicant_name.strip()
	local = (email or "").split("@")[0]
	return " ".join(part.capitalize() for part in local.replace("_", ".").split(".") if part) or (email or "")


def get_or_create_candidate(
	email: str | None,
	phone: str | None = None,
	full_name: str | None = None,
	source: str | None = None,
	resume: str | None = None,
) -> str | None:
	"""The Candidate for this person: an existing one matched by email, then phone, or a new one.

	An existing Candidate only gets blanks filled (phone, source, resume); nothing they already
	have is overwritten. Returns None when there is neither an email nor a phone to go on.
	"""
	if not (normalize_email(email) or normalize_phone(phone)):
		return None

	name = find_duplicate(email, phone)
	if name:
		fill_candidate_blanks(name, phone, source, resume)
		return name

	try:
		return (
			frappe.get_doc(
				{
					"doctype": "Candidate",
					"full_name": default_full_name(full_name, email),
					"email": email,
					"phone": phone,
					"source": source,
					"resume": resume,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	except frappe.ValidationError:
		# two applications for the same person at the same moment: the other one won, use theirs
		name = find_duplicate(email, phone)
		if name:
			return name
		raise


def fill_candidate_blanks(name: str, phone: str | None, source: str | None, resume: str | None) -> None:
	candidate = frappe.get_doc("Candidate", name)
	changed = False
	if phone and not candidate.phone and not find_duplicate(None, phone, exclude=name):
		candidate.phone, changed = phone, True
	if source and not candidate.source:
		candidate.source, changed = source, True
	if resume and not candidate.resume:
		candidate.resume, changed = resume, True
	if changed:
		candidate.save(ignore_permissions=True)


def link_candidate(doc, method=None):
	"""Job Applicant before_insert hook: every new application belongs to a Candidate.

	Covers the Desk form, the public application form and the jobs mailbox, since all of them
	insert a Job Applicant. An applicant that already names a Candidate is left alone."""
	if doc.get("candidate"):
		return
	source = doc.get("source") or ("Website Listing" if frappe.flags.in_web_form else None)
	doc.candidate = get_or_create_candidate(
		doc.get("email_id"), doc.get("phone_number"), doc.get("applicant_name"), source, doc.get("resume_attachment")
	)
