# PWA Desktop Redesign — Phase 2 Report (Air dashboard)

Branch: `feature/pwa-desktop-redesign`. Scope: desktop (`lg:` >= 1024px) Home dashboard in the Air style. Mobile Home unchanged.

## Files

Created
- `frontend/src/components/DesktopDashboard.vue` — orchestrator: greeting hero + stats + quick actions + recent requests/holidays.
- `frontend/src/components/DashboardStats.vue` — 4 stat tiles (annual-leave ring, attendance sparkline, sick-leave ring, pending count); count-up numbers, ring fill via stroke-dashoffset transition, sparkline draw.
- `frontend/src/components/QuickActions.vue` — 3-col action grid (router-links to the same named routes as mobile).
- `frontend/src/components/RecentRequests.vue`, `frontend/src/components/UpcomingHolidays.vue`.
- `frontend/src/composables/useCountUp.js` — rAF ease-out count-up; jumps to target under `prefers-reduced-motion`.
- `frontend/src/composables/useDashboardRequests.js` — read-only view over the existing my/team request resources (recent list, pending counts); does not mutate shared resource data.

Modified
- `frontend/src/views/Home.vue` — existing mobile markup wrapped unchanged inside a `lg:hidden` div (only `lg:hidden` added to its class list); `<DesktopDashboard v-if="isDesktop">` added beside it. `isDesktop` = matchMedia("(min-width: 1024px)") so the dashboard (and its extra fetches) are mounted only on wide viewports. Each quick-link got an additive `description` field (ignored by the mobile `QuickLinks`).
- `frontend/src/data/attendance.js` — added `monthAttendance` resource (existing endpoint `hrms.api.get_attendance_timesheet`, `auto: false`).
- `frontend/src/main.css` — `.air-rise` fade-rise + `air-draw` keyframes, reduced-motion safe.

## Data: real vs placeholder

Real
- Greeting: `$employee.first_name` + time-of-day salutation.
- Annual / Sick tiles: `leaveBalance` (`hrms.api.get_leave_balance_map`) — remaining/allocated/used. Leave types are site-configured, so tiles match by name (annual, else casual/earned/privilege/vacation; sick). If a type isn't allocated the tile shows "—" / "Not allocated" (no invented number). Local dev site has Casual/Privilege/Sick etc., prod has Annual/Sick.
- Attendance %: current month's Attendance records (`get_attendance_timesheet`): (Present + WFH + 0.5*Half Day) / (Present + WFH + Half Day + Absent); "On Leave" excluded. Sparkline = worked hours per day over the last <= 8 recorded days. Shows "—" + dashed baseline when there are no records (this site has no auto-attendance, so many months will be empty).
- Pending: count of the user's own requests (leave/claim/shift/attendance, latest 10 each) in a pending state. Hero subline also shows team requests awaiting the user's approval (team* resources).
- Recent requests: 5 most recent across the four my-* resources, same resources as mobile RequestPanel.
- Upcoming holidays: `hrms.api.get_holidays_for_employee` (next 4).

Placeholder / not implemented
- The artifact's "▲ 2% vs Aug" delta was dropped (would need a second month fetch); note shows present/absent counts instead.
- Recent requests "View all" links to the Leave history list (there's no combined list view).

## Mobile preservation
Mobile Home markup is untouched (only `lg:hidden` appended to its wrapper). No `sm:`/base classes changed. Desktop dashboard is `hidden lg:block` and additionally only mounted when matchMedia says >= 1024px.

## Build
`yarn build` in `docker-frappe-1`: succeeded (only the pre-existing >500kB chunk advisory).

## Notes / concerns
- Desktop Home no longer shows `CheckInPanel` (mobile check-in/out button + geolocation modal); it is still mounted but hidden at `lg:`. If desktop check-in is wanted, it needs a dedicated hero button (CheckInPanel's modal trigger id would collide if mounted twice).
- Not browser-verified (controller's job).
