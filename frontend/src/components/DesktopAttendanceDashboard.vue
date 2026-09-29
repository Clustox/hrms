<template>
	<!--
		Air desktop dashboard for Attendance. Rendered only at `lg:` (and only mounted
		when the viewport is desktop-wide). Reuses the resources the mobile Attendance
		view uses (myAttendanceRequests / myShiftRequests / upcoming shifts from the
		parent) plus monthAttendance, the same source as the Home attendance tile.
	-->
	<div class="hidden max-w-[1180px] px-10 pb-[70px] pt-[34px] lg:block">
		<div class="air-rise mb-8">
			<h1 class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink">
				{{ __("Attendance") }}
			</h1>
			<p class="mt-2.5 text-base text-air-muted">{{ subline }}</p>
		</div>

		<!-- stat tiles -->
		<div class="mb-5 grid grid-cols-4 gap-5">
			<div
				v-for="(tile, i) in tiles"
				:key="tile.key"
				class="air-rise relative rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
				:style="{ '--air-delay': `${i * 70}ms` }"
			>
				<div class="mb-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
					{{ tile.label }}
				</div>
				<div
					class="font-display text-[38px] font-semibold leading-none tracking-[-0.04em] text-air-ink tabular-nums"
				>
					<template v-if="tile.available">
						<span>{{ tile.value }}</span
						><small v-if="tile.suffix" class="text-[15px] font-medium text-air-muted">{{
							tile.suffix
						}}</small>
					</template>
					<span v-else class="text-air-muted">&mdash;</span>
				</div>
				<div class="mt-2.5 text-[13px] text-air-muted">{{ tile.note }}</div>

				<!-- sparkline: worked hours across the most recent recorded days -->
				<svg
					v-if="tile.type === 'attendance'"
					class="mt-4 block overflow-visible"
					width="150"
					height="34"
					viewBox="0 0 150 34"
					preserveAspectRatio="none"
					aria-hidden="true"
				>
					<path
						v-if="sparkPath"
						:d="sparkPath"
						pathLength="1"
						fill="none"
						stroke="var(--air-blue)"
						stroke-width="2.4"
						stroke-linecap="round"
						stroke-linejoin="round"
						class="spark-line"
					/>
					<path
						v-else
						d="M0,28 L150,28"
						fill="none"
						stroke="var(--air-line)"
						stroke-width="2"
						stroke-dasharray="3 5"
						stroke-linecap="round"
					/>
				</svg>
			</div>
		</div>

		<!-- actions -->
		<div class="air-rise mb-7 flex flex-wrap items-center gap-3" style="--air-delay: 280ms">
			<router-link
				:to="{ name: 'AttendanceRequestFormView' }"
				class="rounded-full bg-air-ink px-5 py-2.5 text-[14px] font-semibold text-white transition ease-air hover:bg-air-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue focus-visible:ring-offset-2"
			>
				{{ __("Request attendance") }}
			</router-link>
			<router-link
				:to="{ name: 'TimesheetView' }"
				class="rounded-full border border-air-line bg-air-surface px-5 py-2.5 text-[14px] font-semibold text-air-ink transition ease-air hover:bg-air-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
			>
				{{ __("View timesheet") }}
			</router-link>
			<router-link
				:to="{ name: 'ShiftRequestFormView' }"
				class="rounded-full border border-air-line bg-air-surface px-5 py-2.5 text-[14px] font-semibold text-air-ink transition ease-air hover:bg-air-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
			>
				{{ __("Request a shift") }}
			</router-link>
		</div>

		<!-- sections -->
		<div class="grid grid-cols-[1.4fr_1fr] items-start gap-5">
			<div v-for="(column, c) in columns" :key="c" class="flex min-w-0 flex-col gap-5">
				<div
					v-for="(section, s) in column"
					:key="section.key"
					class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
					:style="{ '--air-delay': `${350 + (c + s * 2) * 70}ms` }"
				>
					<div class="mb-1.5 flex items-center justify-between">
						<h3 class="font-display text-base font-semibold text-air-ink">{{ section.title }}</h3>
						<router-link
							:to="{ name: section.route }"
							class="text-[13.5px] font-medium text-air-blue hover:underline"
						>
							{{ __("View all") }}
						</router-link>
					</div>

					<template v-if="section.rows.length">
						<div
							v-for="row in section.rows"
							:key="row.key"
							class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0"
						>
							<div
								class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink-2"
							>
								<FeatherIcon :name="section.icon" class="h-[17px] w-[17px]" />
							</div>
							<div class="min-w-0">
								<b class="block truncate text-sm font-semibold text-air-ink">{{ row.title }}</b>
								<small class="block truncate text-[12.5px] text-air-muted">{{ row.subtitle }}</small>
							</div>
							<div class="ml-auto shrink-0">
								<span
									v-if="row.timing"
									class="text-sm font-medium tabular-nums text-air-ink-2"
									>{{ row.timing }}</span
								>
								<span
									v-else-if="row.statusText"
									class="whitespace-nowrap rounded-full px-[11px] py-1 text-xs font-semibold"
									:class="pillClass[row.state]"
								>
									{{ row.statusText }}
								</span>
							</div>
						</div>
					</template>
					<div v-else class="py-10 text-center text-sm text-air-muted">
						{{ section.loading ? __("Loading...") : section.empty }}
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"
import { FeatherIcon } from "frappe-ui"

