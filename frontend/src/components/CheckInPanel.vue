<template>
	<div class="flex flex-col bg-white rounded w-full py-6 px-4 border-none">
		<h2 class="text-lg font-bold text-gray-900">
			{{ __("Hey, {0} 👋", [employee?.data?.first_name]) }}
		</h2>

		<!-- Last-check-in info shows for everyone (biometric staff included); only
			the Check In/Out button + modal below stay gated by `canCheckin`. -->
		<div class="font-medium text-sm text-gray-500 mt-1.5" v-if="lastLog?.time">
			<span>{{ __("Last {0} was at {1}", [__(lastLogType), formatTimestamp(lastLog.time)]) }}</span>
			<span class="whitespace-pre"> &middot; </span>
			<router-link :to="{ name: 'EmployeeCheckinListView' }" v-slot="{ navigate }">
				<span @click="navigate" class="underline">View List</span>
			</router-link>
		</div>
		<div v-else class="font-medium text-sm text-gray-500 mt-1.5">
			{{ dayjs().format("ddd, D MMMM, YYYY") }}
		</div>

		<div v-if="staleCheckin" class="mt-2 text-sm font-medium text-amber-700">
			{{
				__("Your check-in at {0} had no check-out, so that session was reset. You can start a new one.", [
					formatTimestamp(staleCheckin.time),
				])
			}}
		</div>

		<Button
			v-if="canCheckin"
			class="mt-4 mb-1 drop-shadow-sm py-5 text-base"
			id="open-checkin-modal"
			:loading="checkins.list.loading"
			@click="handleEmployeeCheckin"
		>
			<template #prefix>
				<FeatherIcon
					:name="nextAction.action === 'IN' ? 'arrow-right-circle' : 'arrow-left-circle'"
					class="w-4"
				/>
			</template>
			{{ nextAction.label }}
		</Button>
	</div>

	<ion-modal
		v-if="canCheckin"
		ref="modal"
		trigger="open-checkin-modal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<div class="h-120 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5">
			<div class="flex flex-col gap-1.5 mt-2 items-center justify-center">
				<div class="font-bold text-xl">
					{{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
				</div>
				<div class="font-medium text-gray-500 text-sm">
					{{ dayjs().format("D MMM, YYYY") }}
				</div>
			</div>

			<template v-if="settings.data?.allow_geolocation_tracking">
				<span v-if="locationStatus" class="font-medium text-gray-500 text-sm">
					{{ locationStatus }}
				</span>

				<div class="rounded border-4 translate-z-0 block overflow-hidden w-full h-170">
					<iframe
						width="100%"
						height="170"
						frameborder="0"
						scrolling="no"
						marginheight="0"
						marginwidth="0"
						style="border: 0"
						:src="`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=15&amp;output=embed`"
					>
					</iframe>
				</div>
			</template>

			<Button
				:loading="checkins.insert.loading"
				:disabled="locationNotReady"
				variant="solid"
				class="w-full py-5 text-sm disabled:bg-gray-700"
				@click="submitLog(nextAction.action)"
			>
				{{ locationNotReady ? __("Fetching location...") : __("Confirm {0}", [nextAction.label]) }}
			</Button>
		</div>
	</ion-modal>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"
import { computed, inject } from "vue"
import { IonModal, modalController } from "@ionic/vue"

import { formatTimestamp } from "@/utils/formatters"
import { settings } from "@/data/settings"
import { useCheckin } from "@/composables/useCheckin"

const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")

// Shared singleton (one resource + one socket subscription app-wide, also used
// by the desktop DesktopCheckin card).
const {
	checkins,
	lastLog,
	lastLogType,
	staleCheckin,
	nextAction,
	checkinTimestamp,
	latitude,
	longitude,
	locationStatus,
	hasApprovedWfh,
	locationNotReady,
	handleEmployeeCheckin,
	submitLog: submitCheckinLog,
} = useCheckin()

// Biometric hardware handles normal office attendance now -- this manual
// button only makes sense on a day the employee has an Approved WFH
// request for.
const canCheckin = computed(
	() => Boolean(settings.data?.allow_employee_checkin_from_mobile_app) && Boolean(hasApprovedWfh.data)
)

// Mobile: close the bottom-sheet modal on success.
const submitLog = (logType) =>
	submitCheckinLog(logType, { onSuccess: () => modalController.dismiss() })
</script>
