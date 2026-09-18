<template>
	<ion-page>
		<ion-header class="ion-no-border">
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
			<div class="flex flex-col p-4 gap-5 w-full sm:w-96">
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
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, inject, watch } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonHeader, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, LoadingIndicator, createResource } from "frappe-ui"

import EmptyState from "@/components/EmptyState.vue"
import DayAttendanceCard from "@/components/DayAttendanceCard.vue"

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
</script>
