import frappe

def run(manager_code="CT-00006"):
    omer = frappe.db.get_value("Employee", {"employee_number": manager_code}, "name")
    if not omer:
        print("MANAGER NOT FOUND:", manager_code)
        return
    n = 0
    for e in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
        if e == omer:
            continue
        if frappe.db.get_value("Employee", e, "reports_to") != omer:
            frappe.db.set_value("Employee", e, "reports_to", omer)
            n += 1
    frappe.db.set_value("Employee", omer, "reports_to", "")
    frappe.db.commit()
    print("REPORTS_TO_START")
    print(f"set reports_to = {omer} for {n} employees (top of tree reports to nobody)")
    print("REPORTS_TO_END")
