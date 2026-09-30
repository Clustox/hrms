// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
//
// Clustox: repurposed as a check-in-driven daily timesheet (see the report's
// .py). Filters are the ones that apply to that: date range, employee, shift,
// department, company, and the late/early toggles.

frappe.query_reports["Shift Attendance"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_end(),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "shift",
			label: __("Shift Type"),
			fieldtype: "Link",
			options: "Shift Type",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "late_entry",
			label: __("Late only"),
			fieldtype: "Check",
		},
		{
			fieldname: "early_exit",
			label: __("Early exit only"),
			fieldtype: "Check",
		},
	],
	formatter: (value, row, column, data, default_formatter) => {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data.status) {
			const color =
				data.status === "Late" ? "red" : data.status === "Early" ? "#b5790a" : "green";
			value = `<span style='color:${color}!important'>${data.status}</span>`;
		}
		if (column.fieldname === "in_time" && data.late_entry_hrs) {
			value = `<span style='color:red!important'>${value}</span>`;
		}
		if (column.fieldname === "out_time" && data.early_exit_hrs) {
			value = `<span style='color:red!important'>${value}</span>`;
		}
		return value;
	},
};
