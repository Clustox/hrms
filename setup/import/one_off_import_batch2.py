"""Batch 2: import the Active Employees list (org placement only).

Source sheet columns: Sr No, Code, Name, Branch, Location, Department,
Designation, Date Of Joining.

Existing employees (matched by employee_number) get ONLY their org fields
updated — personal data from batch 1 is never touched. New employees are
inserted with placeholder DOB (1900-01-01) and gender ("Prefer not to say")
per Hamad's decision 2026-08-19; HR back-fills real values later.

Run: bench --site <site> execute hrms.one_off_import_batch2.run \
        --kwargs "{'data_file': '/path/to/employees_batch2.json'}"
Idempotent: safe to re-run.
"""

import json

import frappe

DATA_FILE = "/workspace/.employee_import/employees_batch2.json"  # default: local docker dev
COMPANY = "Clustox"
ABBR = "CTX"
PLACEHOLDER_DOB = "1900-01-01"
PLACEHOLDER_GENDER = "Prefer not to say"


def run(data_file=None):
    rows = json.load(open(data_file or DATA_FILE))
    log = {"created": [], "updated": [], "warnings": []}

    def upsert(doctype, name, values):
        if frappe.db.exists(doctype, name):
            return
        doc = frappe.new_doc(doctype)
        doc.update(values)
        if (doc.meta.autoname or "").lower() == "prompt":
            doc.name = name
        doc.insert(ignore_permissions=True)
        log["created"].append(f"{doctype}: {name}")

    # ------------------------------------------------------------ masters
    upsert("Gender", PLACEHOLDER_GENDER, {"gender": PLACEHOLDER_GENDER})

    for b in {r["Branch"] for r in rows if r["Branch"]}:
        upsert("Branch", b, {"branch": b})

    for d in {r["Designation"] for r in rows if r["Designation"]}:
        upsert("Designation", d, {"designation_name": d})

    if not frappe.db.exists("Department", "All Departments"):
        root = frappe.new_doc("Department")
        root.update({"department_name": "All Departments", "is_group": 1})
        root.flags.ignore_mandatory = True
        root.insert(ignore_permissions=True)
        log["created"].append("Department: All Departments (root)")

    dept_map = {}
    for dep in {r["Department"] for r in rows if r["Department"]}:
        full = f"{dep} - {ABBR}"
        if not frappe.db.exists("Department", full):
            frappe.get_doc({
                "doctype": "Department",
                "department_name": dep,
                "company": COMPANY,
                "parent_department": "All Departments",
            }).insert(ignore_permissions=True)
            log["created"].append(f"Department: {full}")
        dept_map[dep] = full

    # --------------------------------------------------------- employees
    def split_name(full):
        parts = full.split()
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        middle = " ".join(parts[1:-1])
        return first, middle, last

    for r in rows:
        org_fields = {
            "branch": r["Branch"],
            "department": dept_map.get(r["Department"]),
            "designation": r["Designation"],
            "date_of_joining": r["Date Of Joining"],
        }
        existing = frappe.db.get_value("Employee", {"employee_number": r["Code"]})
        if existing:
            doc = frappe.get_doc("Employee", existing)
            doc.update(org_fields)
            doc.save(ignore_permissions=True)
            log["updated"].append(f"Employee: {r['Code']} {doc.employee_name}")
        else:
            first, middle, last = split_name(r["Name"])
            doc = frappe.new_doc("Employee")
            doc.update(org_fields)
            doc.update({
                "first_name": first, "middle_name": middle, "last_name": last,
                "company": COMPANY,
                "status": "Active",
                "gender": PLACEHOLDER_GENDER,        # placeholder — HR to correct
                "date_of_birth": PLACEHOLDER_DOB,    # placeholder — HR to correct
            })
            doc.employee_number = r["Code"]
            doc.insert(ignore_permissions=True)
            log["created"].append(f"Employee: {r['Code']} {doc.employee_name}")

    frappe.db.commit()

    print("\n========== IMPORT SUMMARY (batch 2) ==========")
    for k, items in log.items():
        print(f"\n{k.upper()} ({len(items)}):")
        for i in items:
            print("  ", i)
