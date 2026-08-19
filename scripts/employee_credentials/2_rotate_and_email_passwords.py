"""
Generates a fresh unique 20-character alphanumeric password for every
Employee-linked User on this site, sets it on their account, and emails it
to them.

Scope: dynamically queries the database for every Employee record that is
(a) Active and (b) linked to an enabled User -- NOT a hardcoded list. This
is intentional so it automatically covers however many users actually exist
on a given site (local test data vs. dev vs. live), instead of drifting out
of date. It will touch every matching account it finds, including ones that
already have a real password set -- review COUNT_ONLY output before ever
flipping SEND_EMAILS.

SEND_EMAILS:
  False -> sets real passwords (works anywhere), but only PREVIEWS each
           email's content instead of sending (safe on machines where the
           configured SMTP/SendGrid key doesn't authenticate).
  True  -> does the same, but actually sends via frappe.sendmail(), which
           uses the default Outgoing Email Account already configured
           (SendGrid). Only flip this on a machine where that account
           actually authenticates (currently: the GPU machine).

COUNT_ONLY:
  True  -> does nothing except print who WOULD be affected (no password
           changes, no emails). Run this first on any new environment.

Run from frappe-bench/sites:
  env/bin/python /path/to/rotate_and_email_passwords.py
"""

import frappe
import json
import secrets
import string
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

COUNT_ONLY = True   # run this first on a new environment -- touches nothing
SEND_EMAILS = False  # flip to True only on the machine where SMTP auth works
SITE_NAME = 'hrms.localhost'  # change to the real site name on the target machine
SITE_URL = "http://localhost:8000"  # change to the real login URL on the target machine

# Accounts to never touch even if they match the query below.
EXCLUDE_EMAILS = {"Administrator", "Guest"}

frappe.init(site=SITE_NAME)
frappe.connect()
ALPHABET = string.ascii_letters + string.digits


def get_target_users():
	"""Every enabled User linked to an Active Employee, on this site, right now."""
	rows = frappe.db.sql(
		"""
		SELECT e.user_id, e.employee_name, e.employee_number
		FROM `tabEmployee` e
		INNER JOIN `tabUser` u ON u.name = e.user_id
		WHERE e.status = 'Active'
		  AND e.user_id IS NOT NULL AND e.user_id != ''
		  AND u.enabled = 1
		ORDER BY e.employee_number
		""",
		as_dict=True,
	)
	return [r for r in rows if r.user_id not in EXCLUDE_EMAILS]


def gen_password(length=20, used=None):
	used = used or set()
	while True:
		pwd = ''.join(secrets.choice(ALPHABET) for _ in range(length))
		if pwd not in used:
			return pwd


def build_email(full_name, email, password):
	subject = "Your Clustox HRMS login"
	text = (
		f"Hi {full_name},\n\n"
		f"Your Clustox HRMS account is ready.\n\n"
		f"Login: {SITE_URL}\n"
		f"Email: {email}\n"
		f"Password: {password}\n\n"
		f"Please change your password after logging in for the first time.\n"
	)
	html = f"""
	<div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
		<p>Hi {full_name},</p>
		<p>Your Clustox HRMS account is ready.</p>
		<p>
			<strong>Login:</strong> <a href="{SITE_URL}">{SITE_URL}</a><br>
			<strong>Email:</strong> {email}<br>
			<strong>Password:</strong> <code>{password}</code>
		</p>
		<p>Please change your password after logging in for the first time.</p>
	</div>
	"""
	return subject, text, html


targets = get_target_users()

if COUNT_ONLY:
	print("COUNT_ONLY_RESULT_START")
	print(json.dumps({
		"count": len(targets),
		"users": [{"email": t.user_id, "name": t.employee_name, "code": t.employee_number} for t in targets],
	}, indent=2))
	print("COUNT_ONLY_RESULT_END")
	raise SystemExit(0)

# --- Phase 1: generate every password up front, then hard-verify uniqueness
# across the WHOLE batch before touching a single account. If this ever
# fails, nothing has been changed and nothing has been sent yet.
used_passwords = set()
password_by_email = {}
for t in targets:
	pwd = gen_password(20, used_passwords)
	used_passwords.add(pwd)
	password_by_email[t.user_id] = pwd

