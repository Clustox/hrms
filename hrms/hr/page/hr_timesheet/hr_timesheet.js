frappe.pages["hr-timesheet"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("HR Timesheet"),
		single_column: true,
	});
	new HRTimesheet(page);
};

class HRTimesheet {
	constructor(page) {
		this.page = page;
		this.scope = "all";
		this.start = 0;
		this.page_length = 10;
		this.from_date = frappe.datetime.month_start();
		this.to_date = frappe.datetime.month_end();
		this.department = "";
		this.search = "";
		this.inject_styles();
		this.make_ui();
		this.load();
	}

	inject_styles() {
		if (document.getElementById("hr-timesheet-styles")) return;
		const css = `
		.hrts-tabs { display:flex; gap:4px; margin-bottom:12px; }
		.hrts-tab { display:flex; align-items:center; gap:6px; padding:6px 14px; border-radius:8px; cursor:pointer;
			font-weight:500; color:var(--text-muted); background:transparent; border:none; }
		.hrts-tab.active { background:var(--bg-light-gray, #f0f0ff); color:var(--text-color); }
		.hrts-toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:12px 16px;
			border:1px solid var(--border-color); border-radius:12px; margin-bottom:14px; background:var(--card-bg); }
		.hrts-toolbar .hrts-range { font-size:15px; font-weight:600; }
		.hrts-toolbar input, .hrts-toolbar select { border:1px solid var(--border-color); border-radius:8px;
			padding:5px 9px; font-size:13px; background:var(--control-bg); color:var(--text-color); }
		.hrts-spacer { flex:1; }
		.hrts-count { color:var(--text-muted); font-size:13px; margin:4px 2px 10px; }
		.hrts-card { display:flex; align-items:center; gap:18px; padding:16px 18px; border:1px solid var(--border-color);
			border-radius:12px; margin-bottom:10px; background:var(--card-bg); cursor:pointer; transition:box-shadow .15s, transform .15s; }
		.hrts-card:hover { box-shadow:0 4px 14px rgba(0,0,0,.06); transform:translateY(-1px); }
		.hrts-ava-wrap { position:relative; width:56px; height:56px; flex-shrink:0; }
		.hrts-ring { width:56px; height:56px; border-radius:50%; display:flex; align-items:center; justify-content:center; }
		.hrts-ava { position:absolute; inset:5px; border-radius:50%; display:flex; align-items:center; justify-content:center;
			font-weight:600; color:#fff; font-size:16px; }
		.hrts-pct { position:absolute; bottom:-8px; left:50%; transform:translateX(-50%); background:var(--card-bg);
			border:1px solid var(--border-color); border-radius:10px; font-size:10px; font-weight:700; padding:0 6px; }
		.hrts-main { flex:1; min-width:0; }
		.hrts-name { font-weight:600; font-size:14.5px; }
		.hrts-name small { color:var(--text-muted); font-weight:500; }
		.hrts-desig { color:var(--text-muted); font-size:12.5px; }
		.hrts-times { display:flex; flex-wrap:wrap; gap:16px; margin-top:8px; font-size:12.5px; }
		.hrts-times .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; vertical-align:middle; }
		.hrts-times b { font-weight:600; }
		.hrts-stats { display:flex; gap:8px; flex-shrink:0; }
		.hrts-stat { min-width:64px; text-align:center; border:1px solid var(--border-color); border-radius:10px; padding:7px 4px; }
		.hrts-stat .n { font-weight:700; font-size:16px; line-height:1; }
		.hrts-stat .l { font-size:10.5px; color:var(--text-muted); margin-top:3px; }
		.hrts-arrow { color:var(--text-muted); font-size:18px; padding-left:6px; }
		.hrts-pager { display:flex; justify-content:center; align-items:center; gap:12px; margin:16px 0; }
		.hrts-empty { text-align:center; color:var(--text-muted); padding:60px 0; }
		`;
		const style = document.createElement("style");
		style.id = "hr-timesheet-styles";
		style.textContent = css;
		document.head.appendChild(style);
	}

	make_ui() {
		const body = $(`
			<div class="hrts-root">
				<div class="hrts-tabs">
					<button class="hrts-tab" data-scope="my">${frappe.utils.icon("user", "sm")} ${__("My")}</button>
					<button class="hrts-tab active" data-scope="all">${frappe.utils.icon("list", "sm")} ${__("All")}</button>
					<button class="hrts-tab" data-scope="subordinates">${frappe.utils.icon("organization", "sm")} ${__("Subordinates")}</button>
				</div>
				<div class="hrts-toolbar">
					<span class="hrts-range"></span>
					<span class="hrts-spacer"></span>
					<label style="font-size:12px;color:var(--text-muted)">${__("From")}</label>
					<input type="date" class="hrts-from">
					<label style="font-size:12px;color:var(--text-muted)">${__("To")}</label>
					<input type="date" class="hrts-to">
					<input type="text" class="hrts-search" placeholder="${__("Search employee")}" style="width:150px">
					<button class="btn btn-default btn-sm hrts-refresh">${__("Refresh")}</button>
				</div>
				<div class="hrts-count"></div>
				<div class="hrts-list"></div>
				<div class="hrts-pager"></div>
			</div>
		`);
		this.page.main.html(body);
		this.$root = body;
		this.$list = body.find(".hrts-list");

		body.find(".hrts-from").val(this.from_date);
		body.find(".hrts-to").val(this.to_date);

		body.find(".hrts-tab").on("click", (e) => {
			body.find(".hrts-tab").removeClass("active");
			$(e.currentTarget).addClass("active");
			this.scope = $(e.currentTarget).data("scope");
			this.start = 0;
			this.load();
		});
		body.find(".hrts-refresh").on("click", () => this.apply_filters());
		body.find(".hrts-from, .hrts-to").on("change", () => this.apply_filters());
		body.find(".hrts-search").on(
			"input",
			frappe.utils.debounce(() => this.apply_filters(), 400)
		);
	}

