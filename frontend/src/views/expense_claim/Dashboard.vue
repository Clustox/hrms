<template>
	<BaseLayout :pageTitle="__('Expense Claims')">
		<template #body>
			<!-- Mobile Expenses (unchanged): hidden once the desktop dashboard takes over at lg -->
			<div class="flex flex-col mt-7 mb-7 p-4 gap-7 lg:hidden">
				<ExpenseClaimSummary />

				<div class="w-full">
					<router-link
						:to="{ name: 'ExpenseClaimFormView' }"
						v-slot="{ navigate }"
					>
						<Button
							@click="navigate"
							variant="solid"
							class="w-full py-5 text-base"
						>
							{{ __("Claim an Expense") }}
						</Button>
					</router-link>
				</div>

				<div>
					<div class="text-lg text-gray-800 font-bold">{{ __("Recent Expenses") }}</div>
					<RequestList
						:component="markRaw(ExpenseClaimItem)"
						:items="myClaims.data"
						:addListButton="true"
						listButtonRoute="ExpenseClaimListView"
					/>
				</div>

				<div>
					<div class="flex flex-row justify-between items-center">
						<div class="text-lg text-gray-800 font-bold">
							{{ __("Employee Advance Balance") }}
						</div>
						<router-link
							:to="{ name: 'EmployeeAdvanceListView' }"
							class="text-sm text-gray-800 font-semibold cursor-pointer underline underline-offset-2"
						>
							{{ __("View List") }}
						</router-link>
					</div>

					<EmployeeAdvanceBalance :items="advanceBalance.data" />
				</div>
			</div>

			<!-- Air desktop dashboard (lg+ only; mounted only on wide viewports) -->
			<DesktopExpenseDashboard v-if="isDesktop" />
		</template>
	</BaseLayout>
</template>

<script setup>
import { markRaw, ref, onMounted, onBeforeUnmount } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import ExpenseClaimSummary from "@/components/ExpenseClaimSummary.vue"
import RequestList from "@/components/RequestList.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"
import EmployeeAdvanceBalance from "@/components/EmployeeAdvanceBalance.vue"
import DesktopExpenseDashboard from "@/components/DesktopExpenseDashboard.vue"

import { myClaims } from "@/data/claims"
import { advanceBalance } from "@/data/advances"

// Mirror Tailwind's `lg` breakpoint so the desktop dashboard is only mounted on wide viewports.
const desktopQuery = window.matchMedia("(min-width: 1024px)")
const isDesktop = ref(desktopQuery.matches)
const onQueryChange = (e) => (isDesktop.value = e.matches)
onMounted(() => desktopQuery.addEventListener("change", onQueryChange))
onBeforeUnmount(() => desktopQuery.removeEventListener("change", onQueryChange))
</script>
