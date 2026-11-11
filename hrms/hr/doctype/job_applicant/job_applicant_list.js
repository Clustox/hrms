// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings["Job Applicant"] = {
	add_fields: ["status", "applicant_rating", "designation"],

	onload: function (listview) {
		patch_kanban_dialog_for_job_applicant();
		add_candidate_avatars_to_kanban_cards();

		// ATS: bring in candidates from the old system. Always a dry run first.
		if (frappe.user.has_role(["System Manager", "HR Manager"])) {
			listview.page.add_menu_item(__("Import from old ATS (CSV)"), () => {
				new frappe.ui.FileUploader({
					restrictions: { allowed_file_types: [".csv"] },
					make_attachments_public: false,
					on_success: (file) => {
						const run = (dry_run) =>
							frappe.xcall("hrms.ats.importer.import_csv_file", { file_url: file.file_url, dry_run });
						run(1).then((r) => {
							const errors = r.errors.slice(0, 20).map((e) => `<li>${__("Row")} ${e.row}: ${frappe.utils.escape_html(e.reason)}</li>`).join("");
							const more = r.errors.length > 20 ? `<p>${__("…and {0} more", [r.errors.length - 20])}</p>` : "";
							const summary = __("Checked {0} rows: {1} would be created ({2} new jobs), {3} already there, {4} with problems.", [r.rows, r.created, r.jobs_created, r.skipped, r.errors.length]);
							frappe.confirm(
								`<p>${summary}</p>${errors ? `<ul>${errors}</ul>${more}` : ""}<p>${__("Nothing has been imported yet. Import the rows without problems now?")}</p>`,
								() => run(0).then((d) => { frappe.msgprint(__("Imported {0} candidates.", [d.created])); listview.refresh(); }),
							);
						});
					},
				});
			});
		}

		// ATS: email the selected candidates from a template, one message each
		listview.page.add_actions_menu_item(__("Send Email"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("Select candidates first."));
			frappe.prompt(
				{ label: __("Template"), fieldname: "template", fieldtype: "Link", options: "Email Template", reqd: 1 },
				(values) => {
					frappe
						.xcall("hrms.ats.mail.send_bulk_email", { template: values.template, applicants: names })
						.then((r) => {
							let msg = __("{0} email(s) queued.", [r.sent]);
							if (r.skipped.length) {
								msg += "<br>" + __("Skipped:") + "<ul>" + r.skipped.map((s) => `<li>${frappe.utils.escape_html(s.applicant)}: ${frappe.utils.escape_html(s.reason)}</li>`).join("") + "</ul>";
							}
							frappe.msgprint(msg);
							listview.refresh();
						});
				},
				__("Send Email to {0} Candidates", [names.length]),
				__("Send"),
			);
		}, true);
	},

	get_indicator: function (doc) {
		if (doc.status === "Accepted") {
			return [__(doc.status), "green", "status,=," + doc.status];
		} else if (doc.status === "Shortlisted") {
			return [__(doc.status), "blue", "status,=," + doc.status];
		} else if (["Open", "Replied"].includes(doc.status)) {
			return [__(doc.status), "orange", "status,=," + doc.status];
		} else if (["Hold", "Rejected"].includes(doc.status)) {
			return [__(doc.status), "red", "status,=," + doc.status];
		}
	},
};

// Replaces the inline textarea UX with a direct frappe.new_doc() call so the
// status of the column is pre-filled and the user lands straight on the form.
document.addEventListener(
	"click",
	function (e) {
		const add_card_btn = e.target.closest(".kanban .add-card");
		if (!add_card_btn) return;

		const route = frappe.get_route();
		if (route[0] !== "List" || route[1] !== "Job Applicant" || route[2] !== "Kanban") return;

		e.stopImmediatePropagation();
		e.preventDefault();

		const column_title = add_card_btn.closest(".kanban-column").dataset.columnValue;
		frappe.new_doc("Job Applicant", { status: column_title });
	},
	true, // capture phase
);

