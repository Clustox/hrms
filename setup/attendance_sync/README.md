# Biometric attendance sync

Live pipeline: ZKTeco biometric device → Frappe HR check-ins → auto-attendance.

```
Biometric device (ZK protocol, comm key)
   │  pyzk pull (this service, every 15 min)
   ▼
sync_checkins.py  ──REST──►  Frappe  /api/method/...add_log_based_on_employee_field
                                     │  creates Employee Checkin (resolved by attendance_device_id)
                                     ▼
                             Frappe scheduler (built-in):
                               update_last_sync_of_checkin + process_auto_attendance_for_all_shifts
                                     ▼
                             Attendance — automatic
```

The service ONLY pushes check-ins; the Frappe scheduler advances the sync cursor
and marks attendance.

## Prerequisites on the Frappe site (run ONCE)

The join key, holidays, and shift are set up by the scripts under `setup/attendance/`
and `setup/import/`. Copy each into the app and run via `bench execute` (see
`setup/README.md`). Then confirm the scheduler is enabled:

```bash
bench --site <site> enable-scheduler
```

Generate an API key/secret for a user that can create Employee Checkins
(a dedicated integration user is preferred over Administrator in production):
**User → Settings → API Access → Generate Keys**.

## Deploy the sync service

```bash
sudo mkdir -p /opt/attendance-sync
sudo cp sync_checkins.py config.example.json /opt/attendance-sync/
cd /opt/attendance-sync
python3 -m venv venv && venv/bin/pip install pyzk requests
sudo cp config.example.json config.json      # then edit config.json:
#   device_ip / device_port / comm_key   = the device's values
#   api_key / api_secret                  = generated keys
#   frappe_url                            = the site URL
#   import_start                          = backfill start (first run pulls from here)
sudo chmod 600 config.json                    # holds the comm key + API secret
```

First run manually and watch the log:
```bash
venv/bin/python sync_checkins.py     # prints pushed/skipped/errors; writes sync.log + sync_state.json
```

Expected: `pushed=<n> skipped_unmapped=<small> errors=0`. `skipped_unmapped` =
device users with no matching employee — normal.

## Schedule it (systemd timer, every 15 min)

```bash
sudo cp clustox-attendance-sync.service clustox-attendance-sync.timer /etc/systemd/system/
# edit the .service: set User and paths to the deploy location
sudo systemctl daemon-reload
sudo systemctl enable --now clustox-attendance-sync.timer
systemctl list-timers clustox-attendance-sync.timer
```

## Notes

- **Device port/comm key**: many ZK devices use the default port 4370 with no comm
  key. If the device requires a comm key or a non-default port, set both in
  config.json — this script passes them (the stock frappe sync tool does not).
- **Idempotency**: `sync_state.json` tracks the last punch timestamp; only newer
  punches are pushed. Delete it to re-pull from `import_start`.
- **Secrets**: `config.json` holds the API secret + comm key — never commit it.
