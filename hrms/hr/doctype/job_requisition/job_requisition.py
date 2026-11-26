# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import format_duration, get_link_to_form, time_diff_in_seconds


class JobRequisition(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		approved_salary_lower: DF.Currency
		approved_salary_upper: DF.Currency
		company: DF.Link
		completed_on: DF.Date | None
		decided_by: DF.Link | None
		decided_on: DF.Datetime | None
		rejection_reason: DF.SmallText | None
		department: DF.Link | None
		description: DF.TextEditor
		designation: DF.Link
		expected_by: DF.Date | None
		expected_compensation: DF.Currency
		hold_reason: DF.SmallText | None
		naming_series: DF.Literal["HR-HIREQ-"]
		no_of_positions: DF.Int
		posting_date: DF.Date
		reason_for_requesting: DF.Text | None
		requested_by: DF.Link
		requested_by_dept: DF.Link | None
		requested_by_designation: DF.Link | None
		requested_by_name: DF.Data | None
		status: DF.Literal["Pending", "Open & Approved", "Rejected", "Filled", "On Hold", "Cancelled"]
		time_to_fill: DF.Duration | None
	# end: auto-generated types

	def _validate_links(self):
		# Frappe checks links, and fetches the requester's name, department and designation,
		# before before_insert runs. A new request therefore has its requester and typed
		# designation resolved here, ahead of that step.
		if self.is_new():
			self.resolve_designation()
			self.set_requester_defaults()
		super()._validate_links()

	def resolve_designation(self):
		"""The portal form takes the designation as typed text. Use the existing
		designation with that name (ignoring case), or create it if it is new."""
		title = " ".join((self.designation or "").split())
		if not title:
			return

		existing = frappe.db.get_value("Designation", title) or frappe.db.sql_list(
			"select name from `tabDesignation` where lower(name) = %s limit 1", title.lower()
		)
		if isinstance(existing, list):
			existing = existing[0] if existing else None

		if not existing:
			frappe.get_doc({"doctype": "Designation", "designation_name": title}).insert(
				ignore_permissions=True
			)
			existing = title
		self.designation = existing

	def validate(self):
		self.validate_approval()
		self.set_time_to_fill()

	def set_requester_defaults(self):
		"""Requests raised through the portal only carry what the requester typed.
		Fill the rest from their Employee record and keep the request Pending."""
		if not self.naming_series:
			self.naming_series = "HR-HIREQ-"

		# The salary is decided by the System Manager on approval, not asked of the requester.
		if self.expected_compensation is None:
			self.expected_compensation = 0

		is_hr = bool({"HR Manager", "System Manager"} & set(frappe.get_roles()))
		if is_hr and self.requested_by and self.company:
			return

		employee = frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "company"], as_dict=True
		)
		if not employee:
			if is_hr:
				return  # the desk's own mandatory checks ask for the missing fields
			frappe.throw(
				_("Your user is not linked to an active Employee, so a Job Requisition cannot be raised.")
			)

		if is_hr:
			# HR may raise a request on someone's behalf; only fill what was left empty.
			self.requested_by = self.requested_by or employee.name
			self.company = self.company or employee.company
			return

		self.requested_by = employee.name
		self.company = employee.company
		self.status = "Pending"
		for field in (
			"approved_salary_lower",
			"approved_salary_upper",
			"rejection_reason",
			"hold_reason",
			"completed_on",
		):
			self.set(field, None)

	def validate_approval(self):
		"""Approving needs a salary range; rejecting and holding each need a reason. Only
		checked on the step that makes the decision, so existing records can still be edited."""
		before = self.get_doc_before_save()
		if not before or self.status == before.status:
			return

		# A hold reason belongs to one hold. Clear it when the request leaves On Hold, so a
		# later hold has to give its own reason.
		if before.status == "On Hold":
			self.hold_reason = None

		if self.status == "On Hold" and before.status in ("Pending", "Open & Approved"):
			if not (self.hold_reason or "").strip():
				frappe.throw(
					_("Enter a Hold Reason on the Approval tab before putting the request on hold."),
					title=_("Hold Reason Required"),
				)
			self.decided_by = frappe.session.user
			self.decided_on = frappe.utils.now_datetime()
			return

		if before.status not in ("Pending", "On Hold"):
			return

		if self.status == "Open & Approved":
			lower, upper = self.approved_salary_lower, self.approved_salary_upper
			if not lower or not upper:
				frappe.throw(
					_("Enter the approved salary range (From and To) on the Approval tab before approving."),
					title=_("Approved Salary Required"),
				)
			if lower > upper:
				frappe.throw(_("Approved Salary (From) cannot be greater than Approved Salary (To)."))
		elif self.status == "Rejected":
			if not (self.rejection_reason or "").strip():
				frappe.throw(
					_("Enter a Rejection Reason on the Approval tab before rejecting."),
					title=_("Rejection Reason Required"),
				)

		if self.status in ("Open & Approved", "Rejected"):
			self.decided_by = frappe.session.user
			self.decided_on = frappe.utils.now_datetime()

	def set_time_to_fill(self):
		if self.status == "Filled" and self.completed_on:
			self.time_to_fill = time_diff_in_seconds(self.completed_on, self.posting_date)

	@frappe.whitelist()
	def check_duplicate_job_requisition(self):
		return frappe.db.exists(
			"Job Requisition",
			{
				"designation": self.designation,
				"department": self.department,
				"requested_by": self.requested_by,
				"status": ("not in", ["Cancelled", "Filled"]),
				"name": ("!=", self.name),
			},
		)

	@frappe.whitelist()
	def associate_job_opening(self, job_opening: str) -> None:
		frappe.has_permission("Job Opening", "write", job_opening, throw=True)
		frappe.db.set_value(
			"Job Opening", job_opening, {"job_requisition": self.name, "vacancies": self.no_of_positions}
		)
		frappe.msgprint(
			_("Job Requisition {0} has been associated with Job Opening {1}").format(
				frappe.bold(self.name), get_link_to_form("Job Opening", job_opening)
			),
			title=_("Job Opening Associated"),
		)


