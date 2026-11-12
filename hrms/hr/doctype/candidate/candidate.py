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

	def onload(self):
		if not self.is_new():
			self.set_onload("applications", get_applications(self.name))

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


def get_applications(candidate: str) -> list[dict]:
	"""The person's applications: job, stage and status of each, newest first."""
	applications = frappe.get_list(
		"Job Applicant",
		filters={"candidate": candidate},
		fields=["name", "job_title", "pipeline_stage", "status", "is_dropped", "drop_reason", "applied_on"],
		order_by="creation desc",
	)
	for application in applications:
		application.job_name = frappe.db.get_value("Job Opening", application.job_title, "job_title")
	return applications
