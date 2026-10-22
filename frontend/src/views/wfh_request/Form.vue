<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Attendance Request"
				v-model="wfhRequest"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showFormButton="false"
				:titleOverride="__('WFH Request')"
				:newTitleOverride="__('New WFH Request')"
			>
				<template #formButton>
					<div class="flex flex-col gap-2">
						<template v-if="!props.id">
							<Button
								variant="solid"
								class="w-full rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
								:loading="createRequest.loading"
								@click="submitNewRequest"
							>
								{{ __("Submit Request") }}
							</Button>
						</template>

						<template v-else-if="isApprover && wfhRequest.status === 'Pending'">
							<div class="flex gap-2">
								<Button
									variant="solid"
									theme="red"
									class="flex-1 rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
									:loading="decide.loading"
									@click="makeDecision('Rejected')"
								>
									{{ __("Reject") }}
								</Button>
								<Button
									variant="solid"
									class="flex-1 rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
									:loading="decide.loading"
									@click="makeDecision('Approved')"
								>
									{{ __("Approve") }}
								</Button>
							</div>
						</template>

						<template v-else-if="isOwner && wfhRequest.status === 'Pending'">
							<Button
								variant="outline"
								theme="red"
								class="w-full rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold"
								:loading="cancelRequest.loading"
								@click="cancelMyRequest"
							>
								{{ __("Cancel Request") }}
							</Button>
						</template>
					</div>
				</template>
			</FormView>
		</ion-content>

		<!-- Same pattern FormView.vue itself uses for save errors: ONE dialog
		     (v-model boolean) can never stack, so repeated failed attempts just
		     refresh its message instead of piling up toasts. -->
		<Dialog v-model="showErrorDialog">
			<template #body-title>
				<h2 class="text-xl font-bold text-gray-900">{{ __("Couldn't save") }}</h2>
			</template>
			<template #body-content>
				<p class="whitespace-pre-line text-[15px] leading-6 text-gray-700">{{ errorDialogMessage }}</p>
			</template>
			<template #actions>
				<Button variant="solid" class="w-full py-5" @click="showErrorDialog = false">{{ __("OK") }}</Button>
			</template>
		</Dialog>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { Button, Dialog, createResource, toast } from "frappe-ui"
import { ref, computed, inject, onMounted, watch } from "vue"
import { userResource } from "@/data/user"
import { useRouter } from "vue-router"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")
const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

const wfhRequest = ref({})

const showErrorDialog = ref(false)
const errorDialogMessage = ref("")

function showError(message) {
	errorDialogMessage.value = message
	showErrorDialog.value = true
}

// Mirrors FormView.vue's own extractErrorMessage: pulls the real,
// human-readable validation message(s) out of a frappe-ui error.
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

// A dedicated "Work From Home" request: only the fields relevant to that --
// never the punch-request fields (Punch Type/Time), the generic Attendance
// Request fields that don't apply here (Half Day, Include Holidays, Shift),
// or the raw "Reason" Select (shared with On Duty / punch requests, fixed
// to "Work From Home" and set programmatically, not shown; "Reason" here
// means the employee's own free-text explanation instead). Total Days and
// the Approval section (Team Lead/Manager, shown as "Approver"/"Approver
// Name" -- same Link + Name-field pairing Leave Application's Leave
// Approver uses) appear on the New Request form too, as a live preview
// computed below -- all four are read_only in the doctype, so they render
// as plain disabled fields. The identity fields (Employee, Department,
// Company) and Status only make sense once the request exists.
const APPROVAL_FIELDS = ["approval_section", "leave_approver", "leave_approver_name"]
const CREATE_FIELDS = ["from_date", "to_date", "total_days", "explanation", ...APPROVAL_FIELDS]
// Status itself is NOT in this list -- the header badge (FormView's own,
// driven by formModel.status) already shows it, and rendering the native
// Select here too is actively misleading: frappe-ui's Autocomplete still
// visually opens on click even when marked read_only (it just has nothing
// to save it to, since this form exposes no generic Save button -- but it
// looks clickable regardless, which is exactly the confusing half-measure
// this works around by not rendering the field at all).
const DETAIL_FIELDS = [
	"employee",
	"employee_name",
	"department",
	"company",
	"from_date",
	"to_date",
	"total_days",
	"reason_section",
	"explanation",
	...APPROVAL_FIELDS,
]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Attendance Request" },
	auto: true,
	transform(data) {
		const relabel = {
			explanation: __("Reason"),
			leave_approver: __("Approver"),
			leave_approver_name: __("Approver Name"),
		}
		const WFH_FIELDS = props.id ? DETAIL_FIELDS : CREATE_FIELDS
		let fields = data.filter((f) => WFH_FIELDS.includes(f.fieldname))
		fields.forEach((f) => {
			if (relabel[f.fieldname]) f.label = relabel[f.fieldname]
			if (f.fieldname === "explanation") f.reqd = 1
		})
		fields.sort((a, b) => WFH_FIELDS.indexOf(a.fieldname) - WFH_FIELDS.indexOf(b.fieldname))
		return fields
	},
	onSuccess() {
		// the approver details may have arrived before the fields did
		if (approvalDetails.data) applyApprovalDetails(approvalDetails.data)
	},
})

// Same source as Leave Application's form: the employee's Leave Approver
// (defaulted), the Department's approvers to choose from, and whether
// HR Settings makes the approver mandatory.
const approvalDetails = createResource({
	url: "hrms.api.get_leave_approval_details",
	auto: false,
	onSuccess: (data) => applyApprovalDetails(data),
})

