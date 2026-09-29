<template>
	<!--
		Air desktop dashboard for Expense claims. Rendered only at `lg:` (and only
		mounted when the viewport is desktop-wide). Reuses the same resources as the
		mobile Expense view: expenseClaimSummary / myClaims (data/claims) and
		advanceBalance (data/advances).
	-->
	<div class="hidden max-w-[1180px] px-10 pb-[70px] pt-[34px] lg:block">
		<div class="air-rise mb-8 flex items-end justify-between gap-6">
			<div>
				<h1 class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink">
					{{ __("Expense claims") }}
				</h1>
				<p class="mt-2.5 text-base text-air-muted">{{ subline }}</p>
			</div>
			<router-link
				:to="{ name: 'ExpenseClaimFormView' }"
				class="shrink-0 rounded-full bg-air-ink px-5 py-2.5 text-[14px] font-semibold text-white transition ease-air hover:bg-air-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue focus-visible:ring-offset-2"
			>
				{{ __("Claim an expense") }}
			</router-link>
		</div>

		<!-- summary tiles -->
		<div v-if="summary.data" class="mb-7 grid grid-cols-4 gap-5">
			<div
				v-for="(tile, i) in tiles"
				:key="tile.key"
				class="air-rise rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
				:style="{ '--air-delay': `${i * 70}ms` }"
			>
				<div class="mb-4 flex items-center justify-between">
					<span class="text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
						{{ tile.label }}
					</span>
					<span
						v-if="tile.icon"
						class="flex h-[26px] w-[26px] items-center justify-center rounded-full"
						:class="tile.wash"
					>
						<FeatherIcon :name="tile.icon" class="h-3.5 w-3.5" />
					</span>
				</div>
				<div
					class="truncate font-display text-[30px] font-semibold leading-none tracking-[-0.04em] text-air-ink tabular-nums"
				>
					{{ money(tile.shown) }}
				</div>
				<div class="mt-2.5 text-[13px] text-air-muted">{{ tile.note }}</div>
			</div>
		</div>
		<div
			v-else
			class="air-rise mb-7 rounded-air border border-air-line bg-air-surface p-[22px] text-center text-sm text-air-muted shadow-air"
		>
			{{ summary.loading ? __("Loading...") : __("No expense summary available") }}
		</div>

		<div class="grid grid-cols-[1.4fr_1fr] gap-5">
			<!-- recent expenses -->
			<div
				class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
				style="--air-delay: 320ms"
			>
				<div class="mb-1.5 flex items-center justify-between">
					<h3 class="font-display text-base font-semibold text-air-ink">{{ __("Recent expenses") }}</h3>
					<router-link
						:to="{ name: 'ExpenseClaimListView' }"
						class="text-[13.5px] font-medium text-air-blue hover:underline"
					>
						{{ __("View all") }}
					</router-link>
				</div>

				<template v-if="recentClaims.length">
					<router-link
						v-for="claim in recentClaims"
						:key="claim.key"
						:to="{ name: 'ExpenseClaimDetailView', params: { id: claim.key } }"
						class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
					>
						<div
							class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink-2"
						>
							<FeatherIcon name="credit-card" class="h-[17px] w-[17px]" />
						</div>
						<div class="min-w-0">
							<b class="block truncate text-sm font-semibold text-air-ink">{{ claim.title }}</b>
							<small class="block truncate text-[12.5px] text-air-muted">{{ claim.subtitle }}</small>
						</div>
						<span
							class="ml-auto shrink-0 whitespace-nowrap rounded-full px-[11px] py-1 text-xs font-semibold"
							:class="claim.pill"
						>
							{{ claim.statusText }}
						</span>
					</router-link>
				</template>
				<div v-else class="py-10 text-center text-sm text-air-muted">
					{{ myClaims.loading && !myClaims.data ? __("Loading...") : __("You have no requests") }}
				</div>
			</div>

			<!-- employee advance balance -->
			<div
				class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
				style="--air-delay: 390ms"
			>
				<div class="mb-1.5 flex items-center justify-between">
					<h3 class="font-display text-base font-semibold text-air-ink">
						{{ __("Employee advance balance") }}
					</h3>
					<router-link
						:to="{ name: 'EmployeeAdvanceListView' }"
						class="text-[13.5px] font-medium text-air-blue hover:underline"
					>
						{{ __("View list") }}
					</router-link>
				</div>

				<template v-if="advances.length">
					<router-link
						v-for="adv in advances"
						:key="adv.key"
						:to="{ name: 'EmployeeAdvanceDetailView', params: { id: adv.key } }"
						class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
					>
						<div class="min-w-0">
							<b class="block truncate font-display text-[17px] font-semibold text-air-ink tabular-nums">
								{{ adv.amount }}
							</b>
							<small class="block truncate text-[12.5px] text-air-muted">{{ adv.subtitle }}</small>
						</div>
						<span
							class="ml-auto shrink-0 whitespace-nowrap rounded-full px-[11px] py-1 text-xs font-semibold"
							:class="adv.pill"
						>
							{{ adv.statusText }}
						</span>
					</router-link>
				</template>
				<div v-else class="py-10 text-center text-sm text-air-muted">
					{{ advanceBalance.loading && !advanceBalance.data ? __("Loading...") : __("You have no advances") }}
				</div>

				<router-link
					:to="{ name: 'EmployeeAdvanceFormView' }"
					class="mt-3 block rounded-full border border-air-line bg-air-surface px-5 py-2.5 text-center text-[14px] font-semibold text-air-ink transition ease-air hover:border-air-blue hover:text-air-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
				>
					{{ __("Request an advance") }}
				</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import { expenseClaimSummary as summary, myClaims } from "@/data/claims"
