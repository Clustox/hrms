<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<DesktopShell />
			<div
				class="flex flex-col h-full w-full lg:h-auto lg:min-h-screen lg:bg-air-bg lg:pl-[250px] lg:pt-[68px] lg:pb-12"
			>
				<div
					class="w-full h-full bg-white sm:w-96 flex flex-col lg:h-auto lg:w-full lg:max-w-[900px] lg:mx-auto lg:mt-8 lg:rounded-air lg:border lg:border-air-line lg:shadow-air lg:overflow-hidden"
				>
					<header
						class="flex flex-row bg-white shadow-sm py-4 px-3 items-center sticky top-0 z-[1000] lg:static lg:bg-transparent lg:shadow-none lg:border-b lg:border-air-line-2 lg:px-7 lg:py-5"
					>
						<Button variant="ghost" class="!pl-0 hover:bg-white" @click="router.back()">
							<FeatherIcon name="chevron-left" class="h-5 w-5" />
						</Button>
						<h2
							class="text-2xl font-semibold text-gray-900 lg:font-display lg:tracking-tight"
						>
							{{ __("New Expense Requests") }}
						</h2>
					</header>

					<div class="flex flex-col gap-4 p-4 lg:px-7 lg:py-6" v-if="fieldsByName">
						<p class="text-sm text-gray-600">
							{{
								__(
									"Add one row per expense. Each row is raised as its own request and follows the approval steps for its type."
								)
							}}
						</p>

						<div
							v-for="(row, index) in rows"
							:key="row.key"
							class="flex flex-col gap-4 rounded-lg border p-4"
							:class="row.error ? 'border-red-300 bg-red-50/40' : 'border-gray-200'"
						>
							<div class="flex flex-row items-center justify-between">
								<span class="text-sm font-semibold text-gray-800">
									{{ __("Request {0}", [index + 1]) }}
								</span>
								<span v-if="row.created" class="text-xs text-gray-600">
									{{ __("Created as {0}", [row.created]) }}
								</span>
								<Button
									v-else-if="rows.length > 1"
									variant="ghost"
									:disabled="busy"
									@click="removeRow(row)"
								>
									<FeatherIcon name="trash-2" class="h-4 w-4 text-gray-700" />
								</Button>
							</div>

							<div class="grid grid-cols-1 gap-4 lg:grid-cols-4">
								<FormField
									fieldtype="Select"
									fieldname="expense_type"
									:label="fieldsByName.expense_type.label"
									:options="fieldsByName.expense_type.options"
									:modelValue="row.expense_type"
									:readOnly="Boolean(row.created)"
									reqd
									@update:modelValue="(v) => setType(row, v)"
								/>
								<FormField
									v-if="isMedical(row)"
									fieldtype="Select"
									fieldname="beneficiary"
									:label="fieldsByName.beneficiary.label"
									:options="fieldsByName.beneficiary.options"
									v-model="row.beneficiary"
									:readOnly="Boolean(row.created)"
								/>
								<FormField
									fieldtype="Date"
									fieldname="expense_date"
									:label="fieldsByName.expense_date.label"
									v-model="row.expense_date"
									:readOnly="Boolean(row.created)"
									:maxDate="today"
									reqd
								/>
								<FormField
									fieldtype="Currency"
									fieldname="amount"
									:label="fieldsByName.amount.label"
									v-model="row.amount"
									:readOnly="Boolean(row.created)"
									reqd
								/>
							</div>

							<FormField
								fieldtype="Small Text"
								fieldname="reason"
								:label="fieldsByName.reason.label"
								v-model="row.reason"
								:readOnly="Boolean(row.created)"
								reqd
							/>

							<div>
								<div
									v-if="!row.files.length"
									class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5"
								>
									<FeatherIcon
										name="paperclip"
										class="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
									/>
									<span class="text-[13px] leading-5 text-amber-800">
										{{ attachmentHint(row) }}
									</span>
								</div>
								<FileUploaderView
									v-model="row.files"
									required
									@handleFileSelect="(e) => addFiles(row, e)"
									@handleFileDelete="(file) => removeFile(row, file)"
								/>
							</div>

							<p v-if="row.error" class="text-sm text-red-600 whitespace-pre-line">
								{{ row.error }}
							</p>
						</div>

						<Button
							variant="outline"
							class="w-full"
							:disabled="busy || rows.length >= MAX_ROWS"
							@click="addRow()"
						>
							<template #prefix><FeatherIcon name="plus" class="h-4 w-4" /></template>
							{{ __("Add row") }}
						</Button>
						<p v-if="rows.length >= MAX_ROWS" class="text-xs text-gray-600">
							{{ __("You can raise up to {0} requests at once.", [MAX_ROWS]) }}
						</p>
					</div>

					<div
						v-if="fieldsByName"
						class="px-4 pt-4 pb-4 standalone:pb-safe-bottom sm:w-96 bg-white sticky bottom-0 w-full drop-shadow-xl z-40 border-t rounded-t-lg flex flex-col gap-2 lg:static lg:w-full lg:rounded-none lg:border-air-line-2 lg:bg-transparent lg:drop-shadow-none lg:px-7 lg:py-5 lg:flex-row-reverse"
					>
						<Button
							class="w-full rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:font-semibold lg:w-auto lg:px-6"
							variant="solid"
							:loading="busy"
							@click="submitAll(true)"
						>
							{{ rows.length > 1 ? __("Submit all for approval") : __("Submit for approval") }}
						</Button>
						<Button
							class="w-full rounded py-5 text-base lg:rounded-air-sm lg:py-3.5 lg:w-auto lg:px-6"
							variant="outline"
							:disabled="busy"
							@click="submitAll(false)"
						>
							{{ __("Save as draft") }}
						</Button>
					</div>
				</div>
			</div>

			<Dialog v-model="showError">
				<template #body-title>
					<h2 class="text-xl font-bold text-gray-900">{{ __("Please check the form") }}</h2>
				</template>
				<template #body-content>
					<p class="text-gray-700 whitespace-pre-line">{{ errorMessage }}</p>
				</template>
				<template #actions>
					<Button variant="solid" class="w-full py-5" @click="showError = false">
						{{ __("OK") }}
					</Button>
				</template>
			</Dialog>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { Button, Dialog, FeatherIcon, call, createResource, toast } from "frappe-ui"
