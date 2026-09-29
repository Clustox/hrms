<template>
	<ion-page>
		<DesktopShell />
		<ion-header class="ion-no-border lg:hidden">
			<div class="w-full sm:w-96">
				<div class="flex flex-row bg-white shadow-sm py-4 px-3 items-center border-b">
					<Button variant="ghost" class="!px-1 mr-1 hover:bg-white" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<h2 class="text-xl font-semibold text-gray-900">{{ __("Timesheet") }}</h2>
				</div>
			</div>
		</ion-header>

		<ion-content>
			<!-- Mobile (unchanged) -->
			<div class="flex flex-col p-4 gap-5 w-full sm:w-96 lg:hidden">
				<!-- Month change, same pattern as AttendanceCalendar -->
				<div class="flex flex-row justify-between items-center px-1">
					<Button
						icon="chevron-left"
						variant="ghost"
						@click="firstOfMonth = firstOfMonth.subtract(1, 'M')"
					/>
					<span class="text-lg text-gray-800 font-bold">
						{{ firstOfMonth.format("MMMM") }} {{ firstOfMonth.format("YYYY") }}
					</span>
					<Button
						icon="chevron-right"
						variant="ghost"
						@click="firstOfMonth = firstOfMonth.add(1, 'M')"
					/>
				</div>

				<div class="flex flex-col gap-3" v-if="!timesheet.loading && timesheet.data?.length">
					<DayAttendanceCard
						v-for="day in timesheet.data"
						:key="day.attendance_date"
						:date="day.attendance_date"
						:inTime="day.in_time"
						:outTime="day.out_time"
						:workingHours="day.working_hours"
						:status="day.status"
					/>
				</div>

				<EmptyState :message="__('No attendance records for this month')" v-else-if="!timesheet.loading" />

				<div v-if="timesheet.loading" class="flex mt-2 items-center justify-center">
					<LoadingIndicator class="w-8 h-8 text-gray-800" />
				</div>
			</div>

			<!-- Air desktop timesheet -->
			<div class="hidden lg:block lg:min-h-full lg:bg-air-bg lg:pl-[250px] lg:pt-[68px] lg:pb-16">
				<div class="mx-auto max-w-[920px] px-10 pt-[30px]">
					<div class="mb-6 flex items-end justify-between">
						<div>
							<h1 class="font-display text-[28px] font-bold tracking-[-0.02em] text-air-ink">
								{{ __("Timesheet") }}
							</h1>
							<p class="mt-1 text-[13.5px] text-air-muted">
								{{ __("Hours logged from your daily check-in and check-out") }}
							</p>
						</div>
						<div class="flex items-center gap-1">
							<button
								class="flex h-9 w-9 items-center justify-center rounded-full text-air-ink-2 transition hover:bg-air-surface-2"
								@click="firstOfMonth = firstOfMonth.subtract(1, 'M')"
							>
								<FeatherIcon name="chevron-left" class="h-4 w-4" />
							</button>
							<span class="w-[150px] text-center font-display text-[15px] font-semibold text-air-ink">
								{{ firstOfMonth.format("MMMM YYYY") }}
							</span>
							<button
								class="flex h-9 w-9 items-center justify-center rounded-full text-air-ink-2 transition hover:bg-air-surface-2"
								@click="firstOfMonth = firstOfMonth.add(1, 'M')"
							>
								<FeatherIcon name="chevron-right" class="h-4 w-4" />
							</button>
						</div>
					</div>

					<div class="mb-5 grid grid-cols-3 gap-4">
						<div class="rounded-air border border-air-line bg-air-surface p-4">
							<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
								{{ __("Hours logged") }}
							</div>
							<div class="mt-1.5 font-display text-[26px] font-semibold tracking-tight text-air-ink tabular-nums">
								{{ totalHours.toFixed(1) }}<small class="ml-1 text-[13px] font-medium text-air-muted">h</small>
							</div>
						</div>
						<div class="rounded-air border border-air-line bg-air-surface p-4">
							<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
								{{ __("Days logged") }}
							</div>
							<div class="mt-1.5 font-display text-[26px] font-semibold tracking-tight text-air-ink tabular-nums">
								{{ daysLogged }}
							</div>
						</div>
						<div class="rounded-air border border-air-line bg-air-surface p-4">
							<div class="text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
								{{ __("Avg / day") }}
							</div>
							<div class="mt-1.5 font-display text-[26px] font-semibold tracking-tight text-air-ink tabular-nums">
								{{ daysLogged ? (totalHours / daysLogged).toFixed(1) : "0.0"
								}}<small class="ml-1 text-[13px] font-medium text-air-muted">h</small>
							</div>
						</div>
					</div>

					<div class="overflow-hidden rounded-air border border-air-line bg-white shadow-air">
						<table
							class="w-full border-collapse text-left"
							v-if="!timesheet.loading && timesheet.data?.length"
						>
							<thead>
								<tr
									class="border-b border-gray-100 text-[11px] font-semibold uppercase tracking-[0.05em] text-gray-500"
								>
									<th class="px-5 py-3 font-semibold">{{ __("Date") }}</th>
									<th class="px-5 py-3 font-semibold">{{ __("Check-in") }}</th>
									<th class="px-5 py-3 font-semibold">{{ __("Check-out") }}</th>
									<th class="px-5 py-3 font-semibold">{{ __("Status") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Hours logged") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="day in timesheet.data"
									:key="day.attendance_date"
									class="border-b border-gray-50 last:border-0 hover:bg-gray-50/60"
								>
									<td class="px-5 py-3.5 text-[14px] font-medium text-gray-900">
										{{ dayjs(day.attendance_date).format("ddd, D MMM") }}
									</td>
									<td class="px-5 py-3.5 text-[14px] tabular-nums text-gray-700">
										{{ fmtTime(day.in_time) }}
									</td>
									<td class="px-5 py-3.5 text-[14px] tabular-nums text-gray-700">
										{{ fmtTime(day.out_time) }}
									</td>
									<td class="px-5 py-3.5">
										<span
											v-if="shiftStatus(day)"
											class="inline-flex rounded-full px-2.5 py-0.5 text-[12px] font-medium"
											:class="shiftStatus(day).cls"
										>
											{{ shiftStatus(day).label }}
										</span>
										<span v-else class="text-[13px] text-gray-400">—</span>
									</td>
									<td class="px-5 py-3.5 text-right text-[14px] font-semibold tabular-nums text-gray-900">
										{{ fmtHours(day.working_hours) }}
									</td>
								</tr>
							</tbody>
						</table>
						<div v-else-if="timesheet.loading" class="flex items-center justify-center py-16">
							<LoadingIndicator class="h-7 w-7 text-gray-400" />
						</div>
						<div v-else class="px-5 py-16 text-center text-[14px] text-gray-500">
							{{ __("No attendance records for this month") }}
						</div>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, inject, watch, computed } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonHeader, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, LoadingIndicator, createResource } from "frappe-ui"

