<template>
	<ion-page>
		<ion-content class="ion-padding">
			<div
				v-if="resetPassword.showDialog"
				class="flex h-screen w-screen flex-col bg-white"
			>
				<header class="flex items-center justify-between px-6 py-4">
					<div class="text-lg font-semibold text-gray-900">
						{{ __("Reset Password") }}
					</div>
					<button
						type="button"
						class="text-sm text-gray-600 hover:text-gray-900 underline"
						@click="resetPassword.showDialog = false"
					>
						{{ __("Back to Login") }}
					</button>
				</header>
				<div class="flex flex-1 flex-col items-center justify-center px-8 text-center">
					<p class="text-gray-700">
						{{ __("Your password has expired. Please reset your password to continue") }}
					</p>
					<a
						class="mt-6 inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-white bg-gray-900 hover:bg-gray-800 active:bg-gray-700 focus-visible:ring focus-visible:ring-gray-400 h-9 text-base px-4 rounded"
						:href="resetPassword.link"
						target="_blank"
					>
						{{ __("Go to Reset Password page") }}
					</a>
				</div>
			</div>

			<div
				v-else
				class="flex h-screen w-screen flex-col justify-center bg-white lg:h-auto lg:min-h-screen lg:bg-air-bg"
			>
				<div class="flex flex-col mx-auto gap-3 items-center lg:hidden">
					<FrappeHRLogo class="h-8 w-8" />
					<div class="text-3xl font-semibold text-gray-900 text-center">
						{{ __("Login to Frappe HR") }}
					</div>
				</div>

				<!-- Desktop ("Air") header; mobile keeps FrappeHRLogo + copy above, untouched. -->
				<div class="hidden lg:flex lg:flex-col lg:mx-auto lg:items-center lg:text-center">
					<ClustoxLogo :height="34" class="text-air-ink" />
					<div class="mt-5 font-display text-[27px] font-semibold tracking-tight text-air-ink">
						{{ __("Sign in to Clustox People") }}
					</div>
					<p class="mt-2 text-[15px] text-air-muted">
						{{ __("Use your company email to continue.") }}
					</p>
				</div>

				<div
					class="mx-auto mt-10 w-full px-8 sm:w-96 lg:mt-7 lg:max-w-[400px] lg:rounded-air lg:border lg:border-air-line lg:bg-air-surface lg:p-8 lg:shadow-air"
				>
					<form v-if="!user_pass_login_disabled.data" class="flex flex-col space-y-4" @submit.prevent="submit">
						<Input
							:label="__('Email')"
							:placeholder="__('johndoe@mail.com')"
							v-model="email"
							type="text"
							autocomplete="username"
							input-class="lg:rounded-[13px] lg:border-air-line lg:py-3 lg:px-4 lg:focus:border-air-blue lg:focus:ring-4 lg:focus:ring-air-blue-wash"
						/>
						<Input
							:label="__('Password')"
							type="password"
							placeholder="••••••"
							v-model="password"
							autocomplete="current-password"
							input-class="lg:rounded-[13px] lg:border-air-line lg:py-3 lg:px-4 lg:focus:border-air-blue lg:focus:ring-4 lg:focus:ring-air-blue-wash"
						/>
						<ErrorMessage :message="errorMessage" />

						<!-- Desktop-only "keep signed in" + forgot password row (keepSignedIn is cosmetic; no backend support exists yet). Mobile's centered forgot-password link below is unchanged. -->
						<div class="hidden lg:flex lg:items-center lg:justify-between lg:text-[13.5px] lg:!mt-3.5">
							<label class="flex items-center gap-2 text-air-muted">
								<input
									type="checkbox"
									v-model="keepSignedIn"
									class="h-3.5 w-3.5 rounded accent-air-blue"
								/>
								{{ __("Keep me signed in") }}
							</label>
							<router-link
								:to="{ name: 'ForgotPassword', query: email ? { email } : {} }"
								class="font-medium text-air-blue no-underline hover:text-air-blue-2"
							>
								{{ __("Forgot password?") }}
							</router-link>
						</div>

						<Button
							:loading="session.login.loading"
							variant="solid"
							class="disabled:bg-gray-700 disabled:text-white !mt-6 lg:w-full lg:h-auto lg:justify-center lg:rounded-full lg:bg-air-blue lg:px-5 lg:py-3.5 lg:text-[15px] lg:font-semibold lg:hover:bg-air-blue-2 lg:disabled:bg-air-blue/40"
						>
							{{ __("Login") }}
						</Button>
						<div class="text-center mt-4 lg:hidden">
							<router-link
								:to="{ name: 'ForgotPassword', query: email ? { email } : {} }"
								class="text-sm text-gray-600 hover:text-gray-900 underline"
							>
								{{ __("Forgot Password?") }}
							</router-link>
						</div>
					</form>

					<template v-if="authProviders.data?.length">
						<div v-if="!user_pass_login_disabled.data" class="text-center text-sm text-gray-600 my-4">or</div>
						<div class="space-y-4">
							<a
								v-for="provider in authProviders.data"
								:key="provider.name"
								class="flex items-center justify-center gap-2 transition-colors focus:outline-none text-gray-800 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 focus-visible:ring focus-visible:ring-gray-400 h-7 text-base p-2 rounded"
								:href="provider.auth_url"
							>
								<img class="h-4 w-4" :src="provider.icon" :alt="provider.provider_name" />
								<span>Login with {{ provider.provider_name }}</span>
							</a>
						</div>
					</template>

					<div v-else-if="user_pass_login_disabled.data" class="text-center text-gray-600 py-8">{{ __("No login methods are available. Please contact your administrator.") }}</div>
				</div>
			</div>
			<Dialog v-model="otp.showDialog">
				<template #body-title>
					<h2 class="text-lg font-bold">{{ __("OTP Verification") }}</h2>
				</template>
				<template #body-content>
					<p class="mb-4" v-if="otp.verification.prompt">
						{{ otp.verification.prompt }}
					</p>

					<form class="flex flex-col space-y-4" @submit.prevent="submit">
						<Input
							:label="__('OTP Code')"
							type="text"
							placeholder="000000"
							v-model="otp.code"
							autocomplete="one-time-code"
						/>
						<ErrorMessage :message="errorMessage" />
						<Button
							:loading="session.otp.loading"
							variant="solid"
							class="disabled:bg-gray-700 disabled:text-white !mt-6"
						>
							{{ __("Verify") }}
						</Button>
					</form>
				</template>
			</Dialog>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { inject, reactive, ref } from "vue"
