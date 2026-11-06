# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ATSTeamMember(Document):
	"""A user attached to a Department or Job Opening as recruiter or collaborator."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		team_role: DF.Literal["Recruiter", "Collaborator"]
		user: DF.Link
	# end: auto-generated types

	pass
