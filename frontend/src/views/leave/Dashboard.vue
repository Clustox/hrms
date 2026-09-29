<template>
	<BaseLayout :pageTitle="__('Leaves & Holidays')">
		<template #body>
			<!-- Mobile Leaves (unchanged): hidden once the desktop dashboard takes over at lg -->
			<div class="flex flex-col items-center mt-7 mb-7 py-4 lg:hidden">
				<LeaveBalance />

				<div class="flex flex-col gap-7 mt-5 px-4 w-full">
					<router-link
						:to="{ name: 'LeaveApplicationFormView' }"
						v-slot="{ navigate }"
					>
						<Button
							@click="navigate"
							variant="solid"
							class="py-5 text-base w-full"
						>
							{{ __("Request a Leave") }}
						</Button>
					</router-link>
					<div>
						<div class="text-lg text-gray-800 font-bold">{{ __('Recent Leaves') }} </div>
						<RequestList
							:component="markRaw(LeaveRequestItem)"
							:items="myLeaves.data"
							:addListButton="true"
							listButtonRoute="LeaveApplicationListView"
						/>
					</div>
					<Holidays />
				</div>
			</div>

			<!-- Air desktop dashboard (lg+ only; mounted only on wide viewports) -->
			<DesktopLeaveDashboard v-if="isDesktop" />
		</template>
	</BaseLayout>
</template>

<script setup>
import { markRaw, ref, onMounted, onBeforeUnmount } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import LeaveBalance from "@/components/LeaveBalance.vue"
import RequestList from "@/components/RequestList.vue"
import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import Holidays from "@/components/Holidays.vue"
import DesktopLeaveDashboard from "@/components/DesktopLeaveDashboard.vue"

import { myLeaves } from "@/data/leaves"

// Mirror Tailwind's `lg` breakpoint so the desktop dashboard is only mounted on wide viewports.
const desktopQuery = window.matchMedia("(min-width: 1024px)")
const isDesktop = ref(desktopQuery.matches)
const onQueryChange = (e) => (isDesktop.value = e.matches)
onMounted(() => desktopQuery.addEventListener("change", onQueryChange))
onBeforeUnmount(() => desktopQuery.removeEventListener("change", onQueryChange))
</script>
