# CX360 — Project Allocation, SOW & Commission Engine (Design)

**Date:** 2026-10-07
**Status:** Design, pending user review
**Context:** Clustox Frappe HR / ERPNext (`frappe.theclustox.com`). This is the detailed design for Phases A (Resource Allocation) and C (Commissions) of the CX360 picture, plus the SOW and billing wiring they depend on. See `docs/cx360-erpnext/implementation-roadmap.md` for the broader programme.

---

## 1. Goal

Model Clustox's services delivery → commission flow end-to-end in ERPNext, reusing stock doctypes where possible and adding the minimum custom layer. A project manager or team lead should only have to: tag the project's team, allocate resources by %, and log timesheet hours (or mark deliverables done). The system then enforces capacity rules and computes every commission automatically from **configurable rules** — no hardcoded percentages.

### Core flow being modelled
Project ← resources allocated by % ← governed by an SOW (Sale or Internal; Sale is Time & Material or Deliverable-based) ← rates from a rate card ← hours logged on timesheets → period reconciliation of allocation + hours + SOW values → commission computed from rules → client invoice → revenue.

## 2. Principles

- **Configurable over hardcoded.** Commission bases, percentages, and payout triggers are data entered on a Commission Rule screen, not logic in code. Exact percentages are deliberately *not* fixed in this spec — the design must express every commission *shape*, and the numbers are entered later.
- **Reuse ERPNext first.** Add custom doctypes only where stock ERPNext has no equivalent.
- **Build bottom-up.** SOW → Allocation → rate wiring → Commission engine. The engine can only compute once the data it reads exists.
- **Review before money moves.** A commission run produces a reviewable statement; nothing posts to payroll automatically in v1.

## 3. Reused ERPNext doctypes (no change)

| Doctype | Use |
|---|---|
| Project | One per engagement; carries status, dates, cost centre. |
| Timesheet | Hours + billing rate + costing rate per time log; already bills to Sales Invoice. Source of "hours logged". |
| Sales Invoice | Client invoice → revenue. From Timesheet (T&M) or per deliverable milestone. |
| Customer | SOW client. |
| Employee | The resource / team member. |
| Activity Type + Activity Cost | Default per-employee rate card; fallback when no project-specific rate is set. |

## 4. Custom doctypes

### 4.1 SOW
Governs a client engagement and its commercial terms.

- `title`, `customer` (Link Customer), `status` (Draft / Active / Closed / Cancelled), `start_date`, `end_date`.
- `sow_type` (Select: **Sale** / **Internal**). Sale invoices the client; Internal does not — but **Internal projects can still pay commission** (base is a Flat amount or the configured Project / Fixed-Monthly value, via a rule scoped to Internal).
- `billing_model` (Select: **Time & Material** / **Deliverable** / **Fixed Monthly**) — applies to both Sale and Internal.
- Time & Material fields: `monthly_hours_commitment` (Int), `default_billing_rate` (Currency, per hour) — a default; per-resource rates live on the allocation.
- Fixed Monthly field: `monthly_value` (Currency) — the fixed monthly figure; commission rules use it as the base (typically scaled by allocation %).
- `total_value` (Currency) — for Deliverable SOWs, the sum of deliverable amounts; for T&M / Fixed Monthly, an estimate of the engagement value.
- **Deliverables** — child table *SOW Deliverable*: `title`, `due_date`, `amount` (Currency), `status` (Pending / Completed), `completed_on`.
- **Team** — child table *SOW Team Member*: `employee` (Link Employee), `role` (Select: **Sales** / **Delivery Lead** / **PM** / **Other**). This is where non-allocated commission roles (Sales, Delivery Lead) are tagged. Working Resources are NOT entered here — they come from Resource Allocation.
- **Projects** — a Project links to its SOW via a custom field `custom_sow` (Link SOW). One SOW may have several Projects; the SOW shows them as a read-only list.

### 4.2 Resource Allocation
One record = one person's commitment to one project for a date range.

- `employee` (Link Employee), `project` (Link Project), `sow` (fetched from project), `status` (Active / Closed).
- `allocation_percent` (Float, 0–100).
- `start_date`, `end_date`.
- `project_billing_rate` (Currency, per hour) — this resource's client rate **on this project** (enables different rates on different projects). Falls back to Activity Cost default if blank.
- `project_cost_rate` (Currency, per hour) — this resource's cost on this project, for margin. Falls back to the employee's cost rate.
- **Derived:** `monthly_capacity_hours` = `allocation_percent`/100 × `STANDARD_MONTHLY_HOURS` (160, held as a single configurable constant / HR setting).

**Validations**
- **Over-allocation (hard block):** for a given `employee`, the sum of `allocation_percent` across Active allocations whose date ranges overlap must be ≤ 100. On violation, `frappe.throw`.
- Date range sanity (`end_date` ≥ `start_date`).

### 4.3 Commission Rule
The configurable screen. One rule = one record; rules stack (a person can match several and earn several).

- **Identity:** `rule_name`, `active` (Check), `effective_from`, `effective_to` (Date). Changing a rate = end-date the old rule, add a new one — history preserved.
- **Who:** `role` (Select: **Working Resource** / **Sales** / **Delivery Lead** / **PM**).
- **Scope:** `sow_type_scope` (Select: Any / Sale-T&M / Sale-Deliverable / Internal); optional `customer_scope` (Link Customer) and `project_scope` (Link Project) to narrow a rule to one client or project. Different projects carrying different rates = different rules, same screen.
- **Base:** `base` (Select):
  - **Resource revenue** — the person's billable hours in the period × their billing rate (from Timesheet / allocation).
  - **Project revenue** — invoiced amount in the period, or SOW/deliverable value for completion triggers.
  - **Margin** — revenue − the person's cost (hours × cost rate).
  - **Deliverable amount** — the fixed amount on a completed deliverable.
  - **Flat amount** — a fixed figure (uses `rate_value` directly as the base).
