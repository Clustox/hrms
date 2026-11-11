# ATS admin guide

The ATS is built on the Frappe HRMS Recruitment module. Everything is in Desk. This guide is for the people who set it up and look after it.

## 1. What you get

| Area | Where |
|---|---|
| Jobs, each with its own stages and counters | Recruitment, Job Opening |
| Candidates across jobs (duplicates found by email and phone) | Recruitment, Candidate |
| One Kanban board per job | Job Opening, **Pipeline Board** button, or Job Applicant, Kanban |
| Applications with stage, history, drop reason | Recruitment, Job Applicant |
| Interviews with calendar event, Meet link, candidate's answer | Recruitment, Interview |
| Email to candidates (single, bulk, automatic on a stage) | Job Applicant, Send Email |
| Guests (outside interviewers) with per-job access | Desk, Job Guest Access list |
| Alerts for stage moves, new candidates, notes, interview changes | The bell in Desk |
| Import from the old system | Job Applicant list, Menu, Import from old ATS (CSV) |

## 2. Roles

| Role | Can do |
|---|---|
| System Manager, HR Manager | Everything, including pipeline templates, guests, import |
| HR User, ATS Recruiter | Work the pipeline: jobs, applicants, candidates, interviews, email |
| ATS Guest | An interviewer from outside HR. Sees only the jobs shared with them, only the stages marked visible to guests, no counters, no salary unless allowed. Can move candidates only if their access says so |
| ATS Salary Viewer | Sees salary fields. Given to a guest only when the share allows it |

Guests get their roles automatically when a job is shared with them and lose them when the last share is revoked or expires. A guest's Desk menu is the recruitment screens and nothing else.

## 3. After every deployment

1. Back up: `bench --site <site> backup --with-files`
2. Update the code and run `bench --site <site> migrate`. It is safe to repeat. It creates the custom fields, roles, standard email templates, the 8 drop reasons, the default pipeline template and the sidebar entries.
3. `bench build --app hrms` and `bench restart`.
4. Make sure the scheduler is on: `bench --site <site> enable-scheduler`. Queued emails, the hourly calendar-answer check and the daily guest-expiry check all depend on it.
5. Smoke test: open a job, move a candidate, send an email, schedule an interview.

## 4. Pipelines

* The standard pipeline is the 15 stages of the default template (Recruitment, Pipeline Template). Changing a template does not change jobs that already copied it.
* Each job has its own stage table (Job Opening, Pipeline). Stages have a type (Active, Hired, Rejected), a status they map to, a "visible to guests" flag, required fields before a candidate may enter, and an optional email template sent automatically on entry.
* A stage with candidates in it cannot be deleted. Renaming a stage renames it on the candidates.
* Dropping a candidate needs a reason (Recruitment, Drop Reason). Dropped candidates keep their stage and can be restored.
* Counters on the job (Hired, In pipeline, Dropped, Headcount as "positions - filled") update on every move.

## 5. Google setup (once)

You do this in your own browser. Nobody else needs your Google password, and the client secret must never be sent in chat or email.

### 5.1 Google Cloud

1. Create a project (for example `Clustox-ATS`). Do not reuse a project that belongs to another product.
2. Enable the **Google Calendar API** and the **Gmail API**.
3. Google Auth Platform: set up the consent screen. Choose **Internal** for a Workspace organisation. For External, add each recruiter under Test users.
4. Clients, Create client, Web application. Authorized redirect URIs (replace the base with the site address; Google requires HTTPS on a real domain, `http://localhost:8000` works only for local testing):
   * `<site>?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback`
   * `<site>/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<connected app name>` (shown on the Connected App after you save it)
5. Keep the client ID and secret. Google shows the secret once. To rotate it, add a new secret, update Frappe, then disable the old one.

The site's `host_name` (site_config.json) must be the address people really use, because Frappe builds the redirect URIs from it.

### 5.2 Calendar (per recruiter)

1. Desk, Google Settings: tick Enable, paste the client ID and secret.
2. Desk, Google Calendar, New: your user, tick Enable and **Push to Google Calendar**, save. Leave "Sync events from Google as public" **off**.
3. Click **Authorize Google Calendar Access** and accept.
4. Click Sync once so Frappe creates its calendar, then set **Google Calendar ID** to `primary` and untick **Pull from Google Calendar**.
   * Why `primary`: Google does not report guests' answers back for events made in a secondary calendar.
   * Why untick Pull: otherwise every personal event in that calendar is copied into Frappe.

From then on every interview gets an event in that calendar with a Meet link, and the invitation goes to the interviewers and the candidate.

### 5.3 Email (per recruiter)

