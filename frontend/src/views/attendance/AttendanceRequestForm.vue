<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Attendance Request"
				v-model="attendanceRequest"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showFormButton="!isApprover"
				@validateForm="validateForm"
			>
				<!-- Approver landing on an existing pending request (e.g. via the
				     notification deep link) gets explicit Approve / Reject here,
				     instead of a locked raw Status dropdown. -->
				<template #formButton>
					<div
						v-if="isApprover"
						class="flex w-full flex-row items-center justify-between gap-3"
					>
						<Button
							class="w-full py-5"
							variant="subtle"
							theme="red"
							:loading="decisionLoading === 'Rejected'"
							:disabled="Boolean(decisionLoading)"
							@click="decide('Rejected')"
						>
							<template #prefix>
								<FeatherIcon name="x" class="w-4" />
							</template>
							{{ __("Reject") }}
						</Button>
						<Button
							class="w-full py-5"
							variant="solid"
							theme="green"
							:loading="decisionLoading === 'Approved'"
							:disabled="Boolean(decisionLoading)"
							@click="decide('Approved')"
						>
							<template #prefix>
								<FeatherIcon name="check" class="w-4" />
							</template>
							{{ __("Approve") }}
						</Button>
					</div>
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, createResource, toast } from "frappe-ui"
import { ref, computed, watch, inject, onMounted } from "vue"
import { useRouter } from "vue-router"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")
const __ = inject("$translate")
const router = useRouter()

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// reactive object to store form data
const attendanceRequest = ref({})

// The /hrms "Request Attendance" form is a punch request (fix a missed
// check-in/out): single date, type, time, reason. Approval creates the
// Employee Checkin — see hrms.overrides.attendance_request.
const PUNCH_FIELDS = ["from_date", "custom_log_type", "custom_punch_time", "explanation"]

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Attendance Request" },
	auto: true,
	transform(data) {
		if (props.id) {
			// Viewing an existing request: hide the raw `status` Select. The
			// portal is not meant to expose status as an editable field (the
			// status badge at the top already shows it, and approvers act via
			// the Approve/Reject buttons below), so a raw dropdown here is just
			// a dead, confusing control.
			return data.filter((f) => f.fieldname !== "status")
		}
		const relabel = { from_date: __("Date"), explanation: __("Reason") }
		const fields = data.filter((f) => PUNCH_FIELDS.includes(f.fieldname))
		fields.forEach((f) => {
			if (relabel[f.fieldname]) f.label = relabel[f.fieldname]
			// punch type, time and reason are all required for a punch request
			if (["custom_log_type", "custom_punch_time", "explanation"].includes(f.fieldname))
				f.reqd = 1
		})
		fields.sort((a, b) => PUNCH_FIELDS.indexOf(a.fieldname) - PUNCH_FIELDS.indexOf(b.fieldname))
		return fields
	},
})

// form scripts
watch(
	() => attendanceRequest.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== employee.data.name) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
	}
)

// An approver (anyone other than the requester who can open this record —
// read access is already scoped to the manager + HR) looking at a request
// that is still Pending (docstatus 0). They get the Approve/Reject buttons;
// the requester and already-decided requests keep the default form button.
const isApprover = computed(() => {
	const doc = attendanceRequest.value
	return Boolean(
		props.id &&
			doc.employee &&
			doc.employee !== employee.data?.name &&
			Number(doc.docstatus ?? 0) === 0 &&
			(doc.status || "Pending") === "Pending"
	)
})

const decisionLoading = ref("")
const setStatus = createResource({ url: "frappe.client.set_value" })
const getDoc = createResource({ url: "frappe.client.get" })
const submitDoc = createResource({ url: "frappe.client.submit" })

// Approve/Reject: set the status, and for an approval also submit the request
// (which, for a punch request, creates the Employee Checkin). Mirrors how the
// list action sheet (RequestActionSheet) decides a request, so approving
// finalizes it instead of leaving it stuck at docstatus 0.
function decide(decision) {
	if (decisionLoading.value) return
	decisionLoading.value = decision
	setStatus.submit(
		{ doctype: "Attendance Request", name: props.id, fieldname: "status", value: decision },
		{
			onSuccess: () => {
				if (decision !== "Approved") return finishDecision(decision)
				getDoc.submit(
					{ doctype: "Attendance Request", name: props.id },
					{
						onSuccess: (doc) =>
							submitDoc.submit(
								{ doc },
								{
									onSuccess: () => finishDecision(decision),
									onError: () => failDecision(decision),
								}
							),
						onError: () => failDecision(decision),
					}
				)
			},
			onError: () => failDecision(decision),
		}
	)
}

function finishDecision(decision) {
	decisionLoading.value = ""
	toast({
		title: __("Success"),
		text: __("{0} successfully!", [__(decision)]),
		icon: "check-circle",
		position: "bottom-center",
		iconClasses: "text-green-500",
	})
	router.push({ name: "AttendanceRequestListView" })
}

function failDecision(decision) {
	decisionLoading.value = ""
	toast({
		title: __("Error"),
		text: __("{0} failed!", [decision === "Approved" ? __("Approval") : __("Rejection")]),
		icon: "alert-circle",
		position: "bottom-center",
		iconClasses: "text-red-500",
	})
}

// Punch-request defaults (new requests only): mark it a punch request, satisfy
// the required native `reason` Select with "Missed Punch", and set company.
onMounted(() => {
	if (props.id) return
	attendanceRequest.value.custom_is_punch_request = 1
	attendanceRequest.value.reason = "Missed Punch"
	attendanceRequest.value.company = employee.data.company
})

// helper functions
function setFormReadOnly() {
	formFields.data.map((field) => (field.read_only = true))
}

function validateForm() {
	attendanceRequest.value.employee = employee.data.name
	// single-day punch: to_date mirrors the chosen date
	attendanceRequest.value.to_date = attendanceRequest.value.from_date
	attendanceRequest.value.custom_is_punch_request = 1
	if (!attendanceRequest.value.reason) attendanceRequest.value.reason = "Missed Punch"
	attendanceRequest.value.company = attendanceRequest.value.company || employee.data.company
}
</script>
