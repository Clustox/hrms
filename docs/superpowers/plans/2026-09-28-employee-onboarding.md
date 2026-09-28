# New-Employee Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let HR onboard a new hire in one action (create Employee + login + invite), have the hire self-complete their personal details + document uploads in `/hrms`, and let HR review/approve — all tracked by a status on the Employee.

**Architecture:** Reuse the existing Employee doctype fields and the PR #15 self-service Profile. Add a status field + attachment fields (shipped as fixtures + created idempotently by a setup script), a small backend module `hrms/onboarding.py` with whitelisted methods for the state transitions, HR desk buttons + a "Pending Onboarding" report, and a stepped onboarding view in the Vue PWA. No separate staging doctype; the hire edits their own record (record-scoped from PR #15).

**Tech Stack:** Frappe/ERPNext v15 (Python 3), Frappe test framework (`FrappeTestCase`), Vue 3 PWA (`frontend/`), MariaDB.

## Global Constraints

- Site is `hrms.localhost`; run code in the container: `sudo docker exec -w /home/frappe/frappe-bench docker-frappe-1 bench --site test_onboarding.localhost <cmd>`. **NEVER `bench console`** (IPython mangles multi-line) — use `bench execute` / `bench run-tests`.
- The running app is `/opt/app/hrms` (bind-mounted); deploy = merge to `develop` → Jenkins redeploy → `bench migrate` (applies fixtures) → `bench build --app hrms`.
- Custom fields are created idempotently by a setup script **and** registered in `hooks.py` `fixtures` so they persist/reproduce on migrate. Follow the existing pattern in `setup/permissions/*` and the `fixtures` block already in `hooks.py` (CNIC fields from #8).
- Mandatory-field enforcement is **server-side** (must hold for Desk, mobile app, and direct API) — mirror how `leave_application.py::validate_medical_certificate` (#24) does it.
- Existing employees have blank `custom_onboarding_status` and must never enter the flow or appear in Pending Onboarding.
- `custom_onboarding_status`, `custom_onboarding_submitted_on`, `custom_onboarding_notes` are system/HR-driven — **not** ESS-writable. Status changes only via the whitelisted methods.
- Reuse provisioning logic from `hrms/provision_pilot.py` + `hrms/send_pilot_invites.py` (refactor into `hrms/onboarding.py`); welcome email uses `User._reset_password()` for the set-password link + the `/hrms/login` bookmark.
- Frontend: edit under `frontend/src/`, then `bench build --app hrms`; reuse `frontend/src/components/ProfileChildTableModal.vue` and `hrms.api.get_doctype_fields`.
- Branch: `feature/employee-onboarding` (already created off `develop`). Commit frequently.

## File Structure

- `hrms/hr/doctype/employee_onboarding_document/` (**create**) — new child doctype (istable) with `document_type` + `attachment`.
- `setup/onboarding/apply_onboarding_schema.py` (**create**) — idempotent creation of all custom fields.
- `hrms/onboarding.py` (**create**) — backend: `validate_onboarding_submission`, `onboard_employee`, `submit_onboarding`, `approve_onboarding`, `request_onboarding_changes`, `_send_hr_notification`, `_send_employee_notification`.
- `hrms/tests/__init__.py`, `hrms/tests/test_onboarding.py` (**create**) — unit/flow tests.
- `hooks.py` (**modify**) — add the new custom field names to `fixtures`.
- `setup/permissions/apply_self_service.py` (**modify**) — grant ESS write on the onboarding personal fields on the own record (permlevel audit).
- `hrms/public/js/erpnext/employee.js` (**modify**) — HR Approve / Request-changes buttons + an "Onboard" entry point.
- `hrms/hr/report/pending_onboarding/` (**create**) — Query Report listing Invited/Submitted employees.
- `frontend/src/views/Profile.vue` (**modify**) + `frontend/src/components/OnboardingSteps.vue` (**create**) — the stepped `/hrms` onboarding view.

---

### Task 1: Onboarding schema (child doctype + custom fields)

**Files:**
- Create: `hrms/hr/doctype/employee_onboarding_document/employee_onboarding_document.json`
- Create: `hrms/hr/doctype/employee_onboarding_document/employee_onboarding_document.py`
- Create: `hrms/hr/doctype/employee_onboarding_document/__init__.py`
- Create: `setup/onboarding/__init__.py`, `setup/onboarding/apply_onboarding_schema.py`
- Modify: `hooks.py` (`fixtures` list)
- Test: `hrms/tests/test_onboarding.py`

**Interfaces:**
- Produces: `setup.onboarding.apply_onboarding_schema.run()` — idempotent; creates the child doctype dependency assumed present and all custom fields. After it runs, these fields exist: `Employee.custom_onboarding_status` (Select `\nInvited\nSubmitted\nApproved`), `Employee.custom_onboarding_submitted_on` (Datetime, read_only), `Employee.custom_onboarding_notes` (Small Text, read_only), `Employee.custom_onboarding_documents` (Table → `Employee Onboarding Document`), `Employee Education.custom_certificate` (Attach), `Employee External Work History.custom_experience_letter` (Attach).

- [ ] **Step 1: Create the child doctype JSON**

`hrms/hr/doctype/employee_onboarding_document/employee_onboarding_document.json`:
```json
{
 "actions": [],
 "creation": "2026-09-28 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["document_type", "attachment"],
 "fields": [
  {"fieldname": "document_type", "fieldtype": "Data", "in_list_view": 1, "label": "Document Type", "reqd": 1, "columns": 4},
  {"fieldname": "attachment", "fieldtype": "Attach", "in_list_view": 1, "label": "Attachment", "reqd": 1, "columns": 6}
 ],
 "istable": 1,
 "editable_grid": 1,
 "links": [],
 "modified": "2026-09-28 00:00:00",
 "module": "HR",
 "name": "Employee Onboarding Document",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC"
}
```

- [ ] **Step 2: Create the child doctype controller + init**

`hrms/hr/doctype/employee_onboarding_document/__init__.py`: empty file.
`hrms/hr/doctype/employee_onboarding_document/employee_onboarding_document.py`:
```python
# Copyright (c) 2026, Clustox and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class EmployeeOnboardingDocument(Document):
	pass
```

- [ ] **Step 3: Create the schema setup script**

`setup/onboarding/__init__.py`: empty file.
`setup/onboarding/apply_onboarding_schema.py`:
```python
"""Idempotent creation of onboarding custom fields. Run:
  bench --site test_onboarding.localhost execute setup.onboarding.apply_onboarding_schema.run
Re-runnable. The Employee Onboarding Document child doctype is shipped as code
(hrms/hr/doctype/employee_onboarding_document) and installed by migrate.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def run():
	print("ONBOARDING_SCHEMA_START")
	fields = {
		"Employee": [
			{
				"fieldname": "custom_onboarding_status",
				"label": "Onboarding Status",
				"fieldtype": "Select",
				"options": "\nInvited\nSubmitted\nApproved",
				"read_only": 1,
				"insert_after": "status",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "custom_onboarding_submitted_on",
				"label": "Onboarding Submitted On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"insert_after": "custom_onboarding_status",
			},
			{
				"fieldname": "custom_onboarding_notes",
				"label": "Onboarding Review Notes",
				"fieldtype": "Small Text",
				"read_only": 1,
				"insert_after": "custom_onboarding_submitted_on",
			},
			{
				"fieldname": "custom_onboarding_documents",
				"label": "Onboarding Documents",
				"fieldtype": "Table",
				"options": "Employee Onboarding Document",
				"insert_after": "custom_onboarding_notes",
			},
		],
		"Employee Education": [
			{
				"fieldname": "custom_certificate",
				"label": "Certificate",
				"fieldtype": "Attach",
				"insert_after": "grade",
			},
		],
		"Employee External Work History": [
			{
				"fieldname": "custom_experience_letter",
				"label": "Experience Letter",
				"fieldtype": "Attach",
				"insert_after": "total_experience",
			},
		],
	}
	create_custom_fields(fields, update=True)
	frappe.db.commit()
	print("ONBOARDING_SCHEMA_DONE")
```

- [ ] **Step 4: Register the custom fields as fixtures**

In `hooks.py`, extend the existing `fixtures` list's Custom Field name filter to also include the new fields (so `bench export-fixtures`/`migrate` carry them). Add these names to the `["name", "in", [...]]` list:
```python
"Employee-custom_onboarding_status",
"Employee-custom_onboarding_submitted_on",
"Employee-custom_onboarding_notes",
"Employee-custom_onboarding_documents",
"Employee Education-custom_certificate",
"Employee External Work History-custom_experience_letter",
```

- [ ] **Step 5: Write the failing test**

`hrms/tests/__init__.py`: empty file.
`hrms/tests/test_onboarding.py`:
```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestOnboardingSchema(FrappeTestCase):
	def test_onboarding_fields_exist(self):
		from setup.onboarding.apply_onboarding_schema import run
		run()
		meta = frappe.get_meta("Employee")
		for fn in ("custom_onboarding_status", "custom_onboarding_submitted_on",
		           "custom_onboarding_notes", "custom_onboarding_documents"):
			self.assertTrue(meta.get_field(fn), f"missing Employee.{fn}")
		self.assertTrue(frappe.get_meta("Employee Education").get_field("custom_certificate"))
		self.assertTrue(frappe.get_meta("Employee External Work History").get_field("custom_experience_letter"))
		self.assertTrue(frappe.db.exists("DocType", "Employee Onboarding Document"))
```

- [ ] **Step 6: Run migrate (installs child doctype) then the test**

Run: `bench --site test_onboarding.localhost migrate`
Then: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_onboarding_fields_exist`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hrms/hr/doctype/employee_onboarding_document setup/onboarding hooks.py hrms/tests
git commit -m "feat(onboarding): schema — status/notes/docs fields + attachments + child doctype"
```

---

### Task 2: `validate_onboarding_submission`

**Files:**
- Create: `hrms/onboarding.py`
- Test: `hrms/tests/test_onboarding.py`

**Interfaces:**
- Produces: `validate_onboarding_submission(employee: str) -> list[str]` — returns the list of missing mandatory field **labels** (empty list = ready to submit). Mandatory: `custom_cnic_no`, `custom_cnic_expiry_date`, `current_address`, `permanent_address`, `blood_group`, `person_to_be_contacted`, `emergency_phone_number`, `relation`.

- [ ] **Step 1: Write the failing test**

Append to `hrms/tests/test_onboarding.py`:
```python
class TestValidateSubmission(FrappeTestCase):
	def _emp(self, **kw):
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Test", "last_name": "Hire",
			"company": "Clustox", "status": "Active",
			"date_of_joining": "2026-01-01", "gender": "Male",
			"date_of_birth": "1995-01-01",
			**kw,
		}).insert(ignore_permissions=True)
		return emp.name

	def test_missing_fields_listed(self):
		from hrms.onboarding import validate_onboarding_submission
		name = self._emp()
		missing = validate_onboarding_submission(name)
		self.assertIn("CNIC", " ".join(missing))
		self.assertIn("Blood Group", " ".join(missing))

	def test_complete_returns_empty(self):
		from hrms.onboarding import validate_onboarding_submission
		name = self._emp(custom_cnic_no="1234512345671", custom_cnic_expiry_date="2030-01-01",
		                 current_address="A", permanent_address="B", blood_group="O+",
		                 person_to_be_contacted="X", emergency_phone_number="0300",
		                 relation="Father")
		self.assertEqual(validate_onboarding_submission(name), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_missing_fields_listed`
Expected: FAIL (module `hrms.onboarding` has no `validate_onboarding_submission`).

- [ ] **Step 3: Write minimal implementation**

`hrms/onboarding.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_missing_fields_listed`
Then: `... --test test_complete_returns_empty`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hrms/onboarding.py hrms/tests/test_onboarding.py
git commit -m "feat(onboarding): validate_onboarding_submission — server-side mandatory check"
```

---

### Task 3: `onboard_employee` (HR create → login + invite)

**Files:**
- Modify: `hrms/onboarding.py`
- Test: `hrms/tests/test_onboarding.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (uses the status field from Task 1).
- Produces: `@frappe.whitelist() onboard_employee(employee: str, send_invite: int = 1) -> dict` — for an existing Employee record with a `company_email`/`personal_email`: creates a System User (role `Employee Self Service`, `send_welcome_email=0`), links `Employee.user_id`, adds a self-scope User Permission (Employee = this record), sets `custom_onboarding_status = "Invited"`, and (if `send_invite`) emails a set-password link + `/hrms/login`. Idempotent: if the user exists, links + sets status without recreating. Returns `{"user": <uid>, "status": "Invited"}`.

- [ ] **Step 1: Write the failing test**

Append:
```python
class TestOnboardEmployee(FrappeTestCase):
	def test_provisions_login_and_status(self):
		from hrms.onboarding import onboard_employee
		email = "test.hire.onb@example.com"
		frappe.db.delete("User", {"name": email})
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Onb", "last_name": "Hire",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "company_email": email,
		}).insert(ignore_permissions=True)
		res = onboard_employee(emp.name, send_invite=0)
		self.assertEqual(res["status"], "Invited")
		self.assertTrue(frappe.db.exists("User", email))
		self.assertEqual(frappe.db.get_value("Employee", emp.name, "custom_onboarding_status"), "Invited")
		self.assertEqual(frappe.db.get_value("Employee", emp.name, "user_id"), email)
		self.assertIn("Employee Self Service", frappe.get_roles(email))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_provisions_login_and_status`
Expected: FAIL (`onboard_employee` not defined).

- [ ] **Step 3: Write minimal implementation**

Append to `hrms/onboarding.py`:
```python
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
	if emp.user_id != email:
		emp.db_set("user_id", email)
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
```
(Note: reuse/replace with the exact welcome copy from `hrms/send_pilot_invites.py` if HR prefers that wording.)

- [ ] **Step 4: Run test to verify it passes**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_provisions_login_and_status`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hrms/onboarding.py hrms/tests/test_onboarding.py
git commit -m "feat(onboarding): onboard_employee — provision login, self-scope, invite"
```

---

### Task 4: Status transitions — submit / approve / request-changes

**Files:**
- Modify: `hrms/onboarding.py`
- Test: `hrms/tests/test_onboarding.py`

**Interfaces:**
- Consumes: `validate_onboarding_submission` (Task 2).
- Produces:
  - `@frappe.whitelist() submit_onboarding(employee: str) -> dict` — validates mandatory; if missing, `frappe.throw` listing them; else sets `Submitted` + `custom_onboarding_submitted_on = now`, notifies HR. Returns `{"status": "Submitted"}`.
  - `@frappe.whitelist() approve_onboarding(employee: str) -> dict` — requires HR role; sets `Approved`; notifies employee. Idempotent.
  - `@frappe.whitelist() request_onboarding_changes(employee: str, note: str) -> dict` — requires HR role; sets `Invited` + `custom_onboarding_notes = note`; notifies employee.

- [ ] **Step 1: Write the failing test**

Append:
```python
class TestTransitions(FrappeTestCase):
	def _hire(self, complete):
		emp = frappe.get_doc({
			"doctype": "Employee", "first_name": "Trans", "last_name": "Hire",
			"company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
			"gender": "Male", "custom_onboarding_status": "Invited",
		})
		if complete:
			emp.update({"custom_cnic_no": "1", "custom_cnic_expiry_date": "2030-01-01",
			            "current_address": "A", "permanent_address": "B", "blood_group": "O+",
			            "person_to_be_contacted": "X", "emergency_phone_number": "0300",
			            "relation": "Father"})
		return emp.insert(ignore_permissions=True).name

	def test_submit_blocked_when_incomplete(self):
		from hrms.onboarding import submit_onboarding
		name = self._hire(complete=False)
		with self.assertRaises(frappe.ValidationError):
			submit_onboarding(name)
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_status"), "Invited")

	def test_submit_then_approve(self):
		from hrms.onboarding import submit_onboarding, approve_onboarding
		name = self._hire(complete=True)
		self.assertEqual(submit_onboarding(name)["status"], "Submitted")
		self.assertEqual(approve_onboarding(name)["status"], "Approved")

	def test_request_changes_reverts(self):
		from hrms.onboarding import submit_onboarding, request_onboarding_changes
		name = self._hire(complete=True)
		submit_onboarding(name)
		request_onboarding_changes(name, "Fix your CNIC scan")
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_status"), "Invited")
		self.assertEqual(frappe.db.get_value("Employee", name, "custom_onboarding_notes"), "Fix your CNIC scan")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_submit_blocked_when_incomplete`
Expected: FAIL (functions not defined).

- [ ] **Step 3: Write minimal implementation**

Append to `hrms/onboarding.py`:
```python
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
		frappe.sendmail(recipients=recipients,
		                subject=_("Onboarding submitted: {0}").format(emp.employee_name),
		                message=_("{0} submitted their onboarding for review.").format(emp.employee_name),
		                now=True)


def _send_employee_notification(emp, message):
	if emp.user_id:
		frappe.sendmail(recipients=[emp.user_id], subject=_("Onboarding update"),
		                message=message, now=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add hrms/onboarding.py hrms/tests/test_onboarding.py
git commit -m "feat(onboarding): submit/approve/request-changes transitions + notifications"
```

---

### Task 5: Permissions — ESS can write own onboarding fields

**Files:**
- Modify: `setup/permissions/apply_self_service.py`
- Test: `hrms/tests/test_onboarding.py`

**Interfaces:**
- Consumes: the fields from Task 1.
- Produces: after running `setup.permissions.apply_self_service.run()`, an Employee Self Service user can `write` the mandatory onboarding fields **on their own record** and cannot write `custom_onboarding_status`. (The self-scope User Permission from Task 3 confines this to the own record.)

- [ ] **Step 1: Audit permlevels (manual)**

Run: `bench --site test_onboarding.localhost execute frappe.client.get_value --kwargs "{'doctype':'DocField','filters':{'parent':'Employee','fieldname':'custom_cnic_no'},'fieldname':'permlevel'}"` (repeat for each mandatory field) — confirm which are permlevel 0 (already writable by owner) vs >0.

- [ ] **Step 2: Write the failing test**

Append:
```python
class TestEssPerms(FrappeTestCase):
	def test_ess_can_write_own_cnic(self):
		from setup.permissions.apply_self_service import run as apply_ess
		apply_ess()
		email = "ess.perm.onb@example.com"
		frappe.db.delete("User", {"name": email})
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Ess",
		                       "send_welcome_email": 0, "user_type": "System User"})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles("Employee Self Service")
		emp = frappe.get_doc({"doctype": "Employee", "first_name": "Ess", "last_name": "Perm",
		                      "company": "Clustox", "status": "Active", "date_of_joining": "2026-01-01",
		                      "gender": "Male", "user_id": email}).insert(ignore_permissions=True)
		frappe.get_doc({"doctype": "User Permission", "user": email, "allow": "Employee",
		                "for_value": emp.name, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)
		self.assertTrue(frappe.has_permission("Employee", "write", doc=emp.name, user=email))
```

- [ ] **Step 3: Run test to verify current state**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding --test test_ess_can_write_own_cnic`
Expected: PASS if ESS already has write on own record (likely — PR #15). If FAIL, proceed to Step 4.

- [ ] **Step 4: Extend the ESS setup (only if Step 3 failed or a mandatory field is permlevel > 0)**

In `setup/permissions/apply_self_service.py`, ensure ESS has `write` at permlevel 0 on Employee (own record) and add a permlevel-1 write grant only for any confidential mandatory field identified in Step 1. Keep it minimal — do not broaden beyond the onboarding fields. Re-run and confirm the test passes.

- [ ] **Step 5: Commit**

```bash
git add setup/permissions/apply_self_service.py hrms/tests/test_onboarding.py
git commit -m "feat(onboarding): ESS write on own onboarding fields (scoped)"
```

---

### Task 6: HR desk — buttons + Pending Onboarding report

**Files:**
- Modify: `hrms/public/js/erpnext/employee.js`
- Create: `hrms/hr/report/pending_onboarding/__init__.py`, `pending_onboarding.json`, `pending_onboarding.py`

**Interfaces:**
- Consumes: `hrms.onboarding.onboard_employee` / `approve_onboarding` / `request_onboarding_changes`.
- Produces: HR-facing desk controls; no code consumed by later tasks.

- [ ] **Step 1: Add the Employee form buttons**

In `hrms/public/js/erpnext/employee.js`, inside the `frappe.ui.form.on("Employee", { refresh(frm) {...} })` handler, add (guard on HR roles):
```javascript
const HR = frappe.user.has_role(["HR Manager", "HR User", "System Manager"]);
if (HR && !frm.is_new()) {
    const st = frm.doc.custom_onboarding_status;
    if (!st) {
        frm.add_custom_button(__("Onboard (create login)"), () => {
            frappe.call({ method: "hrms.onboarding.onboard_employee",
                args: { employee: frm.doc.name }, freeze: true })
                .then(() => { frappe.show_alert(__("Invited")); frm.reload_doc(); });
        }, __("Onboarding"));
    }
    if (st === "Submitted") {
        frm.add_custom_button(__("Approve Onboarding"), () => {
            frappe.call({ method: "hrms.onboarding.approve_onboarding",
                args: { employee: frm.doc.name }, freeze: true })
                .then(() => frm.reload_doc());
        }, __("Onboarding"));
        frm.add_custom_button(__("Request Changes"), () => {
            frappe.prompt({ fieldname: "note", fieldtype: "Small Text",
                label: __("What needs fixing?"), reqd: 1 }, (v) => {
                frappe.call({ method: "hrms.onboarding.request_onboarding_changes",
                    args: { employee: frm.doc.name, note: v.note }, freeze: true })
                    .then(() => frm.reload_doc());
            });
        }, __("Onboarding"));
    }
}
```

- [ ] **Step 2: Create the Pending Onboarding query report**

`hrms/hr/report/pending_onboarding/__init__.py`: empty.
`hrms/hr/report/pending_onboarding/pending_onboarding.json`:
```json
{
 "doctype": "Report", "report_name": "Pending Onboarding", "ref_doctype": "Employee",
 "report_type": "Script Report", "module": "HR", "is_standard": "Yes",
 "roles": [{"role": "HR Manager"}, {"role": "HR User"}]
}
```
`hrms/hr/report/pending_onboarding/pending_onboarding.py`:
```python
import frappe


def execute(filters=None):
	columns = [
		{"label": "Employee", "fieldname": "name", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": "Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
		{"label": "Status", "fieldname": "custom_onboarding_status", "fieldtype": "Data", "width": 110},
		{"label": "Submitted On", "fieldname": "custom_onboarding_submitted_on", "fieldtype": "Datetime", "width": 160},
	]
	rows = frappe.get_all("Employee",
		filters={"custom_onboarding_status": ["in", ["Invited", "Submitted"]]},
		fields=["name", "employee_name", "department", "custom_onboarding_status",
		        "custom_onboarding_submitted_on"],
		order_by="custom_onboarding_submitted_on desc")
	return columns, rows
```

- [ ] **Step 3: Build assets + manual verification**

Run: `bench build --app hrms` then `bench --site test_onboarding.localhost clear-cache`.
Manually: open an Employee (blank status) as HR → see "Onboard (create login)" → click → status Invited + login created; open the Pending Onboarding report → the employee appears. Set status to Submitted (via a quick `bench execute`) → Approve/Request-changes buttons appear and work.

- [ ] **Step 4: Commit**

```bash
git add hrms/public/js/erpnext/employee.js hrms/hr/report/pending_onboarding
git commit -m "feat(onboarding): HR desk buttons + Pending Onboarding report"
```

---

### Task 7: Employee `/hrms` onboarding view

**Files:**
- Create: `frontend/src/components/OnboardingSteps.vue`
- Modify: `frontend/src/views/Profile.vue`

**Interfaces:**
- Consumes: `hrms.onboarding.submit_onboarding`, `hrms.api.get_doctype_fields`, existing `ProfileChildTableModal.vue`.
- Produces: the hire-facing onboarding UI. Nothing consumed later.

- [ ] **Step 1: Build the OnboardingSteps component**

Create `frontend/src/components/OnboardingSteps.vue`: a stepped form over the current employee's own record — Personal (CNIC, CNIC expiry, father/husband name, religion, nationality, blood group, DOB), Address (current, permanent, "same as current" toggle), Emergency contact (person, phone, relation), Education (rows via `ProfileChildTableModal` bound to `education` with the `custom_certificate` attach), Work experience (`external_work_history` + `custom_experience_letter`), Documents (`custom_onboarding_documents` rows). Persist edits through the same resource the Profile already uses. A "Submit for review" button calls:
```javascript
createResource({
  url: "hrms.onboarding.submit_onboarding",
  makeParams: () => ({ employee: employee.data.name }),
  onSuccess: () => { /* refetch employee; hide banner */ },
  onError: (e) => { /* show e.messages (missing fields) inline */ },
}).submit();
```
Follow the patterns already in `Profile.vue` for reading/writing the employee resource and for attach fields.

- [ ] **Step 2: Wire the banner into Profile.vue**

In `frontend/src/views/Profile.vue`, when `employee.custom_onboarding_status` is `Invited` or `Submitted`, render `<OnboardingSteps>` (or a "Complete your profile" banner that opens it) at the top, and show `custom_onboarding_notes` if present. When `Approved` or blank, render the normal Profile unchanged.

- [ ] **Step 3: Build + manual verification**

Run: `bench build --app hrms` then `bench --site test_onboarding.localhost clear-cache`.
Manually (Browser pane): log in as a test hire (status Invited) at `/hrms/login` → the onboarding steps show → complete fields + upload a certificate → "Submit for review" blocked while a mandatory field is empty (missing list shown), then succeeds → status Submitted. Confirm a colleague's data is not visible.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/OnboardingSteps.vue frontend/src/views/Profile.vue
git commit -m "feat(onboarding): /hrms stepped onboarding view + submit"
```

---

### Task 8: End-to-end verification + deploy

**Files:** none (verification only).

- [ ] **Step 1: Full run-tests**

Run: `bench --site test_onboarding.localhost run-tests --module hrms.tests.test_onboarding`
Expected: all PASS.

- [ ] **Step 2: End-to-end manual flow**

As HR: open a new test Employee → "Onbard (create login)" → confirm invite email (check `bench --site test_onboarding.localhost console`-free: look in the Email Queue via a report or `bench execute frappe.client.get_list --kwargs "{'doctype':'Email Queue','limit_page_length':3}"`). As the hire: complete + submit. As HR: see it in Pending Onboarding → Approve. Confirm status Approved and the banner disappears for the hire.

- [ ] **Step 3: Confirm existing employees unaffected**

Run: `bench --site test_onboarding.localhost execute frappe.client.get_list --kwargs "{'doctype':'Employee','filters':{'custom_onboarding_status':['in',['Invited','Submitted','Approved']]},'limit_page_length':0}"` — should list only test/onboarded hires, not the ~130 existing staff.

- [ ] **Step 4: Open PR to develop**

```bash
git push -u origin feature/employee-onboarding
gh pr create --repo Clustox/hrms --base develop --title "Employee onboarding: HR invite + self-complete + review" --body "Implements docs/superpowers/specs/2026-09-28-employee-onboarding-design.md"
```
Merge triggers the Jenkins redeploy (migrate applies fixtures + child doctype, build compiles the PWA). After deploy, re-run Step 2 on the live site.

---

## Self-Review

**Spec coverage:** HR invite+login (Task 3, 6) ✓; self-complete fields (Task 7) ✓; per-row + general attachments (Task 1, 7) ✓; status/review (Task 4, 6, 7) ✓; mandatory server-side (Task 2, 4) ✓; permissions (Task 5) ✓; notifications (Task 4) ✓; existing staff untouched (Task 8 Step 3) ✓; fixtures/deploy (Task 1, 8) ✓.

**Placeholders:** none — all steps carry real code/commands. The frontend tasks (7) use manual verification rather than unit tests because Vue components here have no test harness in `frontend/`; steps give exact resource calls and wiring points.

**Type consistency:** `custom_onboarding_status` values (`Invited`/`Submitted`/`Approved`), method names (`onboard_employee`, `submit_onboarding`, `approve_onboarding`, `request_onboarding_changes`, `validate_onboarding_submission`), and `MANDATORY` field list are consistent across tasks and match the spec.
