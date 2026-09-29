import frappe


def execute():
	from setup.attendance.apply_punch_request_schema import run

	run()
