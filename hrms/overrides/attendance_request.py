"""Repurpose Attendance Request as an employee "punch request".

When `custom_is_punch_request` is set (the /hrms PWA "Request Attendance /
fix a missed punch" form), the request carries a single date + punch type
(check-in / check-out) + time. Its native date-range behaviour (marking
Attendance, shift/overlap validations) is skipped; instead, submitting the
request (the approval step) creates the corresponding Employee Checkin. This
gives ESS employees a manager-approved path to log a missed punch, since they
cannot create Employee Checkin rows directly.

Registered via hooks.py `override_doctype_class`. Non-punch Attendance Requests
keep the stock behaviour untouched.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime

from hrms.hr.doctype.attendance_request.attendance_request import AttendanceRequest

LOG_TYPE_MAP = {"Check-in": "IN", "Check-out": "OUT"}


class PunchAttendanceRequest(AttendanceRequest):
	def validate(self):
		if self.get("custom_is_punch_request"):
			self._validate_punch_request()
			return
		super().validate()

	def on_submit(self):
		if self.get("custom_is_punch_request"):
			self._create_punch_checkin()
			return
		super().on_submit()

	def on_cancel(self):
		if self.get("custom_is_punch_request"):
			self._remove_punch_checkin()
			return
		super().on_cancel()

	# ---- punch-request behaviour ----
	def _validate_punch_request(self):
		if not self.from_date:
			frappe.throw(_("Select the date for the punch request."))
		self.to_date = self.from_date  # single day
		if not self.get("custom_log_type"):
			frappe.throw(_("Select whether this is a check-in or a check-out."))
		if not self.get("custom_punch_time"):
			frappe.throw(_("Enter the punch time."))

	def _create_punch_checkin(self):
		# Idempotent: don't create a second checkin on re-submit / amend.
		if self.get("custom_created_checkin") and frappe.db.exists(
			"Employee Checkin", self.custom_created_checkin
		):
			return

		log_type = LOG_TYPE_MAP.get(self.custom_log_type, "IN")
		punch_dt = get_datetime(f"{self.from_date} {self.custom_punch_time}")

		checkin = frappe.new_doc("Employee Checkin")
		checkin.employee = self.employee
		checkin.log_type = log_type
		checkin.time = punch_dt
		# Approval of the request is the authority to log the punch; the
		# requesting employee cannot create checkins directly.
		checkin.insert(ignore_permissions=True)

		self.db_set("custom_created_checkin", checkin.name)
		frappe.msgprint(
			_("{0} logged at {1}.").format(self.custom_log_type, punch_dt),
			alert=True,
		)

	def _remove_punch_checkin(self):
		name = self.get("custom_created_checkin")
		if name and frappe.db.exists("Employee Checkin", name):
			frappe.delete_doc("Employee Checkin", name, ignore_permissions=True, force=True)
		self.db_set("custom_created_checkin", None)
