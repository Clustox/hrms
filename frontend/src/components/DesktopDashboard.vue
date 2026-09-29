<template>
	<!--
		Air desktop dashboard for Home. Rendered only at `lg:` (and only mounted
		when the viewport is desktop-wide, so phones never fetch its extra data).
		All figures come from the same resources the mobile Home uses.
	-->
	<div class="hidden max-w-[1180px] px-10 pb-[70px] pt-[34px] lg:block">
		<div class="air-rise mb-8">
			<h1 class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink">
				{{ greeting }}
			</h1>
			<p class="mt-2.5 text-base text-air-muted">{{ subline }}</p>
		</div>

		<DesktopCheckin class="air-rise mb-5" :style="{ '--air-delay': '70ms' }" />

		<DashboardStats :pendingCount="pendingCount" class="mb-5" />

		<QuickActions :items="actions" :title="__('Quick actions')" class="mb-7" />

		<div class="grid grid-cols-[1.4fr_1fr] gap-5">
			<RecentRequests :items="recent" :loading="loading" />
			<UpcomingHolidays />
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"

import DesktopCheckin from "@/components/DesktopCheckin.vue"
import DashboardStats from "@/components/DashboardStats.vue"
import QuickActions from "@/components/QuickActions.vue"
import RecentRequests from "@/components/RecentRequests.vue"
import UpcomingHolidays from "@/components/UpcomingHolidays.vue"

import { monthAttendance } from "@/data/attendance"
import { useDashboardRequests } from "@/composables/useDashboardRequests"
import { formatCurrency } from "@/utils/formatters"

const props = defineProps({
	quickLinks: { type: Array, required: true },
})

// Same actions/routes as the mobile Quick Links list, ordered for the grid.
const ACTION_ORDER = [
	"LeaveApplicationFormView",
	"AttendanceRequestFormView",
	"ExpenseClaimFormView",
	"EmployeeAdvanceFormView",
	"ShiftRequestFormView",
	"SalarySlipsDashboard",
]
const actions = computed(() =>
	[...props.quickLinks].sort((a, b) => ACTION_ORDER.indexOf(a.route) - ACTION_ORDER.indexOf(b.route))
)

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

const { recent, pendingCount, teamPendingCount, loading } = useDashboardRequests(__, dayjs, formatCurrency)

const greeting = computed(() => {
	const h = dayjs().hour()
	const salutation = h < 12 ? __("Good morning") : h < 18 ? __("Good afternoon") : __("Good evening")
	const name = employee.data?.first_name
	return name ? `${salutation}, ${name}.` : `${salutation}.`
})

const subline = computed(() => {
	const parts = []
	if (pendingCount.value)
		parts.push(__("{0} of your requests are awaiting approval", [pendingCount.value]))
	if (teamPendingCount.value)
		parts.push(__("{0} team requests need your review", [teamPendingCount.value]))
	return parts.length ? parts.join(" · ") : __("You're all caught up.")
})

onMounted(() => monthAttendance.fetch())
</script>
