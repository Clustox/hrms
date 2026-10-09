# Frappe HR PWA — Attendance / Leave / Manager fixes

**Date:** 2026-10-09
**Branch:** `feature/hrms-pwa-fixes` (off `develop`)
**Scope:** 7 fixes to the `/hrms` self-service PWA (`frontend/src`) + small backend (`leave_rules.py`, a team API). Live system: frappe.theclustox.com.

## Server findings (checked 2026-10-09)
- Shift Types exist — `Morning` 11:00–20:00, `Clustox General` 12:00–21:00 — **neither matches the stated 10:00–18:00**. 91 employees have a `default_shift`, but only **1 Shift Assignment** record. → Decision (Hamad): use **fixed company hours 10:00–18:00, 15-min grace**, held in one config constant (easy to change / swap to shift-based later).
- **778 Employee Check-ins in October but only 3 Attendance records** → attendance isn't being generated from check-ins; that's why the attendance widget is empty (it reads Attendance). The widget fix must derive from / reconcile with check-ins (investigate exact mechanism).

## The 7 fixes

**1. Half-day only for Casual.**
- Frontend `views/leave/Form.vue`: show the Half Day control only when `leave_type` is Casual; clear it when the type changes away from Casual.
- Backend `hrms/leave_rules.py`: validate — `half_day` set AND leave type != Casual → `frappe.throw`. Enforced via form and API.

**2. Check-in / check-out status (early / on-time / late).**
- One shared helper (frontend `utils`) with config `WORK_START=10:00`, `WORK_END=18:00`, `GRACE=15min`. Derives two chips per day: **check-in** Early / On-time / Late (vs start ± grace) and **check-out** Early / On-time / Late (vs end ± grace).
- Rendered on the attendance cards (`DayAttendanceCard.vue`, `DesktopAttendanceDashboard.vue`) and the timesheet view (`views/attendance/Timesheet.vue`). Computed from the in/out times already shown; no biometric change.

**3. 12-hour time (AM/PM).**
- Most displays already use `h:mm A` / `hh:mm a`. Fix the 24-hour instances: `components/ListView.vue:334` (`HH:mm a` → `h:mm A`) and `components/FormField.vue:152` where it shows punch times.

**4. Rename "Pending" → "Pending Request".**
- Display label only; stored status value stays `Pending`. Change the label where status chips render (`LeaveRequestItem.vue`, `DashboardStats.vue`, `DesktopLeaveDashboard.vue`, `DesktopAttendanceDashboard.vue`, and any shared status-label map). No backend/data change.

**5. Empty attendance widget.**
- Root cause above (check-ins exist, Attendance doesn't). Investigate `views/attendance/Dashboard.vue` + `DesktopAttendanceDashboard.vue` + `DashboardStats.vue` + `data/attendance.js`. Likely fix: have the attendance widgets/summary derive the month's present-days and chart from **Employee Check-ins** (which exist) rather than only submitted Attendance, OR surface check-in-derived days. Confirm mechanism before coding; no blind change.

**6. Date-range filter on attendance & leaves lists.**
- Add a from/to date filter to the attendance list (`views/attendance/*List.vue`) and `views/leave/List.vue`, wired into the existing fetch filters (reuse `ListFiltersActionSheet` / a date-range control).

**7. Manager "My Team" view.**
- New PWA section visible to anyone who is a `reports_to` for someone. Backend: whitelisted `get_team_members()` (direct reports of the logged-in user's employee) + team-scoped fetch of a member's Attendance/Timesheet, guarded so a manager sees only their **own** direct reports. Frontend: a "My Team" list + per-member read-only attendance/timesheet view.

## Delivery
- Quick fixes (1,3,4,6) first; then 2; then investigate+fix 5; then 7 (largest).
- Backend gets unit tests (half-day rule, team API). UI verified in the browser preview against the local dev bench.
- Deploy: `cd frontend && yarn build` → tar `hrms/public/frontend` + `hrms/www/hrms.html` → docker cp to prod → `bench build --app hrms` + clear-cache → hard refresh (PWA service-worker caches; use incognito). Backend via the usual bench deploy.

## Open points
- #2 hours: using 10:00–18:00 as confirmed; the 11–20 / 12–21 Shift Types look misconfigured — separate cleanup if those are wrong.
- #5: confirm whether to auto-generate Attendance from check-ins (process fix) or derive the widget from check-ins (UI fix). Leaning UI-derive to avoid changing the attendance pipeline.
