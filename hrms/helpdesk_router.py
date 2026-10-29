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


def set_requester_from_contact(doc, method=None):
    """On-behalf tickets: when an agent picks a `contact`, point `raised_by` at
    that contact's email so the customer-facing emails -- the acknowledgement on
    creation and every agent reply -- reach the EMPLOYEE, not the agent who
    created the ticket (otherwise raised_by stays as the creating agent and the
    employee is never emailed). Also stamp the internal "Clustox" customer for
    @clustox.com requesters. Only sets fields on the doc being saved (no nested
    save), so it is safe inside the ticket transaction -- unlike routing."""
    contact = doc.get("contact")
    if not contact:
        return
    email = frappe.db.get_value("Contact", contact, "email_id")
    if not email:
        email = (frappe.db.get_value("Contact Email", {"parent": contact, "is_primary": 1}, "email_id")
                 or frappe.db.get_value("Contact Email", {"parent": contact}, "email_id"))
    if not email:
        return
    doc.raised_by = email
    if not doc.get("customer") and email.lower().endswith("@clustox.com") \
            and frappe.db.exists("HD Customer", "Clustox"):
        doc.customer = "Clustox"
