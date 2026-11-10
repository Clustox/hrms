# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ApplicantStageLog(Document):
	"""Append-only record of an applicant moving between pipeline stages.

	Rows are written by hrms.ats.pipeline and cannot be edited or deleted by users.
	"""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from_stage: DF.Data | None
		job_applicant: DF.Link
		job_opening: DF.Link | None
		moved_by: DF.Link | None
		moved_on: DF.Datetime | None
		reason: DF.SmallText | None
		to_stage: DF.Data | None
		trigger_source: DF.Literal["Manual", "Board", "Interview", "Offer", "Bulk", "Import", "System"]
	# end: auto-generated types

	def before_insert(self):
		self.moved_by = self.moved_by or frappe.session.user
		self.moved_on = self.moved_on or frappe.utils.now_datetime()

	def on_trash(self):
		# the history is an audit trail; it goes away only together with its applicant
		if not frappe.flags.get("ats_allow_log_delete"):
			frappe.throw(_("Stage history cannot be deleted."), frappe.PermissionError)
