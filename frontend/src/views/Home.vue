<template>
	<BaseLayout>
		<template #body>
			<!-- Mobile Home (unchanged): hidden once the desktop dashboard takes over at lg -->
			<div class="flex flex-col items-center my-7 p-4 gap-7 lg:hidden">
				<CheckInPanel />
				<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
				<RequestPanel />
			</div>

			<!-- Air desktop dashboard (lg+ only; mounted only on wide viewports) -->
			<DesktopDashboard v-if="isDesktop" :quickLinks="quickLinks" />
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, markRaw, ref, onMounted, onBeforeUnmount } from "vue"

import CheckInPanel from "@/components/CheckInPanel.vue"
import QuickLinks from "@/components/QuickLinks.vue"
import BaseLayout from "@/components/BaseLayout.vue"
import RequestPanel from "@/components/RequestPanel.vue"
import DesktopDashboard from "@/components/DesktopDashboard.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import ShiftIcon from "@/components/icons/ShiftIcon.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"

const __ = inject("$translate")

// Mirror Tailwind's `lg` breakpoint so the desktop dashboard (and its extra
// data fetching) is only mounted on wide viewports.
const desktopQuery = window.matchMedia("(min-width: 1024px)")
const isDesktop = ref(desktopQuery.matches)
const onQueryChange = (e) => (isDesktop.value = e.matches)
onMounted(() => desktopQuery.addEventListener("change", onQueryChange))
onBeforeUnmount(() => desktopQuery.removeEventListener("change", onQueryChange))

const quickLinks = [
	{
		icon: markRaw(AttendanceIcon),
		title: __("Request Attendance"),
		description: __("Fix a missed punch"),
		route: "AttendanceRequestFormView",
	},
	{
		icon: markRaw(ShiftIcon),
		title: __("Request a Shift"),
		description: __("Change roster"),
		route: "ShiftRequestFormView",
	},
	{
		icon: markRaw(LeaveIcon),
		title: __("Request Leave"),
		description: __("Apply for time off"),
		route: "LeaveApplicationFormView",
	},
	{
		icon: markRaw(ExpenseIcon),
		title: __("Claim an Expense"),
		description: __("Reimbursements"),
		route: "ExpenseClaimFormView",
	},
	{
		icon: markRaw(EmployeeAdvanceIcon),
		title: __("Request an Advance"),
		description: __("Salary advance"),
		route: "EmployeeAdvanceFormView",
	},
	{
		icon: markRaw(SalaryIcon),
		title: __("View Salary Slips"),
		description: __("Payslips & tax"),
		route: "SalarySlipsDashboard",
	},
]
</script>
