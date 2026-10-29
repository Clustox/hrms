frappe.query_reports["Cost Sheet"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: ["Daily", "Weekly", "Monthly"],
			default: "Daily",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "cost_category",
			label: __("Cost Category"),
			fieldtype: "Select",
			options: [
				"",
				"Cost of Services",
				"Bench Cost",
				"Leadership Cost",
				"Training & Development Cost",
				"Pre-Sales",
				"Support",
				"Invest",
			],
		},
		{
			fieldname: "utilization",
			label: __("Utilization"),
			fieldtype: "Select",
			options: ["", "Billable", "Bench - Utilized", "Bench - Idle", "Overhead"],
		},
	],
};
