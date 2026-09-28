# Copyright (c) 2026, Clustox and contributors
import frappe
from frappe import _

MANDATORY = [
	("custom_cnic_no", "CNIC"),
	("custom_cnic_expiry_date", "CNIC Expiry"),
	("current_address", "Current Address"),
	("permanent_address", "Permanent Address"),
	("blood_group", "Blood Group"),
	("person_to_be_contacted", "Emergency Contact Person"),
	("emergency_phone_number", "Emergency Contact Phone"),
	("relation", "Emergency Contact Relation"),
]


def validate_onboarding_submission(employee: str) -> list[str]:
	doc = frappe.get_doc("Employee", employee)
	return [label for fieldname, label in MANDATORY if not doc.get(fieldname)]


def _ensure_user(employee_doc) -> str:
	email = employee_doc.company_email or employee_doc.personal_email
	if not email:
		frappe.throw(_("Employee has no company or personal email to create a login."))
	if not frappe.db.exists("User", email):
		user = frappe.get_doc({
			"doctype": "User", "email": email,
			"first_name": employee_doc.first_name or employee_doc.employee_name,
			"last_name": employee_doc.last_name or "",
			"send_welcome_email": 0, "user_type": "System User",
		})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
	# Link Employee.user_id before granting the role: erpnext's User.validate hook
	# (validate_employee_role) strips "Employee"/"Employee Self Service" roles whenever
	# no Employee record maps to this user yet, so the link must land first.
	if employee_doc.user_id != email:
		employee_doc.db_set("user_id", email)
	user = frappe.get_doc("User", email)
	if "Employee Self Service" not in frappe.get_roles(email):
		user.add_roles("Employee Self Service")
	return email


def _self_scope(email: str, employee: str):
	if not frappe.db.exists("User Permission",
	                        {"user": email, "allow": "Employee", "for_value": employee}):
		frappe.get_doc({
			"doctype": "User Permission", "user": email,
			"allow": "Employee", "for_value": employee,
			"apply_to_all_doctypes": 1,
		}).insert(ignore_permissions=True)


@frappe.whitelist()
def onboard_employee(employee: str, send_invite: int = 1) -> dict:
	emp = frappe.get_doc("Employee", employee)
	email = _ensure_user(emp)
	_self_scope(email, employee)
	emp.db_set("custom_onboarding_status", "Invited")
	frappe.db.commit()
	if int(send_invite):
		send_onboarding_invite(email)
	return {"user": email, "status": "Invited"}


def send_onboarding_invite(email: str):
	link = frappe.get_doc("User", email)._reset_password(send_email=False)
	url = frappe.utils.get_url()  # nginx serves /hrms/login on the same host
	frappe.sendmail(
		recipients=[email],
		subject=_("Welcome to Clustox HR — set up your account"),
		message=_(
			"<p>Welcome! Set your password here: <a href='{0}'>Set password</a></p>"
			"<p>Then sign in at <a href='{1}/hrms/login'>{1}/hrms/login</a> and complete your profile.</p>"
		).format(link, url),
		now=True,
	)


from frappe.utils import now

HR_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}


def _require_hr():
	if not (HR_ROLES & set(frappe.get_roles())):
		frappe.throw(_("Only HR can perform this action."), frappe.PermissionError)


@frappe.whitelist()
def submit_onboarding(employee: str) -> dict:
	missing = validate_onboarding_submission(employee)
	if missing:
		frappe.throw(_("Please complete these before submitting: {0}").format(", ".join(missing)))
	emp = frappe.get_doc("Employee", employee)
	emp.db_set("custom_onboarding_status", "Submitted")
	emp.db_set("custom_onboarding_submitted_on", now())
	frappe.db.commit()
	_send_hr_notification(emp)
	return {"status": "Submitted"}


@frappe.whitelist()
def approve_onboarding(employee: str) -> dict:
	_require_hr()
	emp = frappe.get_doc("Employee", employee)
	emp.db_set("custom_onboarding_status", "Approved")
	frappe.db.commit()
	_send_employee_notification(emp, _("Your onboarding has been approved."))
	return {"status": "Approved"}


@frappe.whitelist()
def request_onboarding_changes(employee: str, note: str) -> dict:
	_require_hr()
	emp = frappe.get_doc("Employee", employee)
	emp.db_set("custom_onboarding_status", "Invited")
	emp.db_set("custom_onboarding_notes", note)
	frappe.db.commit()
	_send_employee_notification(emp, _("Changes requested on your onboarding: {0}").format(note))
	return {"status": "Invited"}


def _send_hr_notification(emp):
	recipients = [u.parent for u in frappe.get_all(
		"Has Role", filters={"role": "HR Manager", "parenttype": "User"},
		fields=["parent"])]
	recipients = [r for r in set(recipients) if frappe.db.get_value("User", r, "enabled")]
	if recipients:
		try:
			# Queued (not now=True): a status transition must not block on, or fail
			# because of, synchronous SMTP delivery. Delivery happens via the
			# regular email queue flush.
			frappe.sendmail(recipients=recipients,
			                subject=_("Onboarding submitted: {0}").format(emp.employee_name),
			                message=_("{0} submitted their onboarding for review.").format(emp.employee_name))
		except Exception:
			# Status transition already committed above; a mail-server issue
			# (e.g. no Email Account configured) must not surface as an API failure.
			frappe.log_error(title="Onboarding HR notification failed")


def _send_employee_notification(emp, message):
	if emp.user_id:
		try:
			frappe.sendmail(recipients=[emp.user_id], subject=_("Onboarding update"),
			                message=message)
		except Exception:
			frappe.log_error(title="Onboarding employee notification failed")
