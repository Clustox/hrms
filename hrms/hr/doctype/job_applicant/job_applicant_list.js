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
	style.textContent =
		".ats-card-avatar{flex:0 0 auto;display:inline-flex}.ats-card-avatar .avatar{margin:0}" +
		".ats-applicant-board .kanban-col-dot{display:none}" +
		".ats-applicant-board .kanban-card-doc{display:none !important}" +
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
		".ats-card-info svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}" +
		".ats-applicant-board .kanban-column-header{display:flex;align-items:center;gap:8px}" +
		".ats-applicant-board .kanban-column-title{display:flex;align-items:center;flex:1;min-width:0;gap:8px}" +
		".ats-applicant-board .kanban-column-title .kanban-title{flex:1;min-width:0;font-size:13px;font-weight:500}" +
		".kanban-column-count.ats-count-badge{flex:0 0 auto;margin-left:auto;background:#1a6fd6;color:#fff;font-weight:600;" +
		"font-size:11px;min-width:22px;height:18px;line-height:18px;padding:0 7px;border-radius:999px;text-align:center;box-shadow:none}";
	document.head.appendChild(style);

	const add_avatars = () => {
		const route = frappe.get_route();
		const on_board = route[0] === "List" && route[1] === "Job Applicant" && route[2] === "Kanban";
		document.body.classList.toggle("ats-applicant-board", on_board);  // scopes the styles above to this board
		if (!on_board) return;

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

		fill_card_info();
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

// ---- what a card shows under the name: job title, @ employer, time since applied, time in this stage

const CARD_FIELDS = ["candidate_title", "candidate_employer", "designation", "applied_on", "creation", "stage_entered_on"];
const CARD_CACHE_SECONDS = 60;
const card_cache = {};
let card_fetch_running = false;

const ICON_CLOCK = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
const ICON_EYE = '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
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

function card_html(row) {
	const title = row.candidate_title || row.designation || "";
	const lines = [];
	if (title) lines.push(`<div class="ats-info-line" title="${frappe.utils.escape_html(title)}">${frappe.utils.escape_html(title)}</div>`);
	if (row.candidate_employer) {
		const employer = "@ " + row.candidate_employer;
		lines.push(`<div class="ats-info-line" title="${frappe.utils.escape_html(employer)}">${frappe.utils.escape_html(employer)}</div>`);
	}
	const applied_on = row.applied_on || row.creation;
	const applied = short_age(applied_on);
	const in_stage = short_age(row.stage_entered_on);
	const date_of = (value) => (value ? frappe.datetime.str_to_user(String(value).split(" ")[0]) : "");
	lines.push(
		`<div class="ats-info-times">` +
			(applied ? `<span title="${frappe.utils.escape_html(__("Applied on: {0}", [date_of(applied_on)]))}">${ICON_CLOCK}${applied}</span>` : "") +
			(in_stage ? `<span title="${frappe.utils.escape_html(__("In stage since: {0}", [date_of(row.stage_entered_on)]))}">${ICON_BOLT}${in_stage}</span>` : "") +
			`<span class="ats-act" data-ats-action="view" title="${__("Open")}">${ICON_EYE}</span>` +
			`</div>`,
	);
	return lines.join("");
}

function fill_card_info() {
	const cards = Array.from(document.querySelectorAll(".kanban-card-wrapper"));
	const now = Date.now();
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

		if (action === "view") {
			frappe.set_route("Form", "Job Applicant", name);
		} else if (action === "attach") {
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

// started here, not in onload: onload does not run when the board is opened directly
add_candidate_avatars_to_kanban_cards();
