<template>
	<div
		class="air-rise rounded-air border border-air-line bg-air-surface p-6 shadow-air"
		style="--air-delay: 560ms"
	>
		<div class="mb-1.5 flex items-center justify-between">
			<h3 class="font-display text-base font-semibold text-air-ink">{{ __("Recent requests") }}</h3>
			<router-link
				:to="{ name: 'LeaveApplicationListView' }"
				class="text-[13.5px] font-medium text-air-blue hover:underline"
			>
				{{ __("View all") }}
			</router-link>
		</div>

		<template v-if="items.length">
			<div
				v-for="item in items"
				:key="item.key"
				class="flex items-center gap-3.5 border-t border-air-line-2 py-[15px] first:border-t-0"
			>
				<div
					class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink-2"
				>
					<FeatherIcon :name="item.icon" class="h-[17px] w-[17px]" />
				</div>
				<div class="min-w-0">
					<b class="block truncate text-sm font-semibold text-air-ink">{{ item.title }}</b>
					<small class="block truncate text-[12.5px] text-air-muted">{{ item.subtitle }}</small>
				</div>
				<div class="ml-auto flex shrink-0 items-center gap-3">
					<b v-if="item.amount" class="text-sm font-semibold tabular-nums text-air-ink">{{
						item.amount
					}}</b>
					<span
						v-if="item.statusText"
						class="whitespace-nowrap rounded-full px-[11px] py-1 text-xs font-semibold"
						:class="pillClass[item.state]"
					>
						{{ item.statusText }}
					</span>
				</div>
			</div>
		</template>
		<div v-else class="py-10 text-center text-sm text-air-muted">
			{{ loading ? __("Loading...") : __("You have no requests") }}
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon } from "frappe-ui"

defineProps({
	items: { type: Array, required: true },
	loading: { type: Boolean, default: false },
})

const __ = inject("$translate")

const pillClass = {
	pending: "bg-air-warn-w text-air-warn",
	approved: "bg-air-good-w text-air-good",
	rejected: "bg-air-crit-w text-air-crit",
}
</script>
