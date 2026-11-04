# Expense Request Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A self-service Expense Request in the `/hrms` PWA that routes through a type-dependent Manager→HR→Accounts approval chain and ends in a recorded reimbursement.

**Architecture:** A new submittable doctype `Expense Request` (in the `hrms` app) driven by a Frappe **Workflow** for the multi-stage state machine, reusing the PWA's existing workflow plumbing (`FormView.vue` → `WorkflowActionSheet.vue` → `useWorkflow` → `frappe.model.workflow.apply_workflow`). Stage gating: the Manager stage is gated by a workflow **condition** against a resolved `manager` user field (reports_to); the HR and Accounts stages are gated by two dedicated roles. Visibility uses the existing `permission_query_conditions` / `has_permission` pattern with an Expense-Request-specific bypass for HR + Accounts. Reimbursement is a set of fields on the doc (no accounting posting). Stage emails are sent from a dedicated notify module via `doc_events`.

**Tech Stack:** Frappe/ERPNext (`hrms` app), Python controllers + doctype JSON, Frappe Workflow engine, Vue 3 + frappe-ui PWA (`frontend/`), `HRMSTestSuite` (FrappeTestCase).

**Spec:** `docs/superpowers/specs/2026-11-04-expense-request-design.md`

## Global Constraints

- App is `hrms`; follow existing doctype conventions (JSON schema + `.py` controller + `test_*.py`), mirroring `hrms/hr/doctype/shift_request/`.
- Six fixed expense types, exact strings: `AI Tool`, `Certifications`, `Food`, `OPD`, `IPD`, `Long Service Reward`. Manager-first types: `AI Tool`, `Certifications`, `Food`. No-manager types: `OPD`, `IPD`, `Long Service Reward`.
- Currency is PKR; amount is a `Currency` field tied to a sibling `currency` Link field (`fetch_from` `employee.salary_currency`, `fetch_if_empty`, fallback company default), per `expense_claim.json`.
- No accounting/payroll posting; the reimbursement is fields on the doc only (designed so it *could* be wired later).
- No self-approval at any stage; no in-place resubmit after rejection (Rejected is terminal); no manager → auto-route to HR; Accounts may set a `paid_amount` that differs from `amount` (defaulting to `amount`).
- Approvals use the existing PWA workflow components; do **not** build a parallel approval UI or extend `RequestActionSheet`.
- Visibility: employees see own + direct reports (existing `request_visibility` scoping); HR and Accounts roles get full read of Expense Request.
- All notification sends wrapped in `try/except` + `frappe.log_error` so a mail failure never blocks the transaction (per `attendance_request_notify.py`).
- Deploy target: prod `frappe.theclustox.com`, container `docker-frappe-1`, site `hrms.localhost`. Backend = `docker cp` + `bench migrate` (installs doctype + runs the workflow patch) + `bench restart`; frontend = `cd frontend && yarn build` → tar `hrms/public/frontend` + `hrms/www/hrms.html` → `docker cp` → `bench clear-cache`. Do **not** `git pull` on prod.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Review Focus

- **Empty `reports_to` on a manager-first type** → must route Draft straight to Pending HR, never stall at a non-existent manager. (Task 4, workflow condition + Task 2 field resolution; tested in Task 4.)
- **Requester is also an HR/Accounts approver** → cannot advance their own request; another team member must. (Task 4 `allow_self_approval=0`; tested in Task 4.)
- **Accounts user reading the queue** → must see all Pending-Accounts requests org-wide (visibility bypass) yet be blocked from acting on their own. (Task 3 visibility + Task 4 self-approval; tested in Task 3 and Task 4.)
- **Missing mandatory attachment** (any type without a receipt; OPD/IPD without a prescription) → submission blocked. (Task 2; tested in Task 2.)
- **Terminal transition without its required fields** (Reject without a reason; Complete without paid fields) → blocked; `paid_amount` defaults to `amount` when left blank. (Task 2; tested in Task 2.)

---

### Task 1: `Expense Request` doctype schema

