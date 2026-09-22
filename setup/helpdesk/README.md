# Clustox HR — Helpdesk (Frappe Helpdesk)

Configuration and the email-tag team router for the Clustox support desk.

## Email-tag routing (plus-addressing → team)

Support email arrives at a single inbox (`support@clustox.com`, an Email Account
with `append_to = HD Ticket`). Senders address a **plus-tag** and the ticket is
routed to the matching HD Team; the team's existing round-robin Assignment Rule
then assigns an agent:

| Send to | HD Team |
|---|---|
| `support+it@clustox.com` | IT Team |
| `support+accounts@clustox.com` | Accounts Team |
| `support+admin@clustox.com` | Admin Team |

Google Workspace delivers all `support+<tag>@` mail to the `support@` mailbox,
and Frappe stores the original `To`/`Cc` on the ticket's Communication — that's
where the router reads the tag.

### How it's implemented — and why this way

`hrms/helpdesk_router.py` → `route_tickets()` runs on a schedule, finds Open
tickets with no team, reads the recipient tag from the originating **received**
Communication, sets `agent_group`, and saves (which triggers the round-robin).

It is wired as a **scheduled job**, not a doc event:

- Registered via `hooks.py` `scheduler_events["all"]` → picked up by
  `bench migrate` and run by the scheduler like any built-in job. This is the
  durable, migrate-proof registration.
- **Do NOT** route from a `Communication`/`HD Ticket` doc event. Saving the
  ticket *inside* the email-receive transaction throws at `communication.insert`
  and breaks **all** inbound email. (We hit exactly this; the scheduled job runs
  safely outside that transaction.)
- Server-script *Scheduler Events* are **not** registered on this build — they
  never run. Use the Python function above.

To add a tag (e.g. `+hr → HR Team`): create the HD Team, add the pair to
`ROUTES` in `helpdesk_router.py`, redeploy.

### Registering the job on an existing site (no redeploy)

`bench migrate` auto-registers it from the hook. To register it immediately on a
running site without a migrate, create the Scheduled Job Type directly:

```bash
bench --site <site> execute frappe.client.insert --kwargs \
 "{'doc':{'doctype':'Scheduled Job Type','method':'hrms.helpdesk_router.route_tickets','frequency':'Cron','cron_format':'*/2 * * * *','stopped':0}}"
```

(A manually-created job type may be pruned by a later `bench migrate` — the hook
re-creates it, so they converge.)

## Other IT-review findings

- **First Response Time starts at ticket creation, while Unassigned** — this is
  correct SLA behaviour (it measures customer wait time). The default SLA
  `Clustox-Support-SLA` already limits it to business hours (Mon–Fri 10:00–18:00).
- **Duplicate tickets** — caused by `support@` being connected to **both** Frappe
  Helpdesk *and* Atlassian Jira Service Management, which bounced
  auto-acknowledgements at each other. Fix: one system of record — disconnect
  Jira from `support@`. Optional hardening: ignore mail from
  `support@clustox.atlassian.net` / `jira@clustox.atlassian.net`.
- **Ticket on behalf of a user** — supported natively (agent sets the contact;
  that user is notified by email).
- **Slack ticket creation** — not native; needs a small Slack → Helpdesk API
  integration.
