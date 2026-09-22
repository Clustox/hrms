// The flat, one-row-per-scan List View is superseded by the "Employee logs"
// report (grouped one row per employee per day) -- see
// hrms/hr/report/employee_logs. Every entry point that used to land here
// (sidebar, the Employee form's Connections badge, direct links, search)
// still routes to this List first, so redirect on load instead of trying to
// intercept each entry point individually. Carry over an `employee` filter
// if the caller set one (e.g. the Connections badge sets frappe.route_options
// before navigating here).
frappe.listview_settings["Employee Checkin"] = {
	onload: function (listview) {
		const filters = {};

		const employee = frappe.route_options?.employee || get_employee_filter(listview);
		if (employee) {
			// Arriving here scoped to one employee (e.g. the Employee form's
			// Connections badge, whose count is all-time) means "show this
			// person's full history", not the report's own current-month
			// default -- an explicit blank overrides that default, unlike
			// omitting the key entirely.
			filters.employee = employee;
			filters.from_date = "";
			filters.to_date = "";
		}

		frappe.route_options = null;
		frappe.set_route("query-report", "Employee logs", filters);
	},
};

function get_employee_filter(listview) {
	const active = listview.filter_area?.get() || [];
	const match = active.find((f) => f[1] === "employee");
	return match ? match[3] : null;
}
