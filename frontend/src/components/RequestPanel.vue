<template>
	<div class="w-full">
		<TabButtons
			:buttons="TAB_BUTTONS"
			v-model="activeTab"
		/>
		<RequestList v-if="activeTab == 'My Requests'" :items="myRequests" />
		<RequestList
			v-else-if="activeTab == 'Team Requests'"
			:items="teamRequests"
			:teamRequests="true"
		/>
	</div>
</template>

<script setup>
import { ref, inject, onMounted, computed, markRaw } from "vue"

import TabButtons from "@/components/TabButtons.vue"
import RequestList from "@/components/RequestList.vue"

import { myAttendanceRequests, myShiftRequests, teamShiftRequests, teamAttendanceRequests } from "@/data/attendance"
import { myExpenseRequests, teamExpenseRequests } from "@/data/expense_requests"
import { myLeaves, teamLeaves } from "@/data/leaves"

import AttendanceRequestItem from "@/components/AttendanceRequestItem.vue"
import ExpenseRequestItem from "@/components/ExpenseRequestItem.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ShiftRequestItem from "@/components/ShiftRequestItem.vue"

import { useListUpdate } from "@/composables/realtime"

const activeTab = ref("My Requests")
const socket = inject("$socket")

const TAB_BUTTONS = ["My Requests", "Team Requests"] // __("My Requests"), __("Team Requests")

const myRequests = computed(() =>
	updateRequestDetails(myLeaves, myExpenseRequests, myShiftRequests, myAttendanceRequests)
)

const teamRequests = computed(() =>
	updateRequestDetails(teamLeaves, teamExpenseRequests, teamShiftRequests, teamAttendanceRequests)
)

function updateRequestDetails(leaves, expenseRequests, shiftRequests, attendanceRequests) {
	const requests = [leaves, expenseRequests, shiftRequests, attendanceRequests].reduce(
		(acc, resource) => acc.concat(resource?.data || []),
		[]
	)

	const componentMap = {
		"Leave Application": LeaveRequestItem,
		"Expense Request": ExpenseRequestItem,
		"Shift Request": ShiftRequestItem,
		"Attendance Request": AttendanceRequestItem,
	}
	requests.forEach((request) => {
		request.component = markRaw(componentMap[request.doctype])
	})

	return getSortedRequests(requests)
}

function getSortedRequests(list) {
	// return top 10 requests sorted by posting date
	return list
		.sort((a, b) => {
			return new Date(b.creation) - new Date(a.creation)
		})
		.splice(0, 10)
}

onMounted(() => {
	useListUpdate(socket, "Leave Application", () => teamLeaves.reload())
	useListUpdate(socket, "Expense Request", () => teamExpenseRequests.reload())
	useListUpdate(socket, "Shift Request", () => teamShiftRequests.reload())
	useListUpdate(socket, "Attendance Request", () => teamAttendanceRequests.reload())
})
</script>
