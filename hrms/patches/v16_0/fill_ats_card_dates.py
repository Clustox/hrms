"""ATS: show plain dates (Applied On, In Stage Since) on the board cards instead of a date and time."""

import frappe

from hrms.ats.backfill import fill_card_dates
from hrms.ats.board import refresh_board_cards


def execute():
	from hrms.ats.setup import apply_custom_fields

	apply_custom_fields(commit=False)  # the two date fields must exist first
	filled = fill_card_dates()
	boards = refresh_board_cards()
	frappe.db.commit()
	print(f"ATS card dates filled for {filled} applicant(s); {boards} board(s) updated")
