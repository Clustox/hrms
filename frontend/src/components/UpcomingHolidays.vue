<template>
	<div
		class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
		style="--air-delay: 630ms"
	>
		<div class="mb-1.5 flex items-center justify-between">
			<h3 class="font-display text-base font-semibold text-air-ink">{{ __("Upcoming holidays") }}</h3>
		</div>

		<template v-if="upcoming.length">
			<div
				v-for="holiday in upcoming"
				:key="holiday.holiday_date"
				class="flex items-center gap-[13px] border-t border-air-line-2 py-[13px] first:border-t-0"
			>
				<div class="w-[46px] shrink-0 text-center">
					<b class="block font-display text-lg font-semibold leading-none text-air-ink">{{
						holiday.day
					}}</b>
					<small class="text-[11px] uppercase tracking-[0.04em] text-air-muted">{{
						holiday.month
					}}</small>
				</div>
				<div class="min-w-0">
					<b class="block truncate text-sm font-semibold text-air-ink">{{ __(holiday.description) }}</b>
					<small class="text-[12.5px] text-air-muted">{{ holiday.weekday }}</small>
				</div>
			</div>
		</template>
		<div v-else class="py-10 text-center text-sm text-air-muted">
			{{ holidays.loading ? __("Loading...") : __("You have no upcoming holidays") }}
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted } from "vue"
import { createResource } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

// Same endpoint as components/Holidays.vue (hrms.api.get_holidays_for_employee).
// Kept lazy (auto: false) so it only fetches once the desktop dashboard mounts.
const holidays = createResource({
	url: "hrms.api.get_holidays_for_employee",
	params: { employee: employee.data?.name },
	auto: false,
})

onMounted(() => {
	if (employee.data?.name && !holidays.data) holidays.fetch()
})

const upcoming = computed(() =>
	(holidays.data || [])
		.filter((h) => dayjs(h.holiday_date).isAfter(dayjs()))
		.slice(0, 4)
		.map((h) => {
			const d = dayjs(h.holiday_date)
			return { ...h, day: d.format("DD"), month: d.format("MMM"), weekday: d.format("dddd") }
		})
)
</script>
