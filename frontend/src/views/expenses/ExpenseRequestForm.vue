<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Expense Request"
				v-model="expenseRequest"
				:isSubmittable="true"
				:fields="formFields.data"
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
// the controller; workflow, rejection and reimbursement fields are hidden on
// create (and gated by depends_on / workflow state on the detail view).
const CREATE_FIELDS = ["expense_type", "amount", "reason"]

const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Expense Request" },
	auto: true,
	transform(data) {
		if (props.id) return data
		return data.filter((field) => CREATE_FIELDS.includes(field.fieldname))
	},
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
