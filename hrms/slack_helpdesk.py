"""Slack -> Frappe Helpdesk: create HD Tickets from a /ticket slash command.

Flow:
  /ticket  --> slack_command()  verifies Slack signature, opens a modal
  modal submit --> slack_interact()  verifies signature, creates the HD Ticket
                   (with the chosen team), DMs the reporter the ticket number.

The chosen team feeds the existing per-team round-robin, same as email routing.

Config (site_config.json, NOT in code):
  slack_signing_secret : from the Slack app "Basic Information"
  slack_bot_token      : xoxb-... bot token (scopes: commands, users:read,
                         users:read.email, chat:write)

Slack app URLs both point here:
  Slash command Request URL : /api/method/hrms.slack_helpdesk.slack_command
  Interactivity Request URL : /api/method/hrms.slack_helpdesk.slack_interact
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

import frappe
import requests

SLACK_API = "https://slack.com/api"
TEAMS = ["IT Team", "Accounts Team", "Admin Team"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]


# --------------------------------------------------------------- helpers
def _conf(key):
    val = frappe.conf.get(key)
    if not val:
        frappe.throw(f"Missing site config: {key}")
    return val


def _verify_slack():
    """Reject anything not signed by Slack (prevents spoofing)."""
    ts = frappe.get_request_header("X-Slack-Request-Timestamp") or ""
    sig = frappe.get_request_header("X-Slack-Signature") or ""
    if not ts or not sig or abs(time.time() - int(ts)) > 300:
        frappe.throw("Invalid Slack request", frappe.PermissionError)
    body = frappe.request.get_data(as_text=True)
    base = f"v0:{ts}:{body}".encode()
    mine = "v0=" + hmac.new(_conf("slack_signing_secret").encode(), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mine, sig):
        frappe.throw("Bad Slack signature", frappe.PermissionError)
    return body


def _slack_post(method, payload):
    return requests.post(
        f"{SLACK_API}/{method}",
        headers={"Authorization": f"Bearer {_conf('slack_bot_token')}",
                 "Content-Type": "application/json; charset=utf-8"},
        json=payload, timeout=8,
    )


def _slack_email(user_id):
    try:
        r = requests.get(
            f"{SLACK_API}/users.info",
            headers={"Authorization": f"Bearer {_conf('slack_bot_token')}"},
            params={"user": user_id}, timeout=8,
        ).json()
        return (r.get("user", {}).get("profile", {}) or {}).get("email")
    except Exception:
        return None


def _select(options):
    return [{"text": {"type": "plain_text", "text": o}, "value": o} for o in options]


def _modal():
    return {
        "type": "modal",
        "callback_id": "hd_new_ticket",
        "title": {"type": "plain_text", "text": "New Support Ticket"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {"type": "input", "block_id": "subject_b",
             "label": {"type": "plain_text", "text": "Subject"},
             "element": {"type": "plain_text_input", "action_id": "subject"}},
            {"type": "input", "block_id": "desc_b",
             "label": {"type": "plain_text", "text": "Description"},
             "element": {"type": "plain_text_input", "action_id": "desc", "multiline": True}},
            {"type": "input", "block_id": "team_b",
             "label": {"type": "plain_text", "text": "Team"},
             "element": {"type": "static_select", "action_id": "team",
                         "options": _select(TEAMS)}},
            {"type": "input", "block_id": "prio_b", "optional": True,
             "label": {"type": "plain_text", "text": "Priority"},
             "element": {"type": "static_select", "action_id": "prio",
                         "initial_option": _select(["Medium"])[0],
                         "options": _select(PRIORITIES)}},
        ],
    }


# --------------------------------------------------------------- endpoints
@frappe.whitelist(allow_guest=True)
def slack_command():
    body = _verify_slack()
    data = parse_qs(body)
    trigger_id = data.get("trigger_id", [""])[0]
    _slack_post("views.open", {"trigger_id": trigger_id, "view": _modal()})
    return ""  # 200; the modal is shown via views.open


@frappe.whitelist(allow_guest=True)
def slack_interact():
    body = _verify_slack()
    payload = json.loads(parse_qs(body).get("payload", ["{}"])[0])
    if payload.get("type") == "view_submission":
        vals = payload["view"]["state"]["values"]
        prio_opt = vals.get("prio_b", {}).get("prio", {}).get("selected_option")
        args = {
            "subject": vals["subject_b"]["subject"]["value"],
            "desc": vals["desc_b"]["desc"]["value"],
            "team": vals["team_b"]["team"]["selected_option"]["value"],
            "priority": prio_opt["value"] if prio_opt else "Medium",
            "slack_uid": payload["user"]["id"],
        }
        # Create the ticket in the background so we ACK Slack within its 3s limit.
        frappe.enqueue("hrms.slack_helpdesk._create_ticket", queue="short", **args)

    # Close the modal. Slack needs `response_action` at the JSON top level; a plain
    # return would be wrapped by Frappe as {"message": ...}, which Slack rejects
    # (it posts that as a message and leaves the modal open). Setting it on
    # frappe.local.response puts it at the top level. Return None so Frappe does
    # not also add a "message" key.
    frappe.local.response["response_action"] = "clear"
    return None


def _create_ticket(subject, desc, team, priority, slack_uid):
    """Runs in a background worker (no 3s limit)."""
    try:
        email = _slack_email(slack_uid) or f"slack-{slack_uid}@clustox.com"
        doc = {
            "doctype": "HD Ticket",
            "subject": subject,
            "description": desc or subject,
            "priority": priority if priority in PRIORITIES else "Medium",
            "raised_by": email,
        }
        if team in TEAMS and frappe.db.exists("HD Team", team):
            doc["agent_group"] = team
        tk = frappe.get_doc(doc)
        tk.insert(ignore_permissions=True)
        frappe.db.commit()
        _slack_post("chat.postMessage", {
            "channel": slack_uid,
            "text": f":ticket: Ticket *{tk.name}* created for *{team}* — we're on it.",
        })
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="slack_helpdesk create", message=frappe.get_traceback())
        try:
            _slack_post("chat.postMessage", {
                "channel": slack_uid,
                "text": ":warning: Sorry, I couldn't create that ticket — support has been notified.",
            })
        except Exception:
            pass