def get_web_form_department_options() -> str:
	"""Newline separated Select options: the existing departments that have at least
	one active employee, so unused defaults and empty duplicates are not offered."""
	departments = frappe.db.sql_list(
		"""select d.name from `tabDepartment` d
		where d.disabled = 0
		and exists (select 1 from `tabEmployee` e where e.department = d.name and e.status = 'Active')
		order by d.name"""
	)
	return "\n".join(["", *departments])


@frappe.whitelist()
def get_requisition_departments() -> list[str]:
	"""Departments offered on the portal request form."""
	return [d for d in get_web_form_department_options().split("\n") if d]


def sync_web_form_departments(doc=None, method=None):
	"""The web form shows departments as a dropdown, so refresh its options when a
	department or employee changes."""
	frappe.db.set_value(
		"Web Form Field",
		{"parent": "job-requisition", "fieldname": "department"},
		"options",
		get_web_form_department_options(),
	)


@frappe.whitelist()
def make_job_opening(source_name: str, target_doc: str | Document | None = None) -> Document:
	# Whoever may create a Job Opening (HR, System Manager) may create one from a request.
	frappe.has_permission("Job Opening", "create", throw=True)

	def set_missing_values(source, target):
		target.job_title = source.designation
		target.status = "Open"
		target.currency = frappe.db.get_value("Company", source.company, "default_currency")
		target.lower_range = source.approved_salary_lower or source.expected_compensation
		if source.approved_salary_upper:
			target.upper_range = source.approved_salary_upper
		target.description = source.description

	return get_mapped_doc(
		"Job Requisition",
		source_name,
		{
			"Job Requisition": {
				"doctype": "Job Opening",
			},
			"field_map": {
				"designation": "designation",
				"name": "job_requisition",
				"department": "department",
				"no_of_positions": "vacancies",
			},
		},
		target_doc,
		set_missing_values,
	)


@frappe.whitelist()
def get_avg_time_to_fill(
	company: str | None = None, department: str | None = None, designation: str | None = None
):
	filters = {"status": "Filled"}
	if company:
		filters["company"] = company
	if department:
		filters["department"] = department
	if designation:
		filters["designation"] = designation

	avg_time_to_fill = frappe.db.get_list(
		"Job Requisition",
		filters=filters,
		fields=[{"AVG": "time_to_fill", "as": "average_time"}],
	)[0].average_time

	return format_duration(avg_time_to_fill) if avg_time_to_fill else 0
