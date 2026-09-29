<template>
	<!-- Air desktop dashboard: stat tiles (annual leave ring, attendance sparkline, sick ring, pending) -->
	<div class="grid grid-cols-4 gap-5">
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

			<!-- leave ring -->
			<svg
				v-if="tile.type === 'leave' && tile.available"
				class="absolute right-[18px] top-[18px]"
				width="50"
				height="50"
				viewBox="0 0 50 50"
				aria-hidden="true"
			>
				<circle cx="25" cy="25" r="21" fill="none" stroke="var(--air-surface-2)" stroke-width="6" />
				<circle
					cx="25"
					cy="25"
					r="21"
					fill="none"
					stroke="var(--air-blue)"
					stroke-width="6"
					stroke-linecap="round"
					transform="rotate(-90 25 25)"
					:stroke-dasharray="RING"
					:stroke-dashoffset="armed ? RING * (1 - tile.pct) : RING"
					class="transition-[stroke-dashoffset] duration-[1400ms] ease-air motion-reduce:transition-none"
				/>
			</svg>

			<!-- attendance sparkline: worked hours across the most recent recorded days -->
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
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"

import { leaveBalance } from "@/data/leaves"
import { monthAttendance } from "@/data/attendance"
import { useCountUp } from "@/composables/useCountUp"

const props = defineProps({
	pendingCount: { type: Number, default: 0 },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const RING = 2 * Math.PI * 21 // circumference of the r=21 ring

// Rings start empty and fill once mounted (CSS transition; disabled for reduced motion).
const armed = ref(false)
onMounted(() => requestAnimationFrame(() => requestAnimationFrame(() => (armed.value = true))))

const monthLabel = computed(() => dayjs().format("MMM"))

// ---- Leave tiles (real data: hrms.api.get_leave_balance_map via data/leaves) ----
// Leave types are site-configured, so match by name: annual-ish for the first
// tile, sick for the second.
function findType(map, patterns, exclude = []) {
	const keys = Object.keys(map || {}).filter((k) => !exclude.includes(k))
	for (const p of patterns) {
		const hit = keys.find((k) => p.test(k))
		if (hit) return hit
	}
	return null
}

const annualKey = computed(() =>
	findType(leaveBalance.data, [/annual/i, /casual/i, /earned/i, /privilege/i, /vacation/i])
)
const sickKey = computed(() => findType(leaveBalance.data, [/sick/i], [annualKey.value]))

function remaining(key) {
	const a = key && leaveBalance.data?.[key]
	return a ? Number(a.balance_leaves) || 0 : 0
}

const annualRemaining = computed(() => remaining(annualKey.value))
const sickRemaining = computed(() => remaining(sickKey.value))
const annualShown = useCountUp(annualRemaining)
const sickShown = useCountUp(sickRemaining)

const num = (v) => (Number.isInteger(v) ? v : Number(v).toFixed(1))

function leaveTile(key, target, shownVal, fallbackLabel, idx) {
	const a = key && leaveBalance.data?.[key]
	const total = a ? Number(a.allocated_leaves) || 0 : 0
	const label = key ? __(key, null, "Leave Type") : fallbackLabel
	if (!a || !total) {
		return {
			key: `leave-${idx}`,
			type: "leave",
			label,
			available: false,
			note: leaveBalance.loading ? __("Loading...") : __("Not allocated"),
		}
	}
	return {
		key: `leave-${idx}`,
		type: "leave",
		label,
		available: true,
		value: Number.isInteger(target) ? Math.round(shownVal) : shownVal.toFixed(1),
		suffix: ` / ${num(total)}`,
		pct: Math.max(0, Math.min(1, target / total)),
		note: __("{0} days used", [num(total - target)]),
	}
}

// ---- Attendance (real data: hrms.api.get_attendance_timesheet, this month) ----
const attendance = computed(() => {
	const rows = monthAttendance.data || []
	const count = (re) => rows.filter((r) => re.test(r.status || "")).length
	const present = count(/^(Present|Work From Home)$/)
	const half = count(/^Half Day$/)
	const absent = count(/^Absent$/)
	const counted = present + half + absent
	if (!counted) {
		return {
			pct: null,
			note: monthAttendance.loading ? __("Loading...") : __("No records this month"),
		}
	}
	return {
		pct: ((present + half * 0.5) / counted) * 100,
		note: absent
			? __("{0} present · {1} absent", [present + half, absent])
			: __("{0} days present", [present + half]),
	}
})
const attendanceShown = useCountUp(() => attendance.value.pct)

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

// ---- Pending (count computed by the parent from the my-requests resources) ----
const pendingShown = useCountUp(() => props.pendingCount)

// Row order matches the Air mock: annual | attendance | sick | pending
const tiles = computed(() => [
	leaveTile(annualKey.value, annualRemaining.value, annualShown.value, __("Annual leave"), 0),
	{
		key: "attendance",
		type: "attendance",
		label: `${__("Attendance")} · ${monthLabel.value}`,
		available: attendance.value.pct != null,
		value: Math.round(attendanceShown.value),
		suffix: "%",
		note: attendance.value.note,
	},
	leaveTile(sickKey.value, sickRemaining.value, sickShown.value, __("Sick leave"), 1),
	{
		key: "pending",
		type: "pending",
		label: __("Pending"),
		available: true,
		value: Math.round(pendingShown.value),
		note: props.pendingCount ? __("Awaiting approval") : __("Nothing waiting"),
	},
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
