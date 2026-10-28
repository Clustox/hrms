// Live-fill the billing and cost rates when Employee, Project or Start Date changes.
// Cost comes from the employee's Rate Card (as of the allocation start date); billing
// from the project's Sales Order. Only a blank rate is filled, so a value typed by hand
// is never overwritten (mirrors the server on save).
frappe.ui.form.on("Resource Allocation", {
	employee: (frm) => suggest_rates(frm),
	project: (frm) => suggest_rates(frm),
	start_date: (frm) => suggest_rates(frm),
});

function suggest_rates(frm) {
	if (!frm.doc.employee || !frm.doc.project) {
		return;
	}
	frappe.call({
		method: "hrms.cx360.doctype.resource_allocation.resource_allocation.get_suggested_rates",
		args: {
			employee: frm.doc.employee,
			project: frm.doc.project,
			on_date: frm.doc.start_date,
		},
		callback: (r) => {
			if (!r.message) {
				return;
			}
			if (!frm.doc.project_cost_rate && r.message.cost_rate) {
				frm.set_value("project_cost_rate", r.message.cost_rate);
			}
			if (!frm.doc.project_billing_rate && r.message.billing_rate) {
				frm.set_value("project_billing_rate", r.message.billing_rate);
			}
		},
	});
}
