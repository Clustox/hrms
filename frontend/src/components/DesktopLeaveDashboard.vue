<template>
	<!--
		Air desktop dashboard for Leaves & holidays. Rendered only at `lg:` (and only
		mounted when the viewport is desktop-wide). Reuses the same resources as the
		mobile Leaves view: leaveBalance / myLeaves (data/leaves) and the holidays
		endpoint via UpcomingHolidays.
	-->
	<div class="hidden max-w-[1180px] px-10 pb-[70px] pt-[34px] lg:block">
		<div class="air-rise mb-8 flex items-end justify-between gap-6">
			<div>
				<h1 class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink">
					{{ __("Leaves & holidays") }}
				</h1>
				<p class="mt-2.5 text-base text-air-muted">{{ subline }}</p>
			</div>
			<router-link
				:to="{ name: 'LeaveApplicationFormView' }"
				class="shrink-0 rounded-full bg-air-ink px-5 py-2.5 text-[14px] font-semibold text-white transition ease-air hover:bg-air-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue focus-visible:ring-offset-2"
			>
				{{ __("Request a leave") }}
			</router-link>
		</div>

		<!-- leave balance cards -->
		<div v-if="cards.length" class="mb-7 grid grid-cols-4 gap-5">
			<div
				v-for="(card, i) in cards"
				:key="card.key"
				class="air-rise relative rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
				:style="{ '--air-delay': `${Math.min(i, 8) * 70}ms` }"
			>
				<div
					class="mb-4 truncate pr-14 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted"
				>
					{{ card.label }}
				</div>
				<div
					class="font-display text-[38px] font-semibold leading-none tracking-[-0.04em] text-air-ink tabular-nums"
				>
					<span>{{ shownValue(card) }}</span
					><small class="text-[15px] font-medium text-air-muted">{{ card.suffix }}</small>
				</div>
				<div class="mt-2.5 text-[13px] text-air-muted">{{ card.note }}</div>

				<svg
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
						:stroke-dashoffset="armed ? RING * (1 - card.pct) : RING"
						class="transition-[stroke-dashoffset] duration-[1400ms] ease-air motion-reduce:transition-none"
					/>
				</svg>
			</div>
		</div>
		<div
			v-else
			class="air-rise mb-7 rounded-air border border-air-line bg-air-surface p-[22px] text-center text-sm text-air-muted shadow-air"
		>
			{{ leaveBalance.loading ? __("Loading...") : __("You have no leaves allocated") }}
		</div>

		<div class="grid grid-cols-[1.4fr_1fr] gap-5">
			<!-- recent leaves -->
			<div
				class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
				style="--air-delay: 420ms"
			>
				<div class="mb-1.5 flex items-center justify-between">
					<h3 class="font-display text-base font-semibold text-air-ink">{{ __("Recent leaves") }}</h3>
					<router-link
						:to="{ name: 'LeaveApplicationListView' }"
						class="text-[13.5px] font-medium text-air-blue hover:underline"
					>
						{{ __("View all") }}
					</router-link>
				</div>

				<template v-if="recentLeaves.length">
					<div
						v-for="leave in recentLeaves"
						:key="leave.key"
						class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0"
					>
						<div
							class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink-2"
						>
							<FeatherIcon name="calendar" class="h-[17px] w-[17px]" />
						</div>
						<div class="min-w-0">
							<b class="block truncate text-sm font-semibold text-air-ink">{{ leave.title }}</b>
							<small class="block truncate text-[12.5px] text-air-muted">{{ leave.subtitle }}</small>
						</div>
						<span
							class="ml-auto shrink-0 whitespace-nowrap rounded-full px-[11px] py-1 text-xs font-semibold"
							:class="pillClass[leave.state]"
						>
							{{ leave.statusText }}
						</span>
					</div>
				</template>
				<div v-else class="py-10 text-center text-sm text-air-muted">
					{{ myLeaves.loading && !myLeaves.data ? __("Loading...") : __("You have no leaves") }}
				</div>
			</div>

			<UpcomingHolidays />
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { FeatherIcon } from "frappe-ui"

import UpcomingHolidays from "@/components/UpcomingHolidays.vue"

import { leaveBalance, myLeaves, getLeaveDates } from "@/data/leaves"
import { useCountUp } from "@/composables/useCountUp"

const __ = inject("$translate")

const RING = 2 * Math.PI * 21 // circumference of the r=21 ring

const num = (v) => (Number.isInteger(v) ? v : Number(v).toFixed(1))

// ---- Balance cards: one per allocated leave type (hrms.api.get_leave_balance_map) ----
const cards = computed(() =>
	Object.entries(leaveBalance.data || {})
		.map(([type, a]) => {
			const total = Number(a.allocated_leaves) || 0
			const remaining = Number(a.balance_leaves) || 0
			return {
				key: type,
				label: __(type, null, "Leave Type"),
				remaining,
				total,
				suffix: ` / ${num(total)}`,
				pct: total ? Math.max(0, Math.min(1, remaining / total)) : 0,
				note: __("{0} days used", [num(Math.max(0, total - remaining))]),
			}
		})
		.filter((c) => c.total > 0)
)

// One 0 -> 1 roll-up drives every card's number, however many leave types the
// site has (composables can't be called per-row).
const rollup = useCountUp(() => (cards.value.length ? 1 : 0))
const shownValue = (card) => {
	const v = card.remaining * rollup.value
	return Number.isInteger(card.remaining) ? Math.round(v) : v.toFixed(1)
}

// Rings start empty and fill once the cards exist (CSS transition; disabled for reduced motion).
const armed = ref(false)
watch(
	() => cards.value.length,
	(n) => {
		if (n && !armed.value)
			requestAnimationFrame(() => requestAnimationFrame(() => (armed.value = true)))
	},
	{ immediate: true }
)

const totalRemaining = computed(() => cards.value.reduce((n, c) => n + c.remaining, 0))
const subline = computed(() => {
	if (!cards.value.length) return leaveBalance.loading ? __("Loading...") : __("You have no leaves allocated")
	return __("{0} days of leave remaining across {1} leave types", [
		num(totalRemaining.value),
		cards.value.length,
	])
})

// ---- Recent leaves (hrms.api.get_leave_applications via data/leaves) ----
function bucket(status) {
	if (/reject|cancel/i.test(status || "")) return "rejected"
	if (/approv/i.test(status || "")) return "approved"
	return "pending"
}

const pillClass = {
	pending: "bg-air-warn-w text-air-warn",
	approved: "bg-air-good-w text-air-good",
	rejected: "bg-air-crit-w text-air-crit",
}

const recentLeaves = computed(() =>
	(myLeaves.data || []).slice(0, 6).map((leave) => {
		const label = leave.status === "Open" ? "Pending" : leave.status
		return {
			key: leave.name,
			title: __(leave.leave_type, null, "Leave Type"),
			subtitle: `${leave.leave_dates || getLeaveDates(leave)} · ${__("{0}d", [leave.total_leave_days])}`,
			state: bucket(leave.status),
			statusText: __(label, null, "Leave Application"),
		}
	})
)
</script>
