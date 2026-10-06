"""Clustox employee-event notifications (daily scheduler).

Replaces the stock whole-company birthday / work-anniversary reminders with
personal messages, and adds a probation-evaluation reminder for HR:

  * Birthday         -> greeting to the employee, HR in CC.
  * Work anniversary -> congratulations to the employee and their manager
                        (reports_to), HR in CC.
  * Probation        -> reminder to HR one week before the scheduled
                        confirmation date (for employees not yet confirmed).

Wired in hooks.py `scheduler_events["daily"]`. The stock reminders
(`hrms.controllers.employee_reminders.*`) are left disabled in HR Settings so
employees don't receive both.
"""

import frappe
from frappe import _
from frappe.query_builder import DatePart
from frappe.query_builder.functions import Extract
from frappe.utils import add_days, formatdate, getdate

HR_CC = "hr@clustox.com"
# Send from the dedicated HRMS outgoing account (SendGrid).
SENDER = "noreply@frappe.theclustox.com"
PROBATION_REMINDER_LEAD_DAYS = 7


# ---------------------------------------------------------------- helpers
def _emp_email(emp) -> str | None:
	return emp.get("company_email") or emp.get("user_id") or emp.get("personal_email")


def _manager_email(emp) -> str | None:
	if not emp.get("reports_to"):
		return None
	m = frappe.db.get_value(
		"Employee", emp.reports_to, ["company_email", "user_id", "personal_email"], as_dict=True
	)
	return (m.company_email or m.user_id or m.personal_email) if m else None


def _employees_with_event_today(field: str, min_years: int = 0) -> list:
	"""Active employees whose `field` (a date) falls on today's month+day.
	`min_years` requires the date to be at least that many years in the past
	(used so a work anniversary is >= 1 completed year)."""
	today = getdate()
	Employee = frappe.qb.DocType("Employee")
	d = Employee[field]
	q = (
		frappe.qb.from_(Employee)
		.select(
			Employee.name, Employee.employee_name, Employee.first_name,
			Employee.company_email, Employee.personal_email, Employee.user_id,
			Employee.reports_to, Employee.date_of_joining,
		)
		.where(
			(Extract(DatePart.day, d) == today.day)
			& (Extract(DatePart.month, d) == today.month)
			& (Employee.status == "Active")
		)
	)
	if min_years:
		q = q.where(Extract(DatePart.year, d) <= today.year - min_years)
	return q.run(as_dict=True)


def _send(recipients, subject, message, cc=None, emp_name=None):
	recipients = [r for r in dict.fromkeys(recipients) if r]
	cc = [c for c in dict.fromkeys(cc or []) if c and c not in recipients]
	if not recipients:
		return
	frappe.sendmail(
		sender=SENDER, recipients=recipients, cc=cc, subject=subject, message=message,
		reference_doctype="Employee" if emp_name else None, reference_name=emp_name,
	)


def _wish(greeting_html):
	return (
		f"<div style='font-family:Inter,Arial,sans-serif;font-size:15px;color:#1b2430;line-height:1.6'>"
		f"{greeting_html}"
		f"<p style='margin-top:18px;color:#59667a'>Warm regards,<br><b>Clustox HR</b></p></div>"
	)


# ---------------------------------------------------------------- triggers
def send_birthday_greetings():
	for emp in _employees_with_event_today("date_of_birth"):
		to = _emp_email(emp)
		if not to:
			continue
		first = emp.first_name or emp.employee_name
		msg = _wish(
			f"<p>Dear {frappe.utils.escape_html(first)},</p>"
			f"<p>Wishing you a very <b>Happy Birthday</b>! 🎉</p>"
			f"<p>Thank you for being part of the Clustox family. We hope your day is "
			f"filled with joy and celebration.</p>"
		)
		try:
			_send([to], _("Happy Birthday, {0}! 🎉").format(first), msg, cc=[HR_CC], emp_name=emp.name)
		except Exception:
			frappe.log_error(title="birthday greeting failed", message=frappe.get_traceback())


def send_work_anniversary_greetings():
	today = getdate()
	for emp in _employees_with_event_today("date_of_joining", min_years=1):
		to = _emp_email(emp)
		if not to:
			continue
		years = today.year - getdate(emp.date_of_joining).year
		label = _("year") if years == 1 else _("years")
		first = emp.first_name or emp.employee_name
		recipients = [to]
		mgr = _manager_email(emp)
		if mgr:
			recipients.append(mgr)
		msg = _wish(
			f"<p>Dear {frappe.utils.escape_html(first)},</p>"
			f"<p>Congratulations on completing <b>{years} {label}</b> at Clustox! 🎉</p>"
			f"<p>Thank you for your dedication and contributions over this time. "
			f"Here's to many more milestones together.</p>"
		)
		try:
			_send(
				recipients,
				_("Happy {0}-{1} Work Anniversary, {2}! 🎉").format(years, label, first),
				msg, cc=[HR_CC], emp_name=emp.name,
			)
		except Exception:
			frappe.log_error(title="anniversary greeting failed", message=frappe.get_traceback())


