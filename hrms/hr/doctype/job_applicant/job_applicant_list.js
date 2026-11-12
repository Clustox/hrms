// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings["Job Applicant"] = {
	add_fields: ["status", "applicant_rating", "designation"],

	onload: function (listview) {
		patch_kanban_dialog_for_job_applicant();

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
	const star_svg = e.target.closest(".kanban .kanban-card-doc .rating svg, .kanban .ats-info-rating .rating svg");
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
	style.textContent =
		".ats-card-avatar{flex:0 0 auto;display:inline-flex}.ats-card-avatar .avatar{margin:0}" +
		".ats-applicant-board .kanban-col-dot{display:none}" +
		".ats-applicant-board .kanban-card-doc{display:none !important}" +
		".ats-applicant-board .kanban-column{flex:0 0 300px !important;width:300px;min-width:300px;max-width:300px}" +
		".ats-applicant-board .kanban-title-area,.ats-applicant-board .kanban-card-body{min-width:0}" +
		".ats-card-text{min-width:0;overflow:hidden}" +
		".ats-applicant-board .kanban-card-wrapper .kanban-card{min-height:190px}" +
		".ats-applicant-board .kanban-card-header{height:auto !important;overflow:visible !important;align-items:flex-start}" +
		".ats-card-text{flex:1 1 auto;min-width:0}" +
		".ats-card-info{margin-top:1px;padding-left:0;color:var(--text-muted);font-size:12px;line-height:1.35}" +
		".ats-card-info .ats-info-line{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
		".ats-card-info .ats-info-times{display:flex;gap:12px;margin-top:6px;align-items:center}" +
		".ats-card-info .ats-info-times span{display:inline-flex;align-items:center;gap:3px}" +
		".ats-card-actions{margin-left:auto;display:flex;gap:6px;align-items:center;color:var(--text-muted);position:relative}" +
		".ats-card-actions .ats-act,.ats-card-info .ats-act{cursor:pointer;display:inline-flex;align-items:center;color:var(--text-muted)}" +
		".ats-card-actions .ats-act:hover,.ats-card-info .ats-act:hover{color:var(--text-color)}" +
		".ats-card-actions svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}" +
		".ats-card-info .ats-info-times .ats-act{margin-left:auto}" +
		".ats-card-menu{position:absolute;right:0;top:20px;z-index:20;background:var(--card-bg,#fff);border:1px solid var(--border-color);" +
		"border-radius:8px;box-shadow:var(--shadow-md);min-width:130px;padding:4px 0}" +
		".ats-card-menu div{padding:6px 12px;cursor:pointer;color:var(--text-color);font-size:12px}.ats-card-menu div:hover{background:var(--control-bg)}" +
		"body.ats-board-active{overflow:hidden}" +
		"body.ats-board-active .kanban{overflow-x:auto;overflow-y:hidden}" +
		"body.ats-board-active .kanban-column{display:flex;flex-direction:column;height:100%;min-height:0}" +
		"body.ats-board-active .kanban-column .kanban-cards{flex:1 1 auto;min-height:0;max-height:none;overflow-y:auto}" +
		".ats-dropped-bar{position:fixed;bottom:0;height:36px;z-index:5;overflow:hidden;background:#e8f0fb;border-top:1px solid #cddcf3;box-shadow:0 -2px 6px rgba(26,111,214,.08)}" +
		".ats-dropped-item{position:absolute;top:0;height:36px;display:flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;font-size:12.5px;font-weight:500;color:#1a6fd6;white-space:nowrap}" +
		".ats-dropped-item:hover{text-decoration:underline}.ats-dropped-item.ats-dropped-none{opacity:.65}" +
		".ats-dropped-item svg{width:16px;height:16px;flex:0 0 auto}" +
		".ats-job-bar{display:flex;flex-direction:column;gap:2px;padding:8px var(--padding-lg,24px);background:var(--bg-color,#fff);border-bottom:1px solid var(--border-color);line-height:1.3}" +
		".ats-job-line{display:flex;align-items:center;gap:8px;flex-wrap:wrap}" +
		".ats-job-badge{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;border-radius:999px;padding:2px 10px;line-height:1.4}" +
		".ats-badge-green{background:#2eaa5a;color:#fff}.ats-badge-blue{background:#1a6fd6;color:#fff}.ats-badge-grey{background:#8d99a6;color:#fff}" +
		".ats-badge-soft{background:var(--control-bg,#f0f0f0);color:var(--text-color);font-weight:500}.ats-badge-soft svg{width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2}" +
		".ats-job-picker{border:1px solid var(--border-color);border-radius:6px;padding:2px 8px;background:var(--control-bg,#fff);color:var(--text-color);max-width:320px}" +
		".ats-job-title{font-size:16px;font-weight:600;color:var(--text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
		".ats-job-meta{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--text-muted);white-space:nowrap}" +
		".ats-job-meta span{display:inline-flex;align-items:center;gap:4px}" +
		".ats-job-meta svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}" +
		".ats-job-tag{background:var(--control-bg,#f3f3f3);color:var(--text-color);border-radius:6px;padding:1px 8px}" +
		".ats-info-rating{margin-top:2px}.ats-info-rating .rating{display:flex;gap:0}" +
		".ats-info-rating .rating svg{width:16px;height:16px;margin:0 -1px 0 0 !important}" +
		".ats-card-info .ats-info-times svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}" +
		".ats-applicant-board .kanban-column-header{display:flex;align-items:center;gap:8px}" +
		".ats-applicant-board .kanban-column-title{display:flex;align-items:center;flex:1;min-width:0;gap:8px}" +
		".ats-applicant-board .kanban-column-title .kanban-title{flex:1;min-width:0;font-size:13px;font-weight:500}" +
		".kanban-column-count.ats-count-badge{flex:0 0 auto;margin-left:auto;background:#1a6fd6;color:#fff;font-weight:600;" +
		"font-size:11px;min-width:22px;height:18px;line-height:18px;padding:0 7px;border-radius:999px;text-align:center;box-shadow:none}";
	document.head.appendChild(style);

	const add_avatars = () => {
		const route = frappe.get_route();
		const on_board = route[0] === "List" && route[1] === "Job Applicant" && route[2] === "Kanban";
		const on_other_board = route[0] === "List" && route[2] === "Kanban" && !on_board;
		document.body.classList.toggle("ats-board-active", on_board);  // page scroll is off only while this board shows
		if (on_board) fit_board();
		// scopes the styles above to this board. They stay on while a form is opening (the board is still
		// on screen for a moment, and must not flash its old card layout) and go off for any other board.
		if (on_board) document.body.classList.add("ats-applicant-board");
		else if (on_other_board) document.body.classList.remove("ats-applicant-board");
		if (!on_board) {
			const bar = document.querySelector(".ats-dropped-bar");
			if (bar) bar.remove();  // the bar belongs to this board only
			return;
		}

		// the number of candidates in each column: a blue pill, "999+" when there are more than that
		document.querySelectorAll(".kanban-column-count").forEach((badge) => {
			badge.classList.add("ats-count-badge");
			const shown = badge.textContent.trim();
			if (/^\d+$/.test(shown) && parseInt(shown, 10) > 999) {
				badge.setAttribute("title", shown);
				badge.textContent = "999+";
			}
		});

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

		[fill_card_info, fill_job_header, fill_dropped_footers].forEach((fill) => {
			try {
				fill();
			} catch (error) {
				console.error("ATS board:", fill.name, error);
			}
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

// ---- the header of a job's board: job title, recruiter, department tag and location

const job_details = {};
const ICON_USER = '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>';
const ICON_PIN = '<svg viewBox="0 0 24 24"><path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>';

// the job a board is about: the page's job filter, else the job in the board's own filters (a job's own board)
function filtered_job() {
	const list = window.cur_list;
	if (!list || list.doctype !== "Job Applicant" || !list.board) return null;
	const filter = board_filters(list).find((f) => f[1] === "job_title" && f[2] === "=");
	return filter ? filter[3] : null;
}

function load_job_details(job) {
	if (job_details[job]) return Promise.resolve(job_details[job]);
	const fields = ["job_title", "job_owner", "department", "location", "status", "publish", "lower_range", "upper_range", "currency", "salary_negotiable"];
	return frappe.db.get_value("Job Opening", job, fields).then(({ message }) => {
		const m = message || {};
		const details = {
			title: m.job_title || job,
			location: m.location || "",
			status: m.status || "",
			published: !!m.publish,
			salary: "",
			department: "",
			recruiter: "",
		};
		const money = (value) => (value ? format_number(value, null, 0) : "");
		if (m.salary_negotiable) details.salary = __("Negotiable");
		else if (m.lower_range || m.upper_range) {
			details.salary = [m.currency, [money(m.lower_range), money(m.upper_range)].filter(Boolean).join(" - ")].filter(Boolean).join(" ");
		}
		const lookups = [];
		if (m.job_owner) {
			lookups.push(
				frappe.db.get_value("User", m.job_owner, "full_name").then((r) => (details.recruiter = (r.message && r.message.full_name) || m.job_owner)),
			);
		}
		if (m.department) {
			lookups.push(
				frappe.db.get_value("Department", m.department, "department_name").then((r) => (details.department = (r.message && r.message.department_name) || m.department)),
			);
		}
		return Promise.all(lookups).then(() => (job_details[job] = details));
	});
}

// all-jobs board: a picker that opens a job's board (and with it, the job's header)
function open_job_board(job) {
	frappe.xcall("hrms.ats.board.get_job_board", { job }).then((board) => {
		frappe.route_options = { job_title: job };
		frappe.set_route("List", "Job Applicant", "Kanban", board);
	});
}

function fill_job_header() {
	const list = window.cur_list;
	if (!list || list.doctype !== "Job Applicant" || !list.page || !list.page.wrapper) return;
	const wrapper = list.page.wrapper[0];
	const head = wrapper.querySelector(".page-head");
	if (!head) return;
	const job = filtered_job();
	const wanted = job || "*all";
	const existing = wrapper.querySelector(".ats-job-bar");
	if (existing && existing.dataset.atsJob === wanted) return;

	if (existing) existing.remove();
	const bar = document.createElement("div");
	bar.className = "ats-job-bar";
	bar.dataset.atsJob = wanted;
	head.insertAdjacentElement("afterend", bar);
	const e = frappe.utils.escape_html;

	if (!job) {
		bar.innerHTML =
			`<div class="ats-job-title">${__("All jobs")}</div>` +
			`<div class="ats-job-meta"><select class="ats-job-picker"><option value="">${__("Open a job's board…")}</option></select></div>`;
		frappe.db.get_list("Job Opening", { fields: ["name", "job_title"], order_by: "job_title asc", limit: 500 }).then((jobs) => {
			if (!bar.isConnected) return;
			const picker = bar.querySelector(".ats-job-picker");
			jobs.forEach((j) => picker.insertAdjacentHTML("beforeend", `<option value="${e(j.name)}">${e(j.job_title)}</option>`));
			picker.addEventListener("change", () => picker.value && open_job_board(picker.value));
		});
		return;
	}

	load_job_details(job).then((d) => {
		if (bar.dataset.atsJob !== job || !bar.isConnected) return; // the board changed while this was loading
		bar.innerHTML =
			`<div class="ats-job-line"><span class="ats-job-title" title="${e(d.title)}">${e(d.title)}</span>` +
			(d.published ? `<span class="ats-job-badge ats-badge-green">${__("PUBLISHED")}</span>` : "") +
			(d.status ? `<span class="ats-job-badge ${d.status === "Open" ? "ats-badge-blue" : "ats-badge-grey"}">${e(d.status.toUpperCase())}</span>` : "") +
			(d.recruiter ? `<span class="ats-job-badge ats-badge-soft">${ICON_USER}${e(d.recruiter)}</span>` : "") +
			`</div>` +
			`<div class="ats-job-meta">` +
			(d.department ? `<span class="ats-job-tag">${e(d.department)}</span>` : "") +
			(d.location ? `<span>${ICON_PIN}${e(d.location)}</span>` : "") +
			(d.salary ? `<span>${e(d.salary)}</span>` : "") +
			`</div>`;
	});
}

// ---- what a card shows under the name: job title, @ employer, time since applied, time in this stage

const CARD_FIELDS = ["candidate_title", "candidate_employer", "designation", "applied_on", "creation", "stage_entered_on", "applicant_rating"];
const CARD_CACHE_SECONDS = 60;
const card_cache = {};
let card_fetch_running = false;

const ICON_CLOCK = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
const ICON_FILE = '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';
const ICON_DOTS = '<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="12" cy="19" r="1.2"/></svg>';
const ICON_BOLT = '<svg viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/></svg>';

function short_age(value) {
	if (!value) return "";
	const seconds = Math.max(0, (Date.now() - new Date(String(value).replace(" ", "T")).getTime()) / 1000);
	const units = [["y", 31536000], ["mo", 2592000], ["w", 604800], ["d", 86400], ["h", 3600], ["m", 60]];
	for (const [label, size] of units) {
		if (seconds >= size) return Math.floor(seconds / size) + label;
	}
	return "now";
}

// the same stars the rating field has everywhere in Frappe (and the card had before)
function stars_html(rating) {
	return `<div class="ats-info-rating">${frappe.format(Number(rating) || 0, { fieldtype: "Rating", options: 5 })}</div>`;
}

function card_html(row) {
	const title = row.candidate_title || row.designation || "";
	const lines = [];
	if (title) lines.push(`<div class="ats-info-line" title="${frappe.utils.escape_html(title)}">${frappe.utils.escape_html(title)}</div>`);
	if (row.candidate_employer) {
		const employer = "@ " + row.candidate_employer;
		lines.push(`<div class="ats-info-line" title="${frappe.utils.escape_html(employer)}">${frappe.utils.escape_html(employer)}</div>`);
	}
	lines.push(stars_html(row.applicant_rating));
	const applied_on = row.applied_on || row.creation;
	const applied = short_age(applied_on);
	const in_stage = short_age(row.stage_entered_on);
	const date_of = (value) => (value ? frappe.datetime.str_to_user(String(value).split(" ")[0]) : "");
	lines.push(
		`<div class="ats-info-times">` +
			(applied ? `<span title="${frappe.utils.escape_html(__("Applied on: {0}", [date_of(applied_on)]))}">${ICON_CLOCK}${applied}</span>` : "") +
			(in_stage ? `<span title="${frappe.utils.escape_html(__("In stage since: {0}", [date_of(row.stage_entered_on)]))}">${ICON_BOLT}${in_stage}</span>` : "") +
			`</div>`,
	);
	return lines.join("");
}

function fill_card_info() {
	const cards = Array.from(document.querySelectorAll(".kanban-card-wrapper"));
	const now = Date.now();

	// the board already loaded these fields with its cards: use them straight away, no extra request
	const loaded = new Map(((window.cur_list && window.cur_list.data) || []).map((doc) => [doc.name, doc]));
	cards.forEach((card) => {
		const name = decodeURIComponent(card.dataset.name || "");
		const doc = loaded.get(name);
		if (!name || card_cache[name] || !doc || !("stage_entered_on" in doc)) return;
		const row = {};
		["name", ...CARD_FIELDS].forEach((field) => (row[field] = doc[field]));
		card_cache[name] = { at: now, row };
	});
	const wanted = cards.filter((card) => {
		const name = decodeURIComponent(card.dataset.name || "");
		const have = card_cache[name];
		return name && !(have && now - have.at < CARD_CACHE_SECONDS * 1000);  // missing or older than a minute
	});

	const render = () => {
		cards.forEach((card) => {
			const entry = card_cache[decodeURIComponent(card.dataset.name || "")];
			const area = card.querySelector(".kanban-title-area");
			if (!entry || !entry.row || !area) return;
			const header = card.querySelector(".kanban-card-header");
			if (header && !header.querySelector(".ats-card-actions")) {
				const actions = document.createElement("span");
				actions.className = "ats-card-actions";
				actions.innerHTML =
					`<span class="ats-act" data-ats-action="attach" title="${__("Attach file")}">${ICON_FILE}</span>` +
					`<span class="ats-act" data-ats-action="menu" title="${__("More")}">${ICON_DOTS}</span>`;
				header.appendChild(actions);
			}
			const html = card_html(entry.row);
			let info = card.querySelector(".ats-card-info");
			if (info) {
				if (info.innerHTML !== html) info.innerHTML = html;  // refreshed: a moved card starts counting again
				return;
			}
			// the name and what goes under it share one column, so the text sits right below the name
			let column = header && header.querySelector(".ats-card-text");
			if (!column && header) {
				const link = header.querySelector(".kanban-card-title-link");
				column = document.createElement("div");
				column.className = "ats-card-text";
				header.insertBefore(column, link);
				if (link) column.appendChild(link);
			}
			info = document.createElement("div");
			info.className = "ats-card-info";
			info.innerHTML = html;
			(column || area).appendChild(info);
		});
	};

	if (!wanted.length) return render();
	if (card_fetch_running) return;
	card_fetch_running = true;
	const names = [...new Set(wanted.map((card) => decodeURIComponent(card.dataset.name)))];
	frappe
		.xcall("frappe.client.get_list", {
			doctype: "Job Applicant",
			filters: [["name", "in", names]],
			fields: ["name", ...CARD_FIELDS],
			limit_page_length: names.length,
		})
		.then((rows) => {
			names.forEach((name) => (card_cache[name] = { at: Date.now(), row: null }));
			rows.forEach((row) => (card_cache[row.name] = { at: Date.now(), row }));
		})
		.catch(() => names.forEach((name) => (card_cache[name] = { at: Date.now(), row: null })))
		.finally(() => {
			card_fetch_running = false;
			render();
			// cards drawn while this request was running were skipped: ask for them now (no-op when none are missing)
			setTimeout(fill_card_info, 0);
		});
}

document.addEventListener(
	"click",
	function (e) {
		const button = e.target.closest("[data-ats-action]");
		const open_menu = document.querySelector(".ats-card-menu");
		if (open_menu && !e.target.closest(".ats-card-menu")) open_menu.remove();
		if (!button || !button.closest(".kanban-card-wrapper")) return;

		e.stopImmediatePropagation();
		e.preventDefault();
		const name = decodeURIComponent(button.closest(".kanban-card-wrapper").dataset.name);
		const action = button.dataset.atsAction;

		if (action === "attach") {
			new frappe.ui.FileUploader({ doctype: "Job Applicant", docname: name, make_attachments_public: false });
		} else if (action === "menu") {
			if (open_menu) return;
			const menu = document.createElement("div");
			menu.className = "ats-card-menu";
			menu.innerHTML = `<div data-item="open">${__("Open")}</div><div data-item="email">${__("Send Email")}</div>`;
			button.closest(".ats-card-actions").appendChild(menu);
			menu.addEventListener("click", (ev) => {
				const item = ev.target.closest("[data-item]");
				if (!item) return;
				ev.stopPropagation();
				menu.remove();
				if (item.dataset.item === "open") return frappe.set_route("Form", "Job Applicant", name);
				frappe.prompt(
					{ label: __("Template"), fieldname: "template", fieldtype: "Link", options: "Email Template", reqd: 1 },
					(values) =>
						frappe
							.xcall("hrms.ats.mail.send_template_email", { job_applicant: name, template: values.template })
							.then(() => frappe.show_alert({ message: __("Email queued"), indicator: "green" })),
					__("Send Email to Candidate"),
					__("Send"),
				);
			});
		}
	},
	true, // capture phase, so the card does not also open
);

// ---- "N Dropped Candidates" under each column: the people dropped while they were in that stage

const ICON_DROPPED = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#1a6fd6"/><path d="M7 12h10" stroke="#fff" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg>';
const dropped = { key: "", at: 0, loading: false, counts: {} };
const DROPPED_CACHE_SECONDS = 30;

// the filters the board is looking at (the page's, and the board's own), without its "not dropped" rule
function board_filters(list) {
	const page = list.filter_area ? list.filter_area.get() || [] : [];
	const own = (list.board && list.board.filters_array) || [];
	return [...page, ...own].filter((f) => f[1] !== "is_dropped");
}

// the board takes exactly the screen that is left under the header (and above the dropped bar), so the page
// never scrolls: only the cards inside each column do
function fit_board() {
	const board = document.querySelector(".kanban");
	if (!board) return;
	window.scrollTo(0, 0);
	const top = board.getBoundingClientRect().top;
	const room = Math.max(240, window.innerHeight - top - 40);
	if (board.style.height !== room + "px") board.style.height = room + "px";
}

window.addEventListener("resize", () => requestAnimationFrame(fit_board));

// one bar fixed to the bottom of the screen, with the count of each column centred under that column
function place_dropped_bar() {
	const route = frappe.get_route();
	const on_board = route[0] === "List" && route[1] === "Job Applicant" && route[2] === "Kanban";
	let bar = document.querySelector(".ats-dropped-bar");
	const board = document.querySelector(".kanban");
	if (!on_board || !board) {
		if (bar) bar.remove();
		return;
	}
	if (!bar) {
		bar = document.createElement("div");
		bar.className = "ats-dropped-bar";
		document.body.appendChild(bar);
	}

	const frame = board.getBoundingClientRect();
	bar.style.left = frame.left + "px";
	bar.style.width = frame.width + "px";

	const columns = Array.from(document.querySelectorAll(".kanban-column"));
	const seen = new Set();
	columns.forEach((column) => {
		const stage = column.dataset.columnValue;
		if (!stage) return;
		seen.add(stage);
		let item = Array.from(bar.children).find((el) => el.dataset.stage === stage);
		if (!item) {
			item = document.createElement("div");
			item.className = "ats-dropped-item";
			item.dataset.stage = stage;
			bar.appendChild(item);
		}
		const rect = column.getBoundingClientRect();
		item.style.left = rect.left - frame.left + "px";
		item.style.width = rect.width + "px";
		const n = dropped.counts[stage] || 0;
		const label = n === 1 ? __("{0} Dropped Candidate", [n]) : __("{0} Dropped Candidates", [n]);
		const html = `${ICON_DROPPED}<span>${frappe.utils.escape_html(label)}</span>`;
		if (item.innerHTML !== html) item.innerHTML = html;
		item.classList.toggle("ats-dropped-none", !n);
	});
	Array.from(bar.children).forEach((el) => {
		if (!seen.has(el.dataset.stage)) el.remove();
	});
}

// the items follow the columns when the board is scrolled sideways or the window changes
["scroll", "resize"].forEach((name) =>
	window.addEventListener(name, () => requestAnimationFrame(place_dropped_bar), true),
);

function fill_dropped_footers() {
	const list = window.cur_list;
	if (!list || list.doctype !== "Job Applicant" || !list.board) return;
	const filters = board_filters(list);
	const key = JSON.stringify(filters);

	const render = () => place_dropped_bar();

	const stale = Date.now() - dropped.at > DROPPED_CACHE_SECONDS * 1000;
	if ((key !== dropped.key || stale) && !dropped.loading) {
		dropped.loading = true;
		frappe
			.xcall("frappe.client.get_list", {
				doctype: "Job Applicant",
				filters: [...filters, ["Job Applicant", "is_dropped", "=", 1]],
				fields: ["dropped_at_stage", { COUNT: "*", as: "n" }],
				group_by: "dropped_at_stage",
				limit_page_length: 0,
			})
			.then((rows) => {
				dropped.counts = {};
				rows.forEach((row) => (dropped.counts[row.dropped_at_stage] = row.n));
			})
			.catch(() => {})
			.finally(() => {
				dropped.key = key;
				dropped.at = Date.now();
				dropped.loading = false;
				render();
			});
		return;
	}
	render();
}

document.addEventListener(
	"click",
	function (e) {
		const footer = e.target.closest && e.target.closest(".ats-dropped-item");
		if (!footer || !window.cur_list) return;
		e.preventDefault();
		e.stopPropagation();
		const options = { is_dropped: 1, dropped_at_stage: footer.dataset.stage };
		const job = (board_filters(window.cur_list).find((f) => f[1] === "job_title" && f[2] === "=") || [])[3];
		if (job) options.job_title = job;
		frappe.route_options = options;
		frappe.set_route("List", "Job Applicant", "List");
	},
	true,
);

// ---- column counts after a card is dropped in another column
//
// Frappe is meant to adjust the two columns' totals when a card is dropped, but its drop code waits for a
// ".done" callback that the request no longer has, so the pills keep the old numbers until the board is
// reloaded. After a drop we ask the server for the real totals (the same call the board loads with, with
// the board's own filters) and put them back.

function sync_column_counts() {
	const list = window.cur_list;
	if (!list || list.doctype !== "Job Applicant" || !list.get_kanban_api_args || !list.kanban_column_state) return;

	frappe
		.xcall("frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data", list.get_kanban_api_args({ kanban_page_length: 1 }))
		.then((result) => {
			Object.entries(result.columns || {}).forEach(([column, data]) => {
				const state = list.kanban_column_state[column];
				if (state) state.total_count = data.total;
				document.querySelectorAll(".kanban-column").forEach((el) => {
					if (el.dataset.columnValue !== column) return;
					const badge = el.querySelector(".kanban-column-count");
					if (badge) badge.textContent = data.total;
				});
			});
		})
		.catch(() => {});
}

let counts_timers = [];
function after_card_dropped(e) {
	if (!e.target.closest || !e.target.closest(".kanban-column")) return;
	const route = frappe.get_route();
	if (route[0] !== "List" || route[1] !== "Job Applicant" || route[2] !== "Kanban") return;
	counts_timers.forEach(clearTimeout);
	// the move is saved a moment after the drop: look again once it has, and once more to be sure
	counts_timers = [setTimeout(sync_column_counts, 1200), setTimeout(sync_column_counts, 3500)];
}
// the board's drag library uses the browser's own drag and drop, which ends with dragend/drop and sends no pointerup
["dragend", "drop", "pointerup"].forEach((name) => document.addEventListener(name, after_card_dropped, true));

// started here, not in onload: onload does not run when the board is opened directly
add_candidate_avatars_to_kanban_cards();
