frappe.listview_settings["Leave Application"] = {
	add_fields: [
		"leave_type",
		"employee",
		"employee_name",
		"total_leave_days",
		"from_date",
		"to_date",
	],
	has_indicator_for_draft: 1,
	get_indicator: function (doc) {
		const status_color = {
			Approved: "green",
			Rejected: "red",
			Open: "orange",
			Draft: "red",
			Cancelled: "red",
			Submitted: "blue",
		};
		// "Open" is the real status value everywhere that matters (the filter
		// below, validate(), reports) -- "Pending" is only how it should read
		// to a human, so this relabels display only, not `doc.status` itself.
		const status_label = { Open: __("Pending") };
		const status =
			!doc.docstatus && ["Approved", "Rejected"].includes(doc.status) ? "Draft" : doc.status;
		return [status_label[status] || __(status), status_color[status], "status,=," + doc.status];
	},
};
