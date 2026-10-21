<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
		>
		<template #left>
			<AttendanceIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800">
					{{ props.doc.reason }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ props.doc.attendance_dates || getDates(props.doc) }}</span>
					<span v-if="getTotalDays(props.doc) > 0">
						<span class="whitespace-pre"> &middot; </span>
						<span class="whitespace-nowrap">{{ __("{0}d", [getTotalDays(props.doc)]) }}</span>
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge variant="outline" :theme="colorMap[status]" :label="__(status)" size="md" />
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed } from "vue"
import { Badge, FeatherIcon } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import AttendanceIcon from "@/components/icons/AttendanceIcon.vue"
import { getDates, getTotalDays } from "@/data/attendance"

const props = defineProps({
	doc: {
		type: Object,
	},
	workflowStateField: {
		type: String,
		required: false,
	},
})

const status = computed(() => {
	if (props.workflowStateField) return props.doc[props.workflowStateField]
	// A Work From Home / On Duty request carries its own Pending/Approved/
	// Rejected/Cancelled status; a punch request (fixing a missed check-in/
	// out) doesn't really use that field -- it still defaults to "Pending"
	// at the schema level, so checking `reason` too (not just truthiness)
	// keeps it on the plain Draft/Submitted reading it actually means here.
	if (props.doc.status && props.doc.reason !== "Missed Punch") return props.doc.status
	return props.doc.docstatus ? "Submitted" : "Draft"
})

const colorMap = {
	Draft: "gray",
	Submitted: "blue",
	Pending: "orange",
	Approved: "green",
	Rejected: "red",
	Cancelled: "gray",
}
</script>
