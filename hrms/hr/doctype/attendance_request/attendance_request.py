# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, date_diff, format_date, get_fullname, get_link_to_form, getdate, nowdate

from erpnext.setup.doctype.employee.employee import is_holiday

import hrms
from hrms.hr.doctype.leave_application.leave_application import get_employee_leave_approver
from hrms.hr.utils import validate_active_employee, validate_dates


class OverlappingAttendanceRequestError(frappe.ValidationError):
	pass


class AttendanceRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		company: DF.Link
		department: DF.Link | None
		employee: DF.Link
		employee_name: DF.Data | None
		explanation: DF.SmallText | None
		from_date: DF.Date
		half_day: DF.Check
		half_day_date: DF.Date | None
		include_holidays: DF.Check
		leave_approver: DF.Link | None
		leave_approver_name: DF.Data | None
		manager: DF.Link | None
		manager_name: DF.Data | None
		reason: DF.Literal["Work From Home", "On Duty"]
		shift: DF.Link | None
		status: DF.Literal["", "Pending", "Approved", "Rejected", "Cancelled"] | None
		team_lead: DF.Link | None
		team_lead_name: DF.Data | None
		to_date: DF.Date
		total_days: DF.Float
	# end: auto-generated types

	def validate(self):
		validate_active_employee(self.employee)
		validate_dates(self, self.from_date, self.to_date, False)
		self.validate_shifts()
		self.validate_half_day()
		self.validate_request_overlap()
		self.validate_no_attendance_to_create()
		if not self.status:
			self.status = "Pending"
		self.validate_status_change()
		self.set_total_days()
		self.set_approvers()

	def set_total_days(self):
		days = date_diff(self.to_date, self.from_date) + 1
		self.total_days = days - 0.5 if self.half_day else days

	def set_approvers(self):
		self.leave_approver = get_employee_leave_approver(self.employee)
		self.leave_approver_name = get_fullname(self.leave_approver) if self.leave_approver else None
		self.team_lead, self.manager = _resolve_team_lead_and_manager(self.employee)
		# Set explicitly rather than relying on fetch_from to notice the
		# change -- team_lead/manager are being set programmatically in this
		# same validate() cycle, not edited by a user, so the usual
		# changed-value trigger for an automatic fetch isn't guaranteed here.
		self.team_lead_name = (
			frappe.db.get_value("Employee", self.team_lead, "employee_name") if self.team_lead else None
		)
		self.manager_name = (
			frappe.db.get_value("Employee", self.manager, "employee_name") if self.manager else None
		)

	def validate_half_day(self):
		if self.half_day:
			if not getdate(self.from_date) <= getdate(self.half_day_date) <= getdate(self.to_date):
				frappe.throw(_("Half day date should be in between from date and to date"))

	def validate_status_change(self):
		"""The portal only ever changes status via set_wfh_decision/
		cancel_wfh_request (both of which write with db_set, bypassing
		validate entirely) -- this only catches someone editing the field
		directly through Desk or the API (doc.save(), not submit, which
		before_submit already covers for the Approved case) without going
		through either of those, e.g. a colleague maliciously Rejecting
		someone else's request they have no say over."""
		if self.is_new() or self.get("custom_is_punch_request") or self.flags.ignore_permissions:
			return
		if self.has_value_changed("status") and not _can_decide(self):
			frappe.throw(_("You are not allowed to change this request's status directly."), frappe.PermissionError)

	def validate_no_attendance_to_create(self):
		attendance_warnings = self.get_attendance_warnings()
		attendance_request_days = date_diff(self.to_date, self.from_date) + 1
		if len(attendance_warnings) == attendance_request_days and not any(
			warning["action"] == "Overwrite" for warning in attendance_warnings
		):
			message_table = [[_("Date"), _("Reason"), _("Action")]]
			for warning in attendance_warnings:
				message_table.append(
					[
						format_date(warning["date"]),
						_(warning["reason"]),
						_(warning["action"]),
					]
				)
			frappe.msgprint(
				title=_("No attendance records to create due to following reasons"),
				msg=message_table,
				as_table=True,
				raise_exception=True,
			)

	def validate_shifts(self):
		# Shift should be mentioned if employee has a shift assignment
		shifts = self.get_active_shifts()
		if shifts and not self.shift:
			if len(shifts) == 1:
				self.shift = shifts[0]
			else:
				frappe.throw(
					_(
						"There are multiple shifts assigned to the employee for the same period. Please mention the shift"
					)
				)

	def get_active_shifts(self):
		# Attendance requests are typically posted after the shift period for corrections.
		# Expired shift assignments are auto-marked Inactive, but should still be considered
		# here so that the shift is auto-fetched for backdated requests.
		shifts = frappe.get_all(
			"Shift Assignment",
			filters={
				"docstatus": 1,
				"employee": self.employee,
				"start_date": ("<=", self.from_date),
				"end_date": (">=", self.to_date),
			},
			pluck="shift_type",
		)

		return list(set(shifts))

	def validate_request_overlap(self):
		if not self.name:
			self.name = "New Attendance Request"

		Request = frappe.qb.DocType("Attendance Request")
		query = (
			frappe.qb.from_(Request)
			.select(Request.name)
			.where(
				(Request.employee == self.employee)
				& (Request.docstatus < 2)
				& (Request.name != self.name)
				& (self.to_date >= Request.from_date)
				& (self.from_date <= Request.to_date)
				# A Rejected/Cancelled Work From Home / On Duty request still
				# sits at docstatus 0 forever (see set_wfh_decision/
				# cancel_wfh_request) -- it's a decided, dead request, not a
				# live one still competing for these dates, so it must not
				# block a new request for the same period. A punch request's
				# status is always blank, so it's unaffected by this either
				# way.
				& (Request.status.isnull() | Request.status.notin(["Rejected", "Cancelled"]))
			)
		)

		if self.shift:
			query = query.where(Request.shift == self.shift)

		overlapping_request = query.run(as_dict=True)

		if overlapping_request:
			self.throw_overlap_error(overlapping_request[0].name)

	def throw_overlap_error(self, overlapping_request: str):
		msg = _("Employee {0} already has an Attendance Request {1} that overlaps with this period").format(
			frappe.bold(self.employee),
			get_link_to_form("Attendance Request", overlapping_request),
		)

		frappe.throw(msg, title=_("Overlapping Attendance Request"), exc=OverlappingAttendanceRequestError)

	def before_submit(self):
		# The portal UI never exposes status as an editable field (every
		# transition goes through set_wfh_decision), but that's only a UI
		# nicety -- the doctype's own "write" permission is broad enough
		# that an employee could otherwise call frappe.client.submit (or
		# edit+submit via Desk) directly on their own or anyone's request.
		# set_wfh_decision's approval path sets ignore_permissions after
		# already checking _can_decide itself, so this only ever blocks an
		# attempt that skipped that check.
		if self.get("custom_is_punch_request"):
			return
		if self.status == "Approved" and not self.flags.ignore_permissions and not _can_decide(self):
			frappe.throw(_("You are not allowed to approve this request."), frappe.PermissionError)

	def on_submit(self):
		# A Work From Home / On Duty request is only ever submitted as the
		# approval step itself (see set_wfh_decision below) -- Pending/Rejected/
		# Cancelled never reach docstatus 1, so there's no separate "approved
		# but not yet submitted" state to worry about.
		if self.status != "Approved":
			frappe.throw(_("Only an Approved request can be submitted."))
		self.create_attendance_records()

	def before_cancel(self):
		self.status = "Cancelled"

	def on_cancel(self):
		attendance_list = frappe.get_all(
			"Attendance", {"employee": self.employee, "attendance_request": self.name, "docstatus": 1}
		)
		if attendance_list:
			for attendance in attendance_list:
				attendance_obj = frappe.get_doc("Attendance", attendance["name"])
				attendance_obj.cancel()

	def create_attendance_records(self):
		request_days = date_diff(self.to_date, self.from_date) + 1
		for day in range(request_days):
			attendance_date = add_days(self.from_date, day)
			if self.should_mark_attendance(attendance_date):
				self.create_or_update_attendance(attendance_date)

	def create_or_update_attendance(self, date: str):
		doc = self.get_attendance_doc(date)
		status = self.get_attendance_status(date)

		if doc:
			# update existing attendance, change the status
			old_status = doc.status

			if old_status != status:
				doc.db_set({"status": status, "attendance_request": self.name})
				if status == "Half Day":
					doc.db_set("half_day_status", "Absent")
					text = _(
						"Changed the status from {0} to {1} and Status for Other Half to {2} via Attendance Request"
					).format(frappe.bold(old_status), frappe.bold(status), frappe.bold("Absent"))
				else:
					text = _("Changed the status from {0} to {1} via Attendance Request").format(
						frappe.bold(old_status), frappe.bold(status)
					)
				doc.add_comment(comment_type="Info", text=text)

				frappe.msgprint(
					_("Updated status from {0} to {1} for date {2} in the attendance record {3}").format(
						frappe.bold(old_status),
						frappe.bold(status),
						frappe.bold(format_date(date)),
						get_link_to_form("Attendance", doc.name),
					),
					title=_("Attendance Updated"),
				)
			elif status == "Half Day" and doc.half_day_status == "Absent" and self.half_day:
				old_half_day_status = doc.half_day_status
				doc.db_set({"half_day_status": "Present", "attendance_request": self.name})
				text = _(
					"Changed the Status for Other Half from {0} to {1} via Attendance Request as the status is Half Day"
				).format(frappe.bold(old_half_day_status), frappe.bold("Present"))
				doc.add_comment(comment_type="Info", text=text)

				frappe.msgprint(
					_(
						"Updated Status for Other Half from {0} to {1} for date {2} in the attendance record {3}"
					).format(
						frappe.bold(old_half_day_status),
						frappe.bold("Present"),
						frappe.bold(format_date(date)),
						get_link_to_form("Attendance", doc.name),
					),
					title=_("Attendance Updated"),
				)
		else:
			# submit a new attendance record
			doc = frappe.new_doc("Attendance")
			doc.employee = self.employee
			doc.attendance_date = date
			doc.shift = self.shift
			doc.company = self.company
			doc.attendance_request = self.name
			doc.status = status
			doc.half_day_status = "Absent" if status == "Half Day" else None
			doc.insert(ignore_permissions=True)
			doc.submit()

	def should_mark_attendance(self, attendance_date: str) -> bool:
		# Check if attendance_date is a holiday
		if not self.include_holidays and is_holiday(self.employee, attendance_date):
			frappe.msgprint(
				_("Attendance not submitted for {0} as it is a Holiday.").format(
					frappe.bold(format_date(attendance_date))
				)
			)
			return False

		# Check if employee is on leave
		if self.has_leave_record(attendance_date):
			frappe.msgprint(
				_("Attendance not submitted for {0} as {1} is on leave.").format(
					frappe.bold(format_date(attendance_date)), frappe.bold(self.employee)
				)
			)
			return False

		return True

	def has_leave_record(self, attendance_date: str) -> str | None:
		filters = {
			"employee": self.employee,
			"docstatus": 1,
			"from_date": ("<=", attendance_date),
			"to_date": (">=", attendance_date),
			"status": "Approved",
		}
		if self.half_day_date == attendance_date:
			filters["half_day"] = 0

		return frappe.db.exists("Leave Application", filters)

	def has_half_day_leave_record(self, attendance_date: str) -> str | None:
		return frappe.db.exists(
			"Leave Application",
			{
				"employee": self.employee,
				"docstatus": 1,
				"from_date": ("<=", attendance_date),
				"to_date": (">=", attendance_date),
				"status": "Approved",
				"half_day": 1,
				"half_day_date": attendance_date,
			},
		)

	def get_attendance_doc(self, attendance_date: str) -> str | None:
		attendance = frappe.db.exists(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": attendance_date,
				"docstatus": ("!=", 2),
				"shift": self.shift,
			},
		)
		return frappe.get_doc("Attendance", attendance) if attendance else None

	def get_attendance_status(self, attendance_date: str) -> str:
		if self.half_day and date_diff(getdate(self.half_day_date), getdate(attendance_date)) == 0:
			return "Half Day"
		elif self.reason == "Work From Home":
			return "Work From Home"
		else:
			return "Present"

	def status_unchanged(self, attendance_date):
		new_status = self.get_attendance_status(attendance_date)
		attendance_doc = self.get_attendance_doc(attendance_date)
		if attendance_doc and attendance_doc.status == new_status:
			if new_status == "Half Day" and self.half_day and attendance_doc.half_day_status == "Absent":
				return False
			return True
		return False

	def on_update(self):
		self.publish_update()

	def after_delete(self):
		self.publish_update()

	def publish_update(self):
		employee_user = frappe.db.get_value("Employee", self.employee, "user_id", cache=True)
		hrms.refetch_resource("hrms:my_attendance_requests", employee_user)
		hrms.refetch_resource("hrms:team_attendance_requests")

	@frappe.whitelist()
	def get_attendance_warnings(self) -> list:
		attendance_warnings = []
		request_days = date_diff(self.to_date, self.from_date) + 1

		for day in range(request_days):
			attendance_date = add_days(self.from_date, day)
			if not self.include_holidays and is_holiday(self.employee, attendance_date):
				attendance_warnings.append({"date": attendance_date, "reason": "Holiday", "action": "Skip"})
			elif self.has_leave_record(attendance_date):
				attendance_warnings.append({"date": attendance_date, "reason": "On Leave", "action": "Skip"})
			elif self.status_unchanged(attendance_date):
				attendance_warnings.append(
					{"date": attendance_date, "reason": "Attendance status unchanged", "action": "Skip"}
				)
			else:
				attendance = self.get_attendance_doc(attendance_date)
				if attendance:
					attendance_warnings.append(
						{
							"date": attendance_date,
							"reason": "Attendance already marked",
							"record": attendance.name,
							"action": "Overwrite",
						}
					)

		return attendance_warnings


