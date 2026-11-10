# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form

from hrms.ats.candidates import find_duplicate, normalize_email, normalize_phone


class DuplicateCandidateError(frappe.ValidationError):
	pass


class Candidate(Document):
	"""A person who applies for one or more jobs. Each application is a Job Applicant."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		current_employer: DF.Data | None
		current_title: DF.Data | None
		email: DF.Data
		email_normalized: DF.Data | None
		full_name: DF.Data
		phone: DF.Data | None
		phone_normalized: DF.Data | None
		resume: DF.Attach | None
		resume_text: DF.LongText | None
		source: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.full_name = (self.full_name or "").strip()
		self.email_normalized = normalize_email(self.email)
		self.phone_normalized = normalize_phone(self.phone)
		self.validate_not_duplicate()

	def validate_not_duplicate(self):
		existing = find_duplicate(self.email, self.phone, exclude=self.name)
		if existing:
			frappe.throw(
				_("This person already exists as {0}.").format(get_link_to_form("Candidate", existing)),
				exc=DuplicateCandidateError,
				title=_("Duplicate Candidate"),
			)
