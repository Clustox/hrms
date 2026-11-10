"""ATS: show the candidate's title and employer, applied date and stage time on the board cards,
and copy the title and employer onto existing applicants."""

import frappe

from hrms.ats.board import refresh_board_cards


def execute():
	from hrms.ats.setup import apply_custom_fields

	apply_custom_fields(commit=False)  # the card fields must exist first
	frappe.db.sql(
		"""update `tabJob Applicant` ja join `tabCandidate` c on c.name = ja.candidate
		set ja.candidate_title = c.current_title, ja.candidate_employer = c.current_employer"""
	)
	changed = refresh_board_cards()
	frappe.db.commit()
	print(f"ATS board cards refreshed on {changed} board(s)")
