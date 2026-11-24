# Copyright (c) 2026, Clustox and contributors
# License: see license.txt
"""Seed the Job Requisition approval flow: the approval workflow (System Manager decides),
the notifications to the approvers, HR and the requester, the portal web form, and the
Requisition Requester role for existing managers. Idempotent: safe to re-run."""

import frappe
from frappe.permissions import add_permission, update_permission_property

from hrms.hr.doctype.job_requisition.job_requisition import get_web_form_department_options

DOCTYPE = "Job Requisition"
WORKFLOW_NAME = "Job Requisition Approval"
WEB_FORM_NAME = "job-requisition"
ADMIN = "System Manager"
APPROVERS = [ADMIN]
HR = "HR Manager"

# (state, allow_edit). A state may repeat with a different role. While a request is
# Pending only the System Manager can edit it. On Hold, HR can edit it too, for example to
# correct details while the decision waits. Once it is decided, HR takes over because HR
# runs the hiring (Job Opening) from there. The approved salary and rejection reason stay
# writable by the System Manager only, whatever the state (see PERMISSIONS).
STATES = [
	("Pending", ADMIN),
	("Open & Approved", HR),
	("Rejected", HR),
	("On Hold", ADMIN),
	("On Hold", HR),
	("Filled", HR),
	("Cancelled", HR),
]

# Only the System Manager approves, rejects and holds. Approving a request on hold is how
# it is resumed, so the salary range is asked for again. HR cannot decide; it closes the
# loop once the position is filled, or cancels a request.
# (state, action, next_state, allowed)
TRANSITIONS = [
	*[("Pending", "Approve", "Open & Approved", role) for role in APPROVERS],
	*[("Pending", "Reject", "Rejected", role) for role in APPROVERS],
	*[("Pending", "Put On Hold", "On Hold", role) for role in APPROVERS],
	("Pending", "Cancel", "Cancelled", HR),
	*[("Open & Approved", "Put On Hold", "On Hold", role) for role in APPROVERS],
	("Open & Approved", "Mark Filled", "Filled", HR),
	("Open & Approved", "Cancel", "Cancelled", HR),
	*[("On Hold", "Approve", "Open & Approved", role) for role in APPROVERS],
	*[("On Hold", "Reject", "Rejected", role) for role in APPROVERS],
	("On Hold", "Cancel", "Cancelled", HR),
]

NEW_REQUEST_MESSAGE = """
<p>A new Job Requisition needs a decision.</p>
<table>
<tr><td><b>Request</b></td><td>{{ doc.name }}</td></tr>
<tr><td><b>Requested by</b></td><td>{{ doc.requested_by_name or doc.requested_by or "-" }}{% if doc.requested_by_dept %} ({{ doc.requested_by_dept }}){% endif %}</td></tr>
<tr><td><b>Designation</b></td><td>{{ doc.designation }}</td></tr>
<tr><td><b>Department</b></td><td>{{ doc.department or "-" }}</td></tr>
<tr><td><b>Positions</b></td><td>{{ doc.no_of_positions }}</td></tr>
<tr><td><b>Reason</b></td><td>{{ doc.reason_for_requesting or "-" }}</td></tr>
</table>
<p>Open the request to approve, reject or put it on hold:<br>
<a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}</a></p>
"""

# The approved salary range is confidential to HR and the System Manager, so the message
# sent to the requester never contains it.
DECISION_MESSAGE = """
{% set verb = {"Open & Approved": "approved", "Rejected": "rejected", "On Hold": "put on hold"}[doc.status] %}
<p>Job Requisition {{ doc.name }} for {{ doc.designation }} was <b>{{ verb }}</b>
by {{ frappe.db.get_value("User", doc.decided_by, "full_name") or doc.decided_by }}.</p>
{% if doc.status == "Rejected" %}
<p>Reason: {{ doc.rejection_reason }}</p>
{% elif doc.status == "On Hold" %}
<p>Reason: {{ doc.hold_reason }}</p>
{% endif %}
<p>See your requests:<br>
<a href="{{ frappe.utils.get_url('/hrms/job-requisitions') }}">{{ frappe.utils.get_url('/hrms/job-requisitions') }}</a></p>
"""

DECISION_MESSAGE_HR = """
{% set verb = {"Open & Approved": "approved", "Rejected": "rejected", "On Hold": "put on hold"}[doc.status] %}
<p>Job Requisition {{ doc.name }} for {{ doc.designation }} was <b>{{ verb }}</b>
by {{ frappe.db.get_value("User", doc.decided_by, "full_name") or doc.decided_by }}.</p>
{% if doc.status == "Open & Approved" %}
<p>Approved salary range: {{ frappe.utils.fmt_money(doc.approved_salary_lower) }}
to {{ frappe.utils.fmt_money(doc.approved_salary_upper) }}</p>
{% elif doc.status == "Rejected" %}
<p>Reason: {{ doc.rejection_reason }}</p>
{% else %}
<p>Reason: {{ doc.hold_reason }}</p>
{% endif %}
<p>Open the request:<br>
<a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}</a></p>
"""


