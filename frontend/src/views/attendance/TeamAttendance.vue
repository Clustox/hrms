<template>
	<ion-page>
		<DesktopShell />
		<ion-header class="ion-no-border lg:hidden">
			<div class="w-full sm:w-96">
				<div class="flex flex-row items-center border-b bg-white px-3 py-4 shadow-sm">
					<Button variant="ghost" class="mr-1 !px-1 hover:bg-white" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<h2 class="text-xl font-semibold text-gray-900">{{ __("My Team") }}</h2>
				</div>
			</div>
		</ion-header>

		<ion-content>
			<div class="flex w-full flex-col gap-4 p-4 sm:w-96 lg:w-full lg:max-w-[1000px] lg:pl-[274px] lg:pr-10 lg:pt-[84px]">
				<!-- Month navigator -->
				<div class="flex items-center justify-between">
					<h1 class="hidden text-[26px] font-bold tracking-tight text-gray-900 lg:block">
						{{ __("My Team") }}
					</h1>
					<div class="flex items-center gap-1 rounded-lg border bg-white px-1.5 py-1">
						<Button icon="chevron-left" variant="ghost" @click="changeMonth(-1)" />
						<span class="min-w-[120px] text-center text-sm font-semibold text-gray-800">
							{{ firstOfMonth.format("MMMM YYYY") }}
						</span>
						<Button
							icon="chevron-right"
							variant="ghost"
							:disabled="isCurrentMonth"
							@click="changeMonth(1)"
						/>
					</div>
				</div>

				<div v-if="overview.loading" class="flex justify-center py-16">
					<LoadingIndicator class="h-7 w-7 text-gray-400" />
				</div>
				<EmptyState
					v-else-if="!rows.length"
					:message="__('You have no direct reports.')"
				/>

				<!-- Team member cards -->
				<div v-else class="flex flex-col gap-3">
					<div
						v-for="m in rows"
						:key="m.employee"
						class="overflow-hidden rounded-lg border bg-white"
					>
						<button
							class="flex w-full items-center gap-3 p-3.5 text-left hover:bg-gray-50"
							@click="toggle(m.employee)"
						>
							<EmployeeAvatar :employeeID="m.employee" />
							<div class="min-w-0 flex-1">
								<div class="truncate text-[15px] font-semibold text-gray-900">
									{{ m.employee_name }}
								</div>
								<div class="truncate text-[12px] text-gray-500">
									{{ m.designation || "—" }}
								</div>
							</div>
							<div class="hidden shrink-0 gap-4 sm:flex">
								<div class="text-center">
									<div class="text-[15px] font-semibold tabular-nums text-gray-900">
										{{ m.present }}
									</div>
									<div class="text-[10px] uppercase tracking-wide text-gray-400">
										{{ __("Present") }}
									</div>
								</div>
								<div class="text-center">
									<div class="text-[15px] font-semibold tabular-nums text-amber-600">
										{{ m.late_arrival }}
									</div>
									<div class="text-[10px] uppercase tracking-wide text-gray-400">
										{{ __("Late") }}
									</div>
								</div>
								<div class="text-center">
									<div class="text-[15px] font-semibold tabular-nums text-amber-600">
										{{ m.early_left }}
									</div>
									<div class="text-[10px] uppercase tracking-wide text-gray-400">
										{{ __("Early out") }}
									</div>
								</div>
							</div>
							<FeatherIcon
								:name="expanded === m.employee ? 'chevron-up' : 'chevron-down'"
								class="h-4 w-4 shrink-0 text-gray-400"
							/>
						</button>

						<!-- Mobile stat strip -->
						<div class="flex gap-4 border-t px-3.5 py-2 text-[12px] text-gray-600 sm:hidden">
							<span>{{ m.present }} {{ __("present") }}</span>
							<span class="text-amber-600">{{ m.late_arrival }} {{ __("late") }}</span>
							<span class="text-amber-600">{{ m.early_left }} {{ __("early out") }}</span>
							<span class="ml-auto font-medium">{{ m.worked_hours }}h</span>
						</div>

						<!-- Expanded day-by-day detail -->
						<div v-if="expanded === m.employee" class="border-t bg-gray-50/60 p-3">
							<div v-if="memberTimesheet.loading" class="flex justify-center py-6">
								<LoadingIndicator class="h-5 w-5 text-gray-400" />
							</div>
							<EmptyState
								v-else-if="!(memberTimesheet.data || []).length"
								:message="__('No attendance this month')"
							/>
							<div v-else class="flex flex-col gap-2">
								<DayAttendanceCard
									v-for="day in memberTimesheet.data"
									:key="day.attendance_date"
									:date="day.attendance_date"
									:inTime="day.in_time"
									:outTime="day.out_time"
									:workingHours="day.working_hours"
									:status="day.status"
									:shiftStart="day.shift_start"
									:shiftEnd="day.shift_end"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { IonPage, IonHeader, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, LoadingIndicator, createResource } from "frappe-ui"
import { useRouter } from "vue-router"

import DesktopShell from "@/components/DesktopShell.vue"
import DayAttendanceCard from "@/components/DayAttendanceCard.vue"
import EmployeeAvatar from "@/components/EmployeeAvatar.vue"
import EmptyState from "@/components/EmptyState.vue"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const router = useRouter()

const firstOfMonth = ref(dayjs().date(1).startOf("D"))
const isCurrentMonth = computed(() => firstOfMonth.value.isSame(dayjs(), "month"))
const range = () => ({
	from_date: firstOfMonth.value.format("YYYY-MM-DD"),
	to_date: firstOfMonth.value.endOf("M").format("YYYY-MM-DD"),
})

const overview = createResource({
	url: "hrms.api.get_timesheet_overview",
	auto: true,
	makeParams() {
		return { ...range(), scope: "subordinates", page_length: 200 }
	},
})
const rows = computed(() => overview.data?.rows || [])

const expanded = ref(null)
const memberTimesheet = createResource({ url: "hrms.api.get_team_member_timesheet" })

function toggle(employee) {
	if (expanded.value === employee) {
		expanded.value = null
		return
	}
	expanded.value = employee
	memberTimesheet.fetch({ employee, ...range() })
}

function changeMonth(delta) {
	firstOfMonth.value = firstOfMonth.value.add(delta, "M")
	overview.fetch()
	if (expanded.value) memberTimesheet.fetch({ employee: expanded.value, ...range() })
}
</script>
