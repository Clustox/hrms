<template>
	<ion-page>
		<DesktopShell />
		<ion-content
			class="ion-padding lg:![--padding-start:0px] lg:![--padding-end:0px] lg:![--padding-top:0px] lg:![--padding-bottom:0px] lg:[--background:var(--air-bg)]"
		>
			<div class="flex flex-col h-screen w-screen lg:hidden">
				<div class="w-full sm:w-96">
					<header
						class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b sticky top-0 z-10"
					>
						<div class="flex flex-row items-center">
							<Button
								variant="ghost"
								class="!pl-0 hover:bg-white"
								@click="router.back()"
							>
								<FeatherIcon name="chevron-left" class="h-5 w-5" />
							</Button>
							<h2 class="text-xl font-semibold text-gray-900">{{ __("Notifications") }} </h2>
						</div>
					</header>

					<div class="flex flex-col gap-4 mt-5 p-4">
						<div class="flex flex-row justify-between items-center">
							<div
								class="text-lg text-gray-800 font-semibold"
								v-if="unreadNotificationsCount.data"
							>
								{{ __("{0} Unread", [unreadNotificationsCount.data]) }}
							</div>
							<div class="flex ml-auto gap-1">
								<Button
									v-if="allowPushNotifications"
									variant="outline"
									@click="router.push({ name: 'Settings' })"
								>
									<template #prefix>
										<FeatherIcon name="settings" class="w-4" />
									</template>
									{{ __("Settings") }}
								</Button>
								<Button
									v-if="unreadNotificationsCount.data"
									variant="outline"
									@click="markAllAsRead.submit"
									:loading="markAllAsRead.loading"
								>
									<template #prefix>
										<FeatherIcon name="check-circle" class="w-4" />
									</template>
									{{ __("Mark all as read") }}
								</Button>
							</div>
						</div>

						<div
							class="flex flex-col bg-white rounded"
							v-if="notifications.data?.length"
						>
							<router-link
								:class="[
									'flex flex-row items-start p-4 justify-between border-b before:mt-3',
									`before:content-[''] before:mr-2 before:shrink-0 before:w-1.5 before:h-1.5 before:rounded-full`,
									item.read ? 'bg-white-500' : 'before:bg-blue-500',
								]"
								v-for="item in notifications.data"
								:key="item.name"
								:to="getItemRoute(item)"
								@click="markAsRead(item.name)"
							>
								<EmployeeAvatar :userID="item.from_user" size="lg" />
								<div class="flex flex-col gap-0.5 grow ml-3">
									<div
										class="text-sm leading-5 font-normal text-gray-800"
										v-html="item.message"
									></div>
									<div class="text-xs font-normal text-gray-500">
										{{ dayjs(item.creation).fromNow() }}
									</div>
								</div>
							</router-link>
							
						</div>
						<div v-if="notifications.data?.length && notifications.hasNextPage" class="flex">
							<Button
								variant="outline"
								class="ml-auto"
								@click="loadMore"
							>
								{{ __('Load more') }}
							</Button>
						</div>
						<EmptyState v-else-if="!notifications.data" :message="__('You have no notifications')" />
					</div>
				</div>
			</div>

			<!-- Air desktop (lg+ only): shell offset + Air notification list -->
			<div class="hidden min-h-screen lg:block lg:bg-air-bg lg:pl-[250px] lg:pt-[68px]">
				<div class="max-w-[900px] px-10 pb-[70px] pt-[34px]">
					<div class="air-rise flex flex-wrap items-end justify-between gap-4">
						<div>
							<h1
								class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink"
							>
								{{ __("Notifications") }}
							</h1>
							<p class="mt-2.5 text-base text-air-muted">
								{{
									unreadNotificationsCount.data
										? __("{0} Unread", [unreadNotificationsCount.data])
										: __("You're all caught up")
								}}
							</p>
						</div>
						<div class="flex items-center gap-2">
							<button
								v-if="allowPushNotifications"
								type="button"
								class="flex items-center gap-2 rounded-full border border-air-line bg-air-surface px-4 py-2 text-[14px] font-semibold text-air-ink transition ease-air hover:border-air-blue hover:text-air-blue"
								@click="router.push({ name: 'Settings' })"
							>
								<FeatherIcon name="settings" class="h-4 w-4" />
								{{ __("Settings") }}
							</button>
							<button
								v-if="unreadNotificationsCount.data"
								type="button"
								class="flex items-center gap-2 rounded-full border border-air-line bg-air-surface px-4 py-2 text-[14px] font-semibold text-air-ink transition ease-air hover:border-air-blue hover:text-air-blue disabled:opacity-60"
								:disabled="markAllAsRead.loading"
								@click="markAllAsRead.submit()"
							>
								<FeatherIcon name="check-circle" class="h-4 w-4" />
								{{ __("Mark all as read") }}
							</button>
						</div>
					</div>

					<div
						v-if="notifications.data?.length"
						class="air-rise mt-8 overflow-hidden rounded-air border border-air-line bg-air-surface shadow-air"
						:style="{ '--air-delay': '70ms' }"
					>
						<router-link
							v-for="item in notifications.data"
							:key="item.name"
							:to="getItemRoute(item)"
							class="flex items-start gap-4 border-b border-air-line-2 px-[22px] py-4 transition-colors duration-200 ease-air last:border-b-0 hover:bg-air-surface-2"
							:class="item.read ? '' : 'bg-air-blue-wash'"
							@click="markAsRead(item.name)"
						>
							<span
								class="mt-4 h-2 w-2 shrink-0 rounded-full"
								:class="item.read ? 'bg-transparent' : 'bg-air-blue'"
							></span>
							<EmployeeAvatar :userID="item.from_user" size="lg" />
							<div class="flex min-w-0 grow flex-col gap-1">
								<div
									class="text-[14.5px] leading-5 text-air-ink"
									v-html="item.message"
								></div>
								<div class="text-xs text-air-muted">
									{{ dayjs(item.creation).fromNow() }}
								</div>
							</div>
							<FeatherIcon
								name="chevron-right"
								class="mt-2 h-4 w-4 shrink-0 text-air-muted"
							/>
						</router-link>
					</div>

					<div
						v-if="notifications.data?.length && notifications.hasNextPage"
						class="mt-5 flex justify-center"
					>
						<button
							type="button"
							class="rounded-full border border-air-line bg-air-surface px-5 py-2.5 text-[14px] font-semibold text-air-ink transition ease-air hover:border-air-blue hover:text-air-blue"
							@click="loadMore"
						>
							{{ __("Load more") }}
						</button>
					</div>
					<div
						v-else-if="!notifications.data?.length && !notifications.list?.loading"
						class="air-rise mt-8 flex flex-col items-center gap-3 rounded-air border border-air-line bg-air-surface px-6 py-16 text-center shadow-air"
					>
						<span
							class="flex h-12 w-12 items-center justify-center rounded-full bg-air-surface-2 text-air-muted"
						>
							<FeatherIcon name="bell" class="h-5 w-5" />
						</span>
						<p class="text-[15px] text-air-muted">
							{{ __("You have no notifications") }}
						</p>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonContent, IonPage } from "@ionic/vue"
