# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hrms.ats.pipeline import DEFAULT_TEMPLATE_NAME, default_stage_rows


def make_template(name: str, stages: list[dict]):
	return frappe.get_doc({"doctype": "ATS Pipeline Template", "template_name": name, "stages": stages})


class TestATSPipelineTemplate(IntegrationTestCase):
	def test_default_template_is_seeded_in_screenshot_order(self):
		template = frappe.get_doc("ATS Pipeline Template", DEFAULT_TEMPLATE_NAME)
		names = [s.stage_name for s in template.stages]
		self.assertEqual(names[0], "New Candidates")
		self.assertEqual(names[-1], "Offer Rejected")
		# rejection stages sit before Ready to Offer, as on the reference board
		self.assertLess(names.index("Rejected after Final Interview"), names.index("Ready to Offer"))
		self.assertEqual(len(names), len(default_stage_rows()))

	def test_status_defaults_from_stage_type(self):
		template = make_template(
			"_Test Pipeline A",
			[
				{"stage_name": "Applied", "stage_type": "Active"},
				{"stage_name": "Screen", "stage_type": "Active"},
				{"stage_name": "Hired!", "stage_type": "Hired"},
				{"stage_name": "No", "stage_type": "Rejected"},
			],
		).insert()
		self.assertEqual([s.maps_to_status for s in template.stages], ["Open", "Shortlisted", "Accepted", "Rejected"])

	def test_explicit_status_is_kept(self):
		template = make_template(
			"_Test Pipeline B",
			[{"stage_name": "Applied", "stage_type": "Active", "maps_to_status": "Replied"}],
		).insert()
		self.assertEqual(template.stages[0].maps_to_status, "Replied")

	def test_duplicate_stage_names_rejected_case_insensitive(self):
		template = make_template(
			"_Test Pipeline C",
			[{"stage_name": "Interview"}, {"stage_name": "  interview "}],
		)
		self.assertRaises(frappe.ValidationError, template.insert)

	def test_first_stage_must_be_active(self):
		template = make_template(
			"_Test Pipeline D",
			[{"stage_name": "Rejected", "stage_type": "Rejected"}, {"stage_name": "Applied"}],
		)
		self.assertRaises(frappe.ValidationError, template.insert)

	def test_blank_stage_name_rejected(self):
		template = make_template("_Test Pipeline E", [{"stage_name": "   "}])
		self.assertRaises(frappe.ValidationError, template.insert)