- **Rate:** `rate_type` (Percent / Flat) + `rate_value` (Float).
- **Modifiers:** `scale_by_allocation` (Check) — multiplies the result by the person's `allocation_percent`. Intended for Flat bases (e.g. fixed monthly figure × 50% allocation); leave OFF for Resource revenue/Margin, which already reflect hours and would otherwise double-count.
- **Guards (optional):** `min_amount`, `max_amount` (Currency) per payout; `notes`.
- **When:** `trigger` (Select: **Monthly recurring** / **On project completion** / **Per deliverable completed**).

### 4.4 Commission Run (+ Commission Entry child)
The engine output; produced per period or per completion event.

- Header: `run_type` (Monthly / Completion / Deliverable), `period_start`, `period_end` (for Monthly), `project` (optional filter), `status` (Draft / Reviewed / Posted).
- **Entries** — child table *Commission Entry*: `employee`, `project`, `sow`, `role`, `rule` (Link Commission Rule), `base_amount`, `rate`, `commission_amount`, `period`, `notes`.

## 5. The commission engine (Commission Run logic)

For the run's scope and trigger:

1. **Collect (person, project, role) candidates.**
   - Working Resources: from Resource Allocation records Active in the period.
   - Sales / Delivery Lead / PM: from the SOW Team table of the relevant SOW(s).
2. **Match rules.** For each candidate, find all `active` Commission Rules where `role` matches, scope matches (sow_type / customer / project), the run date falls within `effective_from..effective_to`, and `trigger` matches the run type.
3. **Compute base** per rule base type:
   - Resource revenue = Σ(billable hours in period for person+project × billing rate).
   - Margin = resource revenue − Σ(hours × cost rate).
   - Project revenue = invoiced amount in period (Monthly) or SOW `total_value` (On completion) for Sale projects. For Internal / Fixed-Monthly projects (no invoice), it resolves to the SOW's `monthly_value` (Monthly) or `total_value` (On completion).
   - Deliverable amount = the completed deliverable's `amount` (Per deliverable runs iterate completed deliverables).
   - Flat amount = `rate_value` (base is the figure itself).
4. **Compute commission** = base × `rate_value`% (or the flat figure), × allocation% if `scale_by_allocation`, clamped to `min_amount`/`max_amount`.
5. **Emit one Commission Entry** per (person, project, rule). Entries are additive — stacking is automatic.
6. **Review → Post.** Draft is reviewed by HR/Finance. Posting in v1 records the statement (and can export); auto-creating payroll components (Additional Salary / Journal Entry) is a later integration (§7).

### Worked mapping (the shapes must all be expressible)
| Rule | role | base | trigger |
|---|---|---|---|
| Sales attach | Sales | Project revenue | Monthly recurring |
| Resource monthly (T&M) | Working Resource | Resource revenue | Monthly recurring |
| Fixed-cost payout | Working Resource | Project revenue | On project completion |
| Deliverable payout | Working Resource | Deliverable amount | Per deliverable completed |
| Delivery lead | Delivery Lead | Margin | Monthly recurring |
| Internal fixed-monthly | Working Resource | Project value (`monthly_value`), scaled by allocation | Monthly recurring |

## 6. Capacity & hours enforcement

- **Allocation ≤ 100%** — enforced on Resource Allocation save (hard block, §4.2).
- **Hours cap — soft alert, not a block.** On Timesheet save, compare the employee's logged hours for the month on that project against `monthly_capacity_hours`. If exceeded, show an alert/`msgprint` ("Resource X has logged N hrs this month vs capacity M") and flag the record. Overtime is explicitly allowed — the system warns, it does not stop.

## 7. Revenue / invoicing

Reuse Sales Invoice: T&M projects invoice from Timesheet; Deliverable projects invoice per completed milestone; Internal projects do not invoice. Revenue reporting uses the resulting invoices. No custom revenue doctype. Internal-project commissions draw on the SOW's configured value (`monthly_value` / `total_value`), not on invoices.

## 8. Build sequence

1. SOW doctype (+ Deliverable, Team children; Project `custom_sow` field).
2. Resource Allocation doctype + over-allocation validation.
3. Rate wiring (project rates on allocation; fallback to Activity Cost) + Timesheet hours-cap alert.
4. Commission Rule doctype (the config screen).
5. Commission Run engine + Commission Entry; review/post workflow.
6. Invoicing wiring + commission reports.

## 9. Non-goals (v1)

- Automatic posting of commissions into payroll (manual/export in v1; integration later).
- Commission clawbacks / reversals.
- Multi-currency beyond company currency.
- Capacity forecasting / Gantt resourcing UI (allocation is record-based, not a visual planner).

## 10. Open items to confirm during build (not blocking the design)

- **Commission percentages / flat figures** — entered as rules, by design not fixed here.
- **Posting target** — statement-only vs Additional Salary vs Journal Entry when a run is posted.
- **Cost rate composition** — does `project_cost_rate` include overhead, or raw salary cost only? (Affects Margin bases.)
- **Project-revenue timing** — invoiced-in-period vs recognised/accrued, for Monthly Project-revenue rules.
- **Per-person rate override** — whether a Commission Rule's rate can be overridden for one person, or always stays rule-level (v1 assumes rule-level).
