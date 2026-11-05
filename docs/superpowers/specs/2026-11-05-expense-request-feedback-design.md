# Expense Request — Faryal Feedback Remediation (Design)

**Date:** 2026-11-05
**Context:** Testing feedback from Faryal (HR) on the custom Expense Request
feature (Manager → HR → Accounts workflow, raised via the `/hrms` Vue PWA).
Four items; two are bugs, two are enhancements.

## Intent

Fix the issues Faryal found so the Expense Request form is correct and clear
for both requesters and approvers, without changing the approval workflow.

## The four items

### 1. Requester identity is overwritten on approver edits (BUG — data-corrupting)

`frontend/src/views/expenses/ExpenseRequestForm.vue` `validateForm()` assigns
`expenseRequest.value.employee = employee.data.name` on **every** save. The PWA
`FormView.saveForm()` emits `validateForm` for updates as well as inserts, so
when an approver enters a rejection reason (which dirties the form) and saves,
the request's `employee`/`employee_name` are rewritten to the **approver**.
Result: HR-EXR-26-11-00002 shows "Faryal Butt" (the rejecter) as the employee.

- **Fix:** set `employee` only on create (`if (!props.id)`). On edit, the stored
  requester is preserved. `employee_name` is fetched from `employee` server-side,
  so preserving `employee` preserves the name.
- **Anti-goal:** do not special-case by role; the create-vs-edit distinction is
  the correct and complete gate.

### 2. "Beneficiary" dropdown (ENHANCEMENT)

New field so a medical claim can name who it was for.

- Field `beneficiary`, Select, options `Self / Spouse / Children`, **default Self,
  optional** (not `reqd`).
- **Shown only for OPD and IPD** expense types (medical). Hidden — and therefore
  always effectively "Self" — for AI Tool, Certifications, Food, Long Service
  Reward. The PWA create form gates visibility on the current `expense_type`.
- Non-goal: no routing, policy, or approval behaviour depends on beneficiary; it
  is informational.

### 3. Attachment field needs a visual required marker (ENHANCEMENT — cosmetic)

The attachment is already enforced (`ExpenseRequest.validate_attachments` throws
once the request leaves Draft; the PWA shows an amber "attachment required"
banner). Missing only the `*` marker on the uploader so it reads as mandatory
like the other required fields.

- **Fix:** `FileUploaderView` gains a `required` prop; when true it renders a red
  `*` after the "Attachments" header. `FormView` passes `:required="attachmentRequired"`.

### 4. Notification grammar "A AI Tool" (BUG — cosmetic)

`hrms/expense_request_notify.py` hardcodes `A <b>{etype}</b>` in three emails.
"A AI Tool" / "A OPD" are wrong.

- **Fix:** an `_article(word)` helper returning "A"/"An" by the sound of the first
  token — vowel-letter for words, first-letter-name for all-caps acronyms. The six
  current types resolve to: **An** AI Tool, **A** Certifications, **A** Food,
  **An** OPD, **An** IPD, **A** Long Service Reward.

### 5. Recover already-corrupted records (DATA)

Any submitted/rejected request an approver edited via the form before fix #1 has
its `employee` reassigned. Frappe's Version log records the field change, so the
original is recoverable.

- One-time prod console script: for each Expense Request whose current `employee`
  equals a user who is an *approver* (manager/HR/Accounts) and whose Version log
  shows an `employee` change, restore the earliest recorded `employee` (+ refetch
  `employee_name`). **Report candidates and the before/after first; do not mutate
  until the counts look right.** Idempotent.

## Constraints

- Backend deploys zero-downtime via `docker cp` into the running container
  (Werkzeug reloader hot-loads `.py`); frontend via the PWA build + copy.
- Doctype JSON change (`beneficiary`) needs a migrate/reload on the target; run
  via console `frappe.reload_doc` + `clear-cache`, not `bench migrate` (avoids
  maintenance mode) — or add a tiny custom-field-style patch.
- Build and verify on the dev clone (`dev-frappe-1`) first; prod only on approval.

## Left to the builder

- Exact placement of the `beneficiary` field in the doctype layout (near
  `expense_type` in the first column is fine).
- Whether to also surface `beneficiary` in the request summary action sheet
  (nice-to-have; include if trivial).
