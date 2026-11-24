<template>
	<!-- Every routed view needs an ion-page root, or Ionic does not refresh it on navigation. -->
	<ion-page>
	<!-- Air desktop shell (sidebar + topbar); hidden on mobile. -->
	<DesktopShell />

	<ion-header class="ion-no-border lg:hidden">
		<div class="w-full sm:w-96">
			<div class="flex flex-row bg-white shadow-sm py-4 px-3 items-center border-b">
				<Button variant="ghost" class="!px-1 mr-1 hover:bg-white" @click="router.back()">
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
				<div class="hidden lg:block lg:pt-[26px] lg:pb-1">
					<h1 class="font-display text-[28px] font-bold tracking-[-0.02em] text-air-ink">
						{{ __("Job Requisition") }}
					</h1>
				</div>

				<TabButtons class="mt-5" :buttons="TABS" v-model="activeTab" />

				<!-- New request -->
				<form
					v-if="activeTab === 'New Request'"
					class="mt-5 flex flex-col gap-4 rounded bg-white p-4 lg:rounded-air lg:border lg:border-air-line lg:p-6"
					@submit.prevent="submit"
				>
					<FormControl
						type="select"
						:label="__('Department')"
						:options="departmentOptions"
						v-model="form.department"
						:required="true"
					/>
					<FormControl
						type="text"
						:label="__('Designation')"
						:placeholder="__('e.g. Senior Software Engineer')"
						v-model="form.designation"
						:required="true"
					/>
					<FormControl
						type="number"
						:label="__('Number of Positions')"
						v-model="form.no_of_positions"
						:required="true"
					/>
					<FormControl type="date" :label="__('Needed By Date')" v-model="form.expected_by" />
					<FormControl
						type="textarea"
						:label="__('Reason for Requesting')"
						v-model="form.reason_for_requesting"
						:required="true"
					/>
					<div class="flex flex-col gap-1.5">
						<label class="text-xs text-gray-600">{{ __("Job Description") }} *</label>
						<TextEditor
							:key="editorKey"
							:content="form.description"
							:placeholder="__('Enter {0}', [__('Job Description')])"
							@change="(v) => (form.description = v)"
							:fixedMenu="true"
							class="w-full [&_.ProseMirror]:w-full [&_.ProseMirror]:max-w-none"
							editor-class="prose-sm w-full max-w-none border-b border-x border-gray-200 rounded-b-sm p-2 min-h-[12rem]"
						/>
					</div>
					<Button
						type="submit"
						variant="solid"
						class="w-full rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
						:loading="createRequest.loading"
					>
						{{ __("Submit Request") }}
					</Button>
				</form>

				<!-- History -->
				<template v-else>
					<div
						v-if="rows.length"
						class="mt-5 flex flex-col rounded bg-white lg:rounded-air lg:border lg:border-air-line lg:shadow-air lg:overflow-hidden"
					>
						<router-link
							v-for="req in rows"
							:key="req.name"
							:to="{ name: 'JobRequisitionDetailView', params: { id: req.name } }"
							class="flex cursor-pointer flex-col gap-1.5 border-b p-3.5 transition-colors last:border-b-0 hover:bg-gray-50"
						>
							<div class="flex items-start justify-between gap-3">
								<div class="flex flex-col gap-1">
									<div class="text-base font-medium text-gray-800">{{ req.designation }}</div>
									<div class="text-xs text-gray-500">
										{{ [req.department, positionsLabel(req), dayjs(req.creation).format("D MMM YYYY")].filter(Boolean).join(" · ") }}
									</div>
								</div>
								<div class="flex items-center gap-2">
									<Badge
										variant="outline"
										:theme="statusTheme[req.status] || 'gray'"
										:label="statusLabel[req.status] || req.status"
										size="md"
									/>
									<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
								</div>
							</div>
							<div
								v-if="req.status === 'On Hold' && req.hold_reason"
								class="rounded border-l-4 border-l-amber-500 bg-amber-50 px-2.5 py-1.5 text-sm text-amber-900"
							>
								<span class="font-semibold">{{ __("Reason for hold") }}:</span> {{ req.hold_reason }}
							</div>
							<div
								v-if="req.status === 'Rejected' && req.rejection_reason"
								class="rounded border-l-4 border-l-red-500 bg-red-50 px-2.5 py-1.5 text-sm text-red-800"
							>
								<span class="font-semibold">{{ __("Reason for rejection") }}:</span> {{ req.rejection_reason }}
							</div>
						</router-link>
					</div>
					<EmptyState
						v-else-if="!listLoading"
						class="mt-5"
						:message="__('No job requisitions found')"
					/>
					<div v-if="listLoading" class="mt-4 flex items-center justify-center">
						<LoadingIndicator class="w-8 h-8 text-gray-800" />
					</div>
				</template>
			</div>
		</div>
	</ion-content>

	<Dialog v-model="showErrorDialog">
		<template #body-title>
			<h2 class="text-xl font-bold text-gray-900">{{ __("Couldn't submit") }}</h2>
		</template>
		<template #body-content>
			<p class="whitespace-pre-line text-[15px] leading-6 text-gray-700">{{ errorMessage }}</p>
		</template>
		<template #actions>
			<Button variant="solid" class="w-full py-5" @click="showErrorDialog = false">{{ __("OK") }}</Button>
		</template>
	</Dialog>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonHeader, IonContent, onIonViewWillEnter } from "@ionic/vue"
