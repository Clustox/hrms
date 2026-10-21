const routes = [
	{
		name: "WfhRequestListView",
		path: "/wfh-requests",
		component: () => import("@/views/wfh_request/List.vue"),
	},
	{
		name: "WfhRequestFormView",
		path: "/wfh-requests/new",
		component: () => import("@/views/wfh_request/Form.vue"),
	},
	{
		name: "WfhRequestDetailView",
		path: "/wfh-requests/:id",
		props: true,
		component: () => import("@/views/wfh_request/Form.vue"),
	},
]

export default routes
