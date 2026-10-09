# CX360 → ERPNext Hybrid Migration

**Date:** 2026-10-09
**Status:** In progress (Phase 1)
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

**Phase 1 — add the stock seat** *(this change; SOW/Budget untouched and still working)*
- New child doctype **Project Team Member** (employee, employee_name, role).
- Project custom fields above, shipped via fixtures.
- Resource Allocation keeps working (already keyed on Project); SOW link left in place for now, removed in Phase 3.

**Phase 2 — re-seat the commission engine**
- `commission_engine`: `project_value` from the Project's Sales Order; `project_profit` from `Project.gross_margin`; `project_cost` from `Project.total_costing_amount`. Team read from `Project.custom_team`.
- `Commission Rule` base options point at native sources; drop the Project-Budget-backed values. Scope by Project `custom_engagement_type` / `custom_billing_model`.
- Verify a Commission Run reproduces the expected figures against native data.

**Phase 3 — retire the parallels**
- Migrate demo records onto Sales Order / Project + Project Team.
- Drop `SOW`, `Project Budget`, `Designation Rate` (and their children, fixtures, workspace links). Clean the CX360 workspace to point at Sales Order / Project / Resource Allocation / Commission Rule / Commission Run.

## Notes / caveats
- Native **profit** (`gross_margin`) is an *actual* (invoiced revenue − logged cost), so profit-based commissions compute once real Timesheet + Sales Invoice data exists — the correct ERPNext behaviour, different from the planned-budget number in the earlier demo.
- Internal engagements = `Project` with `custom_engagement_type = Internal` and no Sales Order; commission there uses Flat or cost bases.
- Rates: commission cost/margin reads Timesheet `costing_amount` (fed by `Activity Cost`); no custom rate card.
