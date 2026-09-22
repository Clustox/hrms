"""Helpdesk email-tag router.

Routes plus-addressed support email to the right HD Team, so the existing
per-team round-robin Assignment Rule then assigns an agent:

  support+it@       -> IT Team
  support+accounts@ -> Accounts Team
  support+admin@    -> Admin Team

Runs OUTSIDE the email-receive transaction (via the scheduler / cron), so it can
never block inbound email — unlike a Communication doc-event, which does. Reads
the recipient tag from the originating received email's Communication.

Registered as a scheduled job (hooks.py `scheduler_events['all']`). Also safe to
run by cron or manually:
    bench --site <site> execute hrms.helpdesk_router.route_tickets

Idempotent: only touches Open tickets that have no team yet.
"""

import frappe

ROUTES = {
    "it": "IT Team",
    "accounts": "Accounts Team",
    "admin": "Admin Team",
}


def route_tickets():
    # no-op on sites without Frappe Helpdesk installed
    if not frappe.db.exists("DocType", "HD Ticket"):
        return

    names = frappe.get_all(
        "HD Ticket",
        filters={"status": "Open", "agent_group": ["in", ["", None]]},
        pluck="name", limit=100,
    )
    for nm in names:
        try:
            comm = frappe.get_all(
                "Communication",
                filters={"reference_doctype": "HD Ticket", "reference_name": nm, "sent_or_received": "Received"},
                fields=["recipients", "cc"], order_by="creation asc", limit=1,
            )
            if not comm:
                continue
            blob = ((comm[0].recipients or "") + " " + (comm[0].cc or "")).lower()
            team = next((ROUTES[k] for k in ROUTES if ("support+" + k + "@") in blob), None)
            if team and frappe.db.exists("HD Team", team):
                tk = frappe.get_doc("HD Ticket", nm)
                if not tk.agent_group:
                    tk.agent_group = team
                    tk.save()
                    frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="helpdesk_router", message=frappe.get_traceback())