all_pwds = list(password_by_email.values())
assert len(all_pwds) == len(set(all_pwds)), (
	"Password uniqueness check failed -- aborting before any account was touched."
)
assert all(len(p) == 20 for p in all_pwds), "Password length check failed -- aborting."
print(f"UNIQUENESS_CHECK_PASSED: {len(all_pwds)} passwords, all unique, all 20 characters.")

# --- Phase 2: apply. Each password was already generated + verified above,
# so this loop only sets/sends -- it never generates a password itself.
results = []
audit = []  # kept local only, never printed

for t in targets:
	email = t.user_id
	pwd = password_by_email[email]
	record = {"email": email, "employee": t.employee_number}

	# Step 1: stage the password change, but do NOT commit yet. As long as
	# this stays uncommitted, it's fully reversible -- a failure here means
	# nothing was sent and nothing durable happened, so a later run will
	# simply pick this employee up again with a fresh password.
	try:
		user = frappe.get_doc("User", email)
		full_name = user.full_name or t.employee_name or email
		subject, text, html = build_email(full_name, email, pwd)

		user.new_password = pwd
		user.send_welcome_email = 0
		user.save(ignore_permissions=True)
	except Exception as e:
		frappe.db.rollback()
		record["status"] = "ERROR_BEFORE_SEND"
		record["error"] = str(e)
		results.append(record)
		continue

	record["password_set"] = True
	audit.append({"email": email, "password": pwd})

	# Step 2: send, while the password change is still only staged. If this
	# fails, roll back -- the account keeps its old, still-valid password,
	# and nobody was ever told about a password that doesn't work.
	if SEND_EMAILS:
		try:
			frappe.sendmail(recipients=[email], subject=subject, message=html, now=True)
		except Exception as e:
			frappe.db.rollback()
			record["status"] = "ERROR_SEND_FAILED"
			record["error"] = str(e)
			results.append(record)
			continue
		record["status"] = "SENT"
	else:
		record["status"] = "DRY_RUN_PREVIEW"
		record["preview_subject"] = subject
		record["preview_text"] = text

	# Step 3: commit. By now the email (if any) has already been sent, so
	# this is the one step that can't be undone by rolling back -- a failure
	# here is rare (a local DB write, not a network call) but means the
	# emailed password may not actually be valid yet. Never silently retry
	# or regenerate for this account -- flag it for a human to reconcile.
	try:
		frappe.db.commit()
	except Exception as e:
		record["status"] = "CRITICAL_SENT_BUT_NOT_COMMITTED"
		record["error"] = str(e)

	results.append(record)

# Audit file kept local for our own recovery only -- never printed to logs/chat.
# Resolved next to this script (not the process's cwd -- the README has you
# run this from frappe-bench/sites, which is a different directory) so it
# always lands somewhere covered by this folder's .gitignore.
# Delete this file once you've confirmed all emails arrived correctly.
audit_path = SCRIPT_DIR / 'password_audit_DO_NOT_SHARE.json'
with open(audit_path, 'w') as f:
	json.dump(audit, f, indent=2)

# Printed summary intentionally omits password values.
summary = [{k: v for k, v in r.items() if k not in ("preview_text",)} for r in results]
print("ROTATE_RESULT_START")
print(json.dumps(summary, indent=2))
print("ROTATE_RESULT_END")

if not SEND_EMAILS and results:
	print("SAMPLE_EMAIL_PREVIEW_START")
	print(results[0].get("preview_text", "(no preview available)"))
	print("SAMPLE_EMAIL_PREVIEW_END")

SAFE_TO_RETRY_STATUSES = {"ERROR_BEFORE_SEND", "ERROR_SEND_FAILED"}
critical = [r for r in results if r.get("status") == "CRITICAL_SENT_BUT_NOT_COMMITTED"]
retryable_errors = [r for r in results if r.get("status") in SAFE_TO_RETRY_STATUSES]

if critical:
	print(f"CRITICAL: {len(critical)} account(s) were emailed a password whose DB commit then "
	      f"failed -- do NOT rerun this script for these accounts. Verify/fix each one by hand:")
	print(json.dumps([{"email": r["email"], "error": r.get("error")} for r in critical], indent=2))

if retryable_errors:
	print(f"COMPLETED_WITH_ERRORS: {len(retryable_errors)} of {len(results)} account(s) were not "
	      f"touched or notified and are safe to retry on the next run.")

if critical or retryable_errors:
	raise SystemExit(1)
