"""Clustox biometric -> Frappe HR check-in sync.

Pulls punch logs from the uFace800 (ZK protocol, comm key) and pushes each new
one to Frappe HR as an Employee Checkin via the REST API. The Frappe scheduler
(update_last_sync_of_checkin + process_auto_attendance_for_all_shifts) then
marks attendance automatically -- this script does NOT touch attendance.

State: the timestamp of the last synced punch is stored in STATE_FILE so each
run only pushes new punches. First run starts from config "import_start".

Deps:  pip install pyzk requests
Run:   python sync_checkins.py            (one pass; schedule via systemd timer/cron)
Config: config.json next to this script (see config.example.json).
"""

import datetime
import json
import os
import sys

import requests
from zk import ZK

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "config.json")
STATE_FILE = os.path.join(HERE, "sync_state.json")
LOG_FILE = os.path.join(HERE, "sync.log")

PUNCH_TO_LOGTYPE = {0: "IN", 1: "OUT"}  # ZK: 0=check-in, 1=check-out


def log(msg):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_cursor(default_iso):
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE)).get("last_timestamp", default_iso)
    return default_iso


def save_cursor(ts_iso):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_timestamp": ts_iso}, f)


def main():
    cfg = json.load(open(CONFIG_FILE))
    cursor = datetime.datetime.fromisoformat(load_cursor(cfg["import_start"]))
    log(f"cursor start: {cursor.isoformat()}")

    # --- pull from device ---
    zk = ZK(cfg["device_ip"], port=cfg["device_port"], password=cfg["comm_key"],
            timeout=cfg.get("timeout", 30), ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()
        logs = conn.get_attendance()
    finally:
        if conn:
            conn.enable_device()
            conn.disconnect()

    new = sorted((a for a in logs if a.timestamp > cursor), key=lambda a: a.timestamp)
    log(f"device returned {len(logs)} logs; {len(new)} new since cursor")
    if not new:
        return

    # --- push to Frappe ---
    url = cfg["frappe_url"].rstrip("/") + \
        "/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
    headers = {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}

    pushed = skipped = errors = 0
    max_ts = cursor
    for i, a in enumerate(new, 1):
        payload = {
            "employee_field_value": str(a.user_id),
            "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": cfg.get("device_label", "uface800"),
            "log_type": PUNCH_TO_LOGTYPE.get(a.punch, ""),
        }
        try:
            r = requests.post(url, headers=headers, data=payload, timeout=30)
            if r.status_code == 200:
                pushed += 1
            elif "No Employee found" in r.text or "not found" in r.text.lower():
                skipped += 1  # device user not mapped to an employee
            else:
                errors += 1
                log(f"  ERROR {r.status_code} for user {a.user_id} @ {payload['timestamp']}: {r.text[:120]}")
        except Exception as e:
            errors += 1
            log(f"  EXCEPTION for user {a.user_id}: {e}")

        max_ts = max(max_ts, a.timestamp)
        if i % 200 == 0:            # checkpoint so a crash resumes cleanly
            save_cursor(max_ts.isoformat())

    save_cursor(max_ts.isoformat())
    log(f"done: pushed={pushed} skipped_unmapped={skipped} errors={errors} new_cursor={max_ts.isoformat()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)
