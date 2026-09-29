# PWA Desktop Redesign — Phase 1 Report

Branch: `feature/pwa-desktop-redesign`
Scope: Foundation tokens + Clustox logo + shared nav config + desktop shell (sidebar/topbar) + redesigned Login, all gated behind an additive `lg:` (1024px) breakpoint. Mobile layout is byte-for-byte unchanged (base + `sm:` classes untouched everywhere).

## Files created

- `frontend/src/components/icons/ClustoxLogo.vue` — inline `<svg viewBox="0 0 96 39" fill="currentColor">` with the 12 paths copied verbatim from the artifact's `<symbol id="cx">`. The word-mark letter paths have no `fill` attribute of their own, so they inherit `currentColor` from the root `<svg>`; the four arc paths keep their literal `fill="#00C26C"`. Takes a `height` prop (default `24`), width scales automatically via the `viewBox`.
- `frontend/src/config/navItems.js` — `getNavItems(__)` returns the 5-item nav list (Home, Attendance, Leaves, Expenses, Salary) with `{ icon, title, route }`, extracted verbatim from the old `BottomTabs.vue` inline array. Exported as a function (not a static array) because it needs the injected `$translate` function, and this module must stay usable outside a component's `setup()`.
- `frontend/src/components/DesktopShell.vue` — `hidden lg:flex` sidebar (fixed, 250px, left) + `hidden lg:flex` topbar (fixed, offset by the sidebar width, 68px tall). Sidebar: `ClustoxLogo` + "People" suffix, nav from `navItems.js` with active-route highlighting (`router.path === item.route || startsWith(item.route + "/")`), user chip at the bottom (frappe-ui `Avatar` + name + designation/department, linking to Profile). Topbar: page title derived from the active nav item + today's date (via the app's shared `$dayjs`), a (currently non-wired, visual-only) search field, a notifications bell reusing the real `unreadNotificationsCount` resource + unread dot, and an `Avatar` linking to Profile.
- `.superpowers/pwa-phase1-report.md` — this file.

## Files modified

- `frontend/src/theme/variables.css` — added an `--air-*` token block to `:root` (bg/surface/ink/muted/line neutrals, `--air-blue #1677ff`, `--air-green #00c26c`, good/warn/crit semantic colors, shadows, radii, easing) below the existing Ionic color vars. Light-only for now, per the "no dark mode yet" guardrail — values are already tokenized so a `[data-theme="dark"]` override block can be added in Phase 6 without touching consumers.
- `frontend/tailwind.config.js` — added `theme.extend.colors.air.*` (mapped 1:1 to the CSS vars), `boxShadow.air`/`air-2`, `borderRadius.air`/`air-sm`, `fontFamily.display` (`Inter Tight, Inter, system-ui, sans-serif`), and a `transitionTimingFunction.air` matching the artifact's cubic-bezier ease.
- `frontend/index.html` — added Google Fonts `preconnect` + stylesheet `<link>` for Inter Tight (weights 500/600/700) in `<head>`, right after `<title>`. (Only Inter Tight weights were requested — Inter itself is already self-hosted via frappe-ui/InterVar, so the artifact's `family=Inter:...` half of its combined URL was dropped.)
- `frontend/src/components/BottomTabs.vue` — replaced the inline `tabItems` array with `getNavItems(__)` from the new shared config; added `lg:hidden` to the `ion-tab-bar`'s class list so the mobile tab bar disappears once the desktop shell takes over. All other classes/behavior unchanged.
- `frontend/src/views/TabbedView.vue` — mounted `<DesktopShell />` as a sibling of `<ion-tabs>` inside `<ion-page>`, so it frames every tabbed route (Home + the 4 dashboards).
- `frontend/src/components/BaseLayout.vue` (the layout used by exactly those 5 tabbed views) — added `lg:hidden` to the mobile `ion-header`'s inner wrapper (so the per-page mobile header disappears and `DesktopShell`'s fixed topbar takes over at `lg:`), and appended `lg:h-auto lg:w-full lg:min-h-screen lg:bg-air-bg lg:pl-[250px] lg:pt-[68px]` to the content wrapper div (relaxes the `h-screen w-screen sm:w-96` mobile cap and offsets the content so it clears the fixed sidebar/topbar). Base/`sm:` classes untouched.
- `frontend/src/views/Login.vue` — added a parallel `hidden lg:flex` header block (ClustoxLogo + "Sign in to Clustox People" + subcopy) next to the existing mobile header block (which got `lg:hidden` added, otherwise untouched); the form's outer wrapper div gained `lg:` classes to become a centered 400px card (`lg:rounded-air lg:border lg:border-air-line lg:bg-air-surface lg:p-8 lg:shadow-air`); the two `Input`s got an `input-class` prop with `lg:` overrides (rounded pill, air-line border, blue focus ring) — this restyles via the component's existing `inputClass` prop rather than touching frappe-ui internals; a new `hidden lg:flex` "keep signed in" checkbox + "Forgot password?" row was added (the existing mobile-only centered forgot-password link got `lg:hidden`); the `Button` got `lg:` overrides for a full-width blue pill. Real `session.login()` wiring, `v-model`s, and error handling are all unchanged — only presentation classes were added.

