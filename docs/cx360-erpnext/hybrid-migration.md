# CX360 → ERPNext Hybrid Migration

**Date:** 2026-10-09
**Status:** COMPLETE — all 3 phases built, deployed to prod, and verified (2026-10-12). Costing wired natively via Activity Cost; Project Budget stays retired.
**Driver:** Manager direction — map requirements onto stock ERPNext first; keep custom only for the genuine gaps. See the fit-&-gap analysis (artifact "CX360 on ERPNext", https://claude.ai/artifact/EbAf64Q1KYNHjpWE9RZcdA).

## Decisions (locked 2026-10-09, Hamad)

1. **Engagement object = ERPNext `Sales Order`** (+ a few custom fields), replacing the custom `SOW` doctype.
2. **Go fully native on budgeting & rates:** retire `Project Budget` and `Designation Rate`; use native **`Activity Cost`** for rates and native **`Project.gross_margin`** for profit/cost commission bases.
3. **Roll out incrementally in place** on the live instance; nothing breaks mid-way; retire parallel doctypes last.

## Target architecture

**Stock ERPNext (adopt as-is):** `Item` (service) · `Sales Order` (engagement) · `Project` + `Task` · `Activity Cost` (rate card) · `Timesheet` (billing/costing) · `Sales Invoice` (revenue) · `Project.gross_margin` / `total_costing_amount` / `total_billed_amount` (profitability) · `Budget`/`Cost Center` · `Issue`.

**Custom, re-seated on stock (keep):**
- **Resource Allocation** — % allocation + ≤100% capacity, keyed on `Project` only (drop the SOW link).
- **Commission engine** — `Commission Rule` + `Commission Run` + `Commission Entry` + `Commission Rule Override`, reading:
  - *who*: Working Resources from Resource Allocation; Sales/Delivery Lead/PM/Referrer from a **Project Team** child table on `Project` (replacing SOW Team).
  - *bases*: Resource revenue & Total project revenue (from Timesheet — native fields), **Project value** (from the linked Sales Order), **Project profit** (`Project.gross_margin`), **Project cost** (`Project.total_costing_amount`). The planned-budget bases are removed.
  - rules stack; per-person overrides stay; all USD.

**Retire:** `SOW` (+ `SOW Deliverable`, `SOW Team Member`), `Project Budget` (+ `Budget Resource Line`, `Budget Cost Line`), `Designation Rate`.

## Custom fields added to stock doctypes (via `hrms/fixtures/custom_field.json`)

On **Project**:
- `custom_engagement_type` (Select: Sale / Internal)
- `custom_billing_model` (Select: Time & Material / Deliverable / Fixed Monthly)
- `custom_sales_order` (Link → Sales Order) — the primary engagement
- `custom_team` (Table → Project Team Member) — commission roles

## Incremental phases

**Phase 1 — add the stock seat** ✅ done *(additive; SOW/Budget untouched)*
- New child doctype **Project Team Member** (employee, employee_name, role).
- Project custom fields above, shipped via fixtures.
- Resource Allocation keeps working (already keyed on Project); SOW link left in place for now, removed in Phase 3.

**Phase 2 — re-seat the commission engine** ✅ done
- `commission_engine`: `project_value` from the Project's Sales Order (`net_total`); `project_cost` = Σ Timesheet `costing_amount`; `project_profit` = Σ `billing_amount` − Σ `costing_amount`. Team read from `Project.custom_team`.
- **Currency note:** profit/cost are computed from the **USD timesheet line amounts**, NOT native `Project.gross_margin`/`total_costing_amount` — those roll up company-currency (PKR) fields (e.g. `total_purchase_cost` = base amount), and commissions are USD. The timesheet `billing_amount`/`costing_amount` stay in document currency (USD) and are still native Timesheet data fed by Activity Cost.
- `Commission Rule` base options point at native sources; the Project-Budget-backed values are gone. Scope by Project `custom_engagement_type` / `custom_billing_model`.

**Phase 3 — retire the parallels** ✅ done
- Migrated demo records onto Sales Order / Project + Project Team.
- Dropped `SOW`, `Project Budget`, `Designation Rate` (+ children, the `Project.custom_sow` field, the `sow` links on Resource Allocation/Commission Entry). CX360 workspace points at Sales Order / Project / Resource Allocation / Commission Rule / Commission Run.

## Costing & budgeting (decided 2026-10-12 — option A: native costing, no planned budget)
- **Costing is native, via `Activity Cost`** — one record per **Employee × Activity Type** with a **billing rate** (client charge) and a **costing rate** (internal cost). New Timesheets auto-fill both; the `costing_amount` on each line drives project cost and the commission profit/cost bases. Edit rates in the Activity Cost list.
- **Project Budget stays retired.** There is no native resource-plan-by-designation budget (only `Project.estimated_costing` or GL-account `Budget`/`Cost Center`). If up-front planning (plan-vs-actual) is ever needed, the Project Budget layer can be restored from git history (it was removed in this PR).
- Seeded placeholder costing rates on prod (Hamad $18/hr, others $40/hr) so costing/profit compute on the demos — adjust in Activity Cost.

## Notes / caveats
- Profit is an **actual** (timesheet billing − timesheet cost), so profit-based commissions compute once real Timesheet data exists — different from the old planned-budget number.
- Internal engagements = `Project` with `custom_engagement_type = Internal` and no Sales Order; commission there uses Flat or cost bases.
- **Ops:** the prod CI pipeline periodically rewrites `hooks.py` and drops the in-place CX360 edits (the `after_migrate` workspace-placement hook, Timesheet hook). Permanent fix = merge this PR (#48) + #45 into the branch the pipeline deploys.
