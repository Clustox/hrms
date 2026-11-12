# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, nowdate

from hrms.ats.guest_access import can_grant_for_job, sync_guest_roles


class JobGuestAccess(Document):
	"""Lets one guest (an interviewer from outside HR) see one job. Revoking is instant:
	the record rules look at this table on every request."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		can_move_stages: DF.Check
		can_view_salary: DF.Check
		expires_on: DF.Date | None
		granted_by: DF.Link | None
		granted_on: DF.Datetime | None
		job_opening: DF.Link
		revoked_by: DF.Link | None
		revoked_on: DF.Datetime | None
		user: DF.Link
	# end: auto-generated types

	def validate(self):
		if self.user in ("Administrator", "Guest"):
			frappe.throw(_("{0} cannot be given guest access.").format(frappe.bold(self.user)))
		if not can_grant_for_job(self.job_opening):
			frappe.throw(
				_("Only an administrator, an HR Manager or the job owner can share this job."),
				frappe.PermissionError,
			)
		if self.expires_on and getdate(self.expires_on) < getdate(nowdate()) and not self.revoked_on:
			frappe.throw(_("The expiry date is in the past."))
		if not self.revoked_on:
			self.validate_not_already_shared()
		if self.is_new():
			self.granted_by = frappe.session.user
			self.granted_on = now_datetime()

	def validate_not_already_shared(self):
		existing = frappe.db.exists(
			"Job Guest Access",
			{"user": self.user, "job_opening": self.job_opening, "revoked_on": ["is", "not set"], "name": ["!=", self.name or ""]},
		)
		if existing:
			frappe.throw(_("{0} already has access to this job ({1}).").format(self.user, existing))

	def on_update(self):
		sync_guest_roles(self.user)

	def after_delete(self):
		sync_guest_roles(self.user)
