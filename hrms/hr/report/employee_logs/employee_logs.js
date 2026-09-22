// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Employee logs"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
	],
	formatter: (value, row, column, data, default_formatter) => {
		value = default_formatter(value, row, column, data);
		if (["check_in_status", "check_out_status"].includes(column.fieldname)) {
			const color = value.includes(__("Missing")) ? "red" : "green";
			return `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
	onload: function (report) {
		setup_add_checkin_button(report);
		setup_checkin_primary_action(report);
	},
	get_datatable_options: function (options) {
		return Object.assign(options, { layout: "fluid" });
	},
};

function get_next_checkin(last_log_type) {
	return last_log_type === "IN"
		? {
				log_type: "OUT",
				label: __("Check Out"),
				working_label: __("Checking Out..."),
				icon: "circle-arrow-left",
		  }
		: {
				log_type: "IN",
				label: __("Check In"),
				working_label: __("Checking In..."),
				icon: "circle-arrow-right",
		  };
}

function setup_add_checkin_button(report) {
	if (frappe.perm.has_perm("Employee Checkin", 0, "create")) {
		report.page.add_inner_button(__("Add Checkin for Another Employee"), () =>
			frappe.new_doc("Employee Checkin"),
		);
	}
}

async function setup_checkin_primary_action(report) {
	const employee = await frappe.xcall("hrms.api.get_current_employee_info");
	if (!employee) return;

	report.checkin_employee = employee;
	report.track_geolocation = await frappe.db.get_single_value(
		"HR Settings",
		"allow_geolocation_tracking",
	);
	report.set_primary_action = () => {
		const next = report.next_checkin;
		if (!next) return;

		report.page.set_primary_action(
			next.label,
			() => {
				const checkin = start_checkin(report, next);
				return report.track_geolocation ? undefined : checkin;
			},
			next.icon,
			next.working_label,
		);
	};

	await refresh_checkin_state(report);
}

async function refresh_checkin_state(report) {
	const employee = report?.checkin_employee;
	if (!employee) return;

	const [last_log] = await frappe.db.get_list("Employee Checkin", {
		filters: { employee: employee.name },
		fields: ["log_type"],
		order_by: "time desc",
		limit: 1,
	});

	report.next_checkin = get_next_checkin(last_log?.log_type);
	report.set_primary_action();
}

async function start_checkin(report, next) {
	const time = frappe.datetime.now_datetime();

	if (!report.track_geolocation) {
		return submit_checkin(report, next, time);
	}

	let coordinates;
	let failure;
	frappe.dom.freeze(__("Fetching your geolocation") + "...");
	try {
		coordinates = await hrms.get_current_position();
		await frappe.require(["leaflet.bundle.js", "leaflet.bundle.css"]);
	} catch (error) {
		failure = error || {};
	} finally {
		frappe.dom.unfreeze();
	}

	if (failure) {
		return frappe.msgprint({
			message: hrms.get_geolocation_error_message(failure),
			title: __("Geolocation Error"),
			indicator: "red",
			primary_action: {
				label: __("Retry"),
				action: () => {
					frappe.hide_msgprint(true);
					start_checkin(report, next);
				},
			},
		});
	}

	confirm_checkin_location(report, next, time, coordinates);
}

function confirm_checkin_location(report, next, time, coordinates) {
	const geojson = JSON.stringify({
		type: "FeatureCollection",
		features: [
			{
				type: "Feature",
				properties: {},
				geometry: {
					type: "Point",
					coordinates: [coordinates.longitude, coordinates.latitude],
				},
			},
		],
	});

	const dialog = new frappe.ui.Dialog({
		title: next.label,
		fields: [
			{
				fieldname: "time",
				label: __("Time"),
				fieldtype: "Datetime",
				read_only: 1,
				default: time,
			},
			{ fieldtype: "Section Break", hide_border: 1 },
			{
				fieldname: "latitude",
				label: __("Latitude"),
				fieldtype: "Float",
				precision: "7",
				read_only: 1,
				default: coordinates.latitude,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "longitude",
				label: __("Longitude"),
				fieldtype: "Float",
				precision: "7",
				read_only: 1,
				default: coordinates.longitude,
			},
			{ fieldtype: "Section Break", hide_border: 1 },
			{
				fieldname: "geolocation",
				fieldtype: "Geolocation",
				default: geojson,
			},
		],
		primary_action_label: __("Confirm {0}", [next.label]),
		primary_action_loading_label: next.working_label,
		primary_action: async () => {
			const checkin = await submit_checkin(report, next, time, coordinates);
			if (checkin) dialog.hide();
		},
	});

	dialog.fields_dict.geolocation.disabled = 1;
	dialog.show();
}

async function submit_checkin(report, next, time, coordinates) {
	if (report.checkin_in_progress) return;
	report.checkin_in_progress = true;

	try {
		const checkin = await frappe.db.insert({
			doctype: "Employee Checkin",
			employee: report.checkin_employee.name,
			log_type: next.log_type,
			time: time,
			...(coordinates || {}),
		});

		frappe.show_alert({
			message: checkin.offshift
				? __(
						"{0} recorded outside shift hours. It will not be considered for attendance.",
						[next.label],
				  )
				: __("{0} successful", [next.label]),
			indicator: checkin.offshift ? "orange" : "green",
		});

		await refresh_checkin_state(report);
		report.refresh();

		return checkin;
	} catch (error) {
		return;
	} finally {
		report.checkin_in_progress = false;
	}
}