import { Input, Button, ErrorMessage, Dialog, createResource } from "frappe-ui"

import FrappeHRLogo from "@/components/icons/FrappeHRLogo.vue"
import ClustoxLogo from "@/components/icons/ClustoxLogo.vue"

const email = ref(null)
const password = ref(null)
const errorMessage = ref("")
// Desktop-only "keep me signed in" checkbox state (visual, matches the Air
// login concept); not wired to session/login logic since there is no
// remember-me support in the backend yet.
const keepSignedIn = ref(true)

const resetPassword = reactive({
	showDialog: false,
	link: "",
})
const otp = reactive({
	showDialog: false,
	tmp_id: "",
	code: "",
	verification: {},
})

const session = inject("$session")
const __ = inject("$translate")

async function submit(e) {
	try {
		let response
		if (otp.showDialog) {
			response = await session.otp(otp.tmp_id, otp.code)
		} else {
			response = await session.login(email.value, password.value)
		}

		if (response.message === "Password Reset") {
			resetPassword.showDialog = true
			resetPassword.link = response.redirect_to
		} else {
			resetPassword.showDialog = false
			resetPassword.link = ""
		}

		// OTP verification
		if (response.verification) {
			if (response.verification.setup) {
				otp.showDialog = true
				otp.tmp_id = response.tmp_id
				otp.verification = response.verification
			} else {
				// Don't bother handling impossible OTP setup (e.g. no phone number).
				window.open("/login?redirect-to=" + encodeURIComponent(window.location.pathname), "_blank")
			}
		}
	} catch (error) {
		errorMessage.value = error.messages.join("\n")
	}
}

const user_pass_login_disabled = createResource({
	url: "hrms.api.system_settings.get_user_pass_login_disabled",
	method: 'GET',
	initialData: 1,
	auto: true,
})

const authProviders = createResource({
	url: "hrms.api.oauth.oauth_providers",
	auto: true,
})
</script>
