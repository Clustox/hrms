<template>
	<div
		v-if="actions.length > 0"
		:class="[
			props.view === 'form'
				? 'px-4 pt-4 pb-4 standalone:pb-safe-bottom sm:w-96 bg-white sticky bottom-0 w-full drop-shadow-xl z-40 border-t rounded-t-lg lg:static lg:w-full lg:rounded-none lg:border-air-line-2 lg:bg-transparent lg:drop-shadow-none lg:px-7 lg:py-5'
				: 'flex w-full flex-row items-center justify-between gap-3 sticky bottom-0 border-t z-[100] p-4',
		]"
	>
		<!--
			Form view, 1-2 actions (the normal approval case): render the
			transitions as inline, colour-coded buttons so the approver taps
			Approve/Reject directly instead of opening the generic action sheet.
			Destructive actions sit on the left, the primary/positive action on
			the right.
		-->
		<div
			v-if="props.view === 'form' && actions.length <= 2"
			class="flex flex-row gap-3"
		>
			<Button
				v-for="action in orderedActions"
				:key="action.data.action"
				class="flex-1 rounded py-5 text-base font-medium lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
				:variant="action.variant"
				:theme="action.theme"
				:loading="applying === action.data.action"
				:disabled="applying !== null"
				@click="applyWorkflow({ workflowAction: action.data.action })"
			>
				<template #prefix v-if="action.featherIcon">
					<FeatherIcon :name="action.featherIcon" class="w-4" />
				</template>
				{{ action.text }}
			</Button>
		</div>

		<!-- 3+ actions (rare): fall back to the collapsed action sheet -->
		<Button
			v-else-if="props.view === 'form' || actions.length > 2"
			@click="showTransitions()"
			class="w-full rounded py-5 text-base disabled:bg-gray-700 disabled:text-white"
			variant="solid"
		>
			<template #prefix>
				<FeatherIcon name="chevron-up" class="w-4" />
			</template>
			{{ __("Actions") }}
		</Button>

		<template v-else>
			<Button
				v-for="action in actions"
				class="w-full py-5"
				:variant="action.variant"
				:theme="action.theme"
				@click="applyWorkflow({ workflowAction: action.text })"
			>
				<template #prefix v-if="action.featherIcon">
					<FeatherIcon :name="action.featherIcon" class="w-4" />
				</template>
				{{ __(action.text, null, props.doc?.doctype) }}
			</Button>
		</template>
	</div>

	<ion-action-sheet
		:buttons="actions"
		:is-open="showActionSheet"
		@didDismiss="applyWorkflow({ event: $event })"
	>
	</ion-action-sheet>
</template>

<script setup>
import { IonActionSheet, modalController } from "@ionic/vue"
import { computed, ref, onMounted, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
	workflow: {
		type: Object,
		required: false,
	},
	view: {
		type: String,
		default: "form",
		validator: (value) => ["form", "actionSheet"].includes(value),
	},
})

const emit = defineEmits(["workflow-applied"])

let showActionSheet = ref(false)
let actions = ref([])
// Name of the action currently being applied (for the inline button spinner),
// or null when idle. Doubles as a guard against double-taps.
const applying = ref(null)

const __ = inject("$translate")

// Map a transition name to its visual treatment and a sort rank. Rank orders
// the inline buttons left-to-right: destructive first, the positive/primary
// action last (conventional "confirm on the right").
const styleForAction = (label) => {
	const l = label.toLowerCase()
	if (l.includes("reject"))
		return { theme: "red", variant: "subtle", icon: "x", role: "destructive", rank: 0 }
	if (l.includes("cancel"))
		return { theme: "gray", variant: "subtle", icon: "slash", role: "", rank: 1 }
	if (l.includes("complete"))
		return { theme: "green", variant: "solid", icon: "check-circle", role: "", rank: 3 }
	if (l.includes("approve"))
		return { theme: "green", variant: "solid", icon: "check", role: "", rank: 3 }
	if (l.includes("submit"))
		return { theme: "gray", variant: "solid", icon: "send", role: "", rank: 3 }
	return { theme: "gray", variant: "solid", icon: "", role: "", rank: 2 }
}

const getTransitions = async () => {
	const transitions = await props.workflow.getTransitions(props.doc)
	actions.value = transitions.map((transition) => {
		const s = styleForAction(transition.toLowerCase())
		return {
			text: __(transition, null, props.doc?.doctype),
			role: s.role,
			theme: s.theme,
			variant: s.variant,
			featherIcon: s.icon,
			rank: s.rank,
			data: {
				action: transition,
			},
		}
	})
}

// Inline buttons, ordered destructive -> primary.
const orderedActions = computed(() =>
	[...actions.value].sort((a, b) => a.rank - b.rank)
)

const showTransitions = () => {
	if (actions.value?.length > 0) {
		// always add last action for dismissing the modal
		actions.value.push({
			text: __("Dismiss"),
			role: "cancel",
		})
	}

	showActionSheet.value = true
}

const applyWorkflow = async ({ event = "", workflowAction = "" }) => {
	const action = workflowAction || event.detail.data?.action
	if (action) {
		if (applying.value) return
		applying.value = action
		try {
			await props.workflow.applyWorkflow(props.doc, action)
			modalController.dismiss()
			emit("workflow-applied")
		} finally {
			applying.value = null
		}
	}

	showActionSheet.value = false
}

onMounted(() => getTransitions())
</script>

<style scoped>
ion-action-sheet {
	--button-color: var(--text-gray-500);
}
</style>
