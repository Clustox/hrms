/**
 * Air desktop theme controller (Phase 6 — dark mode).
 *
 * Persists the user's choice in localStorage["hrms:theme"] as one of
 * "light" | "dark" | "system" (default "system"), and applies it by toggling a
 * DEDICATED `data-air-theme="dark"` attribute on <html>.
 *
 * Why a dedicated attribute instead of frappe-ui's `data-theme="dark"`:
 * frappe-ui's Tailwind preset ships a full `[data-theme="dark"]` variable block
 * plus a global `img { filter: brightness(.8) }` rule that would re-theme every
 * frappe-ui component and dim every image APP-WIDE — including the mobile phone
 * chrome. The Air dark palette lives under `:root[data-air-theme="dark"]` in
 * theme/variables.css and only redefines the `--air-*` tokens, which are used
 * exclusively by the `lg:` desktop shell/components. The mobile UI never reads
 * `--air-*`, so it stays light regardless of theme or OS preference. The toggle
 * control itself lives only in the desktop shell (hidden lg:flex).
 *
 * When theme === "system" we follow `prefers-color-scheme` live. All
 * localStorage access is guarded (private mode / disabled storage can throw).
 */
import { ref, computed } from "vue"

const STORAGE_KEY = "hrms:theme"
const DARK_ATTR = "data-air-theme"
const VALID = ["light", "dark", "system"]

const systemMedia =
	typeof window !== "undefined" && typeof window.matchMedia === "function"
		? window.matchMedia("(prefers-color-scheme: dark)")
		: null

function readStored() {
	try {
		const v = localStorage.getItem(STORAGE_KEY)
		if (VALID.includes(v)) return v
	} catch (e) {
		/* storage unavailable (private mode, blocked) — fall through */
	}
	return "system"
}

// Module-level singleton state so every consumer (shell toggle, settings, app
// init) shares one source of truth.
const theme = ref(readStored())
const systemDark = ref(systemMedia ? systemMedia.matches : false)

// Currently-effective appearance: honors "system" against the live OS setting.
const isDark = computed(() =>
	theme.value === "system" ? systemDark.value : theme.value === "dark"
)

function applyToDocument() {
	if (typeof document === "undefined") return
	const root = document.documentElement
	if (isDark.value) root.setAttribute(DARK_ATTR, "dark")
	else root.removeAttribute(DARK_ATTR)
}

function setTheme(value) {
	theme.value = VALID.includes(value) ? value : "system"
	try {
		localStorage.setItem(STORAGE_KEY, theme.value)
	} catch (e) {
		/* ignore write failures */
	}
	applyToDocument()
}

// Explicit, obvious two-state flip for the sun/moon button: switch to the
// opposite of what is currently shown (drops out of "system" into a concrete
// choice, which is the least surprising behavior for a single toggle).
function toggleTheme() {
	setTheme(isDark.value ? "light" : "dark")
}

// light -> dark -> system -> light (available for a 3-way control, e.g. a
// future AppSettings "Appearance" row).
function cycleTheme() {
	const next = VALID[(VALID.indexOf(theme.value) + 1) % VALID.length]
	setTheme(next)
}

let initialized = false
/**
 * Apply the persisted/derived theme and start following the OS when in
 * "system" mode. Call once, as early as possible (main.js), so the attribute is
 * set before first paint (no flash). Idempotent.
 */
function initTheme() {
	applyToDocument()
	if (initialized || !systemMedia) return
	initialized = true
	const onChange = (e) => {
		systemDark.value = e.matches
		if (theme.value === "system") applyToDocument()
	}
	if (typeof systemMedia.addEventListener === "function")
		systemMedia.addEventListener("change", onChange)
	else if (typeof systemMedia.addListener === "function")
		systemMedia.addListener(onChange) // Safari < 14 fallback
}

export function useTheme() {
	return { theme, isDark, setTheme, toggleTheme, cycleTheme, initTheme }
}

export { theme, isDark, setTheme, toggleTheme, cycleTheme, initTheme }