**Files:**
- Create: `hrms/hr/doctype/expense_request/expense_request.json`
- Create: `hrms/hr/doctype/expense_request/__init__.py`
- Create: `hrms/hr/doctype/expense_request/expense_request.py` (minimal `class ExpenseRequest(Document): pass` for now)
- Test: `hrms/hr/doctype/expense_request/test_expense_request.py`

**Interfaces:**
- Produces: doctype `Expense Request`, `is_submittable: 1`, `naming_rule: "Expression"`, `autoname: "HR-EXR-.YY.-.MM.-.#####"`, `title_field: "employee_name"`, `track_changes: 1`. Fields (fieldname — fieldtype — notes):
  - `employee` — Link/Employee — reqd, `in_list_view`, `ignore_user_permissions: 1`
  - `employee_name` — Data — `fetch_from: employee.employee_name`, read_only
  - `company` — Link/Company — `fetch_from: employee.company`, read_only
  - `expense_type` — Select — options the six exact strings; reqd; `in_list_view`
  - `requires_manager` — Check — read_only, hidden (set by controller)
  - `manager` — Link/User — read_only, hidden (set by controller)
  - `amount` — Currency — `options: "currency"`, reqd, `in_list_view`
  - `currency` — Link/Currency — `fetch_from: employee.salary_currency`, `fetch_if_empty`, reqd
  - `reason` — Small Text — reqd
  - `receipt` — Attach — reqd (enforced in controller)
  - `prescription` — Attach — `depends_on`/`mandatory_depends_on: eval:["OPD","IPD"].includes(doc.expense_type)`
  - `workflow_state` — Link/"Workflow State" — read_only, hidden; the workflow state field
  - `rejection_reason` — Select — options: `\nAmount exceeds policy limit\nInsufficient documentation\nNot eligible\nOther`; `depends_on: eval:doc.workflow_state=="Rejected"`
  - `rejection_note` — Small Text — `depends_on: eval:doc.workflow_state=="Rejected"`
  - Reimbursement section: `paid_amount` — Currency `options: "currency"`; `payment_date` — Date; `payment_mode` — Select options `\nBank Transfer\nPetty Cash`; `reference_no` — Data; `paid_by` — Link/User read_only. All `depends_on: eval:["Pending Accounts","Completed"].includes(doc.workflow_state)`
  - `amended_from` — Link/"Expense Request" — read_only, no_copy
  - `permissions`: `Employee` (read/write/create/report/share/email/print/export — **no submit/cancel**); `HR Manager` and `HR User` (full incl. submit/cancel/amend); `System Manager` (full). Accounts roles are added in Task 3's role setup, not here.

- [ ] **Step 1: Write the failing test** `test_expense_request.py`

```python
import frappe
from hrms.tests.utils import HRMSTestSuite

class TestExpenseRequest(HRMSTestSuite):
    def setUp(self):
        frappe.db.delete("Expense Request")

    def test_doctype_installed_with_fields(self):
        meta = frappe.get_meta("Expense Request")
        for f in ["employee","expense_type","amount","currency","reason",
                  "receipt","prescription","workflow_state","requires_manager",
                  "manager","rejection_reason","paid_amount","payment_mode","paid_by"]:
            self.assertTrue(meta.has_field(f), f)
        self.assertTrue(meta.is_submittable)
        self.assertEqual(set(meta.get_field("expense_type").options.split("\n")),
            {"AI Tool","Certifications","Food","OPD","IPD","Long Service Reward"})
```

- [ ] **Step 2: Run to verify it fails** — `bench --site <site> run-tests --module hrms.hr.doctype.expense_request.test_expense_request`. Expected: FAIL (`Expense Request` doctype does not exist).
- [ ] **Step 3: Author `expense_request.json`** with the fields above (model it on `shift_request.json` + `attendance_request.json` for naming, and `expense_claim.json` for the Currency idiom), `__init__.py`, and the stub controller. Run `bench --site <site> migrate` to install.
- [ ] **Step 4: Run to verify it passes** — same run-tests command. Expected: PASS.
- [ ] **Step 5: Commit** — `git add hrms/hr/doctype/expense_request && git commit -m "feat(expense-request): add Expense Request doctype schema"`

