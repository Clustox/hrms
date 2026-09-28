# New-Employee Onboarding — Design

**Date:** 2026-09-28
**Repo:** Clustox/hrms (Frappe HR fork)
**Source:** HR feedback (Frappe Feedback sheet, 17/9): *"Create login access for new employee (easy onboarding pre-requisite)"* + required fields: CNIC, CNIC expiry, current address, permanent address, blood group, education fields + attachments, work experience + attachment.

## Goal

Give HR a fast, self-serve way to onboard a new hire: HR creates the employee + login in one step, the new hire completes their own personal details and uploads documents in `/hrms`, and HR reviews and approves. All the personal fields already exist on the Employee doctype; this feature adds the **flow**, the **attachments**, and the **login/review packaging** around them.

## Non-goals (YAGNI)

- Training/task checklists (ERPNext's built-in Employee Onboarding doctype) — not used.
- Offer letters, asset allocation, salary/CTC capture, multi-step approval workflows.
- Bulk onboarding / CSV import (a separate, existing flow — see `.employee_import/`).
- Changing existing staff: the status field defaults blank, so current employees are untouched.

## Flow (hybrid, 3 stages)

```
HR "Onboard New Employee"        New hire in /hrms                 HR
──────────────────────────       ────────────────────────         ─────────────────
create Employee (minimal)        logs in via invite link          sees "Pending Onboarding"
+ System User + ESS role   ─────▶ completes stepped profile  ─────▶ opens, reviews
+ send /hrms/login invite        + uploads documents              Approve  ──▶ Approved
status = Invited                 taps "Submit for review"         Request changes ──▶ Invited
                                 status = Submitted               (with a note to the hire)
```

### State machine — `custom_onboarding_status`
- `Invited` — record + login created; hire is completing it (also the state after "Request changes").
- `Submitted` — hire tapped "Submit for review"; awaiting HR.
- `Approved` — HR accepted; onboarding complete.
- Blank/null — all pre-existing employees; never enters the flow.

Transitions: HR create → `Invited`; hire submit → `Submitted` (requires mandatory fields); HR approve → `Approved`; HR request-changes → `Invited` (+ note + notification).

## Data model (all as **fixtures** in the repo, so reproducible + committed)

| Doctype | Field | Type | Notes |
|---|---|---|---|
| Employee | `custom_onboarding_status` | Select: `\nInvited\nSubmitted\nApproved` | blank default; read-only for ESS (system-driven) |
| Employee | `custom_onboarding_submitted_on` | Datetime | set on submit; read-only |
| Employee | `custom_onboarding_notes` | Small Text | HR "request changes" note shown to the hire |
| Employee Education | `custom_certificate` | Attach | per-row degree/certificate |
| Employee External Work History | `custom_experience_letter` | Attach | per-row experience letter |
| Employee | `custom_onboarding_documents` | Table → **Employee Onboarding Document** | general docs |
| Employee Onboarding Document (new child doctype) | `document_type` (Data), `attachment` (Attach) | | e.g. "CNIC", "Other" |

Existing fields reused as-is (no change): `custom_cnic_no`, `custom_cnic_expiry_date`, `custom_father_or_husband_name`, `custom_religion`, `custom_nationality`, `current_address`, `permanent_address`, `blood_group`, `person_to_be_contacted`, `emergency_phone_number`, `relation`, `education`, `external_work_history`, `date_of_birth`.

## Mandatory before "Submit for review"

Enforced server-side (so it holds for API/mobile too, mirroring how #24 does medical-cert):
- CNIC (`custom_cnic_no`) + CNIC expiry (`custom_cnic_expiry_date`)
- Current address + permanent address
- Blood group
- Emergency contact: person + phone + relation

**Optional:** education rows, work-history rows, general documents (many hires — esp. freshers — have no work history; degrees may be uploaded later). Enforcement lives in a single `validate_onboarding_submission(employee)` function called by the submit action; it returns the list of missing fields so the UI can show them inline.

## HR side (desk)

1. **"Onboard New Employee"** — a desk **Quick Entry / new-Employee form** capturing: first/last name, company email, department, designation, date of joining, gender, employment type. Provisioning is triggered by an **explicit "Onboard" action** (a button on the form / a whitelisted method `onboard_employee(employee)`), **never `after_insert`** — auto-provisioning on every Employee insert would create logins for bulk imports (`.employee_import/`) too. The action provisions:
   - a System User (Employee Self Service role), `send_welcome_email=0`,
   - links `Employee.user_id`,
   - self-scope User Permission (own Employee record),
   - `custom_onboarding_status = Invited`,
   - sends the custom welcome email with a set-password link + `/hrms/login` bookmark.
   Reuses the proven logic in `hrms/provision_pilot.py` + `hrms/send_pilot_invites.py`, refactored into a reusable `hrms/onboarding.py::onboard_employee(...)`.
2. **"Pending Onboarding"** — a Query Report / list filtered on `custom_onboarding_status in (Invited, Submitted)`, showing name, dept, status, submitted-on.
3. **Approve / Request changes** — buttons on the Employee form when status = `Submitted` (via `employee.js` client script calling whitelisted methods `approve_onboarding` / `request_onboarding_changes(note)`).

## Employee side (`/hrms` PWA)

Extend the existing self-service Profile (PR #15):
- When `custom_onboarding_status in (Invited, Submitted)`, the Profile shows a guided, stepped **"Complete your profile"** banner/flow: Personal → Address (with "permanent same as current" toggle) → Emergency contact → Education (rows via existing `ProfileChildTableModal`, each with the new certificate attach) → Work experience (rows + experience-letter attach) → Documents (`custom_onboarding_documents` rows).
- A **"Submit for review"** button calls `submit_onboarding()`; if `validate_onboarding_submission` returns missing fields, they're highlighted and submission is blocked.
- After Approved, the banner disappears and Profile behaves as today.
- If HR requested changes, show `custom_onboarding_notes` at the top.

New frontend work is additive to `frontend/src/views/Profile.vue` + a small `OnboardingSteps.vue`; reuse `ProfileChildTableModal.vue` and `hrms.api.get_doctype_fields`.

## Permissions

- ESS already **reads** its own confidential fields (PR #15, permlevel 1/2 read scoped to own record).
- ESS must **write** the onboarding fields on its **own** record. Audit each field's permlevel: the custom fields (CNIC etc.) are permlevel 0 → already writable by the record owner. If any mandatory field is permlevel 1, grant ESS `write` at permlevel 1 (still scoped to the own record via the existing self-scope User Permission). `custom_onboarding_status`/`submitted_on`/`notes` are **not** ESS-writable (system/HR-driven) — status changes only through the whitelisted methods.
- Colleagues remain invisible (directory scoping from PR #15 unchanged).

## Notifications

- On `Submitted` → notify HR (Notification + email) with a link to the employee.
- On `Approved` / `Request changes` → notify the hire (email); request-changes includes the note.
Implemented via Frappe Notification docs (fixtures) or `frappe.sendmail` in the whitelisted methods — prefer the methods for exact timing/content.

## Error handling / edge cases

- Duplicate company email → block at HR create with a clear message.
- Submit with missing mandatory → blocked, missing list returned (no partial state change).
- Re-submit after "request changes" → allowed (Invited → Submitted again).
- Approve is idempotent; approving an already-Approved record is a no-op.
- Existing employees (blank status) never see the onboarding banner and are excluded from Pending Onboarding.
- Login already exists for the email → skip user creation, still link + set status.

## Testing

- Unit: `validate_onboarding_submission` (each mandatory field missing/present; optional rows ignored).
- Flow: create test hire → Invited + login + invite sent; self-complete + attach files → Submit blocked until mandatory complete → Submitted; HR Approve → Approved; Request changes → back to Invited with note.
- Permissions: the hire can edit only their own record and cannot change `custom_onboarding_status`; cannot see colleagues.
- Attachments: certificate/experience-letter/CNIC files persist and are retrievable.

## Rollout

- Ship custom fields + the new child doctype as **fixtures** (committed), plus `hrms/onboarding.py`, `employee.js` additions, and the frontend changes.
- Deploy via the realigned pipeline (merge to `develop` → Jenkins redeploy → `bench migrate` applies fixtures → `bench build`).
- No data migration for existing employees (blank status).

## Reused existing assets

- `hrms/provision_pilot.py`, `hrms/provision_managers.py`, `hrms/send_pilot_invites.py` — provisioning + invite email (refactor into `onboarding.py`).
- PR #15 self-service Profile + `ProfileChildTableModal.vue` + `hrms.api.get_doctype_fields`.
- `#8` custom fields (CNIC etc.) already present.
