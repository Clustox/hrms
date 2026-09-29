import { ref, watch, onBeforeUnmount, toValue } from "vue"

const prefersReducedMotion = () =>
	typeof window !== "undefined" &&
	window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

/**
 * Animates a number from its previous value up to `source` with an ease-out
 * curve (matches the Air artifact's count-up). Returns a ref holding the
 * current in-flight value. Jumps straight to the target when the user prefers
 * reduced motion.
 */
export function useCountUp(source, duration = 900) {
	const shown = ref(0)
	let frame = null

	function stop() {
		if (frame) cancelAnimationFrame(frame)
		frame = null
	}

	watch(
		() => toValue(source),
		(to) => {
			stop()
			if (typeof to !== "number" || Number.isNaN(to)) {
				shown.value = 0
				return
			}
			if (prefersReducedMotion()) {
				shown.value = to
				return
			}
			const from = shown.value
			let t0 = null
			const step = (t) => {
				t0 = t0 ?? t
				const p = Math.min((t - t0) / duration, 1)
				const eased = 1 - Math.pow(1 - p, 3)
				shown.value = from + (to - from) * eased
				frame = p < 1 ? requestAnimationFrame(step) : null
			}
			frame = requestAnimationFrame(step)
		},
		{ immediate: true }
	)

	onBeforeUnmount(stop)
	return shown
}
