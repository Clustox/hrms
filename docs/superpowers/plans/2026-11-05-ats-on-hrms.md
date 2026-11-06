# ATS on the existing HRMS — Implementation Plan

Source: `ATS Requirements Document (2).docx` (Draft v1.0, 7 screenshots/diagrams reviewed).
Target: this repo (Frappe HRMS `17.0.0-dev` on ERPNext). **No new system** — we extend the Recruitment module that already ships here.

---

## 1. What we already have vs. what is missing

| ATS requirement | Existing in HRMS | Verdict |
|---|---|---|
| Departments (owner, team, industry, location, status, job count) | ERPNext `Department` (+ custom fields hook in `hrms/setup.py:159`) | **Extend** — add 4–5 custom fields, computed job count |
| Jobs (title, dept, location, vacancies, salary range, status, owner, team, tags) | `Job Opening` (job_title, department, location→Branch, vacancies, lower/upper_range, status Open/Closed, publish) | **Extend** — add owner, team table, salary_negotiable, pipeline, cached counters |
| Customizable per-job pipeline + templates | None (`Job Applicant.status` is a fixed 6-value Select) | **New** |
| Kanban board w/ drag & drop | Frappe Desk Kanban only supports a fixed Select → cannot be per-job | **New** (custom Vue board) |
| Candidate in many jobs, each with own stage | `Job Applicant` has ONE `job_title` link (one row = one person × one job) | **New `Candidate` master**; keep `Job Applicant` as the *application* row |
| Duplicate detection (email/phone) | `Job Opening.prevent_duplicate_applicant` (per job only) | **Extend** (global, on `Candidate`) |
| Interviews + feedback | `Interview`, `Interview Feedback`, `Interviewer` role, reminders scheduler | **Reuse + extend** (Google event fields) |
| Offers | `Job Offer` | **Reuse** (hook into stage mover) |
| Email templates, timeline | `Email Template`, `Communication`, `Comment`, `File` | **Reuse** |
| Guest/interviewer restricted access | Only role perms; precedent for record-level rules in `hrms/request_visibility.py` | **New** (same pattern) |
| Gmail / Calendar OAuth, two-way sync | Frappe core has Email Account OAuth + Google Calendar (Event sync) but nothing ATS-aware | **New thin layer** (after spike) |
| Public career page, reports, sourcing, AI | `hrms/www/jobs`, `recruitment_analytics` exist | **Out of scope** (per doc) — don't break them |

**Key constraint:** `Job Applicant` is referenced by Interview, Job Offer, Employee Onboarding, Employee Referral, Appointment Letter, `www/jobs`, and `recruitment_analytics`. Therefore it stays as the application record; everything new hangs off it. Every schema change below must be followed by a sweep of those consumers + tests.

---

## 2. Architecture decisions

1. **Data layer = Frappe DocTypes inside `hrms/hr/doctype/`** (new `ats_*` doctypes) + custom fields via `get_custom_fields()` in `hrms/setup.py` (existing convention). Admin CRUD (departments, templates, drop reasons, email templates) comes free in Desk.
2. **UI = new Vue 3 SPA `ats/`** mirroring the existing `roster/` app (frappe-ui + Tailwind + vite; routed through `website_route_rules` as `/ats/<path>` → `www/ats.html`). Reasons: board needs per-job columns, drag & drop, virtual scrolling; guests must never touch Desk; the mobile PWA (`frontend/`) is employee self-service and the wrong place.
3. **Single write path for stage changes**: `hrms/ats/pipeline.py::move_applicant(applicant, to_stage, user, reason=None)`. Board drag, Interview submit, Job Offer accept/decline, bulk move, and API all call it. It writes the log, updates counters, syncs `Job Applicant.status`, fires email/interview triggers, publishes realtime.
4. **Permissions enforced server-side in Frappe's hooks** (`permission_query_conditions` + `has_permission`, plus `permlevel` for salary) so `/api/resource`, reports, and our APIs are all covered. Never rely on UI hiding.
5. **Roles**: new `ATS Recruiter` and `ATS Guest`; Admin = `System Manager`/`HR Manager`. We do **not** reuse `HR User` for recruiters (it also exposes employee/leave/payroll data).
6. **Google**: OAuth tokens in Frappe's encrypted Connected App / Token Cache; custom client on `google-api-python-client` (already a Frappe dependency) — decided after Phase 0 spike.

