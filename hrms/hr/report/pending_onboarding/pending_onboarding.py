import frappe


def execute(filters=None):
	columns = [
		{"label": "Employee", "fieldname": "name", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
		{"label": "Status", "fieldname": "custom_onboarding_status", "fieldtype": "Data", "width": 110},
		{"label": "Submitted On", "fieldname": "custom_onboarding_submitted_on", "fieldtype": "Datetime", "width": 160},
	]
	rows = frappe.get_all("Employee",
		filters={"custom_onboarding_status": ["in", ["Invited", "Submitted"]]},
		fields=["name", "employee_name", "department", "custom_onboarding_status",
		        "custom_onboarding_submitted_on"],
		order_by="custom_onboarding_submitted_on desc")
	return columns, rows