## Desktop vs. mobile gating

Every desktop-only rule is either:
1. an additive `lg:` Tailwind class next to the original mobile-only class (never replacing it), or
2. inside `DesktopShell.vue`, which is `hidden` (renders `display:none`) below 1024px.

Verified via `git diff` that every touched file's base/`sm:` classes are byte-for-byte identical to `develop` — only `lg:`-prefixed classes and new desktop-only DOM blocks (guarded by `hidden lg:flex`) were added.

## Build result

`docker exec -w /home/frappe/frappe-bench/apps/hrms/frontend docker-frappe-1 yarn build` — **succeeded**, 0 errors, 0 warnings other than the pre-existing "chunk larger than 500kB" advisory (unrelated to this change, present before Phase 1 too). Spot-checked the compiled output (`/workspace/hrms/public/frontend/assets/index-*.css` inside the container) and confirmed:
- `--air-blue: #1677ff` is emitted in `:root`.
- `.lg\:hidden{display:none}` and `.lg\:bg-air-blue{background-color:var(--air-blue)}` are both present (confirms Tailwind picked up the new `lg:` utilities and the `air.*` color tokens).
- The Inter Tight Google Fonts `<link>` tags made it into the built `index.html`.

## Deviations from the artifact / notes

- **Nav icons**: reused the existing app icon components (`HomeIcon`, `AttendanceIcon`, `LeaveIcon`, `ExpenseIcon`, `SalaryIcon`) in both `BottomTabs` and `DesktopShell` rather than hand-building a second icon set matching the artifact's exact line-art. They already use `stroke="currentColor"` Lucide-style line icons, so they read consistently with the Air aesthetic and correctly pick up the active-route blue tint; a pixel-perfect re-trace of the artifact's specific icon paths was judged out of scope for "foundation" work.
- **"Keep me signed in" checkbox**: purely cosmetic (bound to a local `keepSignedIn` ref, matching the artifact, which also doesn't wire it to anything). There is no remember-me/session-duration concept in `session.js`'s `login()` call today, so nothing is sent to the backend. Flagging in case a future phase wants real "remember me" semantics.
- **Search field in the topbar**: visual only (no `v-model`/search wiring) — the artifact's version is non-functional too. Left as a stub for a later phase to wire to a real global search if one exists.
- **Topbar page title**: derived from the active nav item (Home/Attendance/Leaves/Expenses/Salary) via route matching, rather than a per-page `pageTitle` prop, since `DesktopShell` is mounted once in `TabbedView` and doesn't have access to each page's own `pageTitle` prop passed to `BaseLayout`. This means the desktop topbar title always mirrors the sidebar's active nav label; page-specific subtitles (e.g. "2026 leave period") from the artifact were not attempted in Phase 1.
- **Badges** (e.g. the artifact's "2" pending-leave badge on the Leaves nav item) were not implemented — no data wiring existed for it and it wasn't in the explicit Phase 1 checklist.
- **Login "halo" decoration and footer copy** ("New hire? Check your inbox...") from the artifact were skipped — not in the explicit Phase 1 checklist, and the footer copy isn't verified as accurate messaging for this app's actual onboarding flow.
- Dark mode: intentionally not implemented (Phase 6), but all new colors are CSS-var-backed (`--air-*`) so a future `[data-theme="dark"]` block can override them without touching any component.

## Verification performed

- `git diff` reviewed for every modified file to confirm base/`sm:` mobile classes are unchanged.
- Confirmed `DesktopShell` root elements are `hidden lg:flex` / `hidden lg:fixed lg:flex` and `BottomTabs`'s `ion-tab-bar` has `lg:hidden`.
- `yarn build` run twice inside `docker-frappe-1` (clean logs both times).
- Compiled CSS/HTML inspected inside the container for the new tokens, `lg:` utilities, and font link.
- Could not browser-test (per task constraints) — visual/interaction verification at `lg:` widths is left to the controller.