---

### Task 2: Controller validation & field resolution

**Files:**
- Modify: `hrms/hr/doctype/expense_request/expense_request.py`
- Test: `hrms/hr/doctype/expense_request/test_expense_request.py`

**Interfaces:**
- Consumes: doctype from Task 1.
- Produces: `class ExpenseRequest(Document)` with module constants `MANAGER_FIRST_TYPES = {"AI Tool","Certifications","Food"}` and `REJECT_REASON_REQUIRED` logic, and a `validate()` that enforces the rules below. Also module helper `resolve_manager(employee) -> str | None` (returns the reports_to employee's `user_id`, or `None`).
- `validate()` responsibilities (order matters):
  1. `validate_active_employee(self.employee)` (import from `hrms.hr.utils`).
  2. Set `self.requires_manager = 1 if self.expense_type in MANAGER_FIRST_TYPES else 0`.
  3. Set `self.manager = resolve_manager(self.employee)` (so `requires_manager and manager` is false when there is no reports_to → Task 4 routes to HR).
  4. `amount` must be `> 0` else `frappe.throw`.
  5. `receipt` required else `frappe.throw`; if `expense_type in ("OPD","IPD")` then `prescription` required else `frappe.throw`.
  6. If `workflow_state == "Rejected"` and not `rejection_reason`: `frappe.throw`.
  7. If `workflow_state == "Completed"`: if not `paid_amount`, set `paid_amount = amount`; require `payment_date` and `payment_mode` else `frappe.throw`; set `paid_by = frappe.session.user`.

- [ ] **Step 1: Write failing tests** (add to `test_expense_request.py`; add a module factory `make_expense_request(**kw)` that fills required fields and inserts with `ignore_permissions`):

```python
def test_requires_manager_flag_and_manager_resolution(self):
    # employee with a reports_to -> requires_manager True, manager set
    # no-manager type -> requires_manager False
def test_amount_must_be_positive(self):
    self.assertRaises(frappe.ValidationError, make_expense_request, amount=0)
def test_receipt_required(self):
    self.assertRaises(frappe.ValidationError, make_expense_request, receipt=None)
def test_prescription_required_for_opd_ipd(self):
    self.assertRaises(frappe.ValidationError, make_expense_request, expense_type="OPD", prescription=None)
def test_reject_requires_reason(self):
    doc = make_expense_request()
    doc.workflow_state = "Rejected"
    self.assertRaises(frappe.ValidationError, doc.save)
def test_complete_defaults_paid_amount_to_amount(self):
    doc = make_expense_request(amount=5000)
    doc.workflow_state = "Completed"; doc.payment_date = frappe.utils.nowdate(); doc.payment_mode = "Bank Transfer"
    doc.save()
    self.assertEqual(doc.paid_amount, 5000)
    self.assertEqual(doc.paid_by, frappe.session.user)
```

- [ ] **Step 2: Run to verify they fail** — run-tests module. Expected: FAIL.
- [ ] **Step 3: Implement** `validate()`, `resolve_manager()`, and the constants in `expense_request.py`.
- [ ] **Step 4: Run to verify they pass.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(expense-request): controller validation and manager resolution`.

---

### Task 3: Visibility (query + has_permission) and approver roles

**Files:**
- Modify: `hrms/request_visibility.py`
- Modify: `hrms/hooks.py` (register `permission_query_conditions` + `has_permission` for `Expense Request`)
- Create: `hrms/hr/doctype/expense_request/expense_request.js` (empty/trivial desk form script; optional)
- Test: `hrms/test_request_visibility.py` (create if absent; else add to existing)

**Interfaces:**
- Consumes: `ALL_ACCESS_ROLES`, `_visible_employees`, `_conditions`, `has_permission` from `request_visibility.py`.
- Produces:
  - Module constant `EXPENSE_ACCESS_ROLES = ALL_ACCESS_ROLES | {"Accounts Manager","Accounts User"}` (HR + Accounts + System Manager/Administrator see all Expense Requests).
  - `expense_request_query(user=None) -> str`: like `_conditions` but treats `EXPENSE_ACCESS_ROLES` as unrestricted (returns `""`).
  - `expense_request_has_permission(doc, ptype=None, user=None, **kwargs) -> bool`: like the existing `has_permission` but unrestricted for `EXPENSE_ACCESS_ROLES`; employees/managers scoped to own + reports.
  - `hooks.py`: add `"Expense Request": "hrms.request_visibility.expense_request_query"` to `permission_query_conditions` and `"Expense Request": "hrms.request_visibility.expense_request_has_permission"` to `has_permission`.

- [ ] **Step 1: Write failing tests** (`test_request_visibility.py`): with `frappe.set_user`, assert an Accounts-role user gets `""` from `expense_request_query` (unrestricted) and a plain Employee gets a `` `tabExpense Request`.`employee` in (...) `` condition scoped to self + reports; assert `expense_request_has_permission` returns True for an Accounts user on any doc and False for a plain employee on a stranger's doc.
- [ ] **Step 2: Run to verify fail.** Expected: FAIL (functions undefined).
- [ ] **Step 3: Implement** the two functions + constant in `request_visibility.py` and the two hook entries.
- [ ] **Step 4: Run to verify pass.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(expense-request): visibility scoping with HR+Accounts bypass`.

---

### Task 4: Approval Workflow (states, transitions, roles) via patch

**Files:**
- Create: `hrms/patches/post_model_sync/create_expense_request_workflow.py`
- Modify: `hrms/patches.txt` (append the patch under `[post_model_sync]`)
- Test: `hrms/hr/doctype/expense_request/test_expense_request_workflow.py`

**Interfaces:**
- Consumes: doctype (Task 1), roles. The patch is idempotent (`frappe.db.exists` guards) and:
  1. Ensures roles `Expense HR Approver` and `Expense Accounts Approver` exist (`desk_access: 1`), and assigns them to every enabled user currently holding `HR Manager`/`HR User` (→ HR approver) and `Accounts Manager`/`Accounts User` (→ Accounts approver) respectively.
  2. Ensures the seven **Workflow State** records exist (create with any missing).
  3. Creates/updates one **Workflow** `Expense Request Approval` on `Expense Request`, `workflow_state_field: "workflow_state"`, `is_active: 1`, `override_status: 0`, `send_email_alert: 0`.
- Produces the state/transition tables below. **States** (state — doc_status — allow_edit):

  | State | doc_status | allow_edit |
  |---|---|---|
  | Draft | 0 | Employee |
  | Pending Manager | 0 | Employee |
  | Pending HR | 0 | Expense HR Approver |
  | Pending Accounts | 0 | Expense Accounts Approver |
  | Rejected | 0 | *(none)* |
  | Cancelled | 0 | *(none)* |
  | Completed | 1 | *(none)* |

  **Transitions** (state — action — next — allowed — allow_self_approval — condition):

  | State | Action | Next | Allowed | Self-appr | Condition |
  |---|---|---|---|---|---|
  | Draft | Submit for Approval | Pending Manager | Employee | 1 | `doc.requires_manager and doc.manager` |
  | Draft | Submit for Approval | Pending HR | Employee | 1 | `not (doc.requires_manager and doc.manager)` |
  | Draft | Cancel | Cancelled | Employee | 1 | `doc.owner == frappe.session.user` |
  | Pending Manager | Approve | Pending HR | Employee | 0 | `doc.manager == frappe.session.user` |
  | Pending Manager | Reject | Rejected | Employee | 0 | `doc.manager == frappe.session.user` |
  | Pending Manager | Cancel | Cancelled | Employee | 1 | `doc.owner == frappe.session.user` |
  | Pending HR | Approve | Pending Accounts | Expense HR Approver | 0 | *(none)* |
  | Pending HR | Reject | Rejected | Expense HR Approver | 0 | *(none)* |
  | Pending HR | Cancel | Cancelled | Employee | 1 | `doc.owner == frappe.session.user` |
  | Pending Accounts | Complete | Completed | Expense Accounts Approver | 0 | *(none)* |
  | Pending Accounts | Reject | Rejected | Expense Accounts Approver | 0 | *(none)* |
  | Pending Accounts | Cancel | Cancelled | Employee | 1 | `doc.owner == frappe.session.user` |

  Note: verify `frappe.session.user` is available inside workflow `condition` safe-eval on this Frappe version (it is used widely); if not, move the manager check into `expense_request.py` as a transition guard on `on_update` comparing the just-entered `workflow_state`.

- [ ] **Step 1: Write failing tests** (`test_expense_request_workflow.py`, `HRMSTestSuite`; use `make_employee`, `frappe.set_user`, and `frappe.model.workflow.apply_workflow`):

```python
def test_manager_first_routes_to_pending_manager(self):
    # AI Tool with a reports_to -> after "Submit for Approval" state == "Pending Manager"
def test_no_manager_routes_to_pending_hr(self):
    # Food with reports_to empty -> after submit state == "Pending HR"
def test_full_chain_to_completed(self):
    # submit -> manager Approve -> HR Approve -> Accounts sets paid fields + Complete
    # final docstatus == 1, workflow_state == "Completed"
def test_hr_cannot_self_approve_own_request(self):
    # requester holds Expense HR Approver; apply "Approve" at Pending HR as self -> raises
def test_non_manager_cannot_approve_pending_manager(self):
    # a different employee (not the reports_to) -> apply "Approve" raises
def test_requester_can_cancel_before_complete(self):
    # owner applies "Cancel" at Pending HR -> workflow_state == "Cancelled"
```

- [ ] **Step 2: Run to verify fail.** Expected: FAIL (no workflow).
- [ ] **Step 3: Implement** the patch; run `bench --site <site> migrate` to execute it (idempotent).
- [ ] **Step 4: Run to verify pass.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(expense-request): approval workflow, roles, and seeding patch`.

---

### Task 5: Stage notification emails

**Files:**
- Create: `hrms/expense_request_notify.py`
- Modify: `hrms/hooks.py` (`doc_events["Expense Request"]`)
- Test: `hrms/hr/doctype/expense_request/test_expense_request_notify.py`

**Interfaces:**
- Consumes: workflow states (Task 4). Pattern copied from `attendance_request_notify.py` (`PORTAL`, `_request_url`, try/except + `frappe.log_error`).
- Produces: `notify_on_state_change(doc, method=None)` wired to `doc_events["Expense Request"]["on_update"]`. It compares the new `workflow_state` against the DB value (`doc.get_doc_before_save()`); on a change it emails:
  - → `Pending Manager`: the manager (`doc.manager`) with a deep link `{PORTAL}/expense-requests/{doc.name}`.
  - → `Pending HR`: `hr@clustox.com`.
  - → `Pending Accounts`: `accounts@clustox.com`.
  - → `Completed` / `Rejected`: the requester (employee `user_id`); the Rejected mail includes `rejection_reason`/`rejection_note`.
  - Module constants `HR_INBOX = "hr@clustox.com"`, `ACCOUNTS_INBOX = "accounts@clustox.com"`, `PORTAL = "https://frappe.theclustox.com/hrms"`.
- Signature: `notify_on_state_change(doc, method=None) -> None`.

- [ ] **Step 1: Write failing test** — monkeypatch `frappe.sendmail` to capture calls; drive a request through each transition (as the right users) and assert recipients per transition (manager email on Pending Manager; `hr@`/`accounts@` on the respective stages; requester on Completed and Rejected).
- [ ] **Step 2: Run to verify fail.** Expected: FAIL.
- [ ] **Step 3: Implement** `expense_request_notify.py` + the `doc_events` entry.
- [ ] **Step 4: Run to verify pass.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(expense-request): stage notification emails`.

---

### Task 6: PWA list API

**Files:**
- Modify: `hrms/api/__init__.py` (add `get_expense_requests`)
- Test: `hrms/hr/doctype/expense_request/test_expense_request_api.py`

**Interfaces:**
- Consumes: `get_filters`, `get_current_employee`, `get_workflow_state_field` (existing). Because `Expense Request` has a workflow, `get_filters`'s `for_approval` branch already uses the workflow-state path (no `approver_field_map` entry needed).
- Produces:
```python
@frappe.whitelist()
def get_expense_requests(employee: str, approver_id: str | None = None,
                         for_approval: bool = False, limit: int | None = None) -> list[dict]:
    # mirror get_shift_requests: fields = ["name","employee","employee_name","expense_type",
    #   "amount","currency","reason","workflow_state","docstatus","creation"] (+ workflow_state_field),
    #   frappe.get_list(..., order_by="creation desc", limit=limit)
```

- [ ] **Step 1: Write failing test** — create requests for two employees in different states; assert the owner's `employee=` call returns their own, and a `for_approval=1` call as an HR approver returns others' Pending-HR requests (and excludes self).
- [ ] **Step 2: Run to verify fail.** Expected: FAIL.
- [ ] **Step 3: Implement** `get_expense_requests`.
- [ ] **Step 4: Run to verify pass.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(expense-request): PWA list API`.

---

### Task 7: PWA data resources, routes, list view

**Files:**
- Create: `frontend/src/data/expense_requests.js`
- Create: `frontend/src/router/expenses.js`
- Modify: `frontend/src/router/index.js` (import + spread `expenseRoutes`)
- Create: `frontend/src/views/expenses/ExpenseRequestList.vue`

**Interfaces:**
- Consumes: `get_expense_requests` (Task 6), `employeeResource`, generic `ListView.vue`.
- Produces:
  - `myExpenseRequests` / `teamExpenseRequests` via `createResource` (mirror `data/attendance.js` `myShiftRequests`/`teamShiftRequests`; cache keys `hrms:my_expense_requests` / `hrms:team_expense_requests`).
  - Routes (names must be the doctype with spaces removed): `ExpenseRequestListView` → `/expense-requests`, `ExpenseRequestFormView` → `/expense-requests/new`, `ExpenseRequestDetailView` → `/expense-requests/:id` (props). The `:id` detail route reuses `ExpenseRequestForm.vue` (Task 8), matching the `ShiftRequest*` pattern; the deep-link in emails (`/expense-requests/{name}`) resolves here.
  - `ExpenseRequestList.vue`: thin wrapper over `ListView.vue` with `doctype="Expense Request"`, `:tabButtons="['My Requests','Team Requests']"`, fields `[expense_type, amount, workflow_state]`.

- [ ] **Step 1: Build** — add the files; `cd frontend && yarn build`. Expected: build succeeds with no errors.
- [ ] **Step 2: Verify in browser** — start the preview, navigate to `/expense-requests`; confirm the list renders with the My/Team tabs and no console errors (`read_console_messages`). Expected: list screen loads.
- [ ] **Step 3: Commit** — `feat(expense-request): PWA list view, routes, data resources`.

---

### Task 8: PWA create form + approval (detail) view

**Files:**
- Create: `frontend/src/views/expenses/ExpenseRequestForm.vue`

**Interfaces:**
- Consumes: generic `FormView.vue` (drives create via `createListResource().insert`, attachments via `uploadAllAttachments`, and renders `WorkflowActionSheet` automatically because the doctype has a workflow), `get_doctype_fields`.
- Produces: `ExpenseRequestForm.vue`, a thin wrapper over `FormView.vue` with `doctype="Expense Request"`, `:isSubmittable="true"`, `:id="props.id"`, and a `formFields` resource filtered to the create-time fields (`expense_type`, `amount`, `currency`, `reason`, `receipt`, `prescription`) — approval/reimbursement/workflow fields are hidden on create via their `depends_on` (Task 1). Mirror `attendance/ShiftRequestForm.vue`.

- [ ] **Step 1: Build** — add the file; `yarn build`. Expected: success.
- [ ] **Step 2: Verify create** — in the preview as an employee, open `/expense-requests/new`, submit an `AI Tool` request with an attached receipt; confirm it creates and lands on the detail route in `Pending Manager` (check via `read_page`/network). Submit a `Food` request as an employee with no reports_to; confirm it lands in `Pending HR`.
- [ ] **Step 3: Verify approval** — as the manager, open the deep-link detail route; confirm `WorkflowActionSheet` shows `Approve`/`Reject`; Approve and confirm state → `Pending HR`. As an HR approver, Approve → `Pending Accounts`. As an Accounts approver, edit `paid_amount`/`payment_date`/`payment_mode`, Save, then `Complete`; confirm `Completed` and `docstatus==1`. Confirm the requester (same user as an HR/Accounts approver) does **not** see Approve on their own request.
- [ ] **Step 4: Commit** — `feat(expense-request): PWA create form and workflow approval view`.

---

### Task 9: Navigation entry

**Files:**
- Modify: `frontend/src/views/Home.vue` (add a `quickLinks` entry `{ title: "Request Expense", route: "ExpenseRequestFormView", icon: ... }`)

**Interfaces:**
- Consumes: the route from Task 7.

- [ ] **Step 1: Build** — add the entry; `yarn build`. Expected: success.
- [ ] **Step 2: Verify** — Home shows the "Request Expense" quick link routing to the create form. Expected: link present and navigates.
- [ ] **Step 3: Commit** — `feat(expense-request): home quick link`.

---

### Task 10: Deploy to prod & smoke test

**Files:** none (deployment).

- [ ] **Step 1:** Push the branch and merge to `develop` once all tests pass (per project flow).
- [ ] **Step 2: Backend deploy** — `docker cp` the changed `.py`/`.json`/patch into `docker-frappe-1` under the `hrms` app path, chown `frappe:frappe`, then `bench --site hrms.localhost migrate` (installs the doctype + runs the workflow patch + assigns roles), then `sudo docker restart docker-frappe-1`.
- [ ] **Step 3: Frontend deploy** — `cd frontend && yarn build`; tar `hrms/public/frontend` + `hrms/www/hrms.html`; `docker cp` into the container; extract as root; chown `frappe:frappe`; `bench --site hrms.localhost clear-cache`.
- [ ] **Step 4: Smoke test on prod** — create one `AI Tool` request as a test employee, walk it Manager→HR→Accounts→Completed, and confirm the stage emails and the reimbursement fields. Confirm an Accounts user sees the org-wide Pending-Accounts queue. Delete the smoke-test request afterward.
- [ ] **Step 5: Commit/record** — note the deploy in the session; update memory (`cx360-psa`/a new expense memory) with the workflow + roles facts.

---

## Notes for the implementer

- **Workflow condition safe-eval:** the Manager-stage gating relies on `frappe.session.user` being available in workflow transition conditions. It is in standard Frappe, but verify early (Task 4) — if unavailable, enforce the manager check in `expense_request.py` instead (compare `frappe.session.user == self.manager` when `workflow_state` enters `Pending HR` from `Pending Manager`).
- **`allow_edit` is one role per state**, which is why the HR/Accounts stages use the dedicated `Expense HR Approver` / `Expense Accounts Approver` roles (so the right approver can edit `rejection_reason` / `paid_amount` at their stage, and `useWorkflow.isReadOnly` lets them). The patch assigns these roles from the existing HR/Accounts role-holders; HR maintains membership thereafter.
- **No `PWANotificationsMixin`** in v1 (its hardcoded per-doctype approver dicts don't fit a multi-stage approver). In-app bell notifications are future work; v1 uses email only, per the spec.
