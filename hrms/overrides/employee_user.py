"""Clustox: let HR create the portal login for an employee from the Employee form.

ERPNext's `create_user` checks the caller may edit the Employee, but then inserts
the User with the caller's own permissions. HR roles do not have Create on the
User doctype (only System Manager does), so the button fails with "No permission
for User". This override keeps the same Employee write check and creates the User
as the system, with the Employee role only -- HR cannot hand out any other role
through it, and still has no general access to the User doctype.
"""
import frappe
from frappe import _
from frappe.permissions import add_user_permission
from frappe.utils import cint, validate_email_address


@frappe.whitelist(methods=["POST"])
def create_user(employee: str, email: str | None = None, create_user_permission: int = 0) -> str:
	emp = frappe.get_doc("Employee", employee)
	emp.check_permission("write")
	if emp.user_id:
		frappe.throw(_("Employee {0} already has a linked user").format(emp.name))

	if not email:
		frappe.throw(_("Email is required to create a user"))

	email = validate_email_address(email, True)
	employee_name = emp.employee_name.split(" ")
	first_name = employee_name[0]
	middle_name = last_name = ""

	if len(employee_name) >= 3:
		last_name = " ".join(employee_name[2:])
		middle_name = employee_name[1]
	elif len(employee_name) == 2:
		last_name = employee_name[1]

	user = frappe.new_doc("User")
	user.update(
		{
			"email": email,
			"enabled": 1,
			"first_name": first_name,
			"middle_name": middle_name,
			"last_name": last_name,
			"gender": emp.gender,
			"birth_date": emp.date_of_birth,
			"phone": emp.cell_number,
			"bio": emp.bio,
		}
	)
	emp.db_set("user_id", email)
	user.append_roles("Employee")
	# the one change from ERPNext: the caller was already checked against the Employee above
	user.flags.ignore_permissions = True
	user.insert()

	emp.user_id = user.name
	emp.create_user_permission = cint(create_user_permission)
	emp.save()

	if cint(create_user_permission):
		add_user_permission("Employee", emp.name, user.name)
		add_user_permission("Company", emp.company, user.name)

	return user.name
