import { computed } from "vue"

import { myAttendanceRequests, myShiftRequests, teamShiftRequests, teamAttendanceRequests } from "@/data/attendance"
import { myClaims, teamClaims } from "@/data/claims"
import { myLeaves, teamLeaves } from "@/data/leaves"

// Collapse the different per-doctype status fields (workflow state, status,
// approval_status, docstatus) into one of three buckets for display.
function bucket(label, docstatus) {
	if (/reject|cancel/i.test(label || "")) return "rejected"
	if (/approv|paid|submitted|closed/i.test(label || "")) return "approved"
	if (!label && docstatus === 1) return "approved"
	if (!label && docstatus === 2) return "rejected"
	return "pending"
}

function statusLabel(doc) {
	if (doc.workflow_state_field) return doc[doc.workflow_state_field]
	if (doc.doctype === "Expense Claim") {
		if (doc.approval_status === "Rejected") return "Rejected"
		if (doc.approval_status === "Approved") return "Approved"
		return doc.approval_status === "Draft" ? "Pending" : doc.status
	}
	if (doc.doctype === "Attendance Request") return null // no status field, docstatus only
	return doc.status === "Open" || doc.status === "Draft" ? "Pending" : doc.status
}

/**
 * Real data for the desktop dashboard's "Recent requests" list and pending
 * counts, read from the same resources the mobile RequestPanel uses.
 * Read-only: does not mutate the shared resource data.
 */
export function useDashboardRequests(__, dayjs, formatCurrency) {
	const all = computed(() =>
		[myLeaves, myClaims, myShiftRequests, myAttendanceRequests]
			.flatMap((r) => r?.data || [])
			.map((doc) => {
				const label = statusLabel(doc)
				const state = bucket(label, doc.docstatus)
				return { doc, state, label }
			})
	)

	const pendingCount = computed(() => all.value.filter((r) => r.state === "pending").length)

	const teamPendingCount = computed(() =>
		[teamLeaves, teamClaims, teamShiftRequests, teamAttendanceRequests].reduce(
			(n, r) => n + (r?.data?.length || 0),
			0
		)
	)

	const recent = computed(() =>
		[...all.value]
			.sort((a, b) => new Date(b.doc.creation) - new Date(a.doc.creation))
			.slice(0, 5)
			.map(({ doc, state, label }) => describe(doc, state, label, __, dayjs, formatCurrency))
	)

	const loading = computed(() =>
		[myLeaves, myClaims, myShiftRequests, myAttendanceRequests].some((r) => r?.loading && !r?.data)
	)

	return { recent, pendingCount, teamPendingCount, loading }
}

function range(from, to, dayjs) {
	if (!from) return ""
	const a = dayjs(from).format("D MMM")
	if (!to) return a
	const b = dayjs(to).format("D MMM")
	return a === b ? a : `${a} - ${b}`
}

function describe(doc, state, label, __, dayjs, formatCurrency) {
	const base = { key: `${doc.doctype}:${doc.name}`, state, statusText: label ? __(label) : "" }
	switch (doc.doctype) {
		case "Leave Application":
			return {
				...base,
				icon: "calendar",
				title: __(doc.leave_type, null, "Leave Type"),
				subtitle: `${doc.leave_dates || range(doc.from_date, doc.to_date, dayjs)} · ${__("{0}d", [
					doc.total_leave_days,
				])}`,
			}
		case "Expense Claim":
			return {
				...base,
				icon: "credit-card",
				title: doc.total_expenses > 1
					? __("{0} & {1} more", [__(doc.expense_type), doc.total_expenses - 1])
					: __(doc.expense_type) || __("Expense Claim"),
				subtitle: dayjs(doc.posting_date).format("D MMM"),
				amount: formatCurrency(doc.total_claimed_amount, doc.currency),
			}
		case "Shift Request":
			return {
				...base,
				icon: "clock",
				title: __("Shift Request"),
				subtitle: `${__(doc.shift_type || "")} · ${doc.shift_dates || range(doc.from_date, doc.to_date, dayjs)}`.replace(/^ · /, ""),
			}
		default:
			return {
				...base,
				icon: "check-circle",
				title: __("Attendance Request"),
				subtitle: doc.attendance_dates || range(doc.from_date, doc.to_date, dayjs),
				statusText: base.statusText || (state === "approved" ? __("Submitted") : state === "rejected" ? __("Cancelled") : __("Draft")),
			}
	}
}
