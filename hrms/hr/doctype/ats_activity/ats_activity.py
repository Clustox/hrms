# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ATSActivity(Document):
	"""What a guest did: looked at a record, added a note, gave feedback, or moved a candidate.
	Written by hrms.ats.activity; nobody edits these rows."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action: DF.Literal["Viewed", "Added Note", "Gave Feedback", "Moved Candidate"]
		job_opening: DF.Link | None
		occurred_on: DF.Datetime | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		user: DF.Link | None
	# end: auto-generated types

	pass