import { advanceBalance } from "@/data/advances"
import { useCountUp } from "@/composables/useCountUp"
import { formatCurrency } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const currency = computed(() => summary.data?.currency)
const money = (v) => formatCurrency(v, currency.value)

// ---- Summary numbers (same derivations as ExpenseClaimSummary.vue) ----
const totalClaimed = computed(
	() =>
		(summary.data?.total_pending_amount || 0) +
		(summary.data?.total_claimed_in_approved || 0) +
		(summary.data?.total_rejected_amount || 0)
)
const pending = computed(() => summary.data?.total_pending_amount || 0)
const approved = computed(() => summary.data?.total_approved_amount || 0)
const rejected = computed(
	() =>
		(summary.data?.total_rejected_amount || 0) +
		((summary.data?.total_claimed_in_approved || 0) - (summary.data?.total_approved_amount || 0))
)

const shownClaimed = useCountUp(() => totalClaimed.value)
const shownPending = useCountUp(() => pending.value)
const shownApproved = useCountUp(() => approved.value)
const shownRejected = useCountUp(() => rejected.value)

const tiles = computed(() => [
	{
		key: "claimed",
		label: __("Total claimed"),
		shown: shownClaimed.value,
		note: __("Across all your claims"),
	},
	{
		key: "pending",
		label: __("Pending"),
		shown: shownPending.value,
		note: __("Awaiting approval"),
		icon: "alert-circle",
		wash: "bg-air-warn-w text-air-warn",
	},
	{
		key: "approved",
		label: __("Approved"),
		shown: shownApproved.value,
		note: __("Approved for payment"),
		icon: "check-circle",
		wash: "bg-air-good-w text-air-good",
	},
	{
		key: "rejected",
		label: __("Rejected"),
		shown: shownRejected.value,
		note: __("Not reimbursed"),
		icon: "x-circle",
		wash: "bg-air-crit-w text-air-crit",
	},
])

const subline = computed(() => {
	if (!summary.data) return summary.loading ? __("Loading...") : __("Claim and track your expenses")
	return __("{0} pending and {1} approved", [money(pending.value), money(approved.value)])
})

// ---- Status pills (mirrors the status logic of ExpenseClaimItem / EmployeeAdvanceItem) ----
const PILL = {
	neutral: "bg-air-surface-2 text-air-muted",
	info: "bg-air-blue-wash text-air-blue",
	good: "bg-air-good-w text-air-good",
	warn: "bg-air-warn-w text-air-warn",
	crit: "bg-air-crit-w text-air-crit",
}

const claimPill = {
	Draft: PILL.neutral,
	Submitted: PILL.info,
	Cancelled: PILL.crit,
	Paid: PILL.good,
	Unpaid: PILL.warn,
	"Approved & Draft": PILL.neutral,
	"Approved & Unpaid": PILL.warn,
	"Approved & Submitted": PILL.info,
	Rejected: PILL.crit,
}

function claimStatus(doc) {
	if (doc.workflow_state_field && doc[doc.workflow_state_field]) return doc[doc.workflow_state_field]
	if (doc.approval_status === "Approved" && ["Draft", "Unpaid", "Submitted"].includes(doc.status))
		return `${doc.approval_status} & ${doc.status}`
	if (doc.approval_status === "Rejected") return "Rejected"
	return doc.status
}

function claimDates(doc) {
	if (!doc.from_date && !doc.to_date) return dayjs(doc.posting_date).format("D MMM")
	if (doc.from_date === doc.to_date) return dayjs(doc.from_date).format("D MMM")
	return `${dayjs(doc.from_date).format("D MMM")} - ${dayjs(doc.to_date).format("D MMM")}`
}

const recentClaims = computed(() =>
	(myClaims.data || []).slice(0, 6).map((doc) => {
		const status = claimStatus(doc)
		let title = __(doc.expense_type)
		if (doc.total_expenses > 1) title = __("{0} & {1} more", [title, doc.total_expenses - 1])
		return {
			key: doc.name,
			title,
			subtitle: `${claimDates(doc)} · ${formatCurrency(doc.total_claimed_amount, doc.currency)}`,
			pill: claimPill[status] || PILL.neutral,
			statusText: __(status, null, "Expense Claim"),
		}
	})
)

const advancePill = {
	Paid: PILL.good,
	"Partially Paid": PILL.info,
	Unpaid: PILL.warn,
	Claimed: PILL.info,
	Returned: PILL.neutral,
	"Partly Claimed and Returned": PILL.warn,
}

const advances = computed(() =>
	(advanceBalance.data || []).map((doc) => {
		const status = doc.workflow_state_field && doc[doc.workflow_state_field] ? doc[doc.workflow_state_field] : doc.status
		return {
			key: doc.name,
			amount: doc.balance_amount
				? `${formatCurrency(doc.balance_amount, doc.currency)} / ${formatCurrency(doc.paid_amount, doc.currency)}`
				: formatCurrency(doc.advance_amount, doc.currency),
			subtitle: `${__(doc.purpose)} · ${dayjs(doc.posting_date).format("D MMM")}`,
			pill: advancePill[status] || PILL.neutral,
			statusText: __(status, null, "Employee Advance"),
		}
	})
)
</script>