def send_probation_reminders():
	due = add_days(getdate(), PROBATION_REMINDER_LEAD_DAYS)
	emps = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"scheduled_confirmation_date": due,
			"final_confirmation_date": ["is", "not set"],
		},
		fields=["name", "employee_name", "date_of_joining", "scheduled_confirmation_date", "reports_to"],
	)
	for emp in emps:
		mgr_name = frappe.db.get_value("Employee", emp.reports_to, "employee_name") if emp.reports_to else "—"
		msg = _wish(
			f"<p>This is a reminder that the probation period for "
			f"<b>{frappe.utils.escape_html(emp.employee_name)}</b> ({emp.name}) is due for "
			f"evaluation on <b>{formatdate(emp.scheduled_confirmation_date)}</b> "
			f"(one week from today).</p>"
			f"<ul><li>Manager: {frappe.utils.escape_html(mgr_name or '—')}</li>"
			f"<li>Date of joining: {formatdate(emp.date_of_joining)}</li></ul>"
			f"<p>Please complete the probation evaluation before the due date.</p>"
		)
		try:
			_send(
				[HR_CC],
				_("Probation evaluation due in {0} days — {1} ({2})").format(
					PROBATION_REMINDER_LEAD_DAYS, emp.employee_name,
					formatdate(emp.scheduled_confirmation_date)),
				msg, emp_name=emp.name,
			)
		except Exception:
			frappe.log_error(title="probation reminder failed", message=frappe.get_traceback())


# ---------------------------------------------------------------- dev helpers
def disable_stock_reminders():
	"""Turn off the built-in whole-company birthday/anniversary emails."""
	frappe.db.set_single_value("HR Settings", "send_birthday_reminders", 0)
	frappe.db.set_single_value("HR Settings", "send_work_anniversary_reminders", 0)
	frappe.db.commit()
	print("stock birthday/anniversary reminders disabled:",
		  frappe.db.get_single_value("HR Settings", "send_birthday_reminders"),
		  frappe.db.get_single_value("HR Settings", "send_work_anniversary_reminders"))


def preview():
	"""DRY-RUN: list who would be emailed today, without sending."""
	today = getdate()
	print("today:", today)
	b = _employees_with_event_today("date_of_birth")
	print(f"\nBirthdays today: {len(b)}")
	for e in b:
		print("  ", e.name, e.employee_name, "-> to", _emp_email(e), "| cc", HR_CC)
	a = _employees_with_event_today("date_of_joining", min_years=1)
	print(f"\nWork anniversaries today: {len(a)}")
	for e in a:
		yrs = today.year - getdate(e.date_of_joining).year
		print("  ", e.name, e.employee_name, f"({yrs}y)", "-> to", _emp_email(e),
			  "+ mgr", _manager_email(e), "| cc", HR_CC)
	due = add_days(today, PROBATION_REMINDER_LEAD_DAYS)
	p = frappe.get_all("Employee", filters={"status": "Active", "scheduled_confirmation_date": due,
		"final_confirmation_date": ["is", "not set"]}, fields=["name", "employee_name"])
	print(f"\nProbation due on {due} (reminder today): {len(p)} -> to {HR_CC}")
	for e in p:
		print("  ", e.name, e.employee_name)


def test_send(to_email):
	"""Send one sample of each email to `to_email` only (for formatting review)."""
	_send([to_email], "[TEST] Happy Birthday, Sample! 🎉",
		  _wish("<p>Dear Sample,</p><p>Wishing you a very <b>Happy Birthday</b>! 🎉</p>"
				"<p>Thank you for being part of the Clustox family.</p>"))
	_send([to_email], "[TEST] Happy 3-years Work Anniversary, Sample! 🎉",
		  _wish("<p>Dear Sample,</p><p>Congratulations on completing <b>3 years</b> at Clustox! 🎉</p>"
				"<p>Thank you for your dedication.</p>"))
	_send([to_email], "[TEST] Probation evaluation due in 7 days — Sample (01-01-2026)",
		  _wish("<p>Reminder: probation for <b>Sample</b> is due for evaluation on <b>01-01-2026</b>.</p>"))
	frappe.db.commit()
	print("sent 3 test emails to", to_email)
