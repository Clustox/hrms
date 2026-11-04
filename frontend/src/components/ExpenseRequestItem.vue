<template>
	<ListItem
		:isTeamRequest="props.isTeamRequest"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<ExpenseIcon class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800">
					{{ __(props.doc.expense_type) }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span>{{ dayjs(props.doc.creation).format("D MMM") }}</span>
					<span class="whitespace-pre"> &middot; </span>
					<span class="whitespace-nowrap">
						{{ formatCurrency(props.doc.amount, props.doc.currency) }}
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge variant="outline" :theme="statusMap[status] || 'gray'" :label="__(status)" size="md" />
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { FeatherIcon, Badge } from "frappe-ui"
import { computed, inject } from "vue"

import ListItem from "@/components/ListItem.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"

import { formatCurrency } from "@/utils/formatters"

const dayjs = inject("$dayjs")
const __ = inject("$translate")
const props = defineProps({
	doc: {
		type: Object,
	},
	isTeamRequest: {
		type: Boolean,
		default: false,
	},
	workflowStateField: {
		type: String,
		required: false,
	},
})

const statusMap = {
	Draft: "gray",
	"Pending Manager": "orange",
	"Pending HR": "orange",
	"Pending Accounts": "orange",
	Completed: "green",
	Rejected: "red",
	Cancelled: "gray",
}

const status = computed(() => props.doc.workflow_state || "Draft")
</script>
