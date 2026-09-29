import frappeUIPreset from "frappe-ui/src/tailwind/preset"
export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			screens: {
				standalone: {
					raw: "(display-mode: standalone)",
				},
			},
			padding: {
				"safe-top": "env(safe-area-inset-top)",
				"safe-right": "env(safe-area-inset-right)",
				"safe-bottom": "env(safe-area-inset-bottom)",
				"safe-left": "env(safe-area-inset-left)",
			},
			colors: {
				air: {
					bg: "var(--air-bg)",
					surface: "var(--air-surface)",
					"surface-2": "var(--air-surface-2)",
					ink: "var(--air-ink)",
					"ink-2": "var(--air-ink-2)",
					muted: "var(--air-muted)",
					line: "var(--air-line)",
					"line-2": "var(--air-line-2)",
					blue: "var(--air-blue)",
					"blue-2": "var(--air-blue-2)",
					"blue-wash": "var(--air-blue-wash)",
					green: "var(--air-green)",
					btn: "var(--air-btn)",
					"btn-ink": "var(--air-btn-ink)",
					good: "var(--air-good)",
					"good-w": "var(--air-good-w)",
					warn: "var(--air-warn)",
					"warn-w": "var(--air-warn-w)",
					crit: "var(--air-crit)",
					"crit-w": "var(--air-crit-w)",
				},
			},
			boxShadow: {
				air: "var(--air-shadow)",
				"air-2": "var(--air-shadow-2)",
			},
			borderRadius: {
				air: "var(--air-r)",
				"air-sm": "var(--air-r-sm)",
			},
			fontFamily: {
				display: ["Inter Tight", "Inter", "system-ui", "sans-serif"],
			},
			transitionTimingFunction: {
				air: "cubic-bezier(.16,1,.3,1)",
			},
		},
	},
	plugins: [],
}