import { computed, inject, ref } from "vue"
import { useRouter } from "vue-router"

import DesktopShell from "@/components/DesktopShell.vue"
import FileUploaderView from "@/components/FileUploaderView.vue"
import FormField from "@/components/FormField.vue"
import { FileAttachment } from "@/composables"

const __ = inject("$translate")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const router = useRouter()

const DOCTYPE = "Expense Request"
// Beneficiary (Self / Spouse / Children) only applies to medical claims.
const MEDICAL_TYPES = ["OPD", "IPD"]
// One request per row, so keep a sensible ceiling on a single submission.
const MAX_ROWS = 20

const today = dayjs().format("YYYY-MM-DD")

let rowSeq = 0
function newRow() {
	return {
		key: ++rowSeq,
		expense_type: "",
		expense_date: today,
		beneficiary: "",
		amount: "",
		reason: "",
		files: [],
		// set once the request exists on the server, so a retry never creates it twice
		created: null,
		uploaded: [],
		error: "",
	}
}

const rows = ref([newRow()])
const busy = ref(false)
const showError = ref(false)
const errorMessage = ref("")

// Labels and options come from the doctype itself, as on the single-request form.
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: DOCTYPE },
	auto: true,
})
const fieldsByName = computed(() => {
	if (!formFields.data) return null
	return Object.fromEntries(formFields.data.map((f) => [f.fieldname, f]))
})

const isMedical = (row) => MEDICAL_TYPES.includes(row.expense_type)

