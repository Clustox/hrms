# Clustox HR — setup & migration scripts

Repeatable, idempotent scripts for standing up a Clustox Frappe HR site: employee
import, user provisioning, and the biometric attendance pipeline. Run them against
any site (dev/test/prod) to bring it to the same state.

> **No secrets or PII are committed here.** Employee data files, API keys, the
> device IP/comm key, and passwords live only in git-ignored config on the machine
> that runs these — never in the repo. Files ending in real values (`config.json`,
> `employees*.json`, `device_users.json`, `attendance_2026.json`) are git-ignored.

## Custom fields

The Pakistan-specific Employee fields (CNIC, CNIC expiry, father/husband name,
religion, nationality) ship as **fixtures** (`hrms/fixtures/custom_field.json`,
wired in `hooks.py`). They install automatically on `bench migrate` — no script
needed.

## Run order

Each `*.py` under `import/`, `users/`, `attendance/` is a Frappe script: copy it
into `apps/hrms/hrms/` and run with `bench --site <site> execute hrms.<module>.run`
(some take `--kwargs "{'data_file': '/path/to/file.json'}"`).

1. **import/** — `export_employees.py` converts an HR xlsx to JSON; `one_off_import.py`
   and `one_off_import_batch2.py` load employees, company, departments, payroll.
   *(Skip if the site already has the employee data.)*
2. **users/** — `provision_users.py` creates linked login accounts (Employee Self
   Service). `setup_admins_server.py` (standalone; run with the bench python) grants
   System Manager + sets passwords for named admins — fill in its `TARGETS` first.
3. **attendance/** — `map_device_ids.py` (device id → employee), `setup_attendance.py`
   (Holiday List + flexible Shift), `add_holidays.py` (public holidays),
   `backfill_august.py` (one-time attendance backfill from a punch export).
4. **attendance_sync/** — the live device→Frappe sync service. See its README.

## Production checklist (before real data)

- Bind the web port to localhost + put TLS/nginx in front; firewall the device port.
- Use a dedicated integration user (not Administrator) for the sync API key.
- Load the confirmed public-holiday calendar and approved leaves.
- Move work-from-home staff onto Frappe's web/mobile check-in.
