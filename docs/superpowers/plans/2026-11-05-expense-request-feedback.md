# Expense Request Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the four items from Faryal's Expense Request testing feedback (two
bugs, two enhancements) plus recover records corrupted by bug #1.

**Architecture:** Backend changes in the `hrms` app (doctype JSON + the
`expense_request_notify.py` email module); frontend changes in the `/hrms` Vue
PWA (`ExpenseRequestForm.vue`, `FormView.vue`, `FileUploaderView.vue`); a
one-time prod console recovery script. No workflow changes.

**Tech Stack:** Frappe/ERPNext (Python), Vue 3 + Ionic + frappe-ui (PWA), SQLite
dev clone / MariaDB prod on Docker.

**Spec:** `docs/superpowers/specs/2026-11-05-expense-request-feedback-design.md`

## Global Constraints

- Verify on the dev clone (`dev-frappe-1`) first; prod only on explicit approval.
- Deploy backend by `docker cp` of changed `.py` into the running container
  (Werkzeug reloader hot-loads). Doctype JSON change needs
  `frappe.reload_doc("hr","doctype","expense_request")` + `bench clear-cache` via
  console — never `bench migrate` (maintenance mode).
- Dev clone cannot run `bench run-tests` (Fiscal Year overlap in global
  bootstrap) → prove Python via `bench console` harness (RED→GREEN, rolled back)
  and ship pytest files as deliverables. Frontend verified by browser test.
- Beneficiary is informational only — no routing/policy/approval depends on it.
- Commit attribution: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Review Focus

