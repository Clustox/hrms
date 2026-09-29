<template>
	<!-- Air desktop dashboard: quick-actions grid (same routes as the mobile Quick Links list) -->
	<div>
		<div class="mb-3.5 ml-0.5 mt-1.5 text-[13px] font-semibold tracking-[0.01em] text-air-muted">
			{{ title }}
		</div>
		<div class="grid grid-cols-3 gap-5">
			<router-link
				v-for="(link, i) in items"
				:key="link.route"
				:to="{ name: link.route }"
				class="air-rise group flex items-center gap-3.5 rounded-air-sm border border-air-line bg-air-surface p-[17px] text-left transition-all duration-[280ms] ease-air hover:-translate-y-[3px] hover:shadow-air-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-air-blue"
				:style="{ '--air-delay': `${280 + i * 50}ms` }"
			>
				<span
					class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[11px] bg-air-surface-2 text-air-ink"
				>
					<component :is="link.icon" class="h-5 w-5" />
				</span>
				<span class="min-w-0">
					<b class="block text-[14.5px] font-semibold text-air-ink">{{ link.title }}</b>
					<small v-if="link.description" class="text-[12.5px] text-air-muted">{{
						link.description
					}}</small>
				</span>
				<FeatherIcon
					name="chevron-right"
					class="ml-auto h-4 w-4 shrink-0 text-air-muted transition-all duration-[250ms] ease-air group-hover:translate-x-[3px] group-hover:text-air-blue"
				/>
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { FeatherIcon } from "frappe-ui"

defineProps({
	title: { type: String, default: "" },
	items: { type: Array, required: true },
})
</script>
