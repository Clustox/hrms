<template>
	<!--
		Desktop ("Air") shell: sidebar + topbar for wide screens only.
		Entirely additive under `lg:` — renders nothing (`hidden`) below the
		1024px breakpoint, so the mobile tab bar + per-page ion-header remain
		the only chrome on phones.
	-->
	<aside
		class="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:flex lg:w-[250px] lg:flex-col lg:gap-1 lg:border-r lg:border-air-line-2 lg:bg-air-bg lg:px-4 lg:py-6"
	>
		<div class="flex items-center gap-2.5 px-2.5 pb-6 pt-1">
			<ClustoxLogo :height="23" class="text-air-ink" />
			<span class="font-display text-base font-medium tracking-tight text-air-muted">
				{{ __("People") }}
			</span>
		</div>

		<nav class="flex flex-col gap-0.5">
			<router-link
				v-for="item in navItems"
				:key="item.route"
				:to="item.route"
				class="flex items-center gap-3 rounded-[11px] px-3 py-2.5 text-[14.5px] transition-colors duration-200 ease-air"
				:class="
					isActive(item)
						? 'bg-air-surface-2 font-semibold text-air-ink'
						: 'font-medium text-air-ink-2 hover:bg-air-surface-2'
				"
			>
				<component
					:is="item.icon"
					class="h-[19px] w-[19px] shrink-0"
					:class="isActive(item) ? 'text-air-blue' : 'text-air-muted'"
				/>
				{{ item.title }}
			</router-link>
		</nav>

		<router-link
			:to="{ name: 'Profile' }"
			class="mt-auto flex items-center gap-2.5 rounded-2xl p-2 transition-colors duration-200 ease-air hover:bg-air-surface-2"
		>
			<Avatar :image="user.data?.user_image" :label="user.data?.first_name" size="xl" />
			<div class="min-w-0 leading-tight">
				<b class="block truncate text-[13.5px] font-semibold text-air-ink">
					{{ user.data?.full_name || user.data?.first_name }}
				</b>
				<small class="block truncate text-xs text-air-muted">
					{{ employee.data?.designation || employee.data?.department || "" }}
				</small>
			</div>
		</router-link>
	</aside>

	<header
		class="hidden lg:fixed lg:left-[250px] lg:right-0 lg:top-0 lg:z-20 lg:flex lg:h-[68px] lg:items-center lg:gap-4 lg:border-b lg:border-air-line-2 lg:bg-air-bg/80 lg:px-10 lg:backdrop-blur-xl"
	>
		<div class="min-w-0">
			<h2 class="truncate font-display text-[21px] font-semibold text-air-ink">
				{{ pageTitle }}
			</h2>
			<div class="mt-0.5 text-[13px] text-air-muted">{{ today }}</div>
		</div>

		<span class="flex-1"></span>

		<div
			class="flex w-60 items-center gap-2 rounded-full border border-transparent bg-air-surface-2 px-4 py-2.5 text-air-muted transition-colors duration-200 focus-within:border-air-line focus-within:bg-air-surface"
		>
			<FeatherIcon name="search" class="h-4 w-4 shrink-0" />
			<input
				type="text"
				:placeholder="__('Search')"
				class="w-full border-0 bg-transparent p-0 text-[13.5px] text-air-ink placeholder:text-air-muted focus:outline-none focus:ring-0"
			/>
		</div>

		<button
			type="button"
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-air-line bg-air-surface text-air-ink-2 transition-all duration-200 ease-air hover:-translate-y-px hover:text-air-blue hover:shadow-air"
			:aria-label="isDark ? __('Switch to light mode') : __('Switch to dark mode')"
			:title="isDark ? __('Switch to light mode') : __('Switch to dark mode')"
			@click="toggleTheme"
		>
			<FeatherIcon :name="isDark ? 'sun' : 'moon'" class="h-[17px] w-[17px]" />
		</button>

		<router-link
			:to="{ name: 'Notifications' }"
			class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-air-line bg-air-surface text-air-ink-2 transition-all duration-200 ease-air hover:-translate-y-px hover:text-air-blue hover:shadow-air relative"
			:aria-label="__('Notifications')"
		>
			<FeatherIcon name="bell" class="h-[17px] w-[17px]" />
			<span
				v-if="unreadNotificationsCount.data"
				class="absolute right-1.5 top-1.5 inline-block h-2 w-2 rounded-full border border-air-surface bg-air-crit"
			></span>
		</router-link>

		<router-link :to="{ name: 'Profile' }" :aria-label="__('Profile')">
			<Avatar :image="user.data?.user_image" :label="user.data?.first_name" size="lg" />
		</router-link>
	</header>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRoute } from "vue-router"
import { Avatar, FeatherIcon } from "frappe-ui"

import ClustoxLogo from "@/components/icons/ClustoxLogo.vue"
import { getNavItems } from "@/config/navItems"
import { unreadNotificationsCount } from "@/data/notifications"
import { useTheme } from "@/composables/useTheme"

const { isDark, toggleTheme } = useTheme()

const __ = inject("$translate")
const user = inject("$user")
const employee = inject("$employee")
const dayjs = inject("$dayjs")

const route = useRoute()
const navItems = getNavItems(__)

function isActive(item) {
	return route.path === item.route || route.path.startsWith(item.route + "/")
}

const activeItem = computed(() => navItems.find(isActive))
const pageTitle = computed(() => activeItem.value?.title || __("Frappe HR"))
const today = computed(() => (dayjs ? dayjs().format("dddd, D MMMM") : ""))
</script>