---

## 3. Data model

### 3.1 New DocTypes
- **ATS Pipeline Template** (name) + child **ATS Template Stage**.
- **Job Pipeline Stage** — child table on `Job Opening` (stable row `name`, so renames never break links):
  `stage_name`, `idx` (order), `color`, `stage_type` (Active / Hired / Rejected), `visible_to_guests` (check), `auto_email_template` (Link Email Template), `require_fields` (JSON/Small Text), `require_reason` (check).
  Guard: cannot delete a stage that holds applicants unless they are migrated to another stage in the same action.
- **Candidate** — the person: `full_name`, `email` (unique, lower-cased), `phone` (normalized), `current_title`, `current_employer`, `source` (Link Job Applicant Source), `resume` (Attach), `resume_text` (Long Text, FULLTEXT index), `tags`. Duplicate check on email, then normalized phone.
- **Applicant Stage Log** — `job_applicant`, `job_opening`, `from_stage`, `to_stage`, `moved_by`, `moved_on`, `reason`, `trigger` (manual/interview/offer/bulk/import). Append-only (no edit/delete perms).
- **Drop Reason** — master list for dropped candidates.
- **Job Guest Access** — `user`, `job_opening`, `granted_by`, `granted_on`, `can_move_stages`, `can_view_salary`, `revoked_on`, optional `expires_on`.
- **ATS Activity** — guest/recruiter activity audit (login, view candidate, view resume, add feedback). Written from the API layer.
- **Interview Attendee** (child of `Interview`) — `email`, `role` (candidate/interviewer), `rsvp` (needsAction/accepted/declined/tentative).

### 3.2 Custom fields on existing doctypes
- **Department**: `industry`, `location`, `department_owner` (User), `department_team` (Table MultiSelect User). Status = reuse the existing `disabled` flag; "Job count" computed in the list API, not stored.
- **Job Opening**: `job_owner` (User), `job_team` (child: user + role recruiter/collaborator), `salary_negotiable` (check), `pipeline_template` (Link), `current_stage_label`, cached counters `applicants_count`, `hired_count`, `dropped_count`, `filled_count`. Salary fields (`lower_range`, `upper_range`) moved to **permlevel 1**.
- **Job Applicant**: `candidate` (Link), `pipeline_stage` (row name), `stage_entered_on`, `applied_on`, `is_dropped`, `drop_reason`, `dropped_at_stage`, `legacy_id`. Salary-expectation fields to permlevel 1. Index `(job_title, pipeline_stage, is_dropped)`.

### 3.3 Status mapping (don't break existing consumers)
Keep `Job Opening.status` as Open/Closed and `Job Applicant.status` as-is; the UI labels them Active/Completed. `move_applicant` derives `Job Applicant.status` from `stage_type` (Hired→Accepted, Rejected→Rejected, Active→Open/Shortlisted). Existing `Interview.update_job_applicant_status` and `Job Offer` code are re-pointed to `move_applicant` so there is one source of truth.

### 3.4 Counters (header: Hired / In pipeline / Dropped)
- **Hired** = applicants in `stage_type=Hired` stages.
- **Dropped** = `is_dropped=1` OR in `stage_type=Rejected` stage.
- **In pipeline** = everything else.
Cached on `Job Opening` and updated inside `move_applicant` (never `COUNT(*)` over 2,300 rows per list row).

---

## 4. Feature design

### 4.1 Departments screen (screenshot 1)
List API: name (coloured initials avatar), job count, industry, location, status badge, owner, team, created. Filters/sort/refresh, create/edit/deactivate/delete (delete blocked when jobs exist → deactivate). Click → department detail with its jobs.

### 4.2 Jobs list (screenshot 2)
List/Board toggle; columns per spec; server-side pagination (20 default, total count), sort, filters, refresh; inline status dropdown (permission-checked); row actions view + overflow; horizontal scroll with sticky first column. **Job Stage column** and **Headcount "565 - 1"** are ambiguous — see §9.

