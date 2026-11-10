# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class JobPipelineStage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		auto_email_template: DF.Link | None
		color: DF.Color | None
		maps_to_status: DF.Literal["", "Open", "Replied", "Shortlisted", "Hold", "Rejected", "Accepted"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		required_fields: DF.SmallText | None
		stage_name: DF.Data
		stage_type: DF.Literal["Active", "Hired", "Rejected"]
		visible_to_guests: DF.Check
	# end: auto-generated types

	pass
