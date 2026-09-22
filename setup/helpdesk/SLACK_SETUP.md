# Slack → Helpdesk (create tickets from `/ticket`)

Lets staff open a support ticket from Slack with a `/ticket` slash command and a
form (subject, description, team, priority). The chosen team feeds the existing
per-team round-robin, same as email routing. **Works on Slack's free plan** —
only a custom app is required, no paid features.

Code: `hrms/slack_helpdesk.py` (two secured endpoints). Requires a **public
HTTPS** site URL that Slack can reach.

## 1. Create the Slack app
1. https://api.slack.com/apps → **Create New App → From scratch** → pick your workspace.
2. **Slash Commands → Create New Command**
   - Command: `/ticket`
   - Request URL: `https://<your-site>/api/method/hrms.slack_helpdesk.slack_command`
   - Short description: `Create a support ticket`
3. **Interactivity & Shortcuts → Interactivity: On**
   - Request URL: `https://<your-site>/api/method/hrms.slack_helpdesk.slack_interact`
4. **OAuth & Permissions → Bot Token Scopes**, add: `commands`, `users:read`,
   `users:read.email`, `chat:write`.
5. **Install App to Workspace** → copy the **Bot User OAuth Token** (`xoxb-…`).
6. **Basic Information → App Credentials** → copy the **Signing Secret**.

## 2. Configure Frappe (secrets go in site config, never in code)
```bash
bench --site <site> set-config slack_signing_secret '<signing secret>'
bench --site <site> set-config slack_bot_token 'xoxb-...'
```

## 3. Deploy
The module ships with the app. After pulling the fork:
```bash
bench --site <site> clear-cache && bench --site <site> reload-doctype "HD Ticket"
```
(A full `bench migrate` + restart also picks it up.) No scheduler needed — these
are on-demand HTTP endpoints.

## 4. Test
In Slack type `/ticket` → fill the form → submit. You should get a DM like
"🎫 Ticket #0042 created for IT Team — we're on it", and the ticket appears in
Helpdesk on the chosen team, auto-assigned by that team's rotation.

## Security notes
- Every request is rejected unless it carries a valid Slack signature (HMAC of
  the raw body with the signing secret) and a fresh timestamp (≤5 min) — this
  is why the endpoints are `allow_guest` yet safe.
- The reporter is matched to a Frappe contact by their Slack email
  (`users:read.email`); if unresolved, a `slack-<id>@clustox.com` placeholder is
  used so the ticket still creates.

## Roadmap (not in MVP)
- Route by Slack channel instead of a dropdown.
- Post the ticket link into the channel (not just a DM).
- Two-way sync: agent replies → Slack thread; status changes → notifications.

## Add / change teams
Edit `TEAMS` in `hrms/slack_helpdesk.py` (must match HD Team names) and redeploy.
