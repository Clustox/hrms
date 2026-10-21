"""Clustox biometric -> Frappe HR check-in sync (multi-device).

Pulls punch logs from one or more uFace800 devices (ZK protocol, comm key) and
pushes each new one to Frappe HR as an Employee Checkin via the REST API. The
Frappe scheduler then marks attendance automatically -- this script does NOT
touch attendance.

Devices are configured in config.json under "devices" (a list; each entry has
device_ip, device_port, comm_key, device_label). A legacy single-device config
(top-level device_ip/device_port/comm_key/device_label) is still honoured.

State: sync_state.json holds the last-synced punch timestamp PER DEVICE, keyed by
device_label, so each device only pushes its own new punches and the two streams
never clobber each other. A device with no stored cursor starts from config
"import_start" (full backfill). An old flat {"last_timestamp": ...} is migrated
onto the primary (first) device automatically.

Each device syncs independently: if one is unreachable the others still sync.
Cursor is checkpointed every 200 pushes so a crash resumes without re-pushing
(which would create duplicate check-ins).

Run:   python sync_checkins.py              (one pass; schedule via systemd timer)
       python sync_checkins.py --dry-run    (pull + report counts, push nothing)
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
CHECKPOINT_EVERY = 200

DRY_RUN = "--dry-run" in sys.argv[1:]


def log(msg):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            data = json.load(open(STATE_FILE))
            if isinstance(data, dict):
                return data
        except Exception as e:
            log(f"  WARN could not read state ({e}); starting empty")
    return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)  # atomic


def devices_from_config(cfg):
    """New-style 'devices' list, or a one-element list from the legacy fields."""
    if cfg.get("devices"):
        return cfg["devices"]
    return [{
        "device_ip": cfg["device_ip"],
        "device_port": cfg["device_port"],
        "comm_key": cfg.get("comm_key", 0),
        "device_label": cfg.get("device_label", "uface800"),
    }]


def migrate_flat_state(state, devices):
    """Move an old flat {"last_timestamp": ...} onto the primary device's label."""
    if "last_timestamp" in state:
        primary = devices[0].get("device_label", "uface800")
        state.setdefault(primary, state["last_timestamp"])
        state.pop("last_timestamp", None)
    return state


def pull_logs(dev, default_timeout):
    zk = ZK(dev["device_ip"], port=dev["device_port"], password=dev.get("comm_key", 0),
            timeout=dev.get("timeout", default_timeout), ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()
        return conn.get_attendance()
    finally:
        if conn:
            conn.enable_device()
            conn.disconnect()


def sync_device(dev, cfg, state, url, headers):
    label = dev.get("device_label", "uface800")
    cursor = datetime.datetime.fromisoformat(state.get(label, cfg["import_start"]))
    log(f"[{label}] cursor start: {cursor.isoformat()}")

    try:
        logs = pull_logs(dev, cfg.get("timeout", 30))
    except Exception as e:
        log(f"[{label}] CONNECT/PULL FAILED: {e} -- skipping this device, others continue")
        return

    new = sorted((a for a in logs if a.timestamp > cursor), key=lambda a: a.timestamp)
    log(f"[{label}] device returned {len(logs)} logs; {len(new)} new since cursor")
    if not new:
        return

    if DRY_RUN:
        log(f"[{label}] DRY-RUN: would push {len(new)} punches "
            f"(first={new[0].timestamp}, last={new[-1].timestamp}); nothing pushed")
        return

    pushed = skipped = errors = 0
    max_ts = cursor
    for i, a in enumerate(new, 1):
        payload = {
            "employee_field_value": str(a.user_id),
            "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": label,
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
                log(f"  [{label}] ERROR {r.status_code} user {a.user_id} @ {payload['timestamp']}: {r.text[:120]}")
        except Exception as e:
            errors += 1
            log(f"  [{label}] EXCEPTION user {a.user_id}: {e}")

        max_ts = max(max_ts, a.timestamp)
        if i % CHECKPOINT_EVERY == 0:      # resume cleanly after a crash
            state[label] = max_ts.isoformat()
            save_state(state)

    state[label] = max_ts.isoformat()
    save_state(state)
    log(f"[{label}] done: pushed={pushed} skipped_unmapped={skipped} errors={errors} new_cursor={state[label]}")


def main():
    cfg = json.load(open(CONFIG_FILE))
    devices = devices_from_config(cfg)
    state = migrate_flat_state(load_state(), devices)
    if not DRY_RUN:
        save_state(state)

    url = cfg["frappe_url"].rstrip("/") + \
        "/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
    headers = {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}

    for dev in devices:
        sync_device(dev, cfg, state, url, headers)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)
