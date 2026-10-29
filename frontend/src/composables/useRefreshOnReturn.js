import { onBeforeUnmount } from "vue"
import { useRoute, useRouter } from "vue-router"
import { onIonViewWillEnter } from "@ionic/vue"

/**
 * Re-run `refresh` whenever the user comes back to this page.
 *
 * Ionic keeps a page alive when you navigate away and back, so nothing
 * re-mounts -- a request approved/cancelled in the meantime (from its own form,
 * from Desk in another tab, or by someone else) kept showing its old status,
 * because the only refresh was a realtime socket event, which can be missed.
 *
 * Three signals, any of which may fire depending on how the user returned:
 *  - Ionic's ionViewWillEnter (back/forward inside the app)
 *  - the router landing on this page's route again
 *  - the browser tab/window regaining focus (e.g. back from Desk)
 * Bursts are collapsed so one return triggers a single refresh. The first
 * entry is skipped: the page's own mount already loaded its data.
 */
export function useRefreshOnReturn(refresh, { minGapMs = 1000 } = {}) {
	const router = useRouter()
	const routeName = useRoute().name
	let hasEnteredOnce = false
	let lastRun = 0

	const run = () => {
		const now = Date.now()
		if (now - lastRun < minGapMs) return
		lastRun = now
		refresh()
	}

	onIonViewWillEnter(() => {
		if (hasEnteredOnce) run()
		hasEnteredOnce = true
	})

	const stopAfterEach = router.afterEach((to, from) => {
		if (routeName && to.name === routeName && from.name !== to.name) run()
	})

	const onFocus = () => {
		// only while this page is the one on screen
		if (router.currentRoute.value.name === routeName) run()
	}
	window.addEventListener("focus", onFocus)

	onBeforeUnmount(() => {
		stopAfterEach()
		window.removeEventListener("focus", onFocus)
	})
}
