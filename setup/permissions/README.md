# Clustox HR — RBAC / permissions

Reproducible, idempotent scripts that build the whole permission model on a
Frappe HR site: roles, the DocType rights matrix, field-level confidentiality,
employee record scoping, reporting placeholder, role assignment, and role
list cleanup.

> **No PII in this folder.** `assign_roles.py` reads real employee codes from a
> JSON mapping you keep private (see `role_assignments.example.json`). Everything
> else contains only DocType/role/field names.

Each `*.py` is a Frappe script: copy it into `apps/hrms/hrms/` and run with
`bench --site <site> execute hrms.<module>.run`. Back up first:
`bench --site <site> backup`.

## Run order

| # | Script | What it does | Notes |
|---|--------|--------------|-------|
| 1 | `apply_rights_matrix.py` | Creates 5 roles (Team Lead, Department Head, CEO/COO, IT User, Admin User) and applies the DocType permission matrix from `rights_matrix.json`. | Copy `rights_matrix.json` to `/tmp/` first, or pass `--kwargs "{'mapping_file': '/path'}"`. **Slow (~15–20 min)** — run backgrounded (`docker exec -d`) and poll for `MATRIX_END`. System Manager keeps full access on every customized DocType; export/print/import withheld from all other roles. |
| 2 | `apply_field_levels.py` | Moves sensitive Employee fields to Permission Level 1 (DOB, mobile, personal email, addresses, marital status, CNIC, CNIC expiry) and Level 2 (bank name/AC/IBAN); grants L1 to HR + CEO/COO, L2 to HR + CEO/COO + Accounts. | Only `Administrator` bypasses levels — a plain System Manager will **not** see these fields unless also HR/CEO. Fast. |
| 3 | `set_reports_to.py` | Sets `reports_to` for all Active employees to one manager so the org chart renders. | **Placeholder** — flat tree under one head. Pass `--kwargs "{'manager_code': 'CT-00006'}"`. Replace with real lines when available. |
| 4 | `assign_roles.py` | Adds roles to specific login accounts from a private JSON mapping. | Fill in `role_assignments.json` (git-ignored), pass `--kwargs "{'mapping_file': '/tmp/role_assignments.json'}"`. Idempotent; re-run after new logins to attach PENDING roles. |
| 5 | `scope_employees.py` | Restricts regular employees to their **own** transactional records (leave/attendance/salary/etc.) via per-doctype User Permissions, while leaving the Employee directory / org chart visible to all. | Users with a broad role (HR/Accounts/CEO/IT/System Manager) are skipped so they keep company-wide access. Idempotent; re-run after new logins. |
| 6 | `disable_roles.py` | Disables (not deletes) 25 unused ERPNext business-module roles (Sales/Purchase/Stock/Manufacturing/…) to declutter the role picker. | Reversible (`disabled = 0`). Skips any role a real user holds. |

## Layers, in one line each

- **What module** you can touch → rights matrix (#1)
- **Which sensitive fields** you can see → permission levels (#2)
- **Whose records** you can see → user-permission scope (#5)
- **Who is what** → role assignment (#4), on top of the org placeholder (#3)

## Not yet built

- **Manager team-scope** — managers seeing their reports' leave/attendance. Depends
  on real `reports_to` lines replacing the #3 placeholder; ships together with them.
- **Employee self-view of own confidential fields** — currently employees can't see
  their own CNIC/DOB either (HR-managed). Would need a self-service field exception.