function setType(row, type) {
	row.expense_type = type || ""
	// default the dropdown so it is never blank; cleared server-side for other types
	row.beneficiary = isMedical(row) ? row.beneficiary || "Self" : ""
}

function attachmentHint(row) {
	return isMedical(row)
		? __("Attach the receipt and the prescription before submitting.")
		: __("Attach the receipt / invoice before submitting.")
}

function addRow() {
	if (rows.value.length < MAX_ROWS) rows.value.push(newRow())
}

function removeRow(row) {
	rows.value = rows.value.filter((r) => r.key !== row.key)
	if (!rows.value.length) rows.value.push(newRow())
}

function addFiles(row, event) {
	row.files.push(...event.target.files)
	// let the same file be picked again for another row
	event.target.value = ""
}

function removeFile(row, file) {
	row.files = row.files.filter((f) => f !== file)
}

// What is wrong with this row before anything is created (same rules as the single form).
function rowProblem(row) {
	if (!row.expense_type) return __("Select the expense type.")
	if (!row.expense_date) return __("Select the expense date.")
	if (!(Number(row.amount) > 0)) return __("Amount must be greater than zero.")
	if (!String(row.reason || "").trim()) return __("Enter the reason.")
	if (!row.files.length) return attachmentHint(row)
	return ""
}

function messageOf(error) {
	if (!error) return __("Something went wrong. Please try again.")
	let messages = error.messages
	if (typeof messages === "string") messages = [messages]
	const strip = (m) => String(m).replace(/<[^>]*>/g, "").trim()
	if (Array.isArray(messages) && messages.length) {
		const clean = messages.map(strip).filter(Boolean)
		if (clean.length) return [...new Set(clean)].join("\n")
	}
	return strip(error.message || error) || __("Something went wrong. Please try again.")
}

async function processRow(row, sendForApproval) {
	if (!row.created) {
		const doc = await call("frappe.client.insert", {
			doc: {
				doctype: DOCTYPE,
				employee: employee.data.name,
				expense_type: row.expense_type,
				expense_date: row.expense_date,
				beneficiary: isMedical(row) ? row.beneficiary || "Self" : null,
				amount: Number(row.amount),
				reason: String(row.reason).trim(),
			},
		})
		row.created = doc.name
	}

	for (const file of row.files) {
		if (row.uploaded.includes(file)) continue
		await new FileAttachment(file).upload(DOCTYPE, row.created, "")
		row.uploaded.push(file)
	}

	if (sendForApproval) {
		// the request's own workflow decides the route (manager first, or straight to HR)
		await call("frappe.model.workflow.apply_workflow", {
			doc: { doctype: DOCTYPE, name: row.created },
			action: "Submit for Approval",
		})
	}
}

async function submitAll(sendForApproval) {
	if (busy.value) return

	let problems = 0
	for (const row of rows.value) {
		row.error = rowProblem(row)
		if (row.error) problems++
	}
	if (problems) {
		errorMessage.value =
			problems === 1
				? __("One request needs attention. Nothing was created.")
				: __("{0} requests need attention. Nothing was created.", [problems])
		showError.value = true
		return
	}

	busy.value = true
	const total = rows.value.length
	// one at a time, so each request is created, attached and submitted in order
	for (const row of [...rows.value]) {
		try {
			await processRow(row, sendForApproval)
			rows.value = rows.value.filter((r) => r.key !== row.key)
		} catch (error) {
			row.error = messageOf(error)
		}
	}
	busy.value = false

	const failed = rows.value.length
	const done = total - failed
	if (!failed) {
		toast({
			title: __("Success"),
			text: sendForApproval
				? __("{0} expense request(s) submitted for approval.", [done])
				: __("{0} expense request(s) saved as draft.", [done]),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		router.replace({ name: "ExpenseRequestListView" })
		return
	}

	errorMessage.value = done
		? __("{0} of {1} requests went through. The rest are shown below with the reason; fix them and submit again.", [done, total])
		: __("None of the requests went through. The reason is shown on each one.")
	showError.value = true
}
</script>
