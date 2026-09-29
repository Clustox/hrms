<template>
	<ion-page>
		<ListView
			doctype="Attendance Request"
			:pageTitle="__('Attendance Requests')"
			:tabButtons="TAB_BUTTONS"
			:fields="ATTENDANCE_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"
import { inject } from "vue"

const __ = inject("$translate")

// "Team Requests" lets a manager (anyone who can approve, i.e. submit) see and
// approve their team's punch requests, mirroring Leaves / Expenses.
const TAB_BUTTONS = ["My Requests", "Team Requests"] // __("My Requests"), __("Team Requests")
const ATTENDANCE_REQUEST_FIELDS = ["name", "reason", "from_date", "to_date", "docstatus"]
const FILTER_CONFIG = [
	{
		fieldname: "shift",
		fieldtype: "Link",
		label: __("Shift"),
		options: "Shift Type",
	},
	{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
	{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
]
</script>
