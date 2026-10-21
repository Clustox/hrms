<template>
	<ion-page>
		<ListView
			doctype="Attendance Request"
			:pageTitle="__('WFH Requests')"
			:tabButtons="TAB_BUTTONS"
			:fields="WFH_REQUEST_FIELDS"
			:filterConfig="FILTER_CONFIG"
			:fixedFilters="FIXED_FILTERS"
			formViewRouteName="WfhRequestFormView"
			detailViewRouteName="WfhRequestDetailView"
		/>
	</ion-page>
</template>

<script setup>
import { IonPage } from "@ionic/vue"
import ListView from "@/components/ListView.vue"
import { inject } from "vue"

const __ = inject("$translate")

// Same My/Team convention as Leaves and the generic Attendance Requests
// list: "Team Requests" shows colleagues' requests (anyone with read access
// to this doctype); whether a given viewer can actually Approve/Reject one
// is enforced server-side (set_wfh_decision), not by what this list shows.
const TAB_BUTTONS = ["My Requests", "Team Requests"] // __("My Requests"), __("Team Requests")
const WFH_REQUEST_FIELDS = ["name", "employee_name", "from_date", "to_date", "half_day", "status"]
const FIXED_FILTERS = [["Attendance Request", "reason", "=", "Work From Home"]]
// ListFiltersActionSheet.vue does `v-for="option in filter.options"` directly
// -- a plain array like Leave's own status filter uses, not the doctype's
// raw "\n"-joined Select string (which a v-for over a string would iterate
// one character at a time).
const STATUS_FILTER_OPTIONS = ["Pending", "Approved", "Rejected", "Cancelled"] // __("Pending"), __("Approved"), __("Rejected"), __("Cancelled")
const FILTER_CONFIG = [
	{ fieldname: "from_date", fieldtype: "Date", label: __("From Date") },
	{ fieldname: "to_date", fieldtype: "Date", label: __("To Date") },
	{
		fieldname: "status",
		fieldtype: "Select",
		label: __("Status"),
		options: STATUS_FILTER_OPTIONS,
	},
]
</script>
