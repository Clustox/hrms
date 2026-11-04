const routes = [
	{
		name: "ExpenseRequestListView",
		path: "/expense-requests",
		component: () => import("@/views/expenses/ExpenseRequestList.vue"),
	},
	{
		name: "ExpenseRequestFormView",
		path: "/expense-requests/new",
		component: () => import("@/views/expenses/ExpenseRequestForm.vue"),
	},
	{
		name: "ExpenseRequestDetailView",
		path: "/expense-requests/:id",
		props: true,
		component: () => import("@/views/expenses/ExpenseRequestForm.vue"),
	},
]

export default routes
