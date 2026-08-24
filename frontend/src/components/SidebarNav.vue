<template>
	<!--
		Large-screen-only counterpart to BottomTabs — same nav items, same
		routes, same active-state logic, just laid out as a vertical sidebar
		instead of a bottom bar. Hidden below the `lg` breakpoint, where
		BottomTabs is what's shown.
	-->
	<div class="hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 lg:left-0 lg:z-10 lg:w-44 lg:border-r lg:bg-white lg:px-2 lg:py-4 lg:gap-4">
		<div class="flex flex-row items-center gap-2 px-2">
			<span class="grid h-5 w-5 place-items-center rounded bg-gray-900 text-white">
				<FeatherIcon name="zap" class="h-3 w-3" />
			</span>
			<span class="text-base font-bold text-gray-900">{{ __("Frappe HR") }}</span>
		</div>

		<div class="flex flex-col gap-0.5">
			<router-link
				v-for="item in navItems"
				:key="item.title"
				:to="item.route"
				:class="[
					'flex flex-row items-center gap-2 px-3 py-1.5 rounded text-sm transition',
					isActive(item.route)
						? 'bg-gray-100 text-gray-900 font-semibold'
						: 'text-gray-600 font-medium hover:bg-gray-50',
				]"
			>
				<component :is="item.icon" class="h-[18px] w-[18px]" />
				<span>{{ item.title }}</span>
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { useRoute } from "vue-router"
import { FeatherIcon } from "frappe-ui"

import { getNavItems } from "@/data/config/navItems"

const __ = inject("$translate")
const route = useRoute()

const navItems = getNavItems(__)

function isActive(itemRoute) {
	if (itemRoute === "/dashboard/attendance") {
		return route.path.startsWith("/attendance") || route.path.startsWith("/shift")
	}
	return route.path === itemRoute
}
</script>