# (role, permlevel, permissions). Mirrors the doctype JSON, but is also applied through
# the permission API because a site that already customised Job Requisition permissions
# (Custom DocPerm) ignores the JSON rows.
PERMISSIONS = [
	("Requisition Requester", 0, {"create": 1, "read": 1, "if_owner": 1}),
	("Requisition Requester", 1, {"read": 1}),
	# Level 1 (rejection reason) and level 2 (approved salary range) are written by the
	# System Manager only. HR can read them, so write is switched off explicitly.
	("HR Manager", 1, {"read": 1, "write": 0}),
	("HR User", 1, {"read": 1, "write": 0}),
	("System Manager", 1, {"read": 1, "write": 1}),
	# Level 2 holds the approved salary range: HR and System Manager only, never the requester.
	("HR Manager", 2, {"read": 1, "write": 0}),
	("HR User", 2, {"read": 1, "write": 0}),
	("System Manager", 2, {"read": 1, "write": 1}),
]


def execute():
	_grant_permissions()
	_ensure_states_and_actions()
	_create_workflow()
	_create_notifications()
	_create_web_form()
	_assign_requester_role()
	_backfill_requester_details()
	frappe.db.commit()


def _backfill_requester_details():
	"""Requests saved before the requester's name, department and designation were
	fetched correctly have those three fields blank."""
	frappe.db.sql(
		"""update `tabJob Requisition` r
		join `tabEmployee` e on e.name = r.requested_by
		set r.requested_by_name = e.employee_name,
			r.requested_by_dept = e.department,
			r.requested_by_designation = e.designation
		where r.requested_by_name is null or r.requested_by_name = ''"""
	)


def _grant_permissions():
	for role, permlevel, ptypes in PERMISSIONS:
		add_permission(DOCTYPE, role, permlevel)
		for ptype, value in ptypes.items():
			update_permission_property(DOCTYPE, role, permlevel, ptype, value)

	# The form's Designation dropdown needs read access on Designation.
	add_permission("Designation", "Requisition Requester", 0)
	update_permission_property("Designation", "Requisition Requester", 0, "read", 1)

	# Saving a Job Opening checks the active Staffing Plan, so the System Manager, who can
	# create a Job Opening from an approved request, must be able to read it.
	add_permission("Staffing Plan", "System Manager", 0)
	update_permission_property("Staffing Plan", "System Manager", 0, "read", 1)


def _ensure_states_and_actions():
	for state, _role in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": ""}).insert(
				ignore_permissions=True
			)
	for _s, action, *_rest in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def _create_workflow():
	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
	else:
		wf = frappe.new_doc("Workflow")
	wf.workflow_name = WORKFLOW_NAME
	wf.document_type = DOCTYPE
	wf.is_active = 1
	wf.override_status = 0
	wf.send_email_alert = 0
	# The existing Status field carries the workflow state, so reports keep working.
	wf.workflow_state_field = "status"
	wf.set("states", [])
	wf.set("transitions", [])
	for state, role in STATES:
		wf.append("states", {"state": state, "doc_status": "0", "allow_edit": role})
	for state, action, next_state, role in TRANSITIONS:
		wf.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": role,
				"allow_self_approval": 1,
			},
		)
	wf.flags.ignore_permissions = True
	wf.save()


def _create_notifications():
	_upsert_notification(
		"Job Requisition Submitted",
		{
			"event": "New",
			"subject": "Job Requisition {{ doc.name }} for {{ doc.designation }} needs a decision",
			"message": NEW_REQUEST_MESSAGE,
			"recipients": [{"receiver_by_role": role} for role in [*APPROVERS, HR, "HR User"]],
		},
	)
	_upsert_notification(
		"Job Requisition Decided",
		{
			"event": "Value Change",
			"value_changed": "status",
			"condition": 'doc.status in ("Open & Approved", "Rejected", "On Hold") and doc.decided_by',
			"subject": "Job Requisition {{ doc.name }}: {{ doc.status }}",
			"message": DECISION_MESSAGE,
			"recipients": [{"receiver_by_document_field": "owner"}],
		},
	)
	_upsert_notification(
		"Job Requisition Decided (HR)",
		{
			"event": "Value Change",
			"value_changed": "status",
			"condition": 'doc.status in ("Open & Approved", "Rejected", "On Hold") and doc.decided_by',
			"subject": "Job Requisition {{ doc.name }}: {{ doc.status }}",
			"message": DECISION_MESSAGE_HR,
			"recipients": [{"receiver_by_role": HR}, {"receiver_by_role": "HR User"}],
		},
	)


