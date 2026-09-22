// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Attendance", {
	refresh(frm) {
		if (frm.doc.__islocal && !frm.doc.attendance_date) {
			frm.set_value("attendance_date", frappe.datetime.get_today());
		}

		frm.set_query("employee", () => {
			return {
				query: "erpnext.controllers.queries.employee_query",
			};
		});

		if (frm.doc.docstatus === 1 && frm.doc.status === "Absent") {
			frm.add_custom_button(
				__("Attendance Request"),
				() => {
					frappe.new_doc("Attendance Request", {
						employee: frm.doc.employee,
						from_date: frm.doc.attendance_date,
						to_date: frm.doc.attendance_date,
					});
				},
				__("Create"),
			);
		}
	},

	employee(frm) {
		if (frm.doc.employee && frm.doc.attendance_date && !frm.doc.shift) {
			frm.trigger("set_employee_shift");
		}
	},

	attendance_date(frm) {
		if (frm.doc.employee && frm.doc.attendance_date && !frm.doc.shift) {
			frm.trigger("set_employee_shift");
		}
	},

	set_employee_shift(frm) {
		if (!frm.doc.employee || !frm.doc.attendance_date) return;

		frappe.call({
			method: "hrms.hr.doctype.attendance.attendance.get_employee_shift",
			args: {
				employee: frm.doc.employee,
				for_date: frm.doc.attendance_date || frappe.datetime.get_today(),
				consider_default_shift: true,
			},
			callback(r) {
				if (r.message && !frm.doc.shift) {
					frm.set_value("shift", r.message);
				}
			},
		});
	},

	// Check-in/Check-out are a manual HR correction for a missed punch (see
	// the "Details" section) -- both fields, and Working Hours below, are
	// allow_on_submit so this also works on an already-submitted
	// Attendance, not just a draft. Working Hours is derived from both,
	// not separately typed in, so recompute it whenever either changes.
	in_time(frm) {
		frm.trigger("calculate_working_hours");
	},

	out_time(frm) {
		frm.trigger("calculate_working_hours");
	},

	calculate_working_hours(frm) {
		if (!frm.doc.in_time || !frm.doc.out_time) return;

		const in_time = frappe.datetime.str_to_obj(frm.doc.in_time);
		const out_time = frappe.datetime.str_to_obj(frm.doc.out_time);

		if (out_time <= in_time) {
			frappe.msgprint(__("Check-out must be after Check-in."));
			frm.set_value("out_time", "");
			return;
		}

		const hours = (out_time - in_time) / (1000 * 60 * 60);
		frm.set_value("working_hours", Math.round(hours * 100) / 100);
	},
});
