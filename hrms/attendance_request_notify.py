"""Email notifications for Attendance Requests (WFH / Missed Punch / On Duty).

Clustox approval model: an employee raises an Attendance Request (it stays a
draft), their direct manager (`reports_to`) reviews and submits it to approve.
Frappe HR has no built-in notification for this doctype, so:

  * when a request is raised  -> email the employee's manager to review it
  * when it is approved (submitted) -> email the employee

Failures are logged, never raised, so a notification problem can't block the
request itself.
"""

import frappe
from frappe.utils import format_date

PORTAL = "https://frappe.theclustox.com/hrms"


def _range(doc):
    if doc.to_date and str(doc.to_date) != str(doc.from_date):
        return f"{format_date(doc.from_date)} to {format_date(doc.to_date)}"
    return format_date(doc.from_date)


def _manager_user(employee):
    reports_to = frappe.db.get_value("Employee", employee, "reports_to")
    if not reports_to:
        return None
    return frappe.db.get_value("Employee", reports_to, "user_id")


def notify_manager(doc, method=None):
    """Email the employee's manager that a request needs their approval."""
    try:
        manager = _manager_user(doc.employee)
        if not manager:
            return
        emp_name = frappe.db.get_value("Employee", doc.employee, "employee_name") or doc.employee
        frappe.sendmail(
            recipients=[manager],
            subject=f"{emp_name} submitted a {doc.reason} request",
            message=f"""<div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;line-height:1.6">
<p>Hi,</p>
<p><b>{frappe.utils.escape_html(emp_name)}</b> has submitted a <b>{frappe.utils.escape_html(doc.reason)}</b>
request for <b>{_range(doc)}</b> and it is awaiting your approval.</p>
<p>Please review and approve it here:
<a href="{PORTAL}">Open HR portal</a></p>
<p>Thanks,<br>Clustox HR</p></div>""",
            now=False,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "attendance_request_notify.notify_manager")


def notify_employee(doc, method=None):
    """Email the employee that their request was approved."""
    try:
        emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")
        if not emp_user:
            return
        frappe.sendmail(
            recipients=[emp_user],
            subject=f"Your {doc.reason} request was approved",
            message=f"""<div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;line-height:1.6">
<p>Hi,</p>
<p>Your <b>{frappe.utils.escape_html(doc.reason)}</b> request for <b>{_range(doc)}</b> has been
<b>approved</b>.</p>
<p>You can view it here: <a href="{PORTAL}">Open HR portal</a></p>
<p>Thanks,<br>Clustox HR</p></div>""",
            now=False,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "attendance_request_notify.notify_employee")
