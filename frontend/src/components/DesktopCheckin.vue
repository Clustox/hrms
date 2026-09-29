<template>
	<!--
		Air desktop check-in / check-out card for the Home hero. Shares state with
		the (CSS-hidden) mobile CheckInPanel through the useCheckin singleton, so
		there is one Employee Checkin resource and one socket subscription.
	-->
	<div>
		<div
			class="rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
		>
			<div class="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
				<div class="min-w-0">
					<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
						{{ __("Attendance") }}
					</div>

					<template v-if="settings.data?.allow_employee_checkin_from_mobile_app">
						<div v-if="lastLog" class="mt-2 text-[15px] text-air-ink-2">
							<span>{{
								__("Last {0} was at {1}", [__(lastLogType), formatTimestamp(lastLog.time)])
							}}</span>
							<span class="whitespace-pre text-air-muted"> &middot; </span>
							<router-link
								:to="{ name: 'EmployeeCheckinListView' }"
								class="text-air-blue underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
							>
								{{ __("View List") }}
							</router-link>
						</div>
						<div v-else class="mt-2 text-[15px] text-air-muted">
							{{ dayjs().format("ddd, D MMMM, YYYY") }}
						</div>
					</template>
					<div v-else class="mt-2 text-[15px] text-air-muted">
						{{ dayjs().format("ddd, D MMMM, YYYY") }}
					</div>
				</div>

				<button
					v-if="settings.data?.allow_employee_checkin_from_mobile_app"
					type="button"
					:disabled="checkins.list.loading"
					class="inline-flex shrink-0 items-center gap-2 rounded-full bg-air-btn px-5 py-2.5 text-[14px] font-semibold text-air-btn-ink transition ease-air hover:bg-air-blue hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
					@click="openConfirm"
				>
					<FeatherIcon
						:name="nextAction.action === 'IN' ? 'arrow-right-circle' : 'arrow-left-circle'"
						class="h-4 w-4"
					/>
					{{ nextAction.label }}
				</button>
			</div>
		</div>

		<Dialog
			v-if="settings.data?.allow_employee_checkin_from_mobile_app"
			v-model="showDialog"
			:options="{ title: nextAction.label, size: 'md' }"
		>
			<template #body-content>
				<div class="flex flex-col items-center gap-5">
					<div class="flex flex-col items-center gap-1.5">
						<div
							class="font-display text-[38px] font-semibold leading-none tracking-[-0.04em] text-air-ink tabular-nums"
						>
							{{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
						</div>
						<div class="text-sm font-medium text-air-muted">
							{{ dayjs().format("D MMM, YYYY") }}
						</div>
					</div>

					<template v-if="settings.data?.allow_geolocation_tracking">
						<span v-if="locationStatus" class="text-sm font-medium text-air-muted">
							{{ locationStatus }}
						</span>

						<div
							class="block h-[170px] w-full overflow-hidden rounded-air-sm border border-air-line"
						>
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

					<button
						type="button"
						:disabled="checkins.insert.loading"
						class="w-full rounded-full bg-air-btn px-5 py-2.5 text-[14px] font-semibold text-air-btn-ink transition ease-air hover:bg-air-blue hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
						@click="confirm"
					>
						{{ __("Confirm {0}", [nextAction.label]) }}
					</button>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { Dialog, FeatherIcon } from "frappe-ui"
import { inject, ref } from "vue"

import { formatTimestamp } from "@/utils/formatters"
import { settings } from "@/data/settings"
import { useCheckin } from "@/composables/useCheckin"

const dayjs = inject("$dayjs")
const __ = inject("$translate")

const {
	checkins,
	lastLog,
	lastLogType,
	nextAction,
	checkinTimestamp,
	latitude,
	longitude,
	locationStatus,
	handleEmployeeCheckin,
	submitLog,
} = useCheckin()

const showDialog = ref(false)

// Same flow as mobile: stamp the time (and fetch location) first, then confirm.
const openConfirm = () => {
	handleEmployeeCheckin()
	showDialog.value = true
}

const confirm = () => submitLog(nextAction.value.action, { onSuccess: () => (showDialog.value = false) })
</script>