	apply_filters() {
		this.from_date = this.$root.find(".hrts-from").val();
		this.to_date = this.$root.find(".hrts-to").val();
		this.search = this.$root.find(".hrts-search").val();
		this.start = 0;
		this.load();
	}

	load() {
		this.$list.html(`<div class="hrts-empty">${__("Loading...")}</div>`);
		frappe.call({
			method: "hrms.api.get_timesheet_overview",
			args: {
				from_date: this.from_date,
				to_date: this.to_date,
				scope: this.scope,
				start: this.start,
				page_length: this.page_length,
				search: this.search || null,
			},
			callback: (r) => this.render(r.message || {}),
		});
	}

	render(data) {
		const rows = data.rows || [];
		const total = data.total || 0;
		this.$root
			.find(".hrts-range")
			.text(
				`${frappe.datetime.str_to_user(this.from_date)} — ${frappe.datetime.str_to_user(this.to_date)}`
			);
		const to = Math.min(this.start + this.page_length, total);
		this.$root
			.find(".hrts-count")
			.text(total ? __("Showing {0}-{1} of {2}", [this.start + 1, to, total]) : "");

		if (!rows.length) {
			this.$list.html(`<div class="hrts-empty">${__("No employees found")}</div>`);
			this.$root.find(".hrts-pager").empty();
			return;
		}
		this.$list.empty();
		rows.forEach((row) => this.$list.append(this.card(row)));
		this.render_pager(total);
	}

	card(r) {
		const color = this.color_for(r.employee_name);
		const initials = (r.employee_name || "?")
			.split(" ")
			.map((w) => w[0])
			.slice(0, 2)
			.join("")
			.toUpperCase();
		const pct = r.percent || 0;
		const ring = `conic-gradient(${color} ${pct}%, var(--border-color) 0)`;
		const stat = (n, label) => `<div class="hrts-stat"><div class="n">${n}</div><div class="l">${label}</div></div>`;
		const time = (dot, label, h) =>
			`<span><span class="dot" style="background:${dot}"></span>${label}: <b>${this.fmt(h)}</b></span>`;

		const $c = $(`
			<div class="hrts-card">
				<div class="hrts-ava-wrap">
					<div class="hrts-ring" style="background:${ring}">
						<div class="hrts-ava" style="background:${color}">${frappe.utils.escape_html(initials)}</div>
					</div>
					<span class="hrts-pct">${pct}%</span>
				</div>
				<div class="hrts-main">
					<div class="hrts-name">${frappe.utils.escape_html(r.employee_name || "")} <small>(${r.employee})</small></div>
					<div class="hrts-desig">${frappe.utils.escape_html(r.designation || "")}</div>
					<div class="hrts-times">
						${time("#8a8a8a", __("Expected"), r.expected_hours)}
						${time("#22a06b", __("Worked"), r.worked_hours)}
						${time("#e0a106", __("Short"), r.short_hours)}
						${time("#1677ff", __("Over"), r.over_hours)}
					</div>
				</div>
				<div class="hrts-stats">
					${stat(r.present, __("Present"))}
					${stat(r.absent, __("Absent"))}
					${stat(r.leave, __("Leave"))}
					${stat(r.early_left, __("Early Left"))}
					${stat(r.late_arrival, __("Late Arrival"))}
				</div>
				<div class="hrts-arrow">${frappe.utils.icon("right", "md")}</div>
			</div>
		`);
		$c.on("click", () => {
			frappe.set_route("query-report", "Shift Attendance", {
				employee: r.employee,
				from_date: this.from_date,
				to_date: this.to_date,
			});
		});
		return $c;
	}

	render_pager(total) {
		const $p = this.$root.find(".hrts-pager").empty();
		const pages = Math.ceil(total / this.page_length);
		if (pages <= 1) return;
		const cur = Math.floor(this.start / this.page_length) + 1;
		const prev = $(`<button class="btn btn-default btn-sm">${__("Previous")}</button>`);
		const next = $(`<button class="btn btn-default btn-sm">${__("Next")}</button>`);
		prev.prop("disabled", cur <= 1).on("click", () => {
			this.start = Math.max(0, this.start - this.page_length);
			this.load();
		});
		next.prop("disabled", cur >= pages).on("click", () => {
			this.start += this.page_length;
			this.load();
		});
		$p.append(prev, `<span>${__("Page {0} of {1}", [cur, pages])}</span>`, next);
	}

	fmt(h) {
		h = Number(h) || 0;
		const hours = Math.floor(h);
		const mins = Math.round((h - hours) * 60);
		if (!hours && !mins) return "0m";
		return `${hours ? hours + "h " : ""}${mins}m`.trim();
	}

	color_for(name) {
		const palette = ["#1677ff", "#22a06b", "#e0a106", "#d9302b", "#7c3aed", "#0891b2", "#db2777"];
		let hash = 0;
		for (const ch of name || "") hash = (hash << 5) - hash + ch.charCodeAt(0);
		return palette[Math.abs(hash) % palette.length];
	}
}
