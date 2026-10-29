// Copyright (c) 2026, Clustox and contributors
// For license information, please see license.txt

frappe.ui.form.on("Commission Run", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Generate"), () => {
			frm.call({
				doc: frm.doc,
				method: "run_generation",
				freeze: true,
				freeze_message: __("Generating commission entries..."),
			}).then((r) => {
				frm.reload_doc();
				frappe.show_alert({
					message: __("Generated {0} commission entries.", [r.message || 0]),
					indicator: "green",
				});
			});
		});
	},
});