// Allow rating stars to be clicked directly on kanban cards.
// Clicking the same value again toggles the rating back to 0 (matches desk behaviour).
document.addEventListener("click", function (e) {
	const star_svg = e.target.closest(".kanban .kanban-card-doc .rating svg");
	if (!star_svg) return;

	const route = frappe.get_route();
	if (route[0] !== "List" || route[1] !== "Job Applicant" || route[2] !== "Kanban") return;

	e.stopPropagation();

	const OUT_OF = 5;
	const star_index = parseInt(star_svg.getAttribute("data-rating"), 10);
	const rect = star_svg.getBoundingClientRect();
	const is_left_half = e.clientX - rect.left < rect.width / 2;
	const clicked_fraction = (is_left_half ? star_index - 0.5 : star_index) / OUT_OF;

	const card_wrapper = star_svg.closest(".kanban-card-wrapper");
	if (!card_wrapper) return;
	const docname = decodeURIComponent(card_wrapper.dataset.name);

	const rating_el = star_svg.closest(".rating");
	const current_fraction = kanban_rating_from_stars(rating_el, OUT_OF);
	const new_fraction = current_fraction === clicked_fraction ? 0 : clicked_fraction;

	frappe.db
		.set_value("Job Applicant", docname, "applicant_rating", new_fraction)
		.then(() => {
			kanban_apply_stars(rating_el, new_fraction, OUT_OF);
		})
		.catch(() => {
			kanban_apply_stars(rating_el, current_fraction, OUT_OF);
		});
});

function kanban_rating_from_stars(rating_el, out_of) {
	let value = 0;
	rating_el.querySelectorAll("svg").forEach((svg, i) => {
		const has_left = svg.querySelector(".left-half").classList.contains("star-click");
		const has_right = svg.querySelector(".right-half").classList.contains("star-click");
		if (has_left && has_right) value = (i + 1) / out_of;
		else if (has_left) value = (i + 0.5) / out_of;
	});
	return value;
}

function kanban_apply_stars(rating_el, fraction, out_of) {
	const filled = fraction * out_of;
	rating_el.querySelectorAll("svg").forEach((svg, i) => {
		const n = i + 1;
		const left = svg.querySelector(".left-half");
		const right = svg.querySelector(".right-half");
		if (n <= filled && filled % 1 === 0) {
			left.classList.add("star-click");
			right.classList.add("star-click");
		} else if (n <= Math.floor(filled)) {
			left.classList.add("star-click");
			right.classList.add("star-click");
		} else if (n - 0.5 <= filled) {
			left.classList.add("star-click");
			right.classList.remove("star-click");
		} else {
			left.classList.remove("star-click");
			right.classList.remove("star-click");
		}
	});
}

function patch_kanban_dialog_for_job_applicant() {
	if (frappe.views.KanbanView._job_applicant_kanban_patched) return;

	const _original = frappe.views.KanbanView.show_kanban_dialog;
	frappe.views.KanbanView.show_kanban_dialog = function (doctype) {
		if (doctype !== "Job Applicant") {
			return _original.call(this, doctype);
		}
		frappe
			.xcall("hrms.hr.doctype.job_applicant.job_applicant.create_kanban_board", {
				board_name: "Hiring Pipeline",
			})
			.then((board) => {
				frappe.set_route("List", "Job Applicant", "Kanban", board.kanban_board_name);
			});
	};

	frappe.views.KanbanView._job_applicant_kanban_patched = true;
}


// ATS: every candidate card on the board gets a round avatar with the candidate's initials in a colour
// taken from their name (different for different people, the same every time for the same person).
function add_candidate_avatars_to_kanban_cards() {
	if (window._ats_kanban_avatars) return;
	window._ats_kanban_avatars = true;

	const style = document.createElement("style");
	style.textContent = ".ats-card-avatar{flex:0 0 auto;display:inline-flex}.ats-card-avatar .avatar{margin:0}";
	document.head.appendChild(style);

	const add_avatars = () => {
		const route = frappe.get_route();
		if (route[0] !== "List" || route[1] !== "Job Applicant" || route[2] !== "Kanban") return;

		document.querySelectorAll(".kanban-card-wrapper:not(.ats-avatar-done)").forEach((card) => {
			const header = card.querySelector(".kanban-card-header");
			const title = card.querySelector(".kanban-card-title");
			if (!header || !title) return;
			card.classList.add("ats-avatar-done");
			if (header.querySelector(".avatar")) return;

			const name = (title.getAttribute("title") || title.textContent || "").trim();
			if (!name) return;
			const holder = document.createElement("span");
			holder.className = "ats-card-avatar";
			holder.innerHTML = frappe.get_avatar("avatar-medium", name);
			header.insertBefore(holder, header.firstChild);
		});
	};

	let scheduled = false;
	new MutationObserver(() => {
		if (scheduled) return;
		scheduled = true;
		requestAnimationFrame(() => {
			scheduled = false;
			add_avatars();
		});
	}).observe(document.body, { childList: true, subtree: true });
}