1. Desk, Connected App, New: Provider Name `Google Mail`, the client ID and secret, Authorization URI `https://accounts.google.com/o/oauth2/v2/auth`, Token URI `https://oauth2.googleapis.com/token`, Revocation URI `https://oauth2.googleapis.com/revoke`, scope `https://mail.google.com/`, query parameters `access_type=offline` and `prompt=consent`. Save. Copy its Redirect URI into the Google client (5.1 step 4).
2. Email Account, New: your address, Service GMail, Authentication OAuth, the Connected App, Connected User = your Frappe user, tick **Enable Outgoing**. Save, then Authorize API Access.

Mail to candidates is then sent from the recruiter's own address and recorded on the candidate. A recruiter without a connected account sends from the hiring sender address in HR Settings.

## 6. Email to candidates

* Four standard templates are created: ATS Acknowledgement, ATS Interview Invitation, ATS Rejection, ATS Offer. Edit them in Desk, Email Template. A migration never overwrites an edited template.
* Merge fields: `candidate_name`, `job_name`, `company`, `stage_name`, `recruiter_name`, and for an interview `interview_date`, `interview_time`, `interview_type`, `meet_link`. Any Job Applicant field also works.
* Single email: Job Applicant, Pipeline, Send Email. Bulk: select candidates in the list, Actions, Send Email (at most 100 at a time; each person gets their own message).
* Automatic: set the template on a stage; it is sent when a candidate enters the stage.

## 7. Interviews and the calendar

* Scheduling creates the event; rescheduling moves it; cancelling or discarding removes it and Google sends the cancellation.
* A reschedule made in Google Calendar by the organiser moves the interview too.
* The candidate's answer (Yes, No, Maybe) is read every hour and shown on the interview as Candidate Response.
* When an interviewer is already busy (another interview, or something Frappe's own Google sync pulled for them) a warning shows on save. It does not block.

## 8. Guests

Desk, Job Guest Access list, New (one record per user and job). Pick the user, the jobs, whether they may move candidates and whether they may see salary, and an optional expiry date. Revoking takes effect at once. Everything a guest does is logged in ATS Activity.

## 9. Alerts

The job owner and the job team get a bell alert when a candidate moves stage, a new candidate applies, someone adds a note, or an interview is scheduled, moved or cancelled. The person who did the thing is not alerted. Alerts are in-app only.

## 10. Importing from the old system

Job Applicant list, Menu, **Import from old ATS (CSV)**. One row per application.

| Column | Notes |
|---|---|
| job_title | Required. Matched by exact title; a new title creates the job with the default pipeline |
| name, email | Required |
| phone, source, cover_letter, resume_url | Optional |
| stage | One of the job's stages (any capitalisation). Blank means the first stage |
| applied_on | YYYY-MM-DD |
| legacy_id | The old system's id. Makes the import repeatable |
| dropped_reason | A Drop Reason. Puts the candidate in the dropped state |
| department, designation, positions | Used when the job has to be created |

Always run the dry run first. It checks every row and then undoes all its work, and shows the problems by row number. Rows with problems are skipped. A row whose legacy_id, or whose email for the same job, is already in the system is skipped, so the same file can be loaded again safely. At most 2,000 rows per file. Nobody is alerted and no stage email is sent while importing.

Resumes are linked (resume_url), not copied. Attach the files to the candidates afterwards if search by resume text is needed.

## 11. Backup and restore

* Back up: `bench --site <site> backup --with-files` (database and files).
* Restore to a new or existing site: `bench --site <site> restore <database.sql.gz> --with-public-files <files.tar> --with-private-files <private-files.tar>`, then `bench --site <site> migrate`.
* After restoring to another address, check `host_name` and reconnect Google (tokens are tied to the redirect URIs).
* Test a restore on a scratch site before you need it.

## 12. When something goes wrong

| Symptom | Cause and fix |
|---|---|
| Google says `redirect_uri_mismatch` | The address Frappe sends is not in the Google client, character for character. Check `host_name`, the port, the `?cmd=` form for the calendar and the Connected App form for mail |
| Event is created but has no Meet link or no guests | The Google Calendar record is not authorized, or Push to Google Calendar is off |
| Candidate answered but the interview shows nothing | Calendar ID is not `primary`, or the scheduler is off. Check Error Log for "ATS RSVP poll failed" |
| Emails stay "Not Sent" | Scheduler is off or no outgoing account. Check Email Queue and Error Log |
| Mail goes out from the wrong address | The recruiter has no Email Account with themselves as Connected User |
| A guest sees nothing | The grant expired or was revoked, or the candidate is in a stage not marked visible to guests |
| Migrate prints an error from another app | The ATS hooks run first and commit; fix the other app's error separately |
