"""ATS: the board cards also carry the exact times their badges are worked out from."""

import frappe

from hrms.ats.board import refresh_board_cards


def execute():
	changed = refresh_board_cards()
	frappe.db.commit()
	print(f"ATS board card fields refreshed on {changed} board(s)")
