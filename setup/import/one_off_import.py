"""One-off employee data import (temp file — remove after use).

Run: bench --site <site> execute hrms.one_off_import.run \
        --kwargs "{'data_file': '/path/to/employees.json'}"
Idempotent: safe to re-run; existing records are updated, not duplicated.
"""

import json

import frappe

DATA_FILE = "/workspace/.employee_import/employees.json"  # default: local docker dev
COMPANY = "Clustox"
ABBR = "CTX"
SALARY_STRUCTURE = "Clustox Standard"


def run(data_file=None):
    rows = json.load(open(data_file or DATA_FILE))
    log = {"created": [], "updated": [], "skipped_salary": [], "warnings": []}

    def upsert(doctype, name, values, submit=False):
        if frappe.db.exists(doctype, name):
            return frappe.get_doc(doctype, name)
        doc = frappe.new_doc(doctype)
        doc.update(values)
        if (doc.meta.autoname or "").lower() == "prompt":
            doc.name = name
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        log["created"].append(f"{doctype}: {name}")
        return doc

    # ------------------------------------------------------------ masters
    frappe.db.set_value("Currency", "PKR", "enabled", 1)

    if not frappe.db.exists("Company", COMPANY):
        frappe.get_doc({
            "doctype": "Company",
            "company_name": COMPANY,
            "abbr": ABBR,
            "default_currency": "PKR",
            "country": "Pakistan",
            "create_chart_of_accounts_based_on": "Standard Template",
            "chart_of_accounts": "Standard",
        }).insert(ignore_permissions=True)
        log["created"].append(f"Company: {COMPANY}")

    for g in {"Male", "Female"}:
        upsert("Gender", g, {"gender": g})

    for s in {r["Salutation"] for r in rows if r["Salutation"]}:
        upsert("Salutation", s, {"salutation": s})

    # per decision: employment_type comes from the "Job Title" column
    for et in {r["Job Title"] for r in rows if r["Job Title"]}:
        upsert("Employment Type", et, {"employee_type_name": et})

    for b in {r["Branch"] for r in rows if r["Branch"]}:
        upsert("Branch", b, {"branch": b})

    for d in {r["Designation"] for r in rows if r["Designation"]}:
        upsert("Designation", d, {"designation_name": d})

    for g in {r["Grade"] for r in rows if r["Grade"]}:
        upsert("Employee Grade", g, {})

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

    # ------------------------------------------------------ custom fields
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Employee": [
            dict(fieldname="custom_cnic_no", label="CNIC No", fieldtype="Data",
                 insert_after="passport_number"),
            dict(fieldname="custom_cnic_expiry_date", label="CNIC Expiry Date",
                 fieldtype="Date", insert_after="custom_cnic_no"),
            dict(fieldname="custom_father_or_husband_name", label="Father/Husband Name",
                 fieldtype="Data", insert_after="custom_cnic_expiry_date"),
            dict(fieldname="custom_religion", label="Religion", fieldtype="Data",
                 insert_after="custom_father_or_husband_name"),
            dict(fieldname="custom_nationality", label="Nationality", fieldtype="Data",
                 insert_after="custom_religion"),
        ]
    }, ignore_validate=True)

    # --------------------------------------------------------- employees
    def split_name(full):
        parts = full.split()
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        middle = " ".join(parts[1:-1])
        return first, middle, last

    def upsert_employee(code, fields):
        existing = frappe.db.get_value("Employee", {"employee_number": code})
        if existing:
            doc = frappe.get_doc("Employee", existing)
            doc.update(fields)
            doc.save(ignore_permissions=True)
            log["updated"].append(f"Employee: {code} {doc.employee_name}")
        else:
            doc = frappe.new_doc("Employee")
            doc.update(fields)
            doc.employee_number = code
            doc.insert(ignore_permissions=True)
            log["created"].append(f"Employee: {code} {doc.employee_name}")
        return doc

    # If the sheet references a line manager (via Line Manager Code) who has no
    # row of their own, create a minimal stub here so reports_to can resolve,
    # e.g.:
    #   upsert_employee("CT-00000", {
    #       "first_name": "First", "last_name": "Last",
    #       "company": COMPANY, "status": "Active", "gender": "Male",
    #       "date_of_birth": "1980-01-01",    # placeholder
    #       "date_of_joining": "2021-01-01",  # placeholder
    #   })

    for r in rows:
        first, middle, last = split_name(r["Name"])
        upsert_employee(r["Code"], {
            "salutation": r["Salutation"],
            "first_name": first, "middle_name": middle, "last_name": last,
            "company": COMPANY,
            "status": "Active",
            "gender": r["Gender"],
            "date_of_birth": r["D O B"],
            "date_of_joining": r["Joining Date"],
            "cell_number": r["Mobile No"],
            "marital_status": r["Marital Status"],
            "blood_group": r["Blood Group"],
            "personal_email": r["Email"],
            "company_email": r["Official Email"],
            "prefered_contact_email": "Company Email",
            "scheduled_confirmation_date": r["DOC"],
            "final_confirmation_date": r["Confirmation Date"],
            "contract_end_date": r["Contract Expiry Date"],
            "branch": r["Branch"],
            "department": dept_map.get(r["Department"]),
            "designation": r["Designation"],
            "grade": r["Grade"],
            "employment_type": r["Job Title"],
            "salary_mode": "Bank" if r["Bank Name"] else None,
            "bank_name": (r["Bank Name"] or "").strip() or None,
            "bank_ac_no": r["Bank Account No"],
            "permanent_address": r["Permanent Address"],
            "current_address": r["Present Address"],
            "custom_cnic_no": r["CNIC No"],
            "custom_cnic_expiry_date": r["CNIC Expiry Date"],
            "custom_father_or_husband_name": r["Father Or Husband Name"],
            "custom_religion": r["Religion"],
            "custom_nationality": r["Nationality"],
        })

    # -------------------------------------------- reports_to (second pass)
    for r in rows:
        mgr_code = r["Line Manager Code"]
        if not mgr_code:
            continue
        mgr = frappe.db.get_value("Employee", {"employee_number": mgr_code})
        emp = frappe.db.get_value("Employee", {"employee_number": r["Code"]})
        if mgr and emp:
            frappe.db.set_value("Employee", emp, "reports_to", mgr)
        else:
            log["warnings"].append(f"could not link manager {mgr_code} for {r['Code']}")

    # ------------------------------------------------------------ payroll
    # fiscal years (July–June, Pakistan) covering all joining dates.
    # tolerant: a site set up via the wizard may already have overlapping years
    # under different names — skip with a warning instead of aborting.
    for start_year in range(2021, 2027):
        fy_name = f"{start_year}-{str(start_year + 1)[-2:]}"
        if frappe.db.exists("Fiscal Year", {"year_start_date": f"{start_year}-07-01"}):
            continue
        try:
            upsert("Fiscal Year", fy_name, {
                "year": fy_name,
                "year_start_date": f"{start_year}-07-01",
                "year_end_date": f"{start_year + 1}-06-30",
            })
        except Exception as e:
            log["warnings"].append(f"Fiscal Year {fy_name} not created: {e}")

    upsert("Salary Component", "Basic", {
        "salary_component": "Basic", "salary_component_abbr": "B", "type": "Earning",
    })

    if not frappe.db.exists("Salary Structure", SALARY_STRUCTURE):
        ss = frappe.new_doc("Salary Structure")
        ss.name = SALARY_STRUCTURE
        ss.update({
            "company": COMPANY,
            "payroll_frequency": "Monthly",
            "currency": "PKR",
            "is_active": "Yes",
        })
        ss.append("earnings", {
            "salary_component": "Basic",
            "amount_based_on_formula": 1,
            "formula": "base",
        })
        ss.insert(ignore_permissions=True)
        ss.submit()
        log["created"].append(f"Salary Structure: {SALARY_STRUCTURE}")

    for r in rows:
        if not r["Gross Salary"]:
            log["skipped_salary"].append(f"{r['Code']} {r['Name']} (no Gross Salary in sheet)")
            continue
        emp = frappe.db.get_value("Employee", {"employee_number": r["Code"]})
        if frappe.db.exists("Salary Structure Assignment",
                            {"employee": emp, "salary_structure": SALARY_STRUCTURE, "docstatus": 1}):
            continue
        ssa = frappe.new_doc("Salary Structure Assignment")
        ssa.update({
            "employee": emp,
            "salary_structure": SALARY_STRUCTURE,
            "from_date": r["Joining Date"],
            "base": r["Gross Salary"],
            "company": COMPANY,
            "currency": "PKR",
        })
        ssa.insert(ignore_permissions=True)
        ssa.submit()
        log["created"].append(f"Salary Structure Assignment: {r['Code']} base={r['Gross Salary']}")

    frappe.db.commit()

    print("\n========== IMPORT SUMMARY ==========")
    for k, items in log.items():
        print(f"\n{k.upper()} ({len(items)}):")
        for i in items:
            print("  ", i)
