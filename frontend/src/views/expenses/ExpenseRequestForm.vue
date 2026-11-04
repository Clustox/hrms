<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="visibleFields"
				doctype="Expense Request"
				v-model="expenseRequest"
				:isSubmittable="true"
				:fields="visibleFields"
				:id="props.id"
				:showAttachmentView="true"
				:attachmentRequired="true"
				:attachmentRequiredHint="attachmentHint"
				@validateForm="validateForm"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { ref, computed, inject } from "vue"

import FormView from "@/components/FormView.vue"

const __ = inject("$translate")
const employee = inject("$employee")

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

const expenseRequest = ref({})

// Fields the employee fills when raising a request. currency/company are set by
// the controller.
const CREATE_FIELDS = ["expense_type", "amount", "reason"]
// The PWA FormView does not evaluate the doctype's `depends_on`, so we gate
// these per workflow state ourselves: reimbursement is only shown once Accounts
// handles the request (so a requester never sees an editable Paid Amount on
// their draft), and rejection fields only while an approval is in progress or
// after a rejection.
const REIMBURSEMENT_FIELDS = [
	"reimbursement_section",
	"paid_amount",
	"payment_date",
	"column_break_reimb",
	"payment_mode",
	"reference_no",
	"paid_by",
]
const REJECTION_FIELDS = ["rejection_reason", "rejection_note"]
const REIMBURSEMENT_STATES = ["Pending Accounts", "Completed"]
const REJECTION_STATES = ["Pending Manager", "Pending HR", "Pending Accounts", "Rejected"]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Expense Request" },
	auto: true,
})

const visibleFields = computed(() => {
	const data = formFields.data
	if (!data) return null
	if (!props.id) return data.filter((f) => CREATE_FIELDS.includes(f.fieldname))
	const state = expenseRequest.value.workflow_state
	const showReimb = REIMBURSEMENT_STATES.includes(state)
	const showReject = REJECTION_STATES.includes(state)
	return data.filter((f) => {
		if (REIMBURSEMENT_FIELDS.includes(f.fieldname)) return showReimb
		if (REJECTION_FIELDS.includes(f.fieldname)) return showReject
		return true
	})
})

const attachmentHint = computed(() =>
	["OPD", "IPD"].includes(expenseRequest.value.expense_type)
		? __("Attach the receipt and the prescription before submitting.")
		: __("Attach the receipt / invoice before submitting.")
)

function validateForm() {
	expenseRequest.value.employee = employee.data.name
}
</script>