### 4.3 Job detail + pipeline board (screenshots 4–5, flow diagram 3)
- Header: title, Published / stage badges, owner chip, department, location, salary or "Negotiable", Hired / In pipeline / Dropped tiles, status dropdown, tags.
- Tabs: Candidates (count), Summary, Team, Activities, Notes, Interviews, Attachments. Later phases: Scorecards, Sourcing, Reports, AI.
- Board: one column per stage with count; cards show avatar/initials, name, current title @ employer, time since applied, time in stage, quick actions (view, attach, menu). **Per-column cursor pagination (≈30 cards, load-more on scroll)** — a column can hold thousands. Single grouped query for column counts. Drag & drop (SortableJS) → optimistic move → `move_applicant` → rollback on error. Realtime updates via `frappe.publish_realtime` to a per-job room. Left/right arrows for overflow, Filter control (owner, source, date, tag, text), per-column "N Dropped Candidates" drawer with reasons.
- Stage editor (admin/recruiter): add/rename/reorder/delete, colour, type, guest marker ("Visible to guests after this stage" is a boundary; stored as per-stage flag so rejected stages can be set independently), email-on-entry, required fields. Save as / load from template; templates are *copied* into the job, so later edits to a template never mutate live jobs.
- Drop: modal requires reason; candidate keeps stage, hidden from active column, shown in the dropped drawer; reversible ("restore") with log entry.

### 4.4 Candidates
Global list (search name/email/job/department via FULLTEXT + indexed columns; filters). Profile: contact, role, resume + attachments, source, tags, all applications with per-job stage, notes, timeline. Duplicate detection on create/import/public apply form (`www/jobs` must route through the same `Candidate` upsert). Resume upload → background job extracts text (`pypdf`/`docx2txt`) into `resume_text`; failure is non-fatal and logged.

### 4.5 Guests (diagram 6)
- Admin/job owner creates guest → Frappe `User` (user_type Website User, role `ATS Guest`, **no Desk**) + invite email with set-password link → grants `Job Guest Access` rows.
- Enforcement (all server-side):
  - `Job Opening` query/has_permission: guest sees only jobs with active (non-revoked, non-expired) access row.
  - `Job Applicant` / `Candidate` / `File` / `Comment` / `Communication` / `Interview`: guest sees only applicants whose current stage has `visible_to_guests=1` in a shared job (Candidate via its visible applications).
  - Salary: permlevel 1 → fields absent from guest payloads unless `can_view_salary`.
  - Guests can: view profile/resume, see interviews assigned to them, add notes and `Interview Feedback`. Cannot: create/delete jobs, move stages (unless `can_move_stages`), see other jobs/departments/candidate lists, settings.
  - Revocation = set `revoked_on`; takes effect on next request (no caching of grants). Optionally also disable user when last grant is revoked.
  - Audit: every guest API call writes `ATS Activity`.
- Guests are modelled as `Interviewer`s on `Interview` rows so the existing `Interview Feedback` doctype/flow is reused.

### 4.6 Gmail (diagram 7)
- Per-recruiter OAuth → `Email Account` (Gmail, OAuth) tied to the user; scopes `gmail.send`, `gmail.readonly` (+ `gmail.modify` only if we need labels/read state).
- Send from ATS via `frappe.sendmail(sender=<recruiter>, reference_doctype="Job Applicant", ...)` → lands in recruiter's Sent folder, `Communication` created → shows on candidate/job timeline.
- Replies: incoming sync matched by `In-Reply-To`/`References` to the sent `Communication` → attached to the applicant; unmatched mail ignored (not imported wholesale — privacy).
- `Email Template` with merge fields (`candidate_name`, `job_title`, `interview_time`, …); single + bulk send (bulk = per-recipient queued, per-recipient log, rate-limited to Gmail quotas).

