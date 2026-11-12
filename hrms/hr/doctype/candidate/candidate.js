// Copyright (c) 2026, Clustox and contributors
// For license information, please see license.txt

frappe.ui.form.on("Candidate", {
	refresh: function (frm) {
		frm.trigger("show_applications");
	},

	show_applications: function (frm) {
		// every job this person applied for, with their stage in each
		const applications = (frm.doc.__onload && frm.doc.__onload.applications) || [];
		const $wrapper = frm.get_field("applications_html").$wrapper;

		if (!applications.length) {
			$wrapper.html(`<p class="text-muted">${__("No applications yet.")}</p>`);
			return;
		}

		const rows = applications
			.map((a) => {
				const state = a.is_dropped
					? `${__("Dropped")}${a.drop_reason ? ": " + frappe.utils.escape_html(a.drop_reason) : ""}`
					: frappe.utils.escape_html(a.status || "");
				return `<tr>
					<td><a href="/desk/job-opening/${encodeURIComponent(a.job_title)}">${frappe.utils.escape_html(a.job_name || a.job_title || "")}</a></td>
					<td>${frappe.utils.escape_html(a.pipeline_stage || "")}</td>
					<td>${state}</td>
					<td>${a.applied_on ? frappe.datetime.str_to_user(a.applied_on) : ""}</td>
					<td><a href="/desk/job-applicant/${encodeURIComponent(a.name)}">${__("Open")}</a></td>
				</tr>`;
			})
			.join("");

		$wrapper.html(`<table class="table table-bordered table-sm">
			<thead><tr>
				<th>${__("Job")}</th><th>${__("Stage")}</th><th>${__("Status")}</th><th>${__("Applied On")}</th><th></th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table>`);
	},
});
