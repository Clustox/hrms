# PWA Desktop Redesign — Phased Plan ("Air")

**Goal:** Give the `/hrms` Vue+Ionic PWA a modern, minimal desktop web experience (the approved "Air" concept — Apple-style minimalism, Clustox brand) at wide breakpoints, **leaving the mobile layout untouched**.

**Design reference (locked):** the Air artifact — flat surfaces, hairline borders, whitespace, Clustox blue `#1677ff` for actions, green `#00c26c` in the logo, neutrals; Inter Tight headings / Inter body; refined motion (sliding segments, count-up, fade-rise, hover lift). Real Clustox logo SVG (wordmark + green arc).

## Architecture decisions (from the frontend map)
- App = `IonApp > IonRouterOutlet` (root) with `TabbedView` (`IonTabs > IonRouterOutlet + BottomTabs`) hosting the tabbed routes (`/home`, `/dashboard/*`). Standalone routes (Login, Profile, Notifications, Settings) mount on the root outlet.
- Mobile width is pinned by `sm:w-96` / `w-screen` / `h-screen` across ~14 files. **No existing desktop/responsive handling; no dark mode.**
- **Approach:** custom **`lg` (1024px) breakpoint** shell using Tailwind utilities (not `ion-split-pane`). A new `DesktopShell.vue` (sidebar + topbar, `hidden lg:flex`) mounts inside `TabbedView`; `BottomTabs` becomes `lg:hidden`; width caps are relaxed only at `lg:` (`sm:w-96 lg:w-full`, `h-screen lg:h-auto`) so mobile is unchanged.
- **Tokens:** Air palette as CSS vars in `src/theme/variables.css` `:root`; exposed to Tailwind via `tailwind.config.js` `theme.extend.colors` (`air.blue` = `var(--air-blue)`, etc.). Optionally remap `--ion-color-primary` to `#1677ff`.
- **Fonts:** Inter/InterVar already self-hosted (frappe-ui). Add **Inter Tight** for headings via a Google Fonts `<link>` in `index.html` + Tailwind `fontFamily.display`.
- **Nav list:** extract the tab list from `BottomTabs.vue` into a shared `src/config/navItems.js` consumed by both `BottomTabs` and `DesktopShell`.

## Phases (each = one PR, deployed + reviewed)

**Phase 1 — Foundation + Shell + Login.**
- Add Air tokens (`variables.css`, `tailwind.config.js`) + Inter Tight (`index.html`).
- `src/config/navItems.js` (shared nav) + embed the Clustox logo SVG as a component (`src/components/icons/ClustoxLogo.vue`).
- `src/components/DesktopShell.vue` — sidebar (logo + nav + user) + topbar (title, search, notifications, avatar), `hidden lg:flex`, active-route highlighting from the router.
- Wire into `TabbedView.vue`; `BottomTabs` → `lg:hidden`; relax `BaseLayout.vue` width caps at `lg:` so Home + dashboards go full-width inside the shell.
- `Login.vue` — desktop centered Air card at `lg:` (mobile unchanged).
- **Deliverable:** on desktop, the Air shell + redesigned Login; mobile identical to today.

**Phase 2 — Home dashboard** (`Home.vue`): Air dashboard at `lg:` — stat tiles (leave rings, attendance sparkline), quick-actions grid, recent requests, upcoming holidays. Mobile unchanged.

**Phase 3 — Leaves + Attendance dashboards** (`views/leave/Dashboard.vue`, `views/attendance/Dashboard.vue`) in the Air system.

**Phase 4 — Expenses + Salary dashboards.**

**Phase 5 — Profile / Notifications / Settings** desktop treatment (Profile already hosts the onboarding wizard).

**Phase 6 (optional) — Dark mode:** add a `[data-theme="dark"]` token block + a toggle (frappe-ui already wires the `[data-theme="dark"]` selector).

## Guardrails
- Every desktop change is additive under `lg:` or inside `DesktopShell`; never remove the mobile `sm:`/base styles.
- Verify after each phase: mobile view unchanged at phone width; desktop transformed at ≥1024px; `yarn build` clean.
- Deploy per the established flow (merge → the running app is updated + `bench build`).
