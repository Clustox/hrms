<template>
	<!-- Every routed view needs an ion-page root, or Ionic does not refresh it on navigation. -->
	<ion-page>
	<!-- Air desktop shell (sidebar + topbar); hidden on mobile. -->
	<DesktopShell />

	<ion-header class="ion-no-border lg:hidden">
		<div class="w-full sm:w-96">
			<div class="flex flex-row bg-white shadow-sm py-4 px-3 items-center border-b">
				<Button variant="ghost" class="!px-1 mr-1 hover:bg-white" @click="goBack">
					<FeatherIcon name="chevron-left" class="h-5 w-5" />
				</Button>
				<h2 class="text-xl font-semibold text-gray-900">{{ __("Job Requisition") }}</h2>
			</div>
		</div>
	</ion-header>

	<ion-content>
		<div
			class="flex flex-col items-center mb-7 p-4 h-full w-full sm:w-96 overflow-y-auto lg:w-full lg:pl-[250px] lg:pt-[68px] lg:pb-16 lg:bg-air-bg"
		>
			<div class="w-full lg:max-w-[920px] lg:px-6">
				<div class="hidden lg:flex lg:items-center lg:gap-3 lg:pt-[26px] lg:pb-1">
					<button
						class="flex h-9 w-9 items-center justify-center rounded-full border border-air-line bg-air-surface text-air-ink-2 hover:text-air-blue"
						:aria-label="__('Back')"
						@click="goBack"
					>
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</button>
					<h1 class="font-display text-[28px] font-bold tracking-[-0.02em] text-air-ink">
						{{ __("Job Requisition") }}
					</h1>
				</div>

				<div v-if="requisition.loading && !doc" class="mt-6 flex items-center justify-center">
					<LoadingIndicator class="w-8 h-8 text-gray-800" />
				</div>

				<template v-if="doc">
					<div class="mt-5 flex flex-col gap-5 rounded bg-white p-4 lg:rounded-air lg:border lg:border-air-line lg:p-6">
						<div class="flex items-start justify-between gap-3">
							<div class="flex flex-col gap-1">
								<div class="text-xl font-semibold text-gray-900">{{ doc.designation }}</div>
								<div class="text-sm text-gray-500">{{ doc.name }}</div>
							</div>
							<Badge
								variant="outline"
								:theme="statusTheme[doc.status] || 'gray'"
								:label="statusLabel[doc.status] || doc.status"
								size="md"
							/>
						</div>

						<!-- Rejection: the reason the approver gave, kept prominent at the top -->
						<div
							v-if="doc.status === 'Rejected' && doc.rejection_reason"
							class="flex gap-3 rounded border border-red-200 border-l-4 border-l-red-500 bg-red-50 p-3.5"
							role="alert"
						>
							<FeatherIcon name="alert-circle" class="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
							<div class="flex flex-col gap-0.5">
								<div class="text-sm font-semibold text-red-700">{{ __("Reason for rejection") }}</div>
								<div class="text-sm text-red-900 whitespace-pre-line">{{ doc.rejection_reason }}</div>
							</div>
						</div>

						<!-- On hold: the reason the approver gave -->
						<div
							v-if="doc.status === 'On Hold' && doc.hold_reason"
							class="flex gap-3 rounded border border-amber-200 border-l-4 border-l-amber-500 bg-amber-50 p-3.5"
							role="status"
						>
							<FeatherIcon name="pause-circle" class="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
							<div class="flex flex-col gap-0.5">
								<div class="text-sm font-semibold text-amber-700">{{ __("Reason for hold") }}</div>
								<div class="text-sm text-amber-900 whitespace-pre-line">{{ doc.hold_reason }}</div>
							</div>
						</div>

						<dl class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
							<div v-for="item in details" :key="item.label" class="flex flex-col gap-0.5">
								<dt class="text-xs text-gray-500">{{ item.label }}</dt>
								<dd class="text-sm text-gray-900 whitespace-pre-line">{{ item.value }}</dd>
							</div>
						</dl>

						<div v-if="doc.reason_for_requesting" class="flex flex-col gap-0.5">
							<div class="text-xs text-gray-500">{{ __("Reason for Requesting") }}</div>
							<div class="text-sm text-gray-900 whitespace-pre-line">{{ doc.reason_for_requesting }}</div>
						</div>

						<div class="flex flex-col gap-1.5">
							<div class="text-xs text-gray-500">{{ __("Job Description") }}</div>
							<!-- Formatted text; the server cleans it when the request is saved. -->
							<div class="prose-sm max-w-none rounded border border-gray-200 p-3" v-html="doc.description"></div>
						</div>

					</div>
				</template>
			</div>
		</div>
	</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonHeader, IonContent, onIonViewWillEnter } from "@ionic/vue"
import { Badge, Button, FeatherIcon, LoadingIndicator, createResource } from "frappe-ui"

import DesktopShell from "@/components/DesktopShell.vue"

const props = defineProps({ id: { type: String, required: true } })

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

const statusTheme = {
	Pending: "orange",
	"Open & Approved": "green",
	Rejected: "red",
	Filled: "blue",
	"On Hold": "gray",
	Cancelled: "gray",
}
const statusLabel = {
	"Open & Approved": __("Approved"),
	Pending: __("Pending"),
	Rejected: __("Rejected"),
	Filled: __("Filled"),
	"On Hold": __("On Hold"),
	Cancelled: __("Cancelled"),
}

// frappe.client.get leaves out the fields the current user may not read, so the approved
// salary range is never sent to a requester.
const requisition = createResource({
	url: "frappe.client.get",
	makeParams: () => ({ doctype: "Job Requisition", name: props.id }),
	auto: true,
})
const doc = computed(() => requisition.data)
onIonViewWillEnter(() => requisition.reload())

const details = computed(() => {
	const d = doc.value
	if (!d) return []
	return [
		{ label: __("Department"), value: d.department },
		{ label: __("Number of Positions"), value: d.no_of_positions },
		{
			label: __("Requested by"),
			value: [d.requested_by_name, d.requested_by_dept].filter(Boolean).join(" · "),
		},
		{ label: __("Requested on"), value: dayjs(d.creation).format("D MMM YYYY") },
		{ label: __("Needed By Date"), value: d.expected_by ? dayjs(d.expected_by).format("D MMM YYYY") : "" },
	].filter((item) => item.value)
})

function goBack() {
	router.back()
}
</script>