import {
	monthAttendance,
	myAttendanceRequests,
	myShiftRequests,
	getDates,
	getTotalDays,
	getShiftDates,
	getTotalShiftDays,
} from "@/data/attendance"
import { useCountUp } from "@/composables/useCountUp"

const props = defineProps({
	// Upcoming shifts computed by the Attendance view (single hrms.api.get_shifts fetch).
	upcomingShifts: { type: Array, default: () => [] },
	shiftsLoading: { type: Boolean, default: false },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")

onMounted(() => monthAttendance.fetch())

const monthLabel = computed(() => dayjs().format("MMM"))

// ---- This month (hrms.api.get_attendance_timesheet via monthAttendance) ----
const stats = computed(() => {
	const rows = monthAttendance.data || []
	const count = (re) => rows.filter((r) => re.test(r.status || "")).length
	const present = count(/^(Present|Work From Home)$/)
	const half = count(/^Half Day$/)
	const absent = count(/^Absent$/)
	const counted = present + half + absent
	const hours = rows.reduce((n, r) => n + (Number(r.working_hours) || 0), 0)
	const hoursDays = rows.filter((r) => Number(r.working_hours) > 0).length
	return {
		counted,
		daysPresent: present + half,
		absent,
		pct: counted ? ((present + half * 0.5) / counted) * 100 : null,
		hours,
		avgHours: hoursDays ? hours / hoursDays : 0,
	}
})

const subline = computed(() => {
	if (!stats.value.counted)
		return monthAttendance.loading ? __("Loading...") : __("No attendance records this month yet.")
	return stats.value.absent
		? __("{0} days present · {1} absent this month", [stats.value.daysPresent, stats.value.absent])
		: __("{0} days present this month", [stats.value.daysPresent])
})

// Pending = attendance requests still in Draft + shift requests still Open (docstatus 0).
const pendingCount = computed(
	() =>
		[...(myAttendanceRequests.data || []), ...(myShiftRequests.data || [])].filter((r) => !r.docstatus)
			.length
)

const pctShown = useCountUp(() => stats.value.pct)
const presentShown = useCountUp(() => stats.value.daysPresent)
const hoursShown = useCountUp(() => stats.value.hours)
const pendingShown = useCountUp(pendingCount)

const tiles = computed(() => {
	const has = stats.value.counted > 0
	const emptyNote = monthAttendance.loading ? __("Loading...") : __("No records this month")
	return [
		{
			key: "pct",
			type: "attendance",
			label: `${__("Attendance")} · ${monthLabel.value}`,
			available: has,
			value: Math.round(pctShown.value),
			suffix: "%",
			note: has ? __("{0} recorded days", [stats.value.counted]) : emptyNote,
		},
		{
			key: "present",
			type: "present",
			label: __("Days present"),
			available: has,
			value: Math.round(presentShown.value),
			note: has
				? stats.value.absent
					? __("{0} absent", [stats.value.absent])
					: __("No absences")
				: emptyNote,
		},
		{
			key: "hours",
			type: "hours",
			label: __("Hours worked"),
			available: stats.value.hours > 0,
			value: hoursShown.value.toFixed(1),
			suffix: " h",
			note:
				stats.value.hours > 0
					? __("{0} h average per day", [stats.value.avgHours.toFixed(1)])
					: emptyNote,
		},
		{
			key: "pending",
			type: "pending",
			label: __("Pending"),
			available: true,
			value: Math.round(pendingShown.value),
			note: pendingCount.value ? __("Awaiting approval") : __("Nothing waiting"),
		},
	]
})

// Sparkline = worked hours per day for the last ~8 recorded days (oldest -> newest).
const sparkPath = computed(() => {
	const pts = (monthAttendance.data || [])
		.filter((r) => Number(r.working_hours) > 0)
		.sort((a, b) => String(a.attendance_date).localeCompare(String(b.attendance_date)))
		.slice(-8)
		.map((r) => Number(r.working_hours))
	if (pts.length < 2) return ""
	const max = Math.max(...pts)
	const min = Math.min(...pts)
	const span = max - min || 1
	return pts
		.map((v, i) => {
			const x = (i / (pts.length - 1)) * 150
			const y = 29 - ((v - min) / span) * 24
			return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`
		})
		.join(" ")
})

// ---- Lists ----
const pillClass = {
	pending: "bg-air-warn-w text-air-warn",
	approved: "bg-air-good-w text-air-good",
	rejected: "bg-air-crit-w text-air-crit",
}

const withDays = (dates, days) => (days > 0 ? `${dates} · ${__("{0}d", [days])}` : dates)

const attendanceRows = computed(() =>
	(myAttendanceRequests.data || []).slice(0, 5).map((r) => ({
		key: r.name,
		title: r.reason || __("Attendance Request"),
		subtitle: withDays(r.attendance_dates || getDates(r), r.total_attendance_days ?? getTotalDays(r)),
		// Attendance requests have no status field: docstatus only.
		state: r.docstatus ? "approved" : "pending",
		statusText: r.docstatus ? __("Submitted") : __("Draft"),
	}))
)

const shiftRequestRows = computed(() =>
	(myShiftRequests.data || []).slice(0, 5).map((r) => {
		const status = r.docstatus ? r.status : "Open"
		return {
			key: r.name,
			title: r.shift_type,
			subtitle: withDays(r.shift_dates || getDates(r), r.to_date ? r.total_shift_days ?? getTotalDays(r) : 0),
			state: /reject|cancel/i.test(status) ? "rejected" : /approv/i.test(status) ? "approved" : "pending",
			statusText: __(status),
		}
	})
)

const upcomingRows = computed(() =>
	(props.upcomingShifts || []).map((s) => ({
		key: s.name,
		title: s.shift_type,
		subtitle: withDays(
			s.shift_dates || getShiftDates(s),
			s.end_date ? s.total_shift_days ?? getTotalShiftDays(s) : 0
		),
		timing: s.shift_timing,
	}))
)

const loadingRequests = (r) => !!r.loading && !r.data

const columns = computed(() => [
	[
		{
			key: "attendance-requests",
			title: __("Recent attendance requests"),
			route: "AttendanceRequestListView",
			icon: "check-circle",
			rows: attendanceRows.value,
			loading: loadingRequests(myAttendanceRequests),
			empty: __("You have no attendance requests"),
		},
		{
			key: "shift-requests",
			title: __("Recent shift requests"),
			route: "ShiftRequestListView",
			icon: "clock",
			rows: shiftRequestRows.value,
			loading: loadingRequests(myShiftRequests),
			empty: __("You have no shift requests"),
		},
	],
	[
		{
			key: "upcoming-shifts",
			title: __("Upcoming shifts"),
			route: "ShiftAssignmentListView",
			icon: "calendar",
			rows: upcomingRows.value,
			loading: props.shiftsLoading && !props.upcomingShifts?.length,
			empty: __("You have no upcoming shifts"),
		},
	],
])
</script>

<style scoped>
.spark-line {
	stroke-dasharray: 1;
	stroke-dashoffset: 1;
	animation: air-draw 1.7s cubic-bezier(0.16, 1, 0.3, 1) 0.15s forwards;
}
@media (prefers-reduced-motion: reduce) {
	.spark-line {
		animation: none;
		stroke-dashoffset: 0;
	}
}
</style>
