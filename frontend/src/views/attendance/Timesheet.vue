<template>
	<ion-page>
		<DesktopShell />
		<ion-header class="ion-no-border lg:hidden">
			<div class="w-full sm:w-96">
				<div class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b">
					<div class="flex flex-row items-center">
						<Button variant="ghost" class="!px-1 mr-1 hover:bg-white" @click="router.back()">
							<FeatherIcon name="chevron-left" class="h-5 w-5" />
						</Button>
						<h2 class="text-xl font-semibold text-gray-900">{{ __("Timesheet") }}</h2>
					</div>
					<Button
						icon="filter"
						variant="subtle"
						:class="[
							areFiltersApplied
								? '!border !border-gray-800 !bg-white !text-gray-900 !font-semibold'
								: '',
						]"
						@click="showFilterModal = true"
					/>
				</div>
			</div>
		</ion-header>

		<ion-content>
			<!-- Mobile (unchanged) -->
			<div class="flex flex-col p-4 gap-5 w-full sm:w-96 lg:hidden">
				<template v-if="!expandedEmployee">
					<TabButtons :buttons="TAB_BUTTONS" v-model="activeTab" />

					<!-- Month change, same pattern as AttendanceCalendar -->
					<div class="flex flex-row justify-between items-center px-1" v-if="!areFiltersApplied">
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
					<div class="flex flex-row justify-between items-center px-1" v-else>
						<span class="text-base text-gray-800 font-semibold">
							{{ dayjs(appliedRange.from).format("D MMM") }} - {{ dayjs(appliedRange.to).format("D MMM YYYY") }}
						</span>
						<Button variant="outline" class="text-sm" @click="clearFilters">
							{{ __("Clear") }}
						</Button>
					</div>
				</template>

				<!-- My Timesheet -->
				<template v-if="!isTeam">
					<div class="flex flex-col gap-3" v-if="!timesheet.loading && timesheet.data?.length">
						<DayAttendanceCard
							v-for="day in timesheet.data"
							:key="day.attendance_date"
							:date="day.attendance_date"
							:inTime="day.in_time"
							:outTime="day.out_time"
							:workingHours="day.working_hours"
							:status="day.status"
							:lateEntry="day.late_entry"
							:earlyExit="day.early_exit"
							:inLocation="day.in_location"
							:outLocation="day.out_location"
						/>
					</div>

					<EmptyState
						:message="areFiltersApplied ? __('No attendance records for this range') : __('No attendance records for this month')"
						v-else-if="!timesheet.loading"
					/>

					<div v-if="timesheet.loading" class="flex mt-2 items-center justify-center">
						<LoadingIndicator class="w-8 h-8 text-gray-800" />
					</div>
				</template>

				<!-- Team Timesheet -->
				<template v-else-if="!expandedEmployee">
					<div class="flex flex-col gap-3" v-if="!teamTimesheet.loading && teamTimesheet.data?.rows?.length">
						<div
							v-for="row in teamTimesheet.data.rows"
							:key="row.employee"
							class="flex flex-col gap-3 bg-white rounded-lg border p-3.5"
							@click="toggleEmployee(row.employee, row.employee_name)"
						>
							<div class="flex flex-row items-center justify-between">
								<div>
									<div class="text-base font-semibold text-gray-900">{{ row.employee_name }}</div>
									<div class="text-xs text-gray-500">{{ row.designation }}</div>
								</div>
								<div class="flex items-center gap-2">
									<div class="text-right">
										<div class="text-base font-semibold text-gray-900">
											{{ fmtHours(row.worked_hours) }}<span class="text-xs text-gray-500">/{{ fmtHours(row.expected_hours) }}h</span>
										</div>
										<div class="text-xs text-gray-500">{{ __("Worked / Expected") }}</div>
									</div>
									<FeatherIcon name="chevron-right" class="h-4 w-4 shrink-0 text-gray-400" />
								</div>
							</div>
							<hr />
							<div class="grid grid-cols-5 gap-2 text-center">
								<div>
									<div class="text-sm font-semibold text-gray-900">{{ row.present }}</div>
									<div class="text-[11px] text-gray-500">{{ __("Present") }}</div>
								</div>
								<div>
									<div class="text-sm font-semibold text-gray-900">{{ row.absent }}</div>
									<div class="text-[11px] text-gray-500">{{ __("Absent") }}</div>
								</div>
								<div>
									<div class="text-sm font-semibold text-gray-900">{{ row.leave }}</div>
									<div class="text-[11px] text-gray-500">{{ __("Leave") }}</div>
								</div>
								<div>
									<div class="text-sm font-semibold" :class="row.late_arrival ? 'text-amber-600' : 'text-gray-900'">
										{{ row.late_arrival }}
									</div>
									<div class="text-[11px] text-gray-500">{{ __("Late") }}</div>
								</div>
								<div>
									<div class="text-sm font-semibold" :class="row.early_left ? 'text-sky-600' : 'text-gray-900'">
										{{ row.early_left }}
									</div>
									<div class="text-[11px] text-gray-500">{{ __("Early") }}</div>
								</div>
							</div>
						</div>
					</div>

					<EmptyState :message="__('No direct reports found')" v-else-if="!teamTimesheet.loading" />

					<div v-if="teamTimesheet.loading" class="flex mt-2 items-center justify-center">
						<LoadingIndicator class="w-8 h-8 text-gray-800" />
					</div>
				</template>

				<!-- Team Timesheet: one employee's day-by-day log -->
				<template v-else>
					<div class="flex flex-row items-center gap-2">
						<Button variant="ghost" class="!px-1 hover:bg-white" @click="expandedEmployee = null">
							<FeatherIcon name="chevron-left" class="h-5 w-5" />
						</Button>
						<span class="text-lg font-bold text-gray-800">{{ expandedEmployeeName }}</span>
					</div>

					<div class="flex flex-col gap-3" v-if="!employeeLog.loading && employeeLog.data?.length">
						<DayAttendanceCard
							v-for="day in employeeLog.data"
							:key="day.attendance_date"
							:date="day.attendance_date"
							:inTime="day.in_time"
							:outTime="day.out_time"
							:workingHours="day.working_hours"
							:status="day.status"
							:lateEntry="day.late_entry"
							:earlyExit="day.early_exit"
							:inLocation="day.in_location"
							:outLocation="day.out_location"
						/>
					</div>

					<EmptyState :message="__('No attendance records for this period')" v-else-if="!employeeLog.loading" />

					<div v-if="employeeLog.loading" class="flex mt-2 items-center justify-center">
						<LoadingIndicator class="w-8 h-8 text-gray-800" />
					</div>
				</template>
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
						<div class="flex items-center gap-2.5">
							<template v-if="!areFiltersApplied">
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
							</template>
							<span v-else class="font-display text-[15px] font-semibold text-air-ink">
								{{ dayjs(appliedRange.from).format("D MMM") }} - {{ dayjs(appliedRange.to).format("D MMM YYYY") }}
							</span>
							<button
								id="show-filter-modal"
								class="flex items-center gap-2 rounded-full border px-4 py-2 text-[13.5px] font-medium transition ease-air"
								:class="
									areFiltersApplied
										? 'border-air-ink bg-air-surface text-air-ink'
										: 'border-air-line bg-air-surface text-air-ink-2 hover:border-air-ink'
								"
								@click="areFiltersApplied ? clearFilters() : (showFilterModal = true)"
							>
								<FeatherIcon :name="areFiltersApplied ? 'x' : 'filter'" class="h-4 w-4" />
								{{ areFiltersApplied ? __("Clear") : __("Filter") }}
							</button>
						</div>
					</div>

					<TabButtons v-if="!expandedEmployee" class="mb-5" :buttons="TAB_BUTTONS" v-model="activeTab" />
					<div v-else class="mb-5 flex items-center gap-2">
						<button
							class="flex h-9 w-9 items-center justify-center rounded-full text-air-ink-2 transition hover:bg-air-surface-2"
							@click="expandedEmployee = null"
						>
							<FeatherIcon name="chevron-left" class="h-4 w-4" />
						</button>
						<span class="font-display text-[17px] font-semibold text-air-ink">{{ expandedEmployeeName }}</span>
					</div>

					<!-- My Timesheet (reused for a drilled-into team member's log too) -->
					<template v-if="!isTeam || expandedEmployee">
						<div class="mb-5 grid grid-cols-3 gap-4" v-if="!expandedEmployee">
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
								v-if="!displayedLog.loading && displayedLog.data?.length"
							>
								<thead>
									<tr
										class="border-b border-gray-100 text-[11px] font-semibold uppercase tracking-[0.05em] text-gray-500"
									>
										<th class="px-5 py-3 font-semibold">{{ __("Date") }}</th>
										<th class="px-5 py-3 font-semibold">{{ __("Check-in") }}</th>
										<th class="px-5 py-3 font-semibold">{{ __("Check-out") }}</th>
										<th class="px-5 py-3 text-right font-semibold">{{ __("Hours logged") }}</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="day in displayedLog.data"
										:key="day.attendance_date"
										class="border-b border-gray-50 last:border-0 hover:bg-gray-50/60"
									>
										<td class="px-5 py-3.5 text-[14px] font-medium text-gray-900">
											{{ dayjs(day.attendance_date).format("ddd, D MMM") }}
										</td>
										<td class="px-5 py-3.5 text-[14px] tabular-nums text-gray-700">
											<div class="flex items-center gap-2" v-if="day.in_time || !day.status">
												{{ fmtTime(day.in_time) }}
												<span
													v-if="day.late_entry"
													class="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-amber-600/20"
												>
													{{ __("Late") }}
												</span>
												<CheckinLocationPin :location="day.in_location" :label="__('View check-in location')" />
											</div>
											<span
												v-else
												class="inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium"
												:class="statusBadgeClass(day.status)"
											>
												{{ __(day.status) }}
											</span>
										</td>
										<td class="px-5 py-3.5 text-[14px] tabular-nums text-gray-700">
											<div class="flex items-center gap-2" v-if="day.out_time || !day.status">
												{{ fmtTime(day.out_time) }}
												<span
													v-if="day.early_exit"
													class="inline-flex rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-sky-600/20"
												>
													{{ __("Early") }}
												</span>
												<CheckinLocationPin :location="day.out_location" :label="__('View check-out location')" />
											</div>
											<span v-else class="text-gray-400">—</span>
										</td>
										<td class="px-5 py-3.5 text-right text-[14px] font-semibold tabular-nums text-gray-900">
											{{ fmtHours(day.working_hours) }}
										</td>
									</tr>
								</tbody>
							</table>
							<div v-else-if="displayedLog.loading" class="flex items-center justify-center py-16">
								<LoadingIndicator class="h-7 w-7 text-gray-400" />
							</div>
							<div v-else class="px-5 py-16 text-center text-[14px] text-gray-500">
								{{ areFiltersApplied ? __("No attendance records for this range") : __("No attendance records for this month") }}
							</div>
						</div>
					</template>

					<!-- Team Timesheet -->
					<div v-else class="overflow-hidden rounded-air border border-air-line bg-white shadow-air">
						<table
							class="w-full border-collapse text-left"
							v-if="!teamTimesheet.loading && teamTimesheet.data?.rows?.length"
						>
							<thead>
								<tr
									class="border-b border-gray-100 text-[11px] font-semibold uppercase tracking-[0.05em] text-gray-500"
								>
									<th class="px-5 py-3 font-semibold">{{ __("Employee") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Present") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Absent") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Leave") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Late") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Early") }}</th>
									<th class="px-5 py-3 text-right font-semibold">{{ __("Worked / Expected") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in teamTimesheet.data.rows"
									:key="row.employee"
									class="cursor-pointer border-b border-gray-50 last:border-0 hover:bg-gray-50/60"
									@click="toggleEmployee(row.employee, row.employee_name)"
								>
									<td class="px-5 py-3.5 text-[14px]">
										<div class="flex items-center gap-2">
											<div>
												<div class="font-medium text-gray-900">{{ row.employee_name }}</div>
												<div class="text-[12px] text-gray-500">{{ row.designation }}</div>
											</div>
										</div>
									</td>
									<td class="px-5 py-3.5 text-right text-[14px] tabular-nums text-gray-700">{{ row.present }}</td>
									<td class="px-5 py-3.5 text-right text-[14px] tabular-nums text-gray-700">{{ row.absent }}</td>
									<td class="px-5 py-3.5 text-right text-[14px] tabular-nums text-gray-700">{{ row.leave }}</td>
									<td
										class="px-5 py-3.5 text-right text-[14px] tabular-nums"
										:class="row.late_arrival ? 'font-semibold text-amber-600' : 'text-gray-700'"
									>
										{{ row.late_arrival }}
									</td>
									<td
										class="px-5 py-3.5 text-right text-[14px] tabular-nums"
										:class="row.early_left ? 'font-semibold text-sky-600' : 'text-gray-700'"
									>
										{{ row.early_left }}
									</td>
									<td class="px-5 py-3.5 text-right text-[14px] tabular-nums text-gray-900">
										<div class="flex items-center justify-end gap-2">
											<span class="font-semibold">{{ fmtHours(row.worked_hours) }} / {{ fmtHours(row.expected_hours) }}</span>
											<FeatherIcon name="chevron-right" class="h-3.5 w-3.5 shrink-0 text-gray-400" />
										</div>
									</td>
								</tr>
							</tbody>
						</table>
						<div v-else-if="teamTimesheet.loading" class="flex items-center justify-center py-16">
							<LoadingIndicator class="h-7 w-7 text-gray-400" />
						</div>
						<div v-else class="px-5 py-16 text-center text-[14px] text-gray-500">
							{{ __("No direct reports found") }}
						</div>
					</div>
				</div>
			</div>
		</ion-content>

		<CustomIonModal
			trigger="show-filter-modal"
			:isOpen="showFilterModal"
			@did-dismiss="showFilterModal = false"
		>
			<template #actionSheet>
				<ListFiltersActionSheet
					:filterConfig="FILTER_CONFIG"
					@applyFilters="applyFilters"
					@clearFilters="clearFilters"
					v-model:filters="filterMap"
				/>
			</template>
		</CustomIonModal>
	</ion-page>
</template>

<script setup>
import { ref, reactive, inject, watch, computed } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonHeader, IonContent, modalController } from "@ionic/vue"
import { Button, FeatherIcon, LoadingIndicator, createResource } from "frappe-ui"

import EmptyState from "@/components/EmptyState.vue"
import DayAttendanceCard from "@/components/DayAttendanceCard.vue"
import CheckinLocationPin from "@/components/CheckinLocationPin.vue"
import DesktopShell from "@/components/DesktopShell.vue"
import ListFiltersActionSheet from "@/components/ListFiltersActionSheet.vue"
import CustomIonModal from "@/components/CustomIonModal.vue"
import TabButtons from "@/components/TabButtons.vue"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const router = useRouter()

const TAB_BUTTONS = ["My Timesheet", "Team Timesheet"] // __("My Timesheet"), __("Team Timesheet")
const activeTab = ref(TAB_BUTTONS[0])
const isTeam = computed(() => activeTab.value === TAB_BUTTONS[1])

const firstOfMonth = ref(dayjs().date(1).startOf("D"))

// Arbitrary From Date/To Date range, same UI pattern as the Leave list's
// filter panel (ListFiltersActionSheet). While applied, this replaces the
// month-navigation range below instead of combining with it.
const FILTER_CONFIG = [
	{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
	{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
]
const filterMap = reactive({})
const showFilterModal = ref(false)
const areFiltersApplied = ref(false)
const appliedRange = ref({ from: null, to: null })

function initializeFilters() {
	FILTER_CONFIG.forEach((filter) => {
		filterMap[filter.fieldname] = { condition: "=", value: null }
	})
}
initializeFilters()

function applyFilters() {
	const from = filterMap.from_date.value
	const to = filterMap.to_date.value
	if (from && to) {
		appliedRange.value = { from, to }
		areFiltersApplied.value = true
	}
	showFilterModal.value = false
	modalController.dismiss()
}

function clearFilters() {
	initializeFilters()
	appliedRange.value = { from: null, to: null }
	areFiltersApplied.value = false
	showFilterModal.value = false
	modalController.dismiss()
}

// Either the applied From/To Date filter, or the current month -- shared by
// both "My Timesheet" and "Team Timesheet" so switching tabs keeps the same
// period selected.
const effectiveRange = computed(() => {
	if (areFiltersApplied.value && appliedRange.value.from && appliedRange.value.to) {
		return { from: appliedRange.value.from, to: appliedRange.value.to }
	}
	return {
		from: firstOfMonth.value.format("YYYY-MM-DD"),
		to: firstOfMonth.value.endOf("M").format("YYYY-MM-DD"),
	}
})

// Basic timesheet: Date / Check-in / Check-out / Worked Hours, sourced from
// Attendance's own in_time/out_time/working_hours (see
// hrms.api.get_attendance_timesheet), plus a late_entry/early_exit flag per
// day computed server-side from that day's Shift Type grace-period config.
const timesheet = createResource({
	url: "hrms.api.get_attendance_timesheet",
	auto: true,
	makeParams() {
		return { from_date: effectiveRange.value.from, to_date: effectiveRange.value.to }
	},
})

// Team Timesheet: per-direct-report summary (present/absent/leave/late/early,
// worked vs expected hours) for the same period, via hrms.api.get_timesheet_overview
// -- already supports scope="subordinates" (filters Employee by reports_to) but
// was previously only wired into the legacy desk "HR Timesheet" page, unused
// by this app. Fetched lazily, only once the Team Timesheet tab is opened.
const teamTimesheet = createResource({
	url: "hrms.api.get_timesheet_overview",
	auto: false,
	makeParams() {
		return {
			from_date: effectiveRange.value.from,
			to_date: effectiveRange.value.to,
			scope: "subordinates",
			page_length: 100,
		}
	},
})

watch(isTeam, (nowTeam) => {
	if (nowTeam) teamTimesheet.fetch()
	else expandedEmployee.value = null
})

watch(effectiveRange, () => {
	timesheet.fetch()
	if (isTeam.value) teamTimesheet.fetch()
	if (expandedEmployee.value) employeeLog.fetch()
})

// Drill-down: clicking a Team Timesheet row replaces the summary table with
// that employee's own day-by-day log, in the exact same Date/Check-in/
// Check-out/Hours table as My Timesheet (see `displayedLog` below), via
// hrms.api.get_team_member_attendance_timesheet -- only allows looking up a
// direct report this way, not an arbitrary employee.
const expandedEmployee = ref(null)
const expandedEmployeeName = ref("")
const employeeLog = createResource({
	url: "hrms.api.get_team_member_attendance_timesheet",
	auto: false,
	makeParams() {
		return {
			employee: expandedEmployee.value,
			from_date: effectiveRange.value.from,
			to_date: effectiveRange.value.to,
		}
	},
})

function toggleEmployee(employee, employeeName) {
	expandedEmployee.value = employee
	expandedEmployeeName.value = employeeName
	employeeLog.fetch()
}

// Whichever log is on screen: the employee's own (My Timesheet) normally, or
// a drilled-into team member's when one is selected -- same table either way.
const displayedLog = computed(() => (expandedEmployee.value ? employeeLog : timesheet))

// Desktop table helpers (mobile keeps DayAttendanceCard).
const fmtTime = (t) => (t && dayjs(t).isValid() ? dayjs(t).format("h:mm A") : "—")
const fmtHours = (h) => (Number(h) ? Number(h).toFixed(2) : "—")

// Same status set/colors as DayAttendanceCard's colorMap (mobile), for a
// no-checkin day (e.g. "On Leave") shown in the desktop table's Check-in cell.
const STATUS_BADGE_CLASS = {
	Present: "bg-green-50 text-green-700 ring-1 ring-green-600/20",
	"Work From Home": "bg-green-50 text-green-700 ring-1 ring-green-600/20",
	"Half Day": "bg-orange-50 text-orange-700 ring-1 ring-orange-600/20",
	Absent: "bg-red-50 text-red-700 ring-1 ring-red-600/20",
	"On Leave": "bg-blue-50 text-blue-700 ring-1 ring-blue-600/20",
}
const statusBadgeClass = (status) =>
	STATUS_BADGE_CLASS[status] || "bg-gray-100 text-gray-700 ring-1 ring-gray-400/20"

const totalHours = computed(() =>
	(timesheet.data || []).reduce((sum, d) => sum + (Number(d.working_hours) || 0), 0)
)
const daysLogged = computed(
	() => (timesheet.data || []).filter((d) => Number(d.working_hours) > 0).length
)
</script>
