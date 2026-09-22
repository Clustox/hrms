// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const assignable_masters = {};

function get_assignment_actions() {
	return [
		{
			label: __("Holiday List"),
			doctype: "Holiday List Assignment",
			master_field: "holiday_list",
			prefill: (frm) => ({
				applicable_for: "Employee",
				assigned_to: frm.doc.name,
				employee_name: frm.doc.employee_name,
				employee_company: frm.doc.company,
			}),
			hide: ["naming_series"],
			on_change: {
				holiday_list: sync_holiday_list_range,
				from_date: flag_start_date_outside_range,
			},
		},
		{
			label: __("Leave Policy"),
			doctype: "Leave Policy Assignment",
			master: "Leave Policy",
			master_field: "leave_policy",
			prefill: (frm) => ({ employee: frm.doc.name }),
			queries: (frm) => ({
				leave_policy: { docstatus: 1 },
				leave_period: { is_active: 1, company: frm.doc.company },
			}),
			on_change: {
				assignment_based_on: set_leave_effective_dates,
				leave_period: set_leave_effective_dates,
			},
		},
		{
			label: __("Salary Structure"),
			doctype: "Salary Structure Assignment",
			master: "Salary Structure",
			prefill: (frm) => ({ employee: frm.doc.name, company: frm.doc.company }),
			redirect: true,
		},
		{
			label: __("Shift"),
			doctype: "Shift Assignment",
			prefill: (frm) => ({ employee: frm.doc.name, company: frm.doc.company }),
			redirect: true,
		},
		{
			label: __("Shift Schedule"),
			doctype: "Shift Schedule Assignment",
			master: "Shift Schedule",
			prefill: (frm) => ({ employee: frm.doc.name, company: frm.doc.company }),
			redirect: true,
		},
	];
}

function get_assignable_masters(company) {
	if (!assignable_masters[company]) {
		assignable_masters[company] = frappe
			.xcall("hrms.overrides.employee_master.get_assignable_masters", { company })
			.catch(() => {
				delete assignable_masters[company];
				return {};
			});
	}

	return assignable_masters[company];
}

function open_assignment(frm, action) {
	if (action.redirect) return frappe.new_doc(action.doctype, action.prefill(frm));

	frappe.model.with_doctype(action.doctype, () => {
		const doc = Object.assign(
			frappe.model.get_new_doc(action.doctype, null, null, true),
			action.prefill(frm),
		);

		frappe.ui.form.make_quick_entry(
			action.doctype,
			(created_doc) => notify_assignment_created(action, created_doc),
			(dialog) => setup_dialog(dialog, action, frm),
			doc,
			true,
		);
	});
}

function setup_dialog(dialog, action, frm) {
	for (const [fieldname, filters] of Object.entries(action.queries?.(frm) || {}))
		dialog.set_query(fieldname, () => ({ filters }));

	for (const fieldname of action.hide || []) {
		const control = dialog.fields_dict[fieldname];
		if (!control) continue;

		control.df = { ...control.df, hidden: 1 };
		control.refresh();
	}

	for (const [fieldname, handler] of Object.entries(action.on_change || {})) {
		const control = dialog.fields_dict[fieldname];
		if (!control) continue;

		control.df = { ...control.df, onchange: () => handler(dialog, frm) };
	}

	dialog.add_custom_action(__("Edit Full Form"), () => dialog.open_doc(false));
	keep_dialog_open_for_submit(dialog);
}

function keep_dialog_open_for_submit(dialog) {
	dialog.set_primary_action(__("Save"), () => {
		if (dialog.working || !dialog.get_values()) return;

		dialog.working = true;
		dialog.insert().finally(() => (dialog.working = false));
	});
}

function set_field_hint(dialog, fieldname, title) {
	dialog.modal_body.find(".assignment-hint").remove();
	if (!title) return;

	frappe.ui
		.alert({ title, theme: "blue", css_class: "assignment-hint" })
		.insertAfter(dialog.fields_dict[fieldname].$wrapper);
}

async function sync_holiday_list_range(dialog) {
	const holiday_list = dialog.get_value("holiday_list");
	dialog.holiday_list_range = null;

	if (holiday_list) {
		const response = await frappe.db.get_value("Holiday List", holiday_list, [
			"from_date",
			"to_date",
		]);
		dialog.holiday_list_range = response.message?.from_date ? response.message : null;
	}

	const range_start = dialog.holiday_list_range?.from_date;
	if (range_start && !dialog.get_value("from_date"))
		await dialog.set_value("from_date", range_start);

	flag_start_date_outside_range(dialog);
}

async function set_leave_effective_dates(dialog, frm) {
	const assignment_based_on = dialog.get_value("assignment_based_on");

	if (!assignment_based_on) {
		await dialog.set_value("effective_from", "");
		await dialog.set_value("effective_to", "");
		return;
	}

	if (assignment_based_on === "Joining Date") {
		await dialog.set_value("effective_from", frm.doc.date_of_joining);
		await dialog.set_value(
			"effective_to",
			frappe.datetime.add_months(frm.doc.date_of_joining, 12),
		);
		return;
	}

	const leave_period = dialog.get_value("leave_period");
	if (!leave_period) return;

	const response = await frappe.db.get_value("Leave Period", leave_period, [
		"from_date",
		"to_date",
	]);
	if (!response.message) return;

	await dialog.set_value("effective_from", response.message.from_date);
	await dialog.set_value("effective_to", response.message.to_date);
}

