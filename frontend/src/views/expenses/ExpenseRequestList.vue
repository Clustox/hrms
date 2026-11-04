<template>
	<ion-page>
		<ListView
			doctype="Expense Request"
			pageTitle="Expense Requests"
			:tabButtons="TAB_BUTTONS"
			:fields="EXPENSE_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { inject } from "vue"
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"

const __ = inject("$translate")
const TAB_BUTTONS = ["My Requests", "Team Requests"]
const EXPENSE_REQUEST_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"expense_type",
	"amount",
	"workflow_state",
	"docstatus",
]
const EXPENSE_TYPES = ["AI Tool", "Certifications", "Food", "OPD", "IPD", "Long Service Reward"]
const FILTER_CONFIG = [
	{
		fieldname: "expense_type",
		fieldtype: "Select",
		label: __("Type"),
		options: EXPENSE_TYPES,
	},
	{
		fieldname: "employee",
		fieldtype: "Link",
		label: __("Employee"),
		options: "Employee",
	},
]
</script>
