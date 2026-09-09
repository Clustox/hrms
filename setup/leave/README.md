# Leave policy setup

Translates the Clustox **Leaves Policy (v1.3)** into Frappe HR: leave types,
the 2026 leave period, an annual leave policy, and allocations for every active
employee.

```bash
bench --site <site> execute hrms.apply_leave_policy.run
```

Idempotent — re-run to onboard newly-added employees (existing records are
skipped; new hires get prorated allocations based on join date).

## Quotas (policy "Categories of Leaves" table)

| Leave type | Quota | How it's granted |
|---|---|---|
| Annual Leave | 10 / yr | Annual policy; carry-forward capped at 5; usable after 1 yr service |
| Medical/Sick Leave | 7 / yr | Annual policy |
| Casual Leave | 5 / yr | Annual policy; 1 at a time; no carry-forward |
| Religious Leave | 5 / 3 yrs | Standalone allocation, valid 2026–2028 |
| Maternity Leave | 6 wks (30 wd) | Event-based (HR allocates); after 6 mo service |
| Paternity Leave | 3 | Event-based |
| Marriage Leave | 5 | Event-based |
| Bereavement Leave | 2 (calendar) | Event-based |
| Hajj/Umrah Leave | 10 (once) | Event-based; after 1 yr service |
| Long Service Leave | 5 @ 5 yr / 10 @ 10 yr | Event-based |
| Half-day | 0.5 of Casual | Built-in half-day flag on an application |
| Compensatory Off | earned | Compensatory Leave Request |
| Leave Without Pay | — | No allocation needed |

Annually-allocated types (Annual/Sick/Casual) live in the **Leave Policy** and
are assigned to all active employees via `create_assignment_for_multiple_employees`
(prorated by join date). Everything else is allocated by HR when the employee
qualifies.

## Enforced by HR, not encoded (Frappe limitations)

- **Gender** restriction (Maternity = female, Paternity = male) — not native;
  safe because these are event-based, so HR controls allocation.
- **Probation** rules (Casual not permitted in probation; Sick 2 days for
  probationers).
- **Compensatory** "lapses after 1 month" and comp accrual via requests.
- **Advance notice / sandwich-leave** rules (Annual 30/3 days, Marriage 45 days,
  Hajj 2 months) are procedural.
- **Religious** 3-year window resets manually after 2028.

## Prerequisites

- A holiday list for the year (site already has **"Clustox 2026"**) — drives
  working-day counts and the sandwich-leave rule.
