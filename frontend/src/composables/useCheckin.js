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
import { createListResource, toast } from "frappe-ui"

import { settings } from "@/data/settings"

const DOCTYPE = "Employee Checkin"

// Shared UI state (one check-in flow is active at a time, on either UI).
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")

let initialized = false
let checkins = null
let lastLog = null
let lastLogType = null
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
		// re-attach the socket handler in case something removed it.
		attachSocket(socket)
		if (!checkins.list.loading) checkins.reload()
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

		nextAction = computed(() => {
			return lastLog?.value?.log_type === "IN"
				? { action: "OUT", label: __("Check Out") }
				: { action: "IN", label: __("Check In") }
		})
	})

	// Only mark initialized once setup succeeded (a throw above, e.g. null
	// employee.data, leaves later consumers free to retry).
	initialized = true
	checkins.reload()
	attachSocket(socket)
}

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude

	locationStatus.value = [
		__("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
		__("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
	].join(", ")
}

function handleLocationError(error) {
	locationStatus.value = "Unable to retrieve your location"
	if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
	if (!navigator.geolocation) {
		locationStatus.value = __("Geolocation is not supported by your current browser")
	} else {
		locationStatus.value = __("Locating...")
		navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
	}
}

const handleEmployeeCheckin = () => {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")

	if (settings.data?.allow_geolocation_tracking) {
		fetchLocation()
	}
}

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
		nextAction,
		checkinTimestamp,
		latitude,
		longitude,
		locationStatus,
		fetchLocation,
		handleEmployeeCheckin,
		submitLog,
	}
}
