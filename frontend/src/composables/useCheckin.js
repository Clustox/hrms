/**
 * Shared employee check-in / check-out state (Air desktop Phase 7).
 *
 * Module-level singleton: the `Employee Checkin` list resource, the derived
 * last-log / next-action state, the geolocation refs and the socket
 * subscription are created ONCE, no matter how many components call
 * `useCheckin()`.
 *
 * Why: on desktop the mobile `CheckInPanel` is CSS-hidden (`lg:hidden`) but
 * still mounted, alongside the new `DesktopCheckin` card. Each owning its own
 * resource + socket handler would double-subscribe and double-fetch.
 *
 * `$socket` / `$employee` / `$dayjs` / `$translate` are provided by the app and
 * must be `inject()`ed inside a component setup, so the first consumer's
 * `useCheckin()` call (which runs `initCheckin` with those) builds everything.
 * Later calls just return the same state. The socket subscription is app-
 * lifetime (never unsubscribed), matching the other singletons.
 */
import { computed, effectScope, inject, ref } from "vue"
import { createListResource, createResource, toast } from "frappe-ui"

import { settings } from "@/data/settings"

const DOCTYPE = "Employee Checkin"

// Shared UI state (one check-in flow is active at a time, on either UI).
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")
// Biometric hardware now handles normal office attendance automatically
// (see integrations/biometric-attendance-sync), so the manual Check-in/
// Check-out button only makes sense on a day the employee has an Approved
// WFH request for -- otherwise it's hidden outright, same as the existing
// allow_employee_checkin_from_mobile_app gate.
const hasApprovedWfh = createResource({
	url: "hrms.hr.doctype.attendance_request.attendance_request.has_approved_wfh_today",
	auto: false,
})
// True while a geolocation fetch is in flight, so the UI can keep the
// Confirm button disabled until it resolves -- clicking through while it's
// still 0,0 used to submit with no real coordinates and fail server-side
// with a much less clear "Latitude and longitude values are required" error.
const isLocating = ref(false)

// A forgotten check-out shouldn't keep offering "Check Out" indefinitely: a
// check-in older than this is treated as a MISSED check-out, so the dashboard
// stops offering the check-out and lets the employee check in for the new day.
// `checkinClock` ticks every minute so the switch also happens on a page left
// open across the 24h boundary, not only on reload.
const STALE_CHECKIN_HOURS = 24
const checkinClock = ref(Date.now())

let initialized = false
let checkins = null
let lastLog = null
let lastLogType = null
let isCheckedIn = null
let nextAction = null
let employee = null
let dayjs = null
let __ = null
// Detached scope so the computeds/resource outlive the component that happened
// to create them (component-scoped effects are stopped on unmount).
const scope = effectScope(true)

// Named so it can be re-attached idempotently: other views (e.g. Profile) call
// a blanket `socket.off("list_update")` on unmount, which would otherwise drop
// our handler for good.
function onListUpdate(data) {
	if (data.doctype === DOCTYPE) checkins.reload()
}

function attachSocket(socket) {
	if (!socket) return
	socket.off("list_update", onListUpdate)
	socket.on("list_update", onListUpdate)
	socket.emit("doctype_subscribe", DOCTYPE)
}

