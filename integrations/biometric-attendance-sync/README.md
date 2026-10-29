# Biometric attendance sync (uFace800 / ZK → Frappe HR)

Pulls punch logs from one or more **uFace800** (ZKTeco protocol) biometric
devices and pushes each new punch into Frappe HR as an **Employee Checkin** via
the REST API. Frappe's own scheduler then marks attendance — this tool does
**not** write Attendance records itself.

This runs **outside** the Frappe container, as a standalone script on the host,
scheduled by a systemd timer.

## How it works

- Connects to each device over the ZK protocol (`pyzk`) using its `comm_key`.
- For each punch newer than that device's cursor, POSTs to
  `…/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field`
  with the device **user id** (`employee_field_value`), the timestamp, the
  `device_label` as `device_id`, and the IN/OUT `log_type`.
- The device user id is matched to an employee by **`Employee.attendance_device_id`**;
  an unmapped id comes back "No Employee found" and is skipped.
- **Per-device cursor:** `sync_state.json` stores the last-synced timestamp per
  `device_label`, so each device only pushes its own new punches and the two
  streams never clobber each other. A device with no cursor starts from
  `import_start` (full backfill). The cursor is checkpointed every 200 pushes so
  a crash resumes without creating duplicate check-ins.
- **Isolation:** each device syncs independently — if one is unreachable, the
  others still sync.

## Setup

```bash
# 1. Place the tool on the host (example: /opt/clustox-attendance-sync)
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 2. Create config.json from the template and fill in real values
cp config.example.json config.json
chmod 600 config.json          # it holds the Frappe API key/secret + comm keys
#   edit config.json: real device IP/port/comm_key, frappe_url, api_key, api_secret

# 3. Try it without writing anything
./venv/bin/python sync_checkins.py --dry-run

# 4. Schedule it (copy the units, adjust User/paths inside them first)
sudo cp clustox-attendance-sync.service clustox-attendance-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now clustox-attendance-sync.timer   # fires every 15 min
```

Run the script **as the same user** the systemd service uses (so `sync_state.json`
and `sync.log` stay writable by both): e.g. `sudo -u <user> ./venv/bin/python sync_checkins.py`.

## Configuration (`config.json`)

See `config.example.json`. Real device IPs/ports, comm keys, and the Frappe API
credentials live **only** in `config.json`, which is git-ignored — never commit
it.

| Key | Meaning |
|-----|---------|
| `frappe_url` | Base URL of the Frappe site |
| `api_key` / `api_secret` | Frappe API token (`token <key>:<secret>`) |
| `import_start` | ISO timestamp; a device with no cursor backfills from here |
| `timeout` | ZK connection timeout (seconds) |
| `devices[]` | One entry per physical device |
| `devices[].device_ip` / `device_port` | How to reach the device (ZK default port is 4370) |
| `devices[].comm_key` | The device's comm password (0 if none) |
| `devices[].device_label` | Stable name; written to each check-in's `device_id` and used as the cursor key — **don't rename** an in-use device or its cursor resets |

A legacy single-device config (top-level `device_ip`/`device_port`/`comm_key`/
`device_label` with no `devices` list) is still honoured.

## Adding another device

Append an entry to `devices[]` with a new unique `device_label`, then run once
(or wait for the timer). It starts from `import_start` and backfills. **Employee
IDs must be consistent across devices** — the same person must have the same user
id on every device, or their punches map to the wrong employee.

## Operational notes

- Logs: `sync.log` (and `journalctl -u clustox-attendance-sync.service`).
- State lives in `sync_state.json`; back it up with `config.json` before edits.
- An employee whose punches are being skipped needs their device user id set as
  `Employee.attendance_device_id` in Frappe.
