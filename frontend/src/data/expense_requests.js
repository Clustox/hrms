import { createResource } from "frappe-ui"
import { employeeResource } from "./employee"

const transformExpenseRequests = (data) =>
	data.map((request) => {
		request.doctype = "Expense Request"
		return request
	})

export const myExpenseRequests = createResource({
	url: "hrms.api.get_expense_requests",
	params: {
		employee: employeeResource.data.name,
		limit: 10,
	},
	auto: true,
	cache: "hrms:my_expense_requests",
	transform(data) {
		return transformExpenseRequests(data)
	},
})

export const teamExpenseRequests = createResource({
	url: "hrms.api.get_expense_requests",
	params: {
		employee: employeeResource.data.name,
		approver_id: employeeResource.data.user_id,
		for_approval: 1,
		limit: 10,
	},
	auto: true,
	cache: "hrms:team_expense_requests",
	transform(data) {
		return transformExpenseRequests(data)
	},
})