def _upsert_notification(name, values):
	existing = frappe.get_doc("Notification", name) if frappe.db.exists("Notification", name) else None
	doc = existing or frappe.new_doc("Notification")

	# A site may add its own sender account and CC rows on top of these notifications.
	# Re-running the setup keeps them instead of wiping them.
	keep_sender = (doc.sender, doc.sender_email) if existing else (None, None)
	keep_cc = [{"cc": r.cc, "condition": r.condition} for r in doc.recipients if r.cc] if existing else []

	doc.update(
		{
			"name": name,
			"document_type": DOCTYPE,
			"channel": "Email",
			"send_system_notification": 1,
			"enabled": 1,
			"condition": None,
			"value_changed": None,
			**values,
		}
	)
	doc.sender, doc.sender_email = keep_sender
	for row in keep_cc:
		doc.append("recipients", row)
	doc.flags.ignore_permissions = True
	doc.save()


# (fieldname, fieldtype, label, reqd, options, description)
# The salary is not asked here: the System Manager sets the approved range on approval.
# Department is a dropdown; its options are filled in by _create_web_form.
WEB_FORM_FIELDS = [
	("department", "Select", "Department", 1, None, "Department the new hire will join"),
	("designation", "Data", "Designation", 1, None, "Job title of the position, for example Senior Software Engineer"),
	("no_of_positions", "Int", "Number of Positions", 1, None, None),
	("expected_by", "Date", "Needed By Date", 0, None, "Date by which the position should be filled"),
	("reason_for_requesting", "Text", "Reason for Requesting", 1, None, None),
	("description", "Text Editor", "Job Description", 1, None, None),
]


def _create_web_form():
	if frappe.db.exists("Web Form", WEB_FORM_NAME):
		wf = frappe.get_doc("Web Form", WEB_FORM_NAME)
	else:
		wf = frappe.new_doc("Web Form")
		wf.name = WEB_FORM_NAME
	wf.update(
		{
			"title": "Job Requisition",
			"route": WEB_FORM_NAME,
			"doc_type": DOCTYPE,
			"module": "HR",
			"is_standard": 0,
			"published": 1,
			"login_required": 1,
			"allow_edit": 0,
			"allow_multiple": 1,
			"allow_delete": 0,
			"show_list": 1,
			"apply_document_permissions": 1,
			"allow_print": 0,
			"allow_comments": 0,
			"show_sidebar": 0,
			"button_label": "Submit Request",
			"list_title": "My Job Requisitions",
			"success_title": "Request sent",
			"success_message": "Your request was sent to the administrators and HR for a decision.",
			"introduction_text": "Request a new position. An administrator will approve it with a salary range, or reject it with a reason.",
		}
	)
	wf.set("web_form_fields", [])
	for fieldname, fieldtype, label, reqd, options, description in WEB_FORM_FIELDS:
		if fieldname == "department":
			options = get_web_form_department_options()
		wf.append(
			"web_form_fields",
			{
				"fieldname": fieldname,
				"fieldtype": fieldtype,
				"label": label,
				"reqd": reqd,
				"options": options,
				"description": description,
			},
		)
	wf.set("list_columns", [])
	for fieldname, fieldtype, label in (
		("designation", "Link", "Designation"),
		("department", "Link", "Department"),
		("no_of_positions", "Int", "Positions"),
		("status", "Select", "Status"),
		("rejection_reason", "Small Text", "Rejection Reason"),
	):
		wf.append("list_columns", {"fieldname": fieldname, "fieldtype": fieldtype, "label": label})
	wf.flags.ignore_permissions = True
	wf.save()


def _assign_requester_role():
	"""Managers (anyone others report to) and department approvers can request."""
	users = set(
		frappe.db.sql_list(
			"""select distinct m.user_id from `tabEmployee` m
			where m.user_id is not null and m.status = 'Active'
			and exists (select 1 from `tabEmployee` e where e.reports_to = m.name and e.status = 'Active')"""
		)
	)
	users |= set(frappe.get_all("Department Approver", pluck="approver", filters={"approver": ["is", "set"]}))
	for user in users:
		if user in ("Administrator", "Guest") or not frappe.db.exists("User", user):
			continue
		if not frappe.db.exists("Has Role", {"parent": user, "role": "Requisition Requester"}):
			frappe.get_doc("User", user).add_roles("Requisition Requester")