### 4.7 Google Calendar
- Per-recruiter OAuth (`calendar.events`, `calendar.freebusy`).
- Schedule from ATS: `events.insert` with `conferenceData` (Meet), attendees = candidate + interviewers, `sendUpdates=all`. Store `google_event_id`, organizer, Meet link on `Interview`.
- Free/busy check for interviewers during scheduling (`freebusy.query`; interviewers outside the domain → "unknown").
- Two-way: `events.watch` webhook (needs public HTTPS endpoint) **plus** a 5–10-minute scheduler poll fallback using `syncToken`; updates `Interview Attendee.rsvp`, interview status, and time if rescheduled in Google.
- ATS reschedule/cancel → `events.patch/delete` → attendees notified. Existing `Interview` reminder scheduler is kept.

### 4.8 Notifications & audit
Realtime + `Notification Log` for: new candidate, stage change, new note, interview change. Activity feed per job/candidate merges `Applicant Stage Log`, `Comment`, `Communication`, `Interview`, `Version`.

---

## 5. Phased delivery

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 – Spikes (2–3 d)** | (a) Frappe core Gmail OAuth Email Account: send-as-user + reply threading works on this version. (b) Core Google Calendar vs custom client: attendees, Meet, RSVP, free/busy. (c) Confirm public HTTPS URL for webhooks & Google Workspace "Internal" OAuth app. (d) Resolve §9 questions with HR. | Written go/no-go on core vs custom Google layer |
| **1 – Foundation (≈1.5 wk)** | Custom fields, `Candidate`, pipeline doctypes, `move_applicant`, stage log, roles, permlevel, patches to backfill existing Job Applicants into a default pipeline + `Candidate` rows. SPA scaffold + routing + auth shell. | Existing recruitment flows (apply form, interview, offer, onboarding, analytics) still pass tests |
| **2 – Departments & Jobs (≈1 wk)** | Departments list/detail; Jobs list (list view), create/edit job, job detail header + tabs skeleton | Screens match screenshots 1–2 functionally |
| **3 – Pipeline board (≈2 wk)** | Board, DnD, stage editor, templates, drop/restore, counters, filter, realtime, per-column pagination | Smooth with 2,500+ candidates in one job; move is logged |
| **4 – Candidates (≈1 wk)** | Global list/search, profile, dedupe, resume text extraction, notes/timeline, attachments | Dedupe & search tested incl. edge cases |
| **5 – Guests (≈1.5 wk)** | Guest access doctype, invite flow, query/has_permission hooks, salary hiding, guest UI, audit, revocation | Full permission matrix test suite green (see §6) |
| **6 – Google (≈2.5 wk)** | Gmail OAuth/send/sync, templates, bulk send; Calendar schedule/RSVP/free-busy/reschedule/cancel, webhook + poll | End-to-end in a real Workspace test domain |
| **7 – Migration & hardening (≈1.5 wk)** | Clustox CSV/API import (idempotent via `legacy_id`), resume import, perf pass, backup/restore drill, docs | Dry-run import of 162 jobs reconciles counts exactly |

Roughly 11–12 weeks for one senior dev; Phases 2–4 can be parallelised with a second dev after Phase 1.

---

## 6. Testing (the default bar, not an extra step)

- **Permission matrix** (highest risk): for each role (Admin, Recruiter, Dept owner, Guest granted, Guest revoked, Guest expired, Guest on other job, anonymous) × each access path (`/api/resource`, `frappe.client.get_list`, report view, ATS APIs, file download URL, search, realtime channel) assert exact visibility. Includes: guest cannot see a candidate who moved *back* to a non-guest stage; guest cannot fetch salary via `fields=[...]`; guest cannot guess a `File` URL of a hidden resume.
- **Regression sweep** of every `Job Applicant`/`Job Opening` consumer listed in §1 after each schema change.
- **Pipeline edge cases**: delete stage with candidates, reorder during a concurrent move, move to deleted stage, double-drop, drop+restore, stage-type change with existing candidates (counters recomputed), template edit not mutating jobs, concurrent moves of the same card (row-lock/last-writer with conflict error), bulk move partial failure.
- **Duplicates**: case/whitespace in email, `+tag` addresses, phone formats (+92 / 03xx), same person applying to two jobs, import re-run idempotency.
- **Google**: token expiry/refresh, revoked consent, recruiter leaves company (tokens purged), attendee outside Workspace, DST/timezone (Asia/Karachi), recurring-event edits, webhook replay, quota errors.
- **Performance/stress**: seed 160 jobs and a 3,000-candidate job; budgets — jobs list < 500 ms, board first paint < 1 s, column page < 300 ms, move < 300 ms. Verify with query plans/indexes, not guesses.
- Frappe unit tests per doctype/API; Vue component tests for board/stage editor; one Playwright smoke per phase.

