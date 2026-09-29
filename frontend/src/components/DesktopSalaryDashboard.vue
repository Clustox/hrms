<template>
	<!--
		Air desktop dashboard for Salary slips. Rendered only at `lg:` (and only
		mounted when the viewport is desktop-wide). Purely presentational: the
		payroll-period / salary-slip resources, the period-change reload and the
		`hrms:update_salary_slips` socket subscription all live in the parent view
		so they are registered exactly once. Data comes in via props.
	-->
	<div class="hidden max-w-[1180px] px-10 pb-[70px] pt-[34px] lg:block">
		<div class="air-rise mb-8">
			<h1 class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink">
				{{ __("Salary slips") }}
			</h1>
			<p class="mt-2.5 text-base text-air-muted">{{ subline }}</p>
		</div>

		<div class="grid grid-cols-[minmax(0,1fr)_2fr] items-start gap-5">
			<!-- hero YTD + period selector -->
			<div class="flex flex-col gap-5">
				<div
					v-if="lastSalarySlip?.year_to_date"
					class="air-rise rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
				>
					<div class="mb-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
						{{ __("Year to date") }}
					</div>
					<div
						class="truncate font-display text-[38px] font-semibold leading-none tracking-[-0.04em] text-air-ink tabular-nums"
					>
						{{ formatCurrency(shownYtd, lastSalarySlip.currency) }}
					</div>
					<div class="mt-2.5 text-[13px] text-air-muted">
						{{ __("As of your latest salary slip") }}
					</div>
				</div>

				<div
					class="air-rise rounded-air border border-air-line bg-air-surface p-[22px] shadow-air"
					style="--air-delay: 70ms"
				>
					<div class="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted">
						{{ __("Payroll period") }}
					</div>
					<Autocomplete
						class="w-full"
						:placeholder="__('Select Payroll Period')"
						:modelValue="modelValue"
						@update:modelValue="emit('update:modelValue', $event)"
						:options="periods"
					/>
				</div>
			</div>

			<!-- salary slips list -->
			<div
				class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
				style="--air-delay: 140ms"
			>
				<div class="mb-1.5 flex items-center justify-between">
					<h3 class="font-display text-base font-semibold text-air-ink">{{ __("Salary slips") }}</h3>
					<span v-if="slips.length" class="text-[13px] text-air-muted">
						{{ __("Net pay") }}
					</span>
				</div>

				<template v-if="slips.length">
					<router-link
						v-for="slip in slips"
						:key="slip.key"
						:to="{ name: 'SalarySlipDetailView', params: { id: slip.key } }"
						class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
					>
						<div
							class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink-2"
						>
							<FeatherIcon name="file-text" class="h-[17px] w-[17px]" />
						</div>
						<div class="min-w-0">
							<b class="block truncate text-sm font-semibold text-air-ink">{{ slip.title }}</b>
							<small v-if="slip.gross" class="block truncate text-[12.5px] text-air-muted">
								{{ __("{0}: {1}", [__("Gross Pay"), slip.gross]) }}
							</small>
						</div>
						<span
							v-if="slip.net"
							class="ml-auto shrink-0 whitespace-nowrap font-display text-[15px] font-semibold text-air-ink tabular-nums"
						>
							{{ slip.net }}
						</span>
						<FeatherIcon
							name="chevron-right"
							class="h-[18px] w-[18px] shrink-0 text-air-muted"
							:class="slip.net ? '' : 'ml-auto'"
						/>
					</router-link>
				</template>
				<div v-else class="py-10 text-center text-sm text-air-muted">
					{{ loading ? __("Loading...") : __("No salary slips found") }}
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { Autocomplete, FeatherIcon } from "frappe-ui"

import { useCountUp } from "@/composables/useCountUp"
import { formatCurrency } from "@/utils/formatters"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({
	// selected payroll period ({ label, value }) — v-model, owned by the parent view
	modelValue: { type: Object, default: () => ({}) },
	periods: { type: Array, default: () => [] },
	documents: { type: Array, default: () => [] },
	lastSalarySlip: { type: Object, default: null },
	loading: { type: Boolean, default: false },
})
const emit = defineEmits(["update:modelValue"])

const ytd = computed(() => Number(props.lastSalarySlip?.year_to_date) || 0)
const shownYtd = useCountUp(() => ytd.value)

const subline = computed(() => {
	if (props.lastSalarySlip?.year_to_date)
		return __("{0} earned year to date", [
			formatCurrency(props.lastSalarySlip.year_to_date, props.lastSalarySlip.currency),
		])
	return props.loading ? __("Loading...") : __("View and download your salary slips")
})

const slips = computed(() =>
	(props.documents || []).map((doc) => ({
		key: doc.name,
		// same title logic as SalarySlipItem
		title: dayjs(doc.start_date).isSame(doc.end_date, "month")
			? dayjs(doc.start_date).format("MMM YYYY")
			: `${dayjs(doc.start_date).format("MMM YYYY")} - ${dayjs(doc.end_date).format("MMM YYYY")}`,
		gross: doc.gross_pay ? formatCurrency(doc.gross_pay, doc.currency) : "",
		net: doc.net_pay ? formatCurrency(doc.net_pay, doc.currency) : "",
	}))
)
</script>
