# ATS on the existing Recruitment module: verified review and implementation plan

Date: 2026-11-06. Branch: `feature/ats-on-hrms` (from `develop`).
Requirements: `ATS Requirements Document (2).docx` (v1.0, 7 screenshots and diagrams).
Formatted version: https://claude.ai/artifact/8eJsyKnqt7G49n7N7jzS2C (private link)

The ATS extends the Recruitment module already in this HRMS. No new application and no separate front end. Everything below was checked in the code or on the running local site (Frappe/ERPNext develop, v17).

## 1. Method and limits

- **Code read:** all Recruitment doctypes (Job Opening, Job Applicant, Interview, Interview Feedback, Interview Type, Job Offer, Job Requisition, Staffing Plan, Employee Referral, Job Opening Template, Appointment Letter), their JS and Python, `www/jobs`, the job application web form, workspace, sidebar, reports, charts, HR Settings, hooks. Frappe core: Kanban Board, Google Calendar, Email Account, User Email, Event, Notification, `frappe.set_value`.
- **Live tests (rolled back):** per-job Kanban board with custom columns; User Permission scope; Share on one applicant; salary permission level.
- **Not covered:** production customisations (not inspected), Gmail and Google Calendar against a real Google account, screens in a browser.

## 2. What already exists (reuse)

| Area | Implemented today |
|---|---|
| Job Opening | Title, designation, company, department, location (Branch), vacancies, salary range, Open/Closed, publish and route, closing date. Close/Reopen with Staffing Plan warning, template autofill, auto-close by date, closing marks the Job Requisition Filled, optional duplicate block per job |
| Job Applicant | Contact, source, rating, cover letter, resume and PDF preview, salary expectation, referral, status (Open, Replied, Shortlisted, Rejected, Hold, Accepted). Buttons: Shortlist, Reject, Schedule Interview, Create Job Offer. Interview Summary panel. Email thread |
| Hiring Pipeline | Global Desk Kanban on status, 4 fixed columns (Open, Replied, Shortlisted, Accepted), linked from the sidebar |
| Interview | Type, date, times, interviewers, status. Reschedule with email, calendar and Gantt views, reminder and feedback reminder emails |
| Feedback | Interview Feedback with skill ratings, average, Cleared/Rejected |
| Offer | Job Offer with terms and templates, Create Employee, Onboarding, Appointment Letter |
| Planning | Job Requisition, Staffing Plan, Job Opening Template, Employee Referral |
| Public | `/jobs` list and page, application web form, "Jobs" Email Account with append to Job Applicant |
| Analytics | Recruitment Analytics report, 8 charts, 8 number cards |

Verified Frappe features: Kanban per job with custom columns and board filters; User Permission on a Job Opening scopes jobs, applicants and interviews; Share gives a role-less user read on one applicant; `frappe.set_value` saves the document (hooks run); `User Email` OAuth per user; Event with Google sync, Meet link and participants that reference any record; Notification "Value Change"; Data Import.

**Not present:** per-job stages, stage history, dropped reasons, candidate across jobs, phone duplicate check, resume text, guest role, salary hiding (fields are permission level 0), recruitment notifications, version tracking on Job Opening/Job Applicant/Job Offer, Department to Job link, Event linked to Interview, Google response sync and free/busy (no code in core).

## 3. Comparison with the ATS document

Legend: **Exists**, **Modify**, **Add**, **Done** (already on the branch).

| ATS requirement | Verdict | Approach |
|---|---|---|
| Roles | Modify, Add | Administrator = HR Manager. Add `ATS Recruiter`, `ATS Guest`. Department owner is a record rule |
| Departments list, create/edit/filter/sort | Exists | Standard Desk list |
| Department owner, team, industry, location | Done | Custom fields. Job count through a Department dashboard link |
| Department tree | Done | 19 departments seeded |
| Jobs list/board, filters, pagination | Exists | Desk list and Kanban |
| Jobs columns (location, headcount, salary, owner, stage) | Modify | List columns plus cached counters |
| Job owner, team, Negotiable | Done | Fields on Job Opening |
| Headcount (positions - filled, e.g. 3 - 1) and Job Stage badge | Add | Counters updated by the stage hook. Headcount follows the document. The badge rule needs HR confirmation |
| Job detail header and counters | Add | Hired / In pipeline / Dropped on the form |
| Per-job stages, templates | Add | Stage table on Job Opening, Pipeline Template copied in |
| Kanban, counts, drag and drop, filter | Exists | Frappe Kanban, one generated board per job on text field `pipeline_stage` |
| Card details | Modify | Extra card fields. Time-in-stage badge is a spike |
| Dropped with reason | Add | `is_dropped`, `drop_reason`, Drop Reason list |
| Stage visible to guests | Add | Flag per stage plus permission rule |
| Move log, optional email | Add | Applicant Stage Log on save. Notification or hook for email |
| Candidate across jobs, dedupe, resume text | Add | `Candidate` doctype, Job Applicant links to it |
| Guest, per-job access | Exists, Add | User Permission on the job (verified) managed by Job Guest Access |
| Guest stage visibility, salary hiding | Add, Modify | Permission query rule, salary to permission level 1 |
| Guest feedback | Modify | Reuse Interview Feedback, narrow guest role (Interviewer role is too broad) |
| Gmail per recruiter | Modify | `User Email` OAuth, spike with real account |
| Reply sync | Modify | `append_to` plus thread matching |
| Templates, merge fields | Exists | Email Template |
| Calendar event with Meet | Add | Event created from Interview |
| Response sync, free/busy | Add | Not in core, custom code |
| Notifications | Add | Notification records |
| Audit trail | Modify | Turn on version tracking, stage log |
| Performance | Add | Index on job, stage, dropped. 3,000-applicant test |
| Import | Modify | Data Import plus mapping, legacy id |