function flag_start_date_outside_range(dialog) {
	const range = dialog.holiday_list_range;
	const from_date = dialog.get_value("from_date");
	if (!range || !from_date) return set_field_hint(dialog, "from_date", null);

	const outside =
		frappe.datetime.get_diff(from_date, range.from_date) < 0 ||
		frappe.datetime.get_diff(from_date, range.to_date) > 0;

	set_field_hint(
		dialog,
		"from_date",
		outside &&
			__("Assignment must start between {0} and {1}", [
				frappe.datetime.str_to_user(range.from_date),
				frappe.datetime.str_to_user(range.to_date),
			]),
	);
}

function notify_assignment_created(action, doc) {
	frappe.quick_entry?.hide();

	const master_doctype = frappe.meta.get_docfield(action.doctype, action.master_field).options;

	frappe.show_alert({
		message: __("{0} was assigned {1}", [
			__(master_doctype),
			frappe.utils.get_form_link(action.doctype, doc.name, true),
		]),
		indicator: "green",
	});
}

// Connection-list item labels come straight from the linked doctype's own
// name (see frappe/public/js/frappe/form/templates/form_links.html --
// `{{ __(doctype) }}`, no per-item override), and the dashboard section
// they live in can re-render (e.g. on tab switches) after our first pass,
// so relabelling one item means finding it again whenever it (re)appears
// rather than a single one-time DOM edit.
function relabel_connection(frm, doctype, label) {
	// Not `frm.dashboard.wrapper` -- FormDashboard has no such property.
	// `transactions_area` is the actual (pre-existing, if not yet attached)
	// container form_links.html's markup gets appended into.
	const container = frm.dashboard && frm.dashboard.transactions_area && frm.dashboard.transactions_area[0];
	if (!container) return;

	const apply = () => {
		const el = container.querySelector(`.document-link[data-doctype="${doctype}"] .badge-link`);
		if (el && el.textContent !== label) el.textContent = label;
	};

	apply();
	if (frm.__connection_relabel_observer) return;
	frm.__connection_relabel_observer = new MutationObserver(apply);
	frm.__connection_relabel_observer.observe(container, { childList: true, subtree: true });
}

frappe.ui.form.on("Employee", {
	refresh: function (frm) {
		// Restrict the Gender dropdown to Male/Female/Other -- a filter here
		// rather than deleting the other Gender master records, so this only
		// hides them from selection and stays trivially reversible.
		frm.set_query("gender", function () {
			return {
				filters: {
					name: ["in", ["Male", "Female", "Other"]],
				},
			};
		});
		// only_select drops "Create a new Gender" and "Advanced Search" from
		// the dropdown, but frappe's ControlLink always appends a "Filtered
		// by: ..." hint line whenever a query filter is active regardless of
		// only_select (see frappe/public/js/frappe/form/controls/link.js) --
		// there's no df flag for that, so silence it directly on this one
		// field's control instance rather than patching frappe core.
		frm.set_df_property("gender", "only_select", 1);
		const gender_control = frm.get_field("gender");
		if (gender_control) gender_control.get_filter_description = async () => null;

		frm.set_df_property("notice_number_of_days", "label", __("Notice Period (days)"));
		relabel_connection(frm, "Employee Checkin", __("Employee Logs"));

		frm.set_query("payroll_cost_center", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			};
		});

		// filter advance account based on salary currency
		if (frm.doc.salary_currency) {
			frm.set_query("employee_advance_account", function () {
				return {
					filters: {
						root_type: "Asset",
						is_group: 0,
						company: frm.doc.company,
						account_currency: frm.doc.salary_currency,
						account_type: "Receivable",
					},
				};
			});
		}
		frm.set_df_property("holiday_list", "hidden", 1);

		// hide naming series field based on hr settings
		frappe.db.get_single_value("HR Settings", "emp_created_by").then((value) => {
			frm.toggle_display("naming_series", value === "Naming Series");
		});

		frm.trigger("add_assignment_actions");
	},

	add_assignment_actions: async function (frm) {
		if (frm.is_new() || frm.doc.status !== "Active") return;

		const available_masters = await get_assignable_masters(frm.doc.company);

		for (const action of get_assignment_actions()) {
			if (action.master && !available_masters[action.master]) continue;
			if (!frappe.model.can_create(action.doctype)) continue;

			frm.add_custom_button(
				action.label,
				() => open_assignment(frm, action),
				__("Create Assignments"),
			);
		}
	},

	date_of_birth(frm) {
		frm.call({
			method: "hrms.overrides.employee_master.get_retirement_date",
			args: {
				date_of_birth: frm.doc.date_of_birth,
			},
		}).then((r) => {
			if (r && r.message) frm.set_value("date_of_retirement", r.message);
		});
	},
});
