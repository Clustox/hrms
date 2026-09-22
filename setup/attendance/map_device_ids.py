"""Set Employee.attendance_device_id from the biometric device user list.

Mapping rule (verified against Clustox data): the device user ID is the
numeric part of the employee code, i.e. device id N -> employee CT-{N:05d}.
For each device user with a numeric id whose CT code exists as an Employee,
sets attendance_device_id = the device id (the value the device sends in
punch logs). This is the join key that lets Employee Checkins resolve to
the right employee.

Run: bench --site <site> execute hrms.map_device_ids.run \
        --kwargs "{'data_file': '/path/to/device_users.json'}"
Idempotent: safe to re-run.
"""

import json

import frappe

DATA_FILE = "/workspace/.employee_import/device_users.json"  # default: local docker dev


def run(data_file=None):
    dev = json.load(open(data_file or DATA_FILE))
    log = {"mapped": [], "no_employee": [], "non_numeric": [], "unchanged": []}

    for d in dev:
        did = str(d.get("device_user_id", "")).strip()
        name = d.get("name")
        if not did.isdigit():
            log["non_numeric"].append(f"id={did!r} name={name!r}")
            continue
        ct = "CT-%05d" % int(did)
        emp = frappe.db.get_value("Employee", {"employee_number": ct}, "name")
        if not emp:
            log["no_employee"].append(f"device id={did} ({name}) -> {ct} : no employee")
            continue
        current = frappe.db.get_value("Employee", emp, "attendance_device_id")
        if current == did:
            log["unchanged"].append(f"{ct} = {did}")
        else:
            frappe.db.set_value("Employee", emp, "attendance_device_id", did)
            log["mapped"].append(f"{ct} <- device id {did} ({name})")

    frappe.db.commit()

    # employees that ended up with NO device id (not enrolled on the machine)
    unmapped_emps = frappe.db.sql(
        """SELECT employee_number, employee_name FROM `tabEmployee`
           WHERE status='Active'
             AND (attendance_device_id IS NULL OR attendance_device_id='')
           ORDER BY employee_number""",
        as_dict=True,
    )

    print("\n========== DEVICE ID MAPPING SUMMARY ==========")
    for k in ("mapped", "unchanged", "no_employee", "non_numeric"):
        print(f"\n{k.upper()} ({len(log[k])}):")
        for i in log[k]:
            print("  ", i)
    print(f"\nACTIVE EMPLOYEES WITH NO DEVICE ID ({len(unmapped_emps)}):")
    for e in unmapped_emps:
        print(f"   {e.employee_number}  {e.employee_name}")
