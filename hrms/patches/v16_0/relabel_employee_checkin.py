"""Clustox: show the "Employee Checkin" doctype as "Employee Logs" in the UI.

This is a relabel via a Translation, NOT a doctype rename -- the doctype name and
every code reference ("Employee Checkin") stay intact (punch-request override,
timesheet API, Shift Attendance report, etc.). Re-runnable.
"""

import frappe


def execute():
	if not frappe.db.exists(
		"Translation", {"source_text": "Employee Checkin", "language": "en"}
	):
		frappe.get_doc(
			{
				"doctype": "Translation",
				"language": "en",
				"source_text": "Employee Checkin",
				"translated_text": "Employee Logs",
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.cache().delete_key("translation_assets")