---

## 7. Security & non-functional

- OAuth tokens only in encrypted Password fields / Token Cache; never logged or returned to the client; purge on user disable.
- Resume files are **private** `File`s; downloads go through permission-checked URLs.
- TLS at the proxy, MariaDB at-rest encryption/volume encryption (infra task), PII access logged (`ATS Activity`).
- GDPR-style candidate deletion/anonymisation action on `Candidate`.
- Backups: use the existing bench backup + a documented, rehearsed restore (Phase 7).
- All customisations live in this app (custom fields via `setup.py`, patches under `hrms/patches`), so upgrades from upstream HRMS stay merge-safe; no core edits to ERPNext/Frappe.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| `Job Applicant` consumers break after the schema change | Additive-only fields; regression sweep; keep `status` semantics via mapping |
| Guest data leak through an overlooked API path | Hooks at the framework level + matrix tests; lint rule: no `frappe.get_all` in ATS guest-reachable code |
| Gmail restricted scopes require Google verification | Use Workspace **Internal** app (no verification); confirm in Phase 0 |
| Core Google sync insufficient for RSVP/free-busy | Phase 0 spike decides; budgeted custom client |
| Board slowness at thousands of cards | Per-column pagination, cached counters, indexes, no full-job fetch |
| Two writers changing status (Interview/Offer vs board) | Single `move_applicant` path |
| Webhooks unreachable in some environments | Polling fallback always on |

---

## 9. Open questions for HR (need answers before Phases 1–2)

1. **Headcount "565 - 1"**: the doc says "positions-filled (e.g. 3 – 1)" but the screenshot shows 565, 2557, 2351… which look like *applicant count – vacancies/filled*. Which is it?
2. **Job Stage column**: is it the stage of the most recently moved candidate, the furthest stage reached by anyone, or a job-level status set manually?
3. **Recruiter scope**: can a recruiter see all jobs, or only jobs where they are owner/team member (or in their department)?
4. **Guest visibility semantics**: visible if the candidate's *current* stage is flagged, or if they have *ever reached* a flagged stage (matters for later-rejected candidates)?
5. **Dropped vs Rejected stages**: screenshot shows both rejection *columns* and per-column "dropped" counts — confirm that Dropped = flagged-dropped + candidates in Rejected-type stages.
6. **Job status values**: is Active/Completed enough, or do we need Draft/On Hold/Cancelled?
7. **Email replies**: import only replies to ATS-sent threads (recommended) or the recruiter's entire inbox ("shared inbox view")?
8. Is the Google Workspace an **Internal** OAuth-eligible domain, and can we expose a public HTTPS webhook URL?
9. Data migration source: CSV export or API from Clustox? Are resumes downloadable in bulk?

---

## 10. Key file touchpoints

- `hrms/setup.py` — custom fields (Department, Job Opening, Job Applicant), roles
- `hrms/hooks.py` — `permission_query_conditions`, `has_permission`, `doc_events`, `scheduler_events`, `website_route_rules` (`/ats`) — remember the single-dict-per-doctype gotcha noted next to `doc_events["Leave Application"]`
- `hrms/hr/doctype/job_applicant/job_applicant.py`, `job_opening.py`, `interview.py`, `job_offer.py`, `hrms/www/jobs/index.py` — integrate with `Candidate` + `move_applicant`
- `hrms/ats/` (new): `pipeline.py`, `permissions.py`, `api.py`, `google/gmail.py`, `google/calendar.py`, `import_clustox.py`
- `hrms/patches/` — backfill default pipeline, `Candidate` rows, permlevel moves
- `ats/` (new SPA, modelled on `roster/`)
