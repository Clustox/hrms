// Copyright (c) 2026, Clustox and contributors
// For license information, please see license.txt

frappe.listview_settings["Candidate"] = {
	onload: function (listview) {
		// find candidates by the words in their resume
		listview.page.add_inner_button(__("Search Resumes"), () => {
			frappe.prompt(
				{
					label: __("Words in the resume"),
					fieldname: "text",
					fieldtype: "Data",
					reqd: 1,
					description: __("Every word must be found. Example: python django"),
				},
				(values) => {
					frappe.xcall("hrms.ats.resume.search_candidates", { text: values.text }).then((names) => {
						if (!names.length) {
							frappe.show_alert({ message: __("No resume contains all of those words."), indicator: "orange" });
							return;
						}
						listview.filter_area.clear();
						listview.filter_area.add([["Candidate", "name", "in", names]]);
					});
				},
				__("Search Resumes"),
				__("Search"),
			);
		});
	},
};
