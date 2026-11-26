const routes = [
	{
		name: "JobRequisitionView",
		path: "/job-requisitions",
		component: () => import("@/views/job_requisition/Index.vue"),
	},
	{
		name: "JobRequisitionDetailView",
		path: "/job-requisitions/:id",
		props: true,
		component: () => import("@/views/job_requisition/Detail.vue"),
	},
]

export default routes
