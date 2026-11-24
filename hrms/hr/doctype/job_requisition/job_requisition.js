// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Job Requisition", {
	refresh: function (frm) {
		// The referral headline reads Employee Referral, which only HR may read. Without this
		// check an administrator who is not HR gets a permission error on every request.
		const can_see_referrals = frappe.user.has_role("HR User") || frappe.user.has_role("HR Manager");
		if (
			can_see_referrals &&
			!frm.doc.__islocal &&
			!["Filled", "On Hold", "Cancelled"].includes(frm.doc.status)
		) {
			frappe.db
				.get_list("Employee Referral", {
					filters: { for_designation: frm.doc.designation, status: "Pending" },
				})
				.then((data) => {
					if (data && data.length) {
						const link =
							data.length > 1
								? `<a id="referral_links" style="text-decoration: underline;">${__(
										"Employee Referrals",
								  )}</a>`
								: `<a id="referral_links" style="text-decoration: underline;">${__(
										"Employee Referral",
								  )}</a>`;

						const headline = __("{} {} open for this position.", [data.length, link]);
						frm.dashboard.clear_headline();
						frm.dashboard.set_headline(headline, "yellow");

						$("#referral_links").on("click", (e) => {
							e.preventDefault();
							frappe.set_route("List", "Employee Referral", {
								for_designation: frm.doc.designation,
								status: "Pending",
							});
						});
					}
				});
		}

		// Whoever may create a Job Opening (HR, System Manager) gets the buttons.
		if (frm.doc.status === "Open & Approved" && frappe.model.can_create("Job Opening")) {
			frm.add_custom_button(
				__("Create Job Opening"),
				() => {
					frappe.model.open_mapped_doc({
						method: "hrms.hr.doctype.job_requisition.job_requisition.make_job_opening",
						frm: frm,
					});
				},
				__("Actions"),
			);

			frm.add_custom_button(
				__("Associate Job Opening"),
				() => {
					frappe.prompt(
						{
							label: __("Job Opening"),
							fieldname: "job_opening",
							fieldtype: "Link",
							options: "Job Opening",
							reqd: 1,
							get_query: () => {
								const filters = {
									company: frm.doc.company,
									status: "Open",
									designation: frm.doc.designation,
								};

								if (frm.doc.department) filters.department = frm.doc.department;

								return { filters: filters };
							},
						},
						(values) => {
							frm.call("associate_job_opening", { job_opening: values.job_opening });
						},
						__("Associate Job Opening"),
						__("Submit"),
					);
				},
				__("Actions"),
			);

			frm.page.set_inner_btn_group_as_primary(__("Actions"));
		}
	},
	// Approving asks for the salary range; rejecting and putting on hold each ask for a
	// reason. They are saved first because a workflow action reloads the document from the
	// database.
	before_workflow_action: function (frm) {
		const action = frm.selected_workflow_action;
		const reason_fields = {
			Reject: { fieldname: "rejection_reason", label: __("Rejection Reason") },
			"Put On Hold": { fieldname: "hold_reason", label: __("Hold Reason") },
		};
		if (action !== "Approve" && !reason_fields[action]) return;

		const approve = action === "Approve";
		const titles = {
			Approve: __("Approve Job Requisition"),
			Reject: __("Reject Job Requisition"),
			"Put On Hold": __("Put Job Requisition On Hold"),
		};
		const buttons = { Approve: __("Approve"), Reject: __("Reject"), "Put On Hold": __("Put On Hold") };
		return new Promise((resolve, reject) => {
			let decided = false;
			const dialog = new frappe.ui.Dialog({
				title: titles[action],
				fields: approve
					? [
							{
								label: __("Approved Salary (From)"),
								fieldname: "approved_salary_lower",
								fieldtype: "Currency",
								reqd: 1,
								default: frm.doc.approved_salary_lower || frm.doc.expected_compensation || undefined,
							},
							{
								label: __("Approved Salary (To)"),
								fieldname: "approved_salary_upper",
								fieldtype: "Currency",
								reqd: 1,
								default: frm.doc.approved_salary_upper,
							},
					  ]
					: [
							{
								label: reason_fields[action].label,
								fieldname: reason_fields[action].fieldname,
								fieldtype: "Small Text",
								reqd: 1,
							},
					  ],
				primary_action_label: buttons[action],
				primary_action(values) {
					if (approve && flt(values.approved_salary_lower) > flt(values.approved_salary_upper)) {
						frappe.msgprint(__("Approved Salary (From) cannot be greater than Approved Salary (To)."));
						return;
					}
					frappe
						.xcall("frappe.client.set_value", {
							doctype: frm.doctype,
							name: frm.docname,
							fieldname: values,
						})
						.then(() => {
							decided = true;
							dialog.hide();
							// Frappe froze the screen when the action started and unfreezes it
							// once the action is applied, so put the freeze back for that part.
							frappe.dom.freeze();
							resolve();
						})
						// A failed save shows its own message; the dialog stays open to retry.
						.catch(() => {});
				},
			});
			dialog.onhide = () => {
				if (!decided) reject();
			};
			// Frappe freezes the whole screen before calling this hook, which would sit on top
			// of the dialog and block it. Lift the freeze while the dialog is open.
			frappe.dom.unfreeze();
			dialog.show();
		});
	},
	before_save: function (frm) {
		frm.trigger("handle_duplicate_check");
	},
	handle_duplicate_check: function (frm) {
		if (!frm.is_new() || frm.duplicate_confirmed) return;
		frappe.validated = false;

		frm.call("check_duplicate_job_requisition").then((r) => {
			if (!r.message) {
				frm.duplicate_confirmed = true;
				frm.save();
				return;
			}

			frappe.confirm(
				__(
					"A Job Requisition already exists for {0} requested by {1} for the same department.<br> Do you want to continue?",
					[frm.doc.designation.bold(), frm.doc.requested_by.bold()],
				),
				() => {
					frm.duplicate_confirmed = true;
					frm.save();
				},
			);
		});
	},
});
