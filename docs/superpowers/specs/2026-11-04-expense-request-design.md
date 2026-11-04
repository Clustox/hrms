# Expense Request — Design

**Date:** 2026-11-04
**Status:** Approved — writing implementation plan.
**Owner:** Hamad

## Intent & why

Clustox employees have no structured way to request reimbursable expenses —
tool subscriptions, certifications, meals, medical bills, and long-service
rewards are handled ad hoc over chat and email, with no audit trail and no
visibility into where a request stands. This feature adds a self-service
**Expense Request** in the `/hrms` PWA: the employee raises it, it routes
through a defined approval chain depending on the expense type, and it ends in
a recorded reimbursement. Employees see status; HR and Accounts get an
auditable queue instead of scattered messages.

## The flow

An employee opens Expense Request in `/hrms`, picks one of six types, enters
the amount (PKR) and a reason, and attaches supporting files. Routing depends
on the type:

- **Manager-first types** — *AI Tool*, *Certifications*, *Food*:
  `Employee → Manager → HR → Accounts → Completed`
- **No-manager types** — *OPD*, *IPD*, *Long Service Reward*:
  `Employee → HR → Accounts → Completed`

At each stage the current approver can **approve** (advances to the next stage)
or **reject** (asks for a reason, stops the request). The requester can
**cancel** any time before Accounts marks it Completed. When Accounts
completes it, a **reimbursement record** is captured on the request.

- **Manager** = the employee's own `reports_to`.
- **HR stage** = a team queue; any one HR-team member acts for the team.
- **Accounts stage** = a team queue; any one Accounts-team member acts for the
  team.
- **Notifications:** `hr@clustox.com` and `accounts@clustox.com` get a
  heads-up when a request enters their stage; the requester is notified on each
  approval, rejection, and completion.
- **Where approvals happen:** all approvers (manager, HR, Accounts) act on a
  screen inside `/hrms`, reached from the notification email's deep link — the
  same pattern as the existing leave / WFH request screens. HR additionally can
  approve / reject / cancel the request from the main Frappe desk.

### Status model

`Draft → Pending Manager → Pending HR → Pending Accounts → Completed`, with
`Rejected` and `Cancelled` as terminal states reachable from any pending stage.
No-manager types skip `Pending Manager`.

### Reimbursement record (on completion)

A lightweight record attached to the request, for tracking and audit:
amount paid, payment date, payment mode (Bank Transfer / Petty Cash),
reference number, and who marked it paid.

### Attachments

- **Receipt / invoice** — required on every request.
- **Prescription** — additionally required for *OPD* and *IPD*.

### Rejection reason

A short predefined dropdown (e.g. amount too high, insufficient documentation,
not eligible) plus an optional free-text note.

## Goals

- Employee self-service expense request in `/hrms` with type, amount (PKR),
  reason, and attachments.
- Type-driven routing across the two approval chains above.
- HR and Accounts behave as shared team queues; manager = `reports_to`.
- Approve / reject-with-reason at each stage; requester cancel before
  completion.
- Email notifications at each transition (team inbox on arrival at a stage,
  requester on every outcome).
- A lightweight reimbursement record on completion.
- Approvals via the `/hrms` self-service screen from email links; HR can also
  act from the Frappe desk.
- Mobile-first, consistent with the existing leave / WFH request screens.

## Non-goals / anti-goals

- **No accounting or payroll posting.** The reimbursement record does not
  create a Payment Entry, GL entry, or payroll component in this build. It is
  designed so it *could* be wired into Frappe accounting later, but that hookup
  is explicitly out of scope now.
- **No hard policy-limit enforcement.** The form does not block an amount for
  being too high; "amount exceeds policy limit" is a rejection reason a person
  chooses, not a rule the system enforces.
- **HR does not edit the expense-type list through the UI.** The six types are
  a fixed list for now, stored so they are easy to extend later in code/config.
