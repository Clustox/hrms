# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from hrms.ats.pipeline import validate_stages


class ATSPipelineTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hrms.hr.doctype.ats_template_stage.ats_template_stage import ATSTemplateStage

		description: DF.SmallText | None
		stages: DF.Table[ATSTemplateStage]
		template_name: DF.Data
	# end: auto-generated types

	def validate(self):
		validate_stages(self.stages)