import { useRouter } from "vue-router"
import { createResource, FeatherIcon } from "frappe-ui"

import { computed, inject, onMounted, ref } from "vue"
import EmployeeAvatar from "@/components/EmployeeAvatar.vue"
import EmptyState from "@/components/EmptyState.vue"
import DesktopShell from "@/components/DesktopShell.vue"

import {
	unreadNotificationsCount,
	notifications,
	arePushNotificationsEnabled,
} from "@/data/notifications"
import { userResource } from "@/data/user"

const dayjs = inject("$dayjs")
const router = useRouter()
const __ = inject("$translate")
const currentStart = ref(0)
const pageLength = 10


const allowPushNotifications = computed(
	() =>
		window.frappe?.boot.push_relay_server_url &&
		arePushNotificationsEnabled.data
)

const markAllAsRead = createResource({
	url: "hrms.api.mark_all_notifications_as_read",
	onSuccess() {
		notifications.reload()
	},
})

function markAsRead(name) {
	notifications.setValue.submit(
		{ name, read: 1 },
		{
			onSuccess: () => {
				unreadNotificationsCount.reload()
			},
		}
	)
}

function getItemRoute(item) {
	return {
		name: `${item.reference_document_type.replace(/\s+/g, "")}DetailView`,
		params: { id: item.reference_document_name },
	}
}

onMounted(() => {
	// Set the real to_user filter now that the user is hydrated (this is an
	// authenticated route). notifications.js seeds it defensively to avoid a
	// null read at module-load time.
	notifications.filters = { to_user: userResource.data?.name }
	notifications.start = 0,
	notifications.pageLength = 10,
	notifications.fetch()
})

function loadMore() {
	currentStart.value += pageLength
	notifications.start = currentStart.value
	notifications.pageLength = pageLength
	notifications.list.fetch()
}
</script>