import EmptyState from "@/components/EmptyState.vue"
import DayAttendanceCard from "@/components/DayAttendanceCard.vue"
import DesktopShell from "@/components/DesktopShell.vue"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const router = useRouter()

const firstOfMonth = ref(dayjs().date(1).startOf("D"))

// Basic timesheet: Date / Check-in / Check-out / Worked Hours, sourced from
// Attendance's own in_time/out_time/working_hours (see
// hrms.api.get_attendance_timesheet) -- not re-derived from raw Employee
// Checkin rows, and not the "Late/On Time/Overtime" breakdown some other
// attendance tools show, which needs Shift Type timing that isn't set up
// here yet.
const timesheet = createResource({
	url: "hrms.api.get_attendance_timesheet",
	auto: true,
	makeParams() {
		return {
			from_date: firstOfMonth.value.format("YYYY-MM-DD"),
			to_date: firstOfMonth.value.endOf("M").format("YYYY-MM-DD"),
		}
	},
})

watch(
	() => firstOfMonth.value,
	() => {
		timesheet.fetch()
	}
)

// Desktop table helpers (mobile keeps DayAttendanceCard).
const fmtTime = (t) => (t && dayjs(t).isValid() ? dayjs(t).format("h:mm A") : "—")
const fmtHours = (h) => (Number(h) ? Number(h).toFixed(2) : "—")

// Early / On time / Late vs the day's scheduled shift start, with a 10-minute
// buffer either side. shift_start comes from the day's first check-in
// (hrms.api.get_attendance_timesheet). No shift or no check-in -> no badge.
const SHIFT_BUFFER_MINUTES = 10
function shiftStatus(day) {
	if (!day.in_time || !day.shift_start) return null
	const diff = dayjs(day.in_time).diff(dayjs(day.shift_start), "minute")
	if (diff > SHIFT_BUFFER_MINUTES)
		return { label: __("Late"), cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20" }
	if (diff < -SHIFT_BUFFER_MINUTES)
		return { label: __("Early"), cls: "bg-sky-50 text-sky-700 ring-1 ring-sky-600/20" }
	return { label: __("On time"), cls: "bg-green-50 text-green-700 ring-1 ring-green-600/20" }
}

const totalHours = computed(() =>
	(timesheet.data || []).reduce((sum, d) => sum + (Number(d.working_hours) || 0), 0)
)
const daysLogged = computed(
	() => (timesheet.data || []).filter((d) => Number(d.working_hours) > 0).length
)
</script>