function applyApprovalDetails(data) {
	const field = formFields.data?.find((f) => f.fieldname === "leave_approver")
	if (field) {
		field.reqd = data?.is_mandatory
		field.documentList = (data?.department_approvers || []).map((approver) => ({
			label: approver.full_name ? `${approver.name} : ${approver.full_name}` : approver.name,
			value: approver.name,
		}))
	}
	if (!wfhRequest.value.leave_approver) {
		wfhRequest.value.leave_approver = data?.leave_approver
		wfhRequest.value.leave_approver_name = data?.leave_approver_name
	}
}

watch(
	() => wfhRequest.value.leave_approver,
	(newApprover) => {
		if (props.id) return
		const field = formFields.data?.find((f) => f.fieldname === "leave_approver")
		const selected = field?.documentList?.find((opt) => opt.value === newApprover)
		wfhRequest.value.leave_approver_name = selected?.label?.split(" : ")[1] || ""
	}
)

onMounted(() => {
	if (props.id) return
	wfhRequest.value.company = employee.data.company
	approvalDetails.fetch({ employee: employee.data.name })
})

// Live Total Days preview, the same inclusive day-count the server itself
// computes in Attendance Request's own validate() -- shown here purely so
// the employee sees it before submitting, not relied on by the server,
// which always recalculates it anyway.
watch(
	() => [wfhRequest.value.from_date, wfhRequest.value.to_date],
	() => {
		if (props.id) return
		const { from_date, to_date } = wfhRequest.value
		if (!from_date || !to_date) {
			wfhRequest.value.total_days = null
			return
		}
		const days = dayjs(to_date).diff(dayjs(from_date), "day") + 1
		wfhRequest.value.total_days = days > 0 ? days : null
	}
)

const isOwner = computed(() => wfhRequest.value.employee === employee.data.name)
// Approve/Reject only for the request's Leave Approver (or HR), like Leave --
// not every colleague who merely has read access to it. Mirrors the
// server-side _can_decide.
const HR_ROLES = ["HR Manager", "HR User", "System Manager"]
const isApprover = computed(() => {
	if (isOwner.value) return false
	const user = userResource.data
	return (
		wfhRequest.value.leave_approver === user?.name ||
		HR_ROLES.some((role) => user?.roles?.includes(role))
	)
})
// Anyone who opened someone else's request sees it read-only
const isViewingOthers = computed(() => !isOwner.value)

// An approver reviews, not edits -- lock every field once there's a decision
// to make or once one has already been made (mirrors Leave Application's
// Form.vue restricting a non-owner viewer to read-only).
watch(
	() => wfhRequest.value.employee,
	() => {
		if (props.id && isViewingOthers.value) {
			formFields.data?.forEach((field) => (field.read_only = true))
		}
	}
)

const createRequest = createResource({
	url: "frappe.client.insert",
	onSuccess(doc) {
		isSubmittingRequest = false
		toast({
			title: __("Success"),
			text: __("WFH request submitted"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.replace({ name: "WfhRequestDetailView", params: { id: doc.name } })
	},
	onError(error) {
		isSubmittingRequest = false
		showError(extractErrorMessage(error, __("Could not submit the request")))
	},
})

// A plain synchronous flag, not createRequest.loading -- that only flips
// once the resource's own submit() runs, which can be a tick or more after
// the click handler fires. Several rapid clicks landing in that window each
// read loading as still false and would otherwise all fire their own
// insert, each failing on the same overlap and stacking a duplicate toast
// (the showError dialog above also only ever shows one at a time regardless,
// but this still avoids firing three redundant inserts on the server).
let isSubmittingRequest = false

function submitNewRequest() {
	if (isSubmittingRequest) return
	if (!wfhRequest.value.from_date || !wfhRequest.value.to_date) {
		showError(__("From Date and To Date are required"))
		return
	}
	if (!wfhRequest.value.explanation?.trim()) {
		showError(__("Reason is required"))
		return
	}
	isSubmittingRequest = true
	createRequest.submit({
		doc: {
			doctype: "Attendance Request",
			employee: employee.data.name,
			company: wfhRequest.value.company || employee.data.company,
			reason: "Work From Home",
			from_date: wfhRequest.value.from_date,
			to_date: wfhRequest.value.to_date,
			explanation: wfhRequest.value.explanation,
		},
	})
}

const decide = createResource({
	url: "hrms.hr.doctype.attendance_request.attendance_request.set_wfh_decision",
	onSuccess(status) {
		isDeciding = false
		toast({
			title: __("Success"),
			text: status === "Approved" ? __("Request approved") : __("Request rejected"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.back()
	},
	onError(error) {
		isDeciding = false
		showError(extractErrorMessage(error, __("Could not record your decision")))
	},
})

let isDeciding = false

function makeDecision(decision) {
	if (isDeciding) return
	isDeciding = true
	decide.submit({ name: props.id, decision })
}

const cancelRequest = createResource({
	url: "hrms.hr.doctype.attendance_request.attendance_request.cancel_wfh_request",
	onSuccess() {
		isCancelling = false
		toast({
			title: __("Success"),
			text: __("Request cancelled"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.back()
	},
	onError(error) {
		isCancelling = false
		showError(extractErrorMessage(error, __("Could not cancel the request")))
	},
})

let isCancelling = false

function cancelMyRequest() {
	if (isCancelling) return
	isCancelling = true
	cancelRequest.submit({ name: props.id })
}
</script>
