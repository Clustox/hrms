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
							<h2 class="text-xl font-semibold text-gray-900">{{ __("Settings") }} </h2>
						</div>
					</header>

					<div class="flex flex-col gap-5 my-4 w-full p-4">
						<div class="flex flex-col bg-white rounded">
							<div
								class="flex flex-row cursor-pointer flex-start p-4 items-center justify-between border-b"
							>
								<router-link
									:to="{ name: 'ChangePassword' }"
									class="flex flex-row items-center justify-between w-full"
								>
									<div class="flex flex-row items-center gap-3 grow">
										<FeatherIcon
											name="lock"
											class="h-5 w-5 text-gray-500"
										/>
										<div class="text-base font-normal text-gray-800">
											{{ __("Change Password") }}
										</div>
									</div>
									<FeatherIcon
										name="chevron-right"
										class="h-5 w-5 text-gray-500"
									/>
								</router-link>
							</div>
						</div>

						<div class="flex flex-col bg-white rounded">
							<Switch
								size="md"
								:label="__('Enable Push Notifications')"
								:class="description ? 'p-2' : ''"
								:model-value="pushNotificationState"
								:disabled="disablePushSetting"
								:description="description"
								@update:model-value="togglePushNotifications"
							/>
						</div>

						<div
							v-if="isLoading"
							class="flex -mt-2 items-center justify-center gap-2"
						>
							<LoadingIndicator class="w-3 h-3 text-gray-800" />
							<span class="text-gray-900 text-sm">
								{{ pushNotificationState ? __("Disabling Push Notifications...") : __("Enabling Push Notifications...") }}
							</span>
						</div>
					</div>
				</div>
			</div>

			<!-- Air desktop (lg+ only): shell offset + Air settings cards -->
			<div class="hidden min-h-screen lg:block lg:bg-air-bg lg:pl-[250px] lg:pt-[68px]">
				<div class="max-w-[900px] px-10 pb-[70px] pt-[34px]">
					<div class="air-rise">
						<h1
							class="font-display text-[34px] font-bold tracking-[-0.03em] text-air-ink"
						>
							{{ __("Settings") }}
						</h1>
						<p class="mt-2.5 text-base text-air-muted">
							{{ __("Manage your account and notifications") }}
						</p>
					</div>

					<div class="mt-8 flex flex-col gap-5">
						<div
							class="air-rise rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
							:style="{ '--air-delay': '70ms' }"
						>
							<div
								class="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted"
							>
								{{ __("Account") }}
							</div>
							<router-link
								:to="{ name: 'ChangePassword' }"
								class="-mx-2 flex items-center justify-between gap-3 rounded-air-sm px-2 py-2.5 transition-colors duration-200 ease-air hover:bg-air-surface-2"
							>
								<div class="flex grow items-center gap-3">
									<span
										class="flex h-9 w-9 items-center justify-center rounded-full bg-air-surface-2 text-air-ink-2"
									>
										<FeatherIcon name="lock" class="h-[17px] w-[17px]" />
									</span>
									<div class="text-[15px] font-medium text-air-ink">
										{{ __("Change Password") }}
									</div>
								</div>
								<FeatherIcon
									name="chevron-right"
									class="h-4 w-4 text-air-muted"
								/>
							</router-link>
						</div>

						<div
							class="air-rise rounded-air border border-air-line bg-air-surface p-[22px] shadow-air transition-all duration-300 ease-air hover:-translate-y-[3px] hover:shadow-air-2"
							:style="{ '--air-delay': '140ms' }"
						>
							<div
								class="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-air-muted"
							>
								{{ __("Notifications") }}
							</div>
							<Switch
								size="md"
								:label="__('Enable Push Notifications')"
								:class="description ? 'p-2' : ''"
								:model-value="pushNotificationState"
								:disabled="disablePushSetting"
								:description="description"
								@update:model-value="togglePushNotifications"
							/>
							<div
								v-if="isLoading"
								class="mt-3 flex items-center gap-2 text-sm text-air-ink-2"
							>
								<LoadingIndicator class="h-3 w-3 text-air-ink-2" />
								<span>
									{{ pushNotificationState ? __("Disabling Push Notifications...") : __("Enabling Push Notifications...") }}
								</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { useRouter } from "vue-router"
import { FeatherIcon, Switch, toast, LoadingIndicator, Button } from "frappe-ui"

import { computed, inject, ref } from "vue"

import DesktopShell from "@/components/DesktopShell.vue"
import { arePushNotificationsEnabled } from "@/data/notifications"

const __ = inject("$translate")
const router = useRouter()

const pushNotificationState = ref(
	window.frappePushNotification?.isNotificationEnabled()
)
const isLoading = ref(false)

const disablePushSetting = computed(() => {
	return (
		!(
			window.frappe?.boot.push_relay_server_url &&
			arePushNotificationsEnabled.data
		) || isLoading.value
	)
})

const description = computed(() => {
	return !(
		window.frappe?.boot.push_relay_server_url &&
		arePushNotificationsEnabled.data
	)
		? __("Push notifications have been disabled on your site")
		: ""
})

const togglePushNotifications = (newValue) => {
	if (newValue) {
		enablePushNotifications()
	} else {
		isLoading.value = true
		window.frappePushNotification
			.disableNotification()
			.then(() => {
				pushNotificationState.value = false
				toast({
					title: __("Success"),
					text: __("Push notifications disabled"),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			})
			.catch((error) => {
				toast({
					title: __("Error"),
					text: __(error.message),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			})
			.finally(() => {
				isLoading.value = false
			})
	}
}
const enablePushNotifications = () => {
	isLoading.value = true

	window.frappePushNotification
		.enableNotification()
		.then((data) => {
			if (data.permission_granted) {
				pushNotificationState.value = true
			} else {
				toast({
					title: __("Error"),
					text: __("Push Notification permission denied"),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
				pushNotificationState.value = false
			}
		})
		.catch((error) => {
			toast({
				title: __("Error"),
				text: __(error.message),
				icon: "alert-circle",
				position: "bottom-center",
				iconClasses: "text-red-500",
			})
			pushNotificationState.value = false
		})
		.finally(() => {
			isLoading.value = false
		})
}

</script>