def _resolve_team_lead_and_manager(employee: str) -> tuple[str | None, str | None]:
	"""The approver for a Work From Home / On Duty request is the employee's
	Leave Approver -- exactly who Leave Application would pick (Employee's own
	`leave_approver`, else the first of their Department's leave approvers).
	Leave Approver is a User; this returns that user's Employee record in the
	`team_lead` slot. The second slot (`manager`) is kept only so the stored
	schema and callers stay unchanged -- it's always None now."""
	approver_user = get_employee_leave_approver(employee)
	team_lead = (
		frappe.db.get_value("Employee", {"user_id": approver_user, "status": "Active"}, "name")
		if approver_user
		else None
	)
	return team_lead, None


@frappe.whitelist()
def get_my_approvers() -> dict:
	"""Who would approve a Work From Home request raised right now by the
	current user -- for the New Request form's live preview, before the
	document (and its own stored team_lead/manager) exists yet."""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return {}
	leave_approver = get_employee_leave_approver(employee)
	return {
		"leave_approver": leave_approver,
		"leave_approver_name": get_fullname(leave_approver) if leave_approver else None,
	}


@frappe.whitelist()
def has_approved_wfh_today(employee: str | None = None) -> bool:
	"""Whether `employee` (default: the current user) has an Approved,
	submitted Work From Home request covering today -- biometric hardware
	handles normal office attendance automatically now, so the portal's
	manual Check-in/Check-out button is only meant for an approved remote
	day, not shown at all otherwise. Only "Approved" requests ever reach
	docstatus 1 (see before_submit/on_submit above), and this stops
	mattering the day after to_date -- same inclusive date-range check
	has_leave_record uses for the analogous Leave Application case."""
	employee = employee or frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return False

	# Per-employee exemption: fully-remote / field staff can be allowed to use
	# the portal Check-in/out without raising a WFH request each day, via the
	# "Allow Portal Check-in (no WFH request)" flag on their Employee record.
	if frappe.db.get_value("Employee", employee, "custom_allow_portal_checkin"):
		return True

	today = nowdate()
	return bool(
		frappe.db.exists(
			"Attendance Request",
			{
				"employee": employee,
				"reason": "Work From Home",
				"status": "Approved",
				"docstatus": 1,
				"from_date": ["<=", today],
				"to_date": [">=", today],
			},
		)
	)