## 4. Technical approach

- Additive only. Custom fields from an idempotent `after_migrate` hook (`hrms.ats.setup.apply_custom_fields`).
- **Pipeline:** Job Pipeline Stage table on Job Opening is the source of truth. A Kanban Board per job is generated from it, filtered to the job, on text field `pipeline_stage`. Moving a card calls `frappe.set_value`, which saves the Job Applicant, so one `on_update` hook writes the log, counters, status and stage email.
- **Status and stage in step:** Interview, Job Offer and the Desk buttons already save through the document, so a hook maps them to stages. The Employee hook uses `frappe.db.set_value` (no hooks), so it is edited to call the shared helper. Each stage carries a mapped status. Ready to Offer and Offer Placed map to Accepted so offers and onboarding keep working. Hired counts by stage type.
- **Candidate:** created or matched in `Job Applicant.before_insert` (covers Desk, web form, mailbox). Backfill by patch.
- **Guests:** Job Guest Access creates and deletes the User Permission. Query rule for stage visibility. Salary at permission level 1. Feedback through Interview Feedback.
- **Google:** per-recruiter OAuth. Event created from Interview with participants referencing the applicant and interviewers. Scheduled pull for responses, free/busy by direct query.

## 5. Work done on the branch

- Plan document, Team Member table, Department fields, Job Opening fields (committed, verified).
- HR sidebars restored in the new Frappe Sidebar format (committed).
- Demo data and 19-department tree (committed).
- Pipeline template, stage doctypes and default template: written and tested (6 tests), not committed.

## 6. Implementation steps (about 9 to 10 weeks, one developer)

0. **Spikes, 2-3 days:** Gmail send-as-recruiter and threading, Event participants and attendee response, board column sync and card time-in-stage, list bulk email.
1. **Data model, ~1 week:** commit pipeline doctypes, stage table and counters on Job Opening, Job Applicant fields and index, Candidate, Applicant Stage Log, Drop Reason, backfill, version tracking.
2. **Stage move logic, ~1 week:** `on_update` hook, status to stage reconcile, Employee hook edit, drop and restore, Interview prompt change.
3. **Per-job board, Departments, Jobs, ~1.5 weeks:** generated boards, form header counters, list columns, Department link and job count.
4. **Candidates, ~1 week:** upsert, duplicate match, applications table, resume text, search.
5. **Guests, ~1.5 weeks:** roles, Job Guest Access, visibility rule, salary level, activity log, restricted workspace.
6. **Gmail and Calendar, ~2 weeks:** per-recruiter Gmail, templates, threading, bulk send; Interview to Event, responses, free/busy, reschedule and cancel.
7. **Notifications, migration, hardening, ~1 week:** notifications, import mapping and dry run, performance, backup and restore, admin guide.

## 7. Testing

Permission matrix across roles and access paths; regression of apply form, interview, offer, employee creation and analytics after each schema change; pipeline edge cases (delete stage with candidates, concurrent moves, drop and restore); duplicate cases (email, phone formats, import re-run); Google cases (token expiry, outside domain, time zone); performance budgets (job list under 500 ms, board under 1 s, move under 300 ms) with a 3,000-applicant job.

## 8. Risks and open items

Production customisations not seen; card time-in-stage; board columns edited directly; Gmail not run against Google; Google response sync and free/busy are custom; guest data exposure; status and stage drift; local dev DB issues unrelated to this work (CX360 migrate hook, test base class fiscal-year clash).

## 9. Questions for HR

1. Job Stage badge: "last stage in pipeline order that holds a candidate"?
2. Recruiter scope: all jobs or own and team jobs?
3. Hired counter with an empty Offer Accepted column.
4. Guest visibility: current stage or ever reached.
5. Dropped vs rejected definition.
6. Unexplained icons (orange "!", list icon, "$", green stage icon, progress bar).
7. Production boards, fields or screens not seen here.
8. Email replies: ATS threads only or whole inbox.
9. Google: Internal Workspace app and public HTTPS address.
10. Migration source and bulk resume access.
11. Legacy Hold applicants and Staffing Plan rule for ATS jobs.