- Approver rejects **without** dirtying the form (pure workflow action, no Save) —
  employee must still be preserved (fix #1 must not rely on Save firing). Covered
  by Task 3 reasoning: the only writer of `employee` is create.
- Beneficiary left at default when switching expense_type OPD→AI Tool→OPD — a
  stale non-Self value must not persist silently on a non-medical request. Task 2
  controller normalizes beneficiary to blank for non-medical types.
- `_article` on an empty/null `expense_type` must not crash the email. Task 1 test.
- `_article` on a mixed acronym (e.g. "IPD") picks article by spoken first letter,
  not written vowel. Task 1 test.
- Recovery script must be idempotent and must not "restore" a record whose current
  employee is legitimately the original. Task 4 report-first + guard.

---

### Task 1: Email article fix (`_article` helper)

**Files:**
- Modify: `hrms/expense_request_notify.py`
- Test: `hrms/hr/doctype/expense_request/test_expense_request_notify.py`

**Interfaces:**
- Produces: `_article(word: str, capitalized: bool = True) -> str` ("A"/"An").

- [ ] **Step 1: Write failing tests** — `_article` returns, for the six types:
  `An AI Tool`, `A Certifications`, `A Food`, `An OPD`, `An IPD`,
  `A Long Service Reward`; and `_article("")` → `"A"` (no crash). Assert the
  Pending-HR email body for an `AI Tool` request contains `"An <b>AI Tool</b>"`.
- [ ] **Step 2: Run tests — expect FAIL** (`_article` undefined / body says "A AI Tool").
- [ ] **Step 3: Implement** `_article` (vowel-letter for words; first-letter spoken
  sound for all-caps acronyms via a `AEFHILMNORSX` set) and replace the three
  hardcoded `A <b>{etype}</b>` occurrences with `{_article(etype)} <b>{etype}</b>`.
- [ ] **Step 4: Run tests — expect PASS.**
- [ ] **Step 5: Verify on dev** via `bench console` harness (build a request, drive to
  Pending HR, assert the queued email subject/body) and roll back.
- [ ] **Step 6: Commit.**

### Task 2: `beneficiary` field on the doctype

**Files:**
- Modify: `hrms/hr/doctype/expense_request/expense_request.json`
- Modify: `hrms/hr/doctype/expense_request/expense_request.py`
- Test: `hrms/hr/doctype/expense_request/test_expense_request.py`

**Interfaces:**
- Produces: field `beneficiary` (Select, options `Self\nSpouse\nChildren`,
  default `Self`, `reqd=0`) in the first column near `expense_type`.
- Produces: `ExpenseRequest.validate` normalizes `beneficiary` to `""` when
  `expense_type not in {"OPD","IPD"}` (medical-only; keeps non-medical rows clean).

- [ ] **Step 1: Write failing test** — a non-medical request (e.g. `AI Tool`) with
  `beneficiary="Spouse"` is normalized to blank on validate; an `OPD` request keeps
  `beneficiary="Spouse"`.
- [ ] **Step 2: Run — expect FAIL** (no normalization; field may be absent).
- [ ] **Step 3: Add the field to JSON** (after `expense_type`, before
  `requires_manager`) and add `normalize_beneficiary()` to `validate`.
- [ ] **Step 4: Reload doctype on dev** (`frappe.reload_doc` + `clear-cache`) and
  **Run — expect PASS** via console harness.
- [ ] **Step 5: Commit.**

### Task 3: PWA form — employee preservation, beneficiary (OPD/IPD), attachment `*`

**Files:**
- Modify: `frontend/src/views/expenses/ExpenseRequestForm.vue`
- Modify: `frontend/src/components/FormView.vue`
- Modify: `frontend/src/components/FileUploaderView.vue`

**Interfaces:**
- Consumes: `beneficiary` from `hrms.api.get_doctype_fields` (Task 2).
- `FileUploaderView` gains prop `required: Boolean`; renders red `*` after the
  "Attachments" header when true. `FormView` passes `:required="attachmentRequired"`.

- [ ] **Step 1 (bug #1):** change `validateForm()` to
  `if (!props.id) expenseRequest.value.employee = employee.data.name`.
- [ ] **Step 2 (beneficiary):** include `beneficiary` in the create-form candidate
  fields, shown only when `expenseRequest.value.expense_type` is `OPD`/`IPD`
  (extend the `visibleFields` computed with an expense-type gate; keep default Self).
- [ ] **Step 3 (attachment `*`):** add the `required` prop to `FileUploaderView`,
  render the asterisk, and pass it from `FormView`'s attachment block.
- [ ] **Step 4: Build the PWA**, deploy to dev, **browser-test** on
  `frappe-dev.theclustox.com`:
  (a) create an OPD request → Beneficiary dropdown visible, defaults Self; switch to
  AI Tool → dropdown hidden; (b) attachment header shows `*`; (c) as an approver,
  open someone else's request, add a rejection reason, reject → employee unchanged.
- [ ] **Step 5: Commit.**

### Task 4: Recover corrupted `employee` on existing records (prod)

**Files:**
- Create: `scripts/recover_expense_request_employee.py` (console script, report-first).

- [ ] **Step 1:** Write a script that lists every Expense Request whose Version log
  contains an `employee` change, printing `name`, current employee, earliest-logged
  employee, and whether current == an approver (manager/HR/Accounts user). No writes.
- [ ] **Step 2:** Run it read-only on the dev clone, then (on approval) prod; eyeball
  the candidates.
- [ ] **Step 3:** Add an `apply=True` branch that, for each candidate where current
  != original, sets `employee` back to the earliest-logged value and re-fetches
  `employee_name` (`db_set`, `update_modified=False`), committing per row with
  try/except. Idempotent (a row already matching its origin is skipped).
- [ ] **Step 4:** Run with `apply=True` on prod (after approval); report counts.
- [ ] **Step 5: Commit the script.**

---

## Self-Review

- **Spec coverage:** items 1–4 → Tasks 1–3; recovery → Task 4. ✓
- **Types:** `_article` signature consistent (Task 1). `beneficiary` options/default
  consistent between JSON (Task 2) and the form gate (Task 3). ✓
- **Review Focus:** reject-without-save, beneficiary stale value, empty expense_type,
  acronym article, recovery idempotency — each tied to a task above. ✓
- **Proportion:** four small edits + a report-first script; no code block larger than
  the change it describes. ✓
