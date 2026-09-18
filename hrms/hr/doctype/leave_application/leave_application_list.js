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
			Pending: "orange",
			Draft: "red",
			Cancelled: "red",
			Submitted: "blue",
		};
		const status =
			!doc.docstatus && ["Approved", "Rejected"].includes(doc.status) ? "Draft" : doc.status;
		return [__(status), status_color[status], "status,=," + doc.status];
	},
	onload: function (listview) {
		if (!listview.page.add_actions_menu_item) return;
		listview.page.add_actions_menu_item(
			__("Approve"),
			() => bulk_set_leave_status(listview, "Approved"),
			false
		);
		listview.page.add_actions_menu_item(
			__("Reject"),
			() => bulk_set_leave_status(listview, "Rejected"),
			false
		);
	},
};

function bulk_set_leave_status(listview, status) {
	const docnames = listview.get_checked_items(true);
	if (!docnames.length) {
		frappe.msgprint(__("Select at least one Leave Application"));
		return;
	}

	frappe.confirm(
		__("Set {0} selected Leave Application(s) to {1}?", [docnames.length, __(status)]),
		() => {
			frappe.call({
				method: "hrms.hr.doctype.leave_application.leave_application.bulk_approve_or_reject",
				args: { docnames, status },
				freeze: true,
				freeze_message: __("Updating..."),
				callback: function (r) {
					const failed = r.message?.failed || [];
					if (failed.length) {
						frappe.msgprint(
							__("Could not update: {0}. See Error Log for details.", [failed.join(", ")])
						);
					}
					listview.clear_checked_items();
					listview.refresh();
				},
			});
		}
	);
}