- **Not built on Frappe's native Expense Claim doctype** (see below).

## Constraints

- Production is `frappe.theclustox.com`, Frappe HR on Docker (`docker-frappe-1`,
  site `hrms.localhost`). Standard deploy conventions apply: backend `.py` via
  `docker cp` + chown + `bench restart`; frontend via `yarn build` → tar →
  `docker cp` → `bench clear-cache`; PWA is service-worker cached (users
  hard-refresh). Do **not** `git pull` on prod.
- RBAC: reuse the existing `request_visibility` scoping pattern (own + direct
  reports) so employees see their own requests and managers see their reports'.
- Currency is PKR throughout.
- Must sit alongside, and match the interaction model of, the existing leave /
  WFH / shift request screens in the PWA.

## The "how" decided (my calls — please sanity-check while reading)

1. **Custom doctype `Expense Request`** rather than bending Frappe's native
   Expense Claim. The native doctype is coupled to payroll and accounting
   (expense claim types, payable account, GL on sanction) in ways that fight a
   plain HR → Accounts routing flow with a standalone reimbursement record.
2. **Rejection reason** = predefined dropdown + optional note (above).
3. **Six types are a fixed, code/config-level list**, not UI-editable yet.
4. **Reimbursement is a lightweight record** (fields above), not an accounting
   document.

## Left to the builder

- Exact doctype and field names; whether the reimbursement record is a child
  table, a linked doctype, or a field group on the request.
- Workflow implementation: Frappe Workflow doctype vs a custom `status` field
  with server-side transition guards (must enforce the type → chain routing and
  stage-appropriate permissions).
- How "HR team" and "Accounts team" membership is resolved precisely — by role
  (HR-role users / Accounts-role users) vs a designated Frappe group/role; the
  default assumption is the existing HR and Accounts roles.
- PWA component structure (list, create form, and the email-linked
  approve/reject/cancel screen), reusing leave/WFH patterns.
- Email templates and the per-transition notification wiring, including the
  team-inbox addresses.
- Permission / `request_visibility` hook wiring for the new doctype, and the
  HR desk-access path.
- Test coverage for routing, stage permissions, cancellation window, and the
  attachment requirements.

## Decisions resolved in review (2026-11-04)

A builder-check pass flagged six points. Three were the user's call (answered
below); three I settled as the builder and note here.

**User decisions:**

1. **No manager on a manager-first type → auto-skip to HR.** If an employee on
   an *AI Tool / Certifications / Food* request has no `reports_to`, the request
   routes straight to the HR stage (no Pending-Manager step, nothing stalls).
2. **No self-approval (separation of duties).** If the requester is themselves
   on the HR or Accounts team, they cannot act on their own request at that
   stage — another member of that team must approve/reject it. Transition
   guards must exclude the requester as an approver at any stage.
3. **Accounts can set an actual paid amount.** The reimbursement record holds a
   `paid_amount` distinct from the requested amount, so Accounts can record a
   partial or corrected reimbursement at completion. The requested amount is
   preserved on the request.

**My calls (builder):**

4. **Queue visibility via role.** Employees see their own requests and managers
   see their direct reports' (the existing `request_visibility` own+reports
   scoping). HR and Accounts roles get full read access to Expense Requests so
   their team queues work org-wide; the ability to *act* is still gated by the
   current stage (and by decision 2). This resolves the tension between the
   own+reports constraint and the org-wide team queues.
5. **Manager is notified.** On `Draft → Pending Manager`, the manager is
   emailed at their own employee email (the HR/Accounts team inboxes only cover
   those two stages).
6. **Rejection is terminal; resubmit = new request.** A rejected request keeps
   its reason as a record and has no outbound transitions. To try again, the
   employee raises a new request. No in-place edit/resubmit in v1.

## Open questions deferred

None blocking. The accounting hookup and UI-editable type list are explicitly
future work, not part of this build.
