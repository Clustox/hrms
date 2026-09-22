# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


def execute():
	"""Leave Application's "Open" status is renamed to "Pending" (see the
	doctype's status field options) -- update existing rows to match, since
	changing a Select field's options doesn't touch already-stored values.
	"""
	frappe.reload_doctype("Leave Application")
	frappe.db.set_value("Leave Application", {"status": "Open"}, "status", "Pending", update_modified=False)
