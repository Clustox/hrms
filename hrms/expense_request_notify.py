"""Stage email notifications for Expense Request as it moves through the
Manager -> HR -> Accounts approval workflow.

On each workflow-state change:
  * -> Pending Manager  : email the employee's manager to review
  * -> Pending HR        : email the HR team inbox
  * -> Pending Accounts  : email the Accounts team inbox
  * -> Completed         : email the requester (reimbursed)
  * -> Rejected          : email the requester (with the reason)

Failures are logged, never raised, so a mail problem can't block the request.
"""

import frappe
from frappe.utils import escape_html, fmt_money

PORTAL = "https://frappe.theclustox.com/hrms"
HR_INBOX = "hr@clustox.com"
ACCOUNTS_INBOX = "accounts@clustox.com"


def _request_url(doc):
	return f"{PORTAL}/expense-requests/{doc.name}"


def _money(doc):
	return fmt_money(doc.amount, currency=doc.currency)


def _wrap(body):
	return (
		'<div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;line-height:1.6">'
		+ body
		+ '<p>Thanks,<br>Clustox HR</p></div>'
	)


def _send(recipients, subject, body):
	frappe.sendmail(recipients=recipients, subject=subject, message=_wrap(body), now=False)


def _notify_requester(doc, etype, link, status_line):
	emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if not emp_user:
		return
	_send(
		[emp_user],
		f"Update on your {etype} expense request",
		f"<p>Hi,</p><p>Your <b>{etype}</b> expense request for <b>{_money(doc)}</b> moved forward. "
		f"{status_line}</p>{link}",
	)


def notify_on_state_change(doc, method=None):
	"""doc_events on_update hook: email the right party when workflow_state changes."""
	try:
		new_state = doc.workflow_state
		before = doc.get_doc_before_save()
		old_state = before.workflow_state if before else None
		if new_state == old_state:
			return

		emp_name = escape_html(doc.employee_name or doc.employee)
		etype = escape_html(doc.expense_type or "")
		link = f'<p>Open the request: <a href="{_request_url(doc)}">{doc.name}</a></p>'

		if new_state == "Pending Manager" and doc.manager:
			_send(
				[doc.manager],
				f"{emp_name} submitted a {etype} expense request",
				f"<p>Hi,</p><p><b>{emp_name}</b> submitted a <b>{etype}</b> expense request for "
				f"<b>{_money(doc)}</b> and it is awaiting your approval.</p>{link}",
			)
		elif new_state == "Pending HR":
			_send(
				[HR_INBOX],
				f"Expense request awaiting HR approval — {emp_name}",
				f"<p>Hi,</p><p>A <b>{etype}</b> expense request from <b>{emp_name}</b> for "
				f"<b>{_money(doc)}</b> is awaiting HR approval.</p>{link}",
			)
			# Reaching HR from the manager stage means the manager approved; tell
			# the requester (not on the Draft -> Pending HR auto-skip, which is no
			# approval). Spec: the requester hears on each approval.
			if old_state == "Pending Manager":
				_notify_requester(doc, etype, link, "Your manager approved it; it is now with HR.")
		elif new_state == "Pending Accounts":
			_send(
				[ACCOUNTS_INBOX],
				f"Expense request awaiting Accounts — {emp_name}",
				f"<p>Hi,</p><p>A <b>{etype}</b> expense request from <b>{emp_name}</b> for "
				f"<b>{_money(doc)}</b> is approved and awaiting reimbursement by Accounts.</p>{link}",
			)
			_notify_requester(doc, etype, link, "HR approved it; it is now with Accounts for reimbursement.")
		elif new_state in ("Completed", "Rejected"):
			emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")
			if not emp_user:
				return
			if new_state == "Completed":
				_send(
					[emp_user],
					f"Your {etype} expense request was reimbursed",
					f"<p>Hi,</p><p>Your <b>{etype}</b> expense request for <b>{_money(doc)}</b> has been "
					f"<b>completed</b> and reimbursed.</p>{link}",
				)
			else:
				reason = escape_html(doc.rejection_reason or "")
				note = escape_html(doc.rejection_note or "")
				detail = f" Reason: <b>{reason}</b>." if reason else ""
				detail += f" Note: {note}" if note else ""
				_send(
					[emp_user],
					f"Your {etype} expense request was rejected",
					f"<p>Hi,</p><p>Your <b>{etype}</b> expense request for <b>{_money(doc)}</b> was "
					f"<b>rejected</b>.{detail}</p>{link}",
				)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "expense_request_notify.notify_on_state_change")