function initCheckin({ socket, employee: emp, dayjs: dj, translate }) {
	if (initialized) {
		// A consumer (re)mounted, e.g. navigating back to Home: refresh like the
		// original panel did on mount, but never start a duplicate request, and
		// re-attach the socket handler in case something removed it. Also
		// re-checks WFH coverage, so a request that expired overnight (or one
		// just approved) is reflected without needing a full page reload.
		attachSocket(socket)
		if (!checkins.list.loading) checkins.reload()
		hasApprovedWfh.fetch()
		return
	}
	employee = emp
	dayjs = dj
	__ = translate

	scope.run(() => {
		checkins = createListResource({
			doctype: DOCTYPE,
			fields: ["name", "employee", "employee_name", "log_type", "time", "device_id"],
			filters: {
				employee: employee.data.name,
			},
			orderBy: "time desc",
		})

		lastLog = computed(() => {
			if (checkins.list.loading || !checkins.data) return {}
			return checkins.data[0]
		})

		lastLogType = computed(() => {
			return lastLog?.value?.log_type === "IN" ? "check-in" : "check-out"
		})

		// Currently checked in = last log is an IN still within the 24h window.
		// An older IN is a forgotten check-out, so treat the employee as checked
		// out (missed check-out) -- they can start the new day's check-in.
		isCheckedIn = computed(() => {
			const log = lastLog?.value
			if (log?.log_type !== "IN" || !log?.time) return false
			void checkinClock.value // reactive tick so this re-evaluates over time
			return dayjs().diff(dayjs(log.time), "hour") < STALE_CHECKIN_HOURS
		})

		nextAction = computed(() => {
			return isCheckedIn.value
				? { action: "OUT", label: __("Check Out") }
				: { action: "IN", label: __("Check In") }
		})
	})

	// Only mark initialized once setup succeeded (a throw above, e.g. null
	// employee.data, leaves later consumers free to retry).
	initialized = true
	checkins.reload()
	hasApprovedWfh.fetch()
	attachSocket(socket)
	// App-lifetime tick (like the socket handler) so the 24h stale-check-in
	// switch happens live, not only on reload.
	setInterval(() => (checkinClock.value = Date.now()), 60000)
}

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude
	isLocating.value = false

	locationStatus.value = [
		__("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
		__("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
	].join(", ")
}

function handleLocationError(error) {
	isLocating.value = false
	locationStatus.value = "Unable to retrieve your location"
	if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
	if (!navigator.geolocation) {
		locationStatus.value = __("Geolocation is not supported by your current browser")
	} else {
		isLocating.value = true
		locationStatus.value = __("Locating...")
		navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
	}
}

const handleEmployeeCheckin = () => {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")

	if (settings.data?.allow_geolocation_tracking) {
		// Reset before fetching, not after -- otherwise a previous check-in's
		// coordinates (or a previous failed fetch's 0,0) would make this new
		// one look "ready" for the instant between opening the modal and
		// fetchLocation's isLocating flip.
		latitude.value = 0
		longitude.value = 0
		fetchLocation()
	}
}

// Whether tracking is required but no real fix has come back yet (still
// fetching, or the fetch hasn't been kicked off / failed and left 0,0) --
// used to keep the Confirm button disabled so a click can't submit a
// checkin with no real coordinates.
const locationNotReady = computed(
	() => Boolean(settings.data?.allow_geolocation_tracking) && (isLocating.value || (!latitude.value && !longitude.value))
)

/**
 * Insert an Employee Checkin. `onSuccess` lets each UI close its own
 * confirmation (ion-modal on mobile, Dialog on desktop) before the toast.
 */
const submitLog = (logType, { onSuccess } = {}) => {
	const actionLabel = logType === "IN" ? __("Check-in") : __("Check-out")

	checkins.insert.submit(
		{
			employee: employee.data.name,
			log_type: logType,
			time: checkinTimestamp.value,
			latitude: latitude.value,
			longitude: longitude.value,
		},
		{
			onSuccess() {
				if (onSuccess) onSuccess()
				toast({
					title: __("Success"),
					text: __("{0} successful!", [actionLabel]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(error) {
				let messages = error.messages || []

				for (const message of messages) {
					toast({
						title: __("Error"),
						text: message || __("{0} failed!", [actionLabel]),
						icon: "alert-circle",
						position: "bottom-center",
						iconClasses: "text-red-500",
					})
				}
			},
		}
	)
}

/**
 * Call inside a component's setup. The first call builds the shared resource +
 * socket subscription; every call returns the same state.
 */
export function useCheckin() {
	initCheckin({
		socket: inject("$socket"),
		employee: inject("$employee"),
		dayjs: inject("$dayjs"),
		translate: inject("$translate"),
	})

	return {
		checkins,
		lastLog,
		lastLogType,
		isCheckedIn,
		nextAction,
		checkinTimestamp,
		latitude,
		longitude,
		locationStatus,
		hasApprovedWfh,
		isLocating,
		locationNotReady,
		fetchLocation,
		handleEmployeeCheckin,
		submitLog,
	}
}
