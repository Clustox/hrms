<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<DesktopShell />
			<div
				class="flex flex-col h-full w-full lg:h-auto lg:min-h-screen lg:bg-air-bg lg:pl-[250px] lg:pt-[68px] lg:pb-12"
			>
				<div
					class="w-full h-full bg-white sm:w-96 flex flex-col lg:h-auto lg:w-full lg:max-w-[1100px] lg:mx-auto lg:mt-8 lg:rounded-air lg:border lg:border-air-line lg:shadow-air lg:overflow-hidden"
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

						<!-- the table: a header row, then one line per expense -->
						<div class="lg:overflow-x-auto lg:rounded lg:border lg:bg-white">
							<div class="exp-table flex flex-col gap-3 lg:gap-0">
								<div
									class="hidden lg:grid exp-grid items-center border-b bg-gray-50 px-3 py-2 text-xs font-medium text-gray-600"
									:class="{ 'with-beneficiary': showBeneficiary }"
								>
									<span>{{ __("No.") }}</span>
									<span>{{ fieldsByName.expense_type.label }} <i class="not-italic text-red-600">*</i></span>
									<span v-if="showBeneficiary">{{ fieldsByName.beneficiary.label }}</span>
									<span>{{ fieldsByName.reason.label }} <i class="not-italic text-red-600">*</i></span>
									<span>{{ fieldsByName.amount.label }} <i class="not-italic text-red-600">*</i></span>
									<span>{{ __("Attachments") }} <i class="not-italic text-red-600">*</i></span>
									<span></span>
								</div>

								<div
									v-for="(row, index) in rows"
									:key="row.key"
									class="exp-row rounded border p-3.5 lg:rounded-none lg:border-0 lg:border-b lg:px-3 lg:py-2.5 lg:last:border-b-0"
									:class="row.error ? 'border-red-300 bg-red-50/40' : 'border-gray-200 bg-white'"
								>
									<div class="exp-grid items-start" :class="{ 'with-beneficiary': showBeneficiary }">
										<div class="flex flex-row items-center justify-between lg:justify-start lg:pt-2.5">
											<span class="text-sm text-gray-500">{{ index + 1 }}</span>
											<span v-if="row.created" class="text-xs text-gray-600 lg:hidden">
												{{ __("Created as {0}", [row.created]) }}
											</span>
											<Button
												v-else-if="rows.length > 1"
												class="lg:hidden"
												variant="ghost"
												:disabled="busy"
												@click="removeRow(row)"
											>
												<FeatherIcon name="trash-2" class="h-4 w-4 text-gray-700" />
											</Button>
										</div>

										<div class="exp-cell min-w-0">
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
										</div>

										<div
											v-if="showBeneficiary"
											class="exp-cell min-w-0"
											:class="isMedical(row) ? '' : 'hidden lg:block'"
										>
											<FormField
												v-if="isMedical(row)"
												fieldtype="Select"
												fieldname="beneficiary"
												:label="fieldsByName.beneficiary.label"
												:options="fieldsByName.beneficiary.options"
												v-model="row.beneficiary"
												:readOnly="Boolean(row.created)"
											/>
											<span v-else class="hidden lg:block pt-2 text-gray-400">&mdash;</span>
										</div>

										<div class="exp-cell min-w-0">
											<FormField
												fieldtype="Data"
												fieldname="reason"
												:label="fieldsByName.reason.label"
												v-model="row.reason"
												:readOnly="Boolean(row.created)"
												reqd
											/>
										</div>

										<div class="exp-cell min-w-0">
											<FormField
												fieldtype="Currency"
												fieldname="amount"
												:label="fieldsByName.amount.label"
												v-model="row.amount"
												:readOnly="Boolean(row.created)"
												reqd
											/>
										</div>

										<div class="exp-cell min-w-0 flex flex-col gap-1.5">
											<span class="text-sm leading-5 text-gray-700 lg:hidden">
												{{ __("Attachments") }} <i class="not-italic text-red-600">*</i>
											</span>
											<label
												class="flex cursor-pointer items-center justify-center gap-1.5 rounded border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
												:class="row.created ? 'pointer-events-none opacity-50' : ''"
											>
												<FeatherIcon name="paperclip" class="h-4 w-4" />
												{{ row.files.length ? __("{0} file(s)", [row.files.length]) : __("Attach") }}
												<input
													class="hidden"
													type="file"
													multiple
													accept="*"
													@change="(e) => addFiles(row, e)"
												/>
											</label>
										</div>

										<div class="hidden lg:flex flex-row items-center justify-end pt-1.5">
											<span v-if="row.created" :title="row.created">
												<FeatherIcon name="check" class="h-4 w-4 text-green-600" />
											</span>
											<Button
												v-else-if="rows.length > 1"
												variant="ghost"
												:title="__('Delete')"
												:disabled="busy"
												@click="removeRow(row)"
											>
												<FeatherIcon name="trash-2" class="h-4 w-4 text-gray-600" />
											</Button>
										</div>
									</div>

									<!-- files chosen for this row -->
									<ul v-if="row.files.length" class="mt-2 flex flex-wrap gap-2 lg:pl-10">
										<li
											v-for="file in row.files"
											:key="file.name + file.size"
											class="flex items-center gap-1.5 rounded bg-gray-100 px-2 py-1 text-xs text-gray-700"
										>
											<span class="max-w-[16rem] truncate">{{ file.name }}</span>
											<FeatherIcon
												v-if="!row.created"
												name="x"
												class="h-3.5 w-3.5 cursor-pointer"
												@click="removeFile(row, file)"
											/>
										</li>
									</ul>

									<p v-if="row.error" class="mt-2 text-sm text-red-600 whitespace-pre-line lg:pl-10">
										{{ row.error }}
									</p>
								</div>
							</div>
						</div>

						<Button
							variant="outline"
							class="w-full lg:w-auto lg:self-start"
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
import FormField from "@/components/FormField.vue"
import { FileAttachment } from "@/composables"

const __ = inject("$translate")
const employee = inject("$employee")
const router = useRouter()

const DOCTYPE = "Expense Request"
// Beneficiary (Self / Spouse / Children) only applies to medical claims.
const MEDICAL_TYPES = ["OPD", "IPD"]
// One request per row, so keep a sensible ceiling on a single submission.
const MAX_ROWS = 20

let rowSeq = 0
function newRow() {
	return {
		key: ++rowSeq,
		expense_type: "",
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
// the Beneficiary column exists only while at least one row is a medical (OPD / IPD) expense
const showBeneficiary = computed(() => rows.value.some(isMedical))

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

<style scoped>
/* one row = one grid: stacked on a phone, lined up under the header on a desktop */
.exp-grid {
	display: grid;
	gap: 0.75rem;
	grid-template-columns: 1fr;
}
@media (min-width: 1024px) {
	.exp-grid {
		gap: 0.5rem;
		grid-template-columns: 2rem 11.5rem minmax(10rem, 1fr) 7.5rem 7.5rem 2.5rem;
	}
	.exp-grid.with-beneficiary {
		grid-template-columns: 2rem 11.5rem 8rem minmax(10rem, 1fr) 7.5rem 7.5rem 2.5rem;
	}
	.exp-table {
		min-width: 50rem;
	}
	/* the column titles are in the header row, so hide each field's own label here */
	.exp-row .exp-cell > :deep(div) > span:first-child {
		display: none;
	}
}
</style>