def _can_decide(doc) -> bool:
	if {"HR Manager", "HR User", "System Manager"} & set(frappe.get_roles()):
		return True
	approver = doc.leave_approver or get_employee_leave_approver(doc.employee)
	return bool(approver) and frappe.session.user == approver


@frappe.whitelist()
def set_wfh_decision(name: str, decision: str) -> str:
	"""Approve or reject a Work From Home / On Duty Attendance Request.
	Callable by either of the employee's two computed approvers (Team Lead or
	Manager) or an HR role -- not gated by the doctype's normal submit
	permission, since the Employee role alone can't submit this doctype and
	an approver is ordinarily just a regular employee themselves."""
	if decision not in ("Approved", "Rejected"):
		frappe.throw(_("Invalid decision: {0}").format(decision))

	doc = frappe.get_doc("Attendance Request", name)
	if doc.get("custom_is_punch_request"):
		frappe.throw(_("Punch requests are approved by HR, not here."))
	if doc.status != "Pending":
		frappe.throw(_("This request has already been decided."))
	if not _can_decide(doc):
		frappe.throw(_("You are not an approver for this request."), frappe.PermissionError)

	if decision == "Approved":
		doc.status = "Approved"
		doc.flags.ignore_permissions = True
		doc.submit()
	else:
		doc.db_set("status", "Rejected")

	return doc.status


@frappe.whitelist()
def cancel_wfh_request(name: str) -> str:
	"""The requesting employee cancels their own still-Pending request --
	before any decision, there's nothing submitted yet to run the doctype's
	normal cancel (docstatus 1->2) against."""
	doc = frappe.get_doc("Attendance Request", name)
	employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if frappe.session.user != employee_user:
		frappe.throw(_("You can only cancel your own request."), frappe.PermissionError)
	if doc.status != "Pending":
		frappe.throw(_("Only a Pending request can be cancelled."))

	doc.db_set("status", "Cancelled")
	return doc.status
