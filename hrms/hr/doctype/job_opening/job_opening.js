// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Job Opening", {
	onload: function (frm) {
		frm.set_query("department", function () {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});
	},
	refresh: function (frm) {
		frm.trigger("add_status_toggle_button");
		frm.trigger("add_pipeline_board_button");
		frm.trigger("show_pipeline_counters");
	},
	show_pipeline_counters: function (frm) {
		// ATS: Hired / In pipeline / Dropped at the top of the job
		if (frm.is_new()) return;
		// the counts include candidates a guest may not see, so only staff get them
		if (!frappe.user.has_role(["System Manager", "HR Manager", "HR User", "ATS Recruiter"])) return;

		frm.dashboard.add_indicator(__("Hired: {0}", [frm.doc.hired_count || 0]), "green");
		frm.dashboard.add_indicator(__("In pipeline: {0}", [frm.doc.in_pipeline_count || 0]), "blue");
		frm.dashboard.add_indicator(__("Dropped: {0}", [frm.doc.dropped_count || 0]), "gray");
	},
	add_pipeline_board_button: function (frm) {
		// ATS: open the Kanban board of this job's candidates
		if (frm.is_new()) return;

		// dropped candidates of this job, with the stage they were dropped from and the reason
		frm.add_custom_button(__("Dropped Candidates"), () => {
			frappe.route_options = { job_title: frm.doc.name, is_dropped: 1 };
			frappe.set_route("List", "Job Applicant", "List");
		});

		frm.add_custom_button(__("Pipeline Board"), () => {
			frappe.xcall("hrms.ats.board.get_job_board", { job: frm.doc.name }).then((board) => {
				frappe.route_options = { job_title: frm.doc.name };
				frappe.set_route("List", "Job Applicant", "Kanban", board);
			});
		});
	},
	add_status_toggle_button: function (frm) {
		if (frm.is_new()) return;

		const is_open = frm.doc.status === "Open";
		const label = is_open ? __("Close Job Opening") : __("Reopen Job Opening");

		frm.add_custom_button(label, () => {
			frm.set_value("status", is_open ? "Closed" : "Open");
			frm.save();
		});
	},
	designation: function (frm) {
		if (frm.doc.designation) {
			frm.set_value("job_title", frm.doc.designation);
		}
		if (frm.doc.designation && frm.doc.company) {
			frappe.call({
				method: "hrms.hr.doctype.staffing_plan.staffing_plan.get_active_staffing_plan_details",
				args: {
					company: frm.doc.company,
					designation: frm.doc.designation,
					date: frappe.datetime.now_date(), // ToDo - Date in Job Opening?
				},
				callback: function (data) {
					if (data.message) {
						frm.set_value("staffing_plan", data.message[0].name);
						frm.set_value("planned_vacancies", data.message[0].vacancies);
					} else {
						frm.set_value("staffing_plan", "");
						frm.set_value("planned_vacancies", 0);
						frappe.show_alert({
							indicator: "orange",
							message: __("No Staffing Plans found for this Designation"),
						});
					}
				},
			});
		} else {
			frm.set_value("staffing_plan", "");
			frm.set_value("planned_vacancies", 0);
		}
	},
	company: function (frm) {
		frm.set_value("designation", "");
	},
	status: function (frm) {
		frm.close_warning_confirmed = false;
	},
	before_save: function (frm) {
		frm.trigger("confirm_close_if_needed");
	},
	after_save: function (frm) {
		frm.close_warning_confirmed = false;
	},
	confirm_close_if_needed: function (frm) {
		if (frm.is_new() || frm.close_warning_confirmed || frm.doc.status !== "Closed") {
			return;
		}

		frappe.validated = false;

		frm.call("get_close_warning").then((r) => {
			if (!r.message) {
				frm.close_warning_confirmed = true;
				frm.save();
				return;
			}

			frappe.confirm(r.message, () => {
				frm.close_warning_confirmed = true;
				frm.save();
			});
		});
	},

	job_opening_template: function (frm) {
		if (!frm.doc.job_opening_template) return;
		frappe.db.get_doc("Job Opening Template", frm.doc.job_opening_template).then((doc) => {
			frm.set_value({
				designation: doc.designation,
				department: doc.department,
				employment_type: doc.employment_type,
				location: doc.location,
				description: doc.description,
				currency: doc.currency,
				upper_range: doc.upper_range,
				lower_range: doc.lower_range,
				salary_per: doc.salary_per,
				publish_salary_range: doc.publish_salary_range,
			});

			frm.refresh_fields();
		});
	},
	publish: function (frm) {
		if (frm.doc.publish && !frm.doc.route) {
			frm.trigger("set_route");
		}
	},
	set_route: function (frm) {
		if (frm.doc.publish && !frm.doc.route) {
			route = `jobs/${frappe.scrub(frm.doc.company)}/${frappe.scrub(frm.doc.job_title)}`;
			frm.set_value("route", route);
		}
	},
});
