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
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { ref, watch, inject, onMounted } from "vue"

import FormView from "@/components/FormView.vue"

const employee = inject("$employee")
const __ = inject("$translate")

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
		if (props.id) return data
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