import {
	Badge,
	Button,
	Dialog,
	FeatherIcon,
	FormControl,
	LoadingIndicator,
	TextEditor,
	createResource,
	toast,
} from "frappe-ui"

import DesktopShell from "@/components/DesktopShell.vue"
import EmptyState from "@/components/EmptyState.vue"
import TabButtons from "@/components/TabButtons.vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")
const router = useRouter()

const TABS = ["New Request", "History"] // __("New Request"), __("History")
const activeTab = ref("New Request")

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

const emptyForm = () => ({
	department: "",
	designation: "",
	no_of_positions: 1,
	expected_by: "",
	reason_for_requesting: "",
	description: "",
})
const form = reactive(emptyForm())
// Changing the key remounts the editor, which is how it is cleared after a submit.
const editorKey = ref(0)

// The editor returns HTML; an empty editor still returns a bare "<p></p>".
const isDescriptionEmpty = () => !form.description?.replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim()

const departments = createResource({
	url: "hrms.hr.doctype.job_requisition.job_requisition.get_requisition_departments",
	auto: true,
})
const departmentOptions = computed(() => [
	{ label: "", value: "" },
	...(departments.data || []).map((d) => ({ label: d, value: d })),
])

const LIST_FIELDS = [
	"name",
	"designation",
	"department",
	"no_of_positions",
	"status",
	"creation",
	"rejection_reason",
	"hold_reason",
]

const history = createResource({
	url: "frappe.client.get_list",
	makeParams() {
		return {
			doctype: "Job Requisition",
			fields: LIST_FIELDS,
			filters: { requested_by: employee.data?.name },
			order_by: "creation desc",
			limit_page_length: 100,
		}
	},
})

const rows = computed(() => history.data || [])
const listLoading = computed(() => history.loading)

function loadLists() {
	if (employee.data?.name) history.fetch()
}
onMounted(loadLists)
// The employee record can load after the page opens; coming back from a request
// should also show its new status.
watch(() => employee.data?.name, loadLists)
onIonViewWillEnter(loadLists)

const positionsLabel = (req) =>
	req.no_of_positions ? __("{0} position(s)", [req.no_of_positions]) : ""

const showErrorDialog = ref(false)
const errorMessage = ref("")
function showError(message) {
	errorMessage.value = message
	showErrorDialog.value = true
}

function extractErrorMessage(error, fallback) {
	if (!error) return fallback
	let msgs = error.messages
	if (typeof msgs === "string") msgs = [msgs]
	const strip = (m) => String(m).replace(/<[^>]*>/g, "").trim()
	if (Array.isArray(msgs) && msgs.length) {
		const clean = msgs.map(strip).filter(Boolean)
		if (clean.length) return [...new Set(clean)].join("\n")
	}
	return strip(error.message || error) || fallback
}

const createRequest = createResource({
	url: "frappe.client.insert",
	onSuccess() {
		toast({
			title: __("Success"),
			text: __("Your request was sent to the administrators and HR for a decision."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		Object.assign(form, emptyForm())
		editorKey.value++
		activeTab.value = "History"
		loadLists()
	},
	onError(error) {
		showError(extractErrorMessage(error, __("Could not submit the request")))
	},
})

function submit() {
	if (createRequest.loading) return
	const missing = []
	if (!form.department) missing.push(__("Department"))
	if (!form.designation?.trim()) missing.push(__("Designation"))
	if (!form.no_of_positions || Number(form.no_of_positions) < 1) missing.push(__("Number of Positions"))
	if (!form.reason_for_requesting?.trim()) missing.push(__("Reason for Requesting"))
	if (isDescriptionEmpty()) missing.push(__("Job Description"))
	if (missing.length) {
		showError(__("Please fill in: {0}", [missing.join(", ")]))
		return
	}

	createRequest.submit({
		doc: {
			doctype: "Job Requisition",
			department: form.department,
			designation: form.designation.trim(),
			no_of_positions: Number(form.no_of_positions),
			expected_by: form.expected_by || null,
			reason_for_requesting: form.reason_for_requesting,
			description: form.description,
		},
	})
}
</script>
