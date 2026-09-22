"""Fix post-login landing: route each user to the right app instead of forcing
everyone to /hrms via a global default.

Problem: System Settings `default_app` was set to "hrms" so ALL users (incl. HR
Manager / HR User) land in the /hrms self-service PWA and never reach the desk
HR dashboard. `default_app` is meant to be per-user.

Fix:
  * clear the GLOBAL System Settings default_app (so it stops overriding),
  * set each enabled user's `User.default_app` by cohort:
      - staff/desk roles      -> "erpnext"  (desk, /desk/home)
      - pure self-service emp -> "hrms"     (/hrms PWA)
      - pure helpdesk agent   -> "helpdesk" (/helpdesk)

Employees still enter via https://<site>/hrms/login regardless; this only fixes
where the generic /login and app-switcher send each cohort.

Idempotent. Run: bench --site <site> execute hrms.set_app_landing.run
"""

import frappe

STAFF_DESK_ROLES = {
    "System Manager", "HR User", "HR Manager", "Accounts Manager",
    "Accounts User", "IT User", "CEO/COO", "Department Head", "Team Lead",
}
AGENT_ROLES = {"Agent", "Agent Manager"}
ESS_ROLE = "Employee Self Service"

SKIP_USERS = {"Administrator", "Guest"}


def target_app(roles):
    if roles & STAFF_DESK_ROLES:
        return "erpnext"
    if ESS_ROLE in roles or "Employee" in roles:
        # Employees route to /hrms via role_home_page (bare /login) and
        # /hrms/login. default_app is CLEARED so it never points them at the
        # desk (get_route('hrms') == app_home == /desk/hr-setup).
        return ""
    if roles & AGENT_ROLES:
        return "helpdesk"
    return None  # leave untouched


def _probe(email):
    if not email or not frappe.db.exists("User", email):
        return
    frappe.set_user(email)
    try:
        from frappe.apps import get_default_path
        path = get_default_path()
    except Exception as e:
        path = f"err {e!r}"[:80]
    frappe.set_user("Administrator")
    da = frappe.db.get_value("User", email, "default_app")
    print(f"    {email:34} default_app={da!r:12} -> get_default_path()={path}")


def _pick(role):
    for u in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"):
        if u not in SKIP_USERS and frappe.db.get_value("User", u, "enabled"):
            return u
    return None


def run():
    print("SETLANDING_START")

    # 1) stop the global override
    frappe.db.set_single_value("System Settings", "default_app", "")

    # 2) per-user routing
    users = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name")
    counts = {"erpnext": 0, "cleared(employee)": 0, "helpdesk": 0, "unchanged": 0}
    for u in users:
        if u in SKIP_USERS:
            continue
        roles = set(frappe.get_roles(u))
        want = target_app(roles)
        if want is None:
            counts["unchanged"] += 1
            continue
        if frappe.db.get_value("User", u, "default_app") != want:
            frappe.db.set_value("User", u, "default_app", want)
        counts["cleared(employee)" if want == "" else want] += 1

    frappe.clear_cache()
    frappe.db.commit()

    print(f"global System Settings default_app -> '' (cleared)")
    print(f"routed: desk(erpnext)={counts['erpnext']}  employee(cleared->/hrms via role_home_page)"
          f"={counts['cleared(employee)']}  helpdesk={counts['helpdesk']}  "
          f"unchanged={counts['unchanged']}")

    print("\n=== VERIFY get_default_path() after fix ===")
    _probe(_pick("HR Manager"))
    _probe(_pick("HR User"))
    _probe("testemp@clustox.com")
    print("SETLANDING_END")
