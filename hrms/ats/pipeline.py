"""Pipeline stage rules shared by pipeline templates and per-job pipelines."""

import frappe
from frappe import _

STAGE_TYPES = ("Active", "Hired", "Rejected")

# Applicant status (the legacy HRMS field) that a stage maps to unless set explicitly.
DEFAULT_STATUS_BY_TYPE = {"Hired": "Accepted", "Rejected": "Rejected"}

DEFAULT_TEMPLATE_NAME = "Default Hiring Pipeline"

# (name, type, status, visible_to_guests). Order follows the reference screenshots:
# the two "Rejected after ..." stages sit before "Ready to Offer".
DEFAULT_STAGES = [
	("New Candidates", "Active", "Open", 0),
	("Technical Profile Review", "Active", "Open", 0),
	("Shortlisted (Phone Screening)", "Active", "Shortlisted", 1),
	("Technical Assessment", "Active", "Shortlisted", 1),
	("1st Technical Interview", "Active", "Shortlisted", 1),
	("2nd Technical Interview", "Active", "Shortlisted", 1),
	("Final Interview", "Active", "Shortlisted", 1),
	("Rejected after Technical Interview", "Rejected", "Rejected", 0),
	("Rejected after Final Interview", "Rejected", "Rejected", 0),
	# Ready to Offer / Offer Placed map to Accepted so the existing Job Offer and
	# onboarding flow (gated on Accepted) keeps working before the offer is accepted.
	("Ready to Offer", "Active", "Accepted", 0),
	("Offer Placed", "Active", "Accepted", 0),
	("Offer Accepted", "Hired", "Accepted", 0),
	("Offer Rejected", "Rejected", "Rejected", 0),
]


def validate_stages(stages) -> None:
	"""Validate and normalise a list of stage rows (template or job pipeline)."""
	if not stages:
		frappe.throw(_("A pipeline needs at least one stage."))

	seen = set()
	for idx, row in enumerate(stages):
		name = (row.stage_name or "").strip()
		if not name:
			frappe.throw(_("Row {0}: Stage Name is required.").format(idx + 1))
		row.stage_name = name

		key = name.lower()
		if key in seen:
			frappe.throw(_("Row {0}: Stage {1} is listed more than once.").format(idx + 1, frappe.bold(name)))
		seen.add(key)

		if row.stage_type not in STAGE_TYPES:
			row.stage_type = "Active"

		if not row.maps_to_status:
			if row.stage_type in DEFAULT_STATUS_BY_TYPE:
				row.maps_to_status = DEFAULT_STATUS_BY_TYPE[row.stage_type]
			else:
				row.maps_to_status = "Open" if idx == 0 else "Shortlisted"

	if stages[0].stage_type != "Active":
		frappe.throw(_("The first stage must be an Active stage, because new candidates start there."))


def default_stage_rows() -> list[dict]:
	return [
		{
			"stage_name": name,
			"stage_type": stage_type,
			"maps_to_status": status,
			"visible_to_guests": visible,
		}
		for name, stage_type, status, visible in DEFAULT_STAGES
	]
