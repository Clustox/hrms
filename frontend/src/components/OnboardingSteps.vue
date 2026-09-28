<template>
	<div class="flex flex-col w-full sm:w-96" v-if="employeeDoc.doc">
		<header
			class="flex flex-col bg-white shadow-sm py-4 px-3 gap-1 sticky top-0 z-10 border-b"
		>
			<h2 class="text-xl font-semibold text-gray-900">
				{{ __("Complete Your Profile") }}
			</h2>
			<span class="text-sm text-gray-500">
				{{ __("Step {0} of {1}: {2}", [stepIndex + 1, steps.length, currentStep.title]) }}
			</span>
		</header>

		<!-- HR review notes -->
		<div
			v-if="employeeDoc.doc.custom_onboarding_notes"
			class="bg-orange-50 border border-orange-200 text-orange-800 text-sm rounded p-3 mx-4 mt-4"
		>
			<div class="font-semibold mb-1">{{ __("Changes requested by HR") }}</div>
			<div>{{ employeeDoc.doc.custom_onboarding_notes }}</div>
		</div>

		<!-- submitted, pending review -->
		<div
			v-if="isReadOnly"
			class="bg-blue-50 border border-blue-200 text-blue-800 text-sm rounded p-3 mx-4 mt-4"
		>
			{{ __("Your onboarding details have been submitted and are awaiting HR review.") }}
		</div>

		<div class="grow overflow-y-auto pb-4">
			<!-- Simple field steps: Personal / Address / Emergency -->
			<div
				v-if="currentStep.type === 'fields' && employeeFields.data"
				class="flex flex-col gap-4 p-4"
			>
				<template v-for="fieldname in currentStep.fields" :key="fieldname">
					<label
						v-if="currentStep.key === 'address' && fieldname === 'permanent_address'"
						class="flex flex-row items-center gap-2 text-sm text-gray-700"
					>
						<input
							type="checkbox"
							v-model="sameAsCurrent"
							:disabled="isReadOnly"
						/>
						{{ __("Same as current address") }}
					</label>

					<FormField
						:fieldtype="getField(fieldname)?.fieldtype"
						:fieldname="fieldname"
						:model-value="employeeDoc.doc[fieldname]"
						@update:modelValue="(v) => (employeeDoc.doc[fieldname] = v)"
						:label="getFieldLabel(fieldname)"
						:options="getField(fieldname)?.options"
						:reqd="MANDATORY_FIELDNAMES.includes(fieldname)"
						:readOnly="
							isReadOnly ||
							(fieldname === 'permanent_address' && sameAsCurrent)
						"
					/>
				</template>

				<ErrorMessage :message="stepError" />
			</div>

			<!-- Child table steps: Education / Work History / Documents -->
			<div
				v-else-if="currentStep.type === 'childTable'"
				class="flex flex-col gap-3 p-4"
			>
				<div class="flex flex-row justify-between items-center gap-2">
					<div class="flex flex-col">
						<h2 class="text-base font-semibold text-gray-800">
							{{ currentStep.section.title }}
						</h2>
						<span class="text-xs text-gray-500">
							{{ __("Add each {0} as a separate entry", [currentStep.section.addLabel.toLowerCase()]) }}
						</span>
					</div>
					<Button
						v-if="!isReadOnly"
						variant="subtle"
						class="text-sm shrink-0"
						@click="openRowModal(currentStep.section)"
					>
						<template #prefix>
							<FeatherIcon name="plus" class="h-4 w-4" />
						</template>
						{{ __("Add {0}", [currentStep.section.addLabel]) }}
					</Button>
				</div>

				<div
					v-if="(employeeDoc.doc[currentStep.section.fieldname] || []).length"
					class="flex flex-col bg-white rounded border divide-y overflow-auto"
				>
					<div
						v-for="(row, idx) in employeeDoc.doc[currentStep.section.fieldname]"
						:key="idx"
						class="flex flex-row p-3.5 items-start justify-between gap-2 cursor-pointer"
						@click="openRowModal(currentStep.section, row, idx)"
					>
						<div class="flex flex-col gap-1 min-w-0 grow">
							<span class="text-sm font-medium text-gray-900 truncate">
								{{ rowTitle(row, childFields[currentStep.section.childDoctype] || []) }}
							</span>
							<div
								v-if="rowDetails(row, childFields[currentStep.section.childDoctype] || []).length"
								class="flex flex-row flex-wrap gap-x-3 gap-y-0.5"
							>
								<span
									v-for="detail in rowDetails(row, childFields[currentStep.section.childDoctype] || [])"
									:key="detail.label"
									class="text-xs text-gray-500"
								>
									<span class="text-gray-400">{{ detail.label }}:</span>
									{{ detail.value }}
								</span>
							</div>
							<span
								v-if="rowHasAttachment(row, currentStep.section.childDoctype)"
								class="inline-flex flex-row items-center gap-1 text-xs text-green-700 w-fit"
							>
								<FeatherIcon name="paperclip" class="h-3 w-3" />
								{{ __("{0} attached", [attachFieldLabel(currentStep.section.childDoctype)]) }}
							</span>
						</div>
						<div v-if="!isReadOnly" class="flex flex-row items-center gap-1 shrink-0">
							<Button
								icon="edit-2"
								variant="ghost"
								:label="__('Edit')"
								class="text-gray-500"
								@click.stop="openRowModal(currentStep.section, row, idx)"
							/>
							<Button
								icon="trash-2"
								variant="ghost"
								:label="__('Remove')"
								class="text-red-600"
								:loading="quickDeletingKey === `${currentStep.section.fieldname}:${idx}`"
								@click.stop="quickDeleteRow(currentStep.section, idx)"
							/>
						</div>
						<FeatherIcon
							v-else
							name="chevron-right"
							class="h-5 w-5 text-gray-500 shrink-0 mt-1"
						/>
					</div>
				</div>
				<EmptyState
					v-else
					:message="__('No {0} added yet', [currentStep.section.title.toLowerCase()])"
					:isTableField="true"
				/>

				<ErrorMessage :message="stepError" />
			</div>

			<!-- Review & submit -->
			<div v-else-if="currentStep.type === 'review'" class="flex flex-col gap-4 p-4">
				<div class="flex flex-col bg-white rounded border p-4 gap-2">
					<h2 class="text-base font-semibold text-gray-800">
						{{ __("Mandatory fields") }}
					</h2>
					<div v-if="!missingMandatory.length" class="text-sm text-green-600">
						{{ __("All mandatory fields are complete.") }}
					</div>
					<ul v-else class="text-sm text-red-600 list-disc list-inside">
						<li v-for="label in missingMandatory" :key="label">{{ label }}</li>
					</ul>
				</div>

				<ErrorMessage :message="submitError" />

				<div v-if="submitOnboarding.data" class="text-sm text-green-600">
					{{ __("Submitted for review.") }}
				</div>
			</div>
		</div>

		<!-- Step navigation -->
		<div
			class="px-4 pt-4 pb-4 standalone:pb-safe-bottom sm:w-96 bg-white sticky bottom-0 w-full drop-shadow-xl z-40 border-t rounded-t-lg flex flex-row gap-3"
		>
			<Button
				v-if="stepIndex > 0"
				variant="outline"
				class="w-full py-5"
				@click="goBack"
			>
				{{ __("Back") }}
			</Button>
			<Button
				v-if="currentStep.type !== 'review'"
				variant="solid"
				class="w-full py-5"
				:loading="saveFields.loading"
				@click="saveCurrentStep"
			>
				{{ currentStep.type === "fields" ? __("Save & Continue") : __("Continue") }}
			</Button>
			<Button
				v-else-if="!isReadOnly"
				variant="solid"
				class="w-full py-5"
				:loading="submitOnboarding.loading"
				@click="submit"
			>
				{{ __("Submit for review") }}
			</Button>
		</div>

		<!-- Add/Edit child table row -->
		<CustomIonModal :isOpen="isRowModalOpen" @didDismiss="closeRowModal">
			<template #actionSheet>
				<div class="bg-white w-full flex flex-col items-center justify-center pb-5">
					<div class="w-full pt-8 pb-5 border-b text-center">
						<span class="text-gray-900 font-bold text-lg">{{ rowModalTitle }}</span>
					</div>
					<div
						class="w-full flex flex-col items-center justify-center gap-5 p-4 max-h-[70vh] overflow-y-auto"
					>
						<div class="flex flex-col w-full space-y-4 px-0.5">
							<template v-for="field in activeChildFields" :key="field.fieldname">
								<div v-if="field.fieldtype === 'Attach'" class="flex flex-col gap-1.5 w-full">
									<span
										:class="[
											field.reqd ? `after:content-['_*'] after:text-red-600` : ``,
											`block text-sm leading-5 text-gray-700`,
										]"
									>
										{{ __(field.label) }}
									</span>

									<div
										v-if="rowItem[field.fieldname]"
										class="flex flex-row items-center justify-between border rounded p-2 gap-2"
									>
										<a
											:href="rowItem[field.fieldname]"
											target="_blank"
											class="text-sm text-gray-700 truncate"
										>
											{{ rowItem[field.fieldname].split("/").pop() }}
										</a>
										<FeatherIcon
											name="x"
											class="h-4 w-4 cursor-pointer text-gray-700 shrink-0"
											@click="rowItem[field.fieldname] = ''"
										/>
									</div>
									<label v-else class="cursor-pointer">
										<div
											class="flex flex-row items-center justify-center gap-2 border shadow-sm rounded p-2.5 text-sm text-gray-700"
										>
											<LoadingIndicator
												v-if="uploadingField === field.fieldname"
												class="w-3 h-3"
											/>
											<FeatherIcon v-else name="upload" class="h-4 w-4" />
											{{ __("Upload") }}
										</div>
										<input
											class="hidden"
											type="file"
											@change="(e) => handleRowFileSelect(e, field.fieldname)"
										/>
									</label>
								</div>

								<FormField
									v-else
									:fieldtype="field.fieldtype"
									:fieldname="field.fieldname"
									v-model="rowItem[field.fieldname]"
									:label="__(field.label)"
									:options="field.options"
									:reqd="Boolean(field.reqd)"
								/>
							</template>
						</div>

						<ErrorMessage :message="rowModalError" />

						<div class="flex w-full flex-row items-center justify-between gap-3">
							<Button
								v-if="editingRowIdx !== null"
								class="border-red-600 text-red-600 py-5 text-sm"
								variant="outline"
								theme="red"
								@click="deleteActiveRow"
							>
								<template #prefix>
									<FeatherIcon name="trash" class="w-4" />
								</template>
								{{ __("Delete") }}
							</Button>
							<Button
								variant="solid"
								class="w-full py-5 text-sm disabled:bg-gray-700 disabled:text-white"
								:disabled="!canSaveRow"
								:loading="childTableSaving"
								@click="saveActiveRow"
							>
								{{ editingRowIdx === null ? __("Add") : __("Update") }}
							</Button>
						</div>
					</div>
				</div>
			</template>
		</CustomIonModal>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref, watch } from "vue"
import { useRouter } from "vue-router"
import {
	Button,
	ErrorMessage,
	FeatherIcon,
	LoadingIndicator,
	createDocumentResource,
	createResource,
	toast,
} from "frappe-ui"

import FormField from "@/components/FormField.vue"
import EmptyState from "@/components/EmptyState.vue"
import CustomIonModal from "@/components/CustomIonModal.vue"

import { FileAttachment } from "@/composables"

const DOCTYPE = "Employee"

const employee = inject("$employee")
const __ = inject("$translate")
const router = useRouter()

// Same cache key (doctype + name) as Profile.vue's own employeeDoc, so this
// is literally the same resource instance -- edits here are immediately
// reflected on the Profile view and vice versa.
const employeeDoc = createDocumentResource({
	doctype: DOCTYPE,
	name: employee.data.name,
	fields: "*",
	auto: true,
})

const employeeFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: DOCTYPE },
	auto: true,
})

// Several onboarding fields (current_address, permanent_address,
// custom_cnic_no, custom_cnic_expiry_date, date_of_birth, ...) sit at
// Employee permlevel 1 on the live server, where ESS only has read access
// (see setup/permissions/apply_field_levels.py + apply_self_service.py) --
// so a hire can never save them through frappe.client.set_value
// (employeeDoc.setValue), which enforces field-level permlevel. All writes
// go through this whitelisted, status-gated backend method instead.
const saveFields = createResource({
	url: "hrms.onboarding.save_onboarding_fields",
})

function saveOnboardingValues(values, { onSuccess, onError } = {}) {
	saveFields.submit(
		{ employee: employee.data.name, values },
		{
			onSuccess: (data) => {
				employeeDoc.reload()
				onSuccess?.(data)
			},
			onError,
		}
	)
}

function getField(fieldname) {
	return employeeFields.data?.find((field) => field.fieldname === fieldname)
}

function getFieldLabel(fieldname) {
	const field = getField(fieldname)
	return __(field?.label || fieldname, null, DOCTYPE)
}

// Mirrors hrms.onboarding.MANDATORY (backend is the source of truth; this is
// only used to show a "required" hint and a client-side preview -- the real
// gate is the missing-fields error thrown by submit_onboarding).
const MANDATORY_FIELDNAMES = [
	"custom_cnic_no",
	"custom_cnic_expiry_date",
	"current_address",
	"permanent_address",
	"blood_group",
	"person_to_be_contacted",
	"emergency_phone_number",
	"relation",
]

// `addLabel` is the singular noun used on the "Add ..." button and error/empty
// copy (e.g. "Add Education", "No work experience added yet") -- kept
// separate from `title` (the step/section heading, which for Documents reads
// better in the plural).
const CHILD_SECTIONS = {
	education: {
		key: "education",
		fieldname: "education",
		childDoctype: "Employee Education",
		title: __("Education"),
		addLabel: __("Education"),
	},
	work_history: {
		key: "work_history",
		fieldname: "external_work_history",
		childDoctype: "Employee External Work History",
		title: __("Work Experience"),
		addLabel: __("Work Experience"),
	},
	documents: {
		key: "documents",
		fieldname: "custom_onboarding_documents",
		childDoctype: "Employee Onboarding Document",
		title: __("Documents"),
		addLabel: __("Document"),
	},
}

// hrms.api.get_doctype_fields only returns SUPPORTED_FIELD_TYPES, which does
// not include "Attach" -- these three Attach fields (added for onboarding)
// never come back from that endpoint, so their metadata is hardcoded here
// instead of being read off the child doctype's fields.
const ATTACH_FIELD_BY_DOCTYPE = {
	"Employee Education": { fieldname: "custom_certificate", label: "Certificate", reqd: false },
	"Employee External Work History": {
		fieldname: "custom_experience_letter",
		label: "Experience Letter",
		reqd: false,
	},
	"Employee Onboarding Document": { fieldname: "attachment", label: "Attachment", reqd: true },
}

const steps = [
	{
		key: "personal",
		type: "fields",
		title: __("Personal"),
		fields: [
			"custom_cnic_no",
			"custom_cnic_expiry_date",
			"custom_father_or_husband_name",
			"custom_religion",
			"custom_nationality",
			"blood_group",
			"date_of_birth",
			"cell_number",
			"marital_status",
			"bio",
		],
	},
	{
		key: "address",
		type: "fields",
		title: __("Address"),
		fields: ["current_address", "permanent_address"],
	},
	{
		key: "emergency",
		type: "fields",
		title: __("Emergency Contact"),
		fields: ["person_to_be_contacted", "emergency_phone_number", "relation"],
	},
	{ key: "education", type: "childTable", title: __("Education"), section: CHILD_SECTIONS.education },
	{
		key: "work_history",
		type: "childTable",
		title: __("Work Experience"),
		section: CHILD_SECTIONS.work_history,
	},
	{
		key: "documents",
		type: "childTable",
		title: __("Documents"),
		section: CHILD_SECTIONS.documents,
	},
	{ key: "review", type: "review", title: __("Review & Submit") },
]

const LAST_STEP_INDEX = steps.length - 1

const stepIndex = ref(0)
const currentStep = computed(() => steps[stepIndex.value])
const stepError = ref("")

// Always derived from the CURRENT stepIndex.value and clamped to
// [0, LAST_STEP_INDEX] -- never an absolute jump -- so Next/Back can only
// ever move the wizard by exactly one step in either direction, regardless
// of which step type (fields / childTable / review) is active.
function goNext() {
	stepError.value = ""
	stepIndex.value = Math.min(stepIndex.value + 1, LAST_STEP_INDEX)
}

function goBack() {
	stepError.value = ""
	stepIndex.value = Math.max(stepIndex.value - 1, 0)
}

const isReadOnly = computed(() => employeeDoc.doc?.custom_onboarding_status === "Submitted")

// "same as current address" toggle for the Address step
const sameAsCurrent = ref(false)
watch(
	() => employeeDoc.doc?.current_address,
	(value) => {
		if (sameAsCurrent.value && employeeDoc.doc) {
			employeeDoc.doc.permanent_address = value
		}
	}
)
watch(sameAsCurrent, (value) => {
	if (value && employeeDoc.doc) {
		employeeDoc.doc.permanent_address = employeeDoc.doc.current_address
	}
})

function saveCurrentStep() {
	if (isReadOnly.value || currentStep.value.type !== "fields") {
		goNext()
		return
	}

	const values = {}
	currentStep.value.fields.forEach((fieldname) => {
		values[fieldname] = employeeDoc.doc[fieldname]
	})

	stepError.value = ""
	saveOnboardingValues(values, {
		onSuccess: () => goNext(),
		onError: (e) => {
			stepError.value = e.messages?.join(", ") || __("Failed to save. Please try again.")
		},
	})
}

// child-doctype field metadata, lazy-loaded once per doctype (same approach
// as Profile.vue's childFields for the read-only Education/Work Experience
// sections)
const childFields = reactive({})
function loadChildFields(doctype) {
	if (childFields[doctype]) return
	createResource({
		url: "hrms.api.get_doctype_fields",
		params: { doctype },
		auto: true,
		onSuccess: (data) => {
			childFields[doctype] = data
		},
	})
}

const SKIP_FIELDTYPES = new Set(["Section Break", "Column Break", "HTML"])

// Populated, displayable (non-layout, non-attach) fields for a row, in the
// child doctype's own field order -- this drives both rowTitle and
// rowDetails below so the row list always reflects the doctype's actual
// fields (school/qualification/year for Education, company/designation/
// experience for Work History, document type for Documents, ...).
function displayableRowFields(row, fields) {
	return fields.filter(
		(f) => !SKIP_FIELDTYPES.has(f.fieldtype) && f.fieldtype !== "Attach" && row[f.fieldname]
	)
}

// First populated field is used as the row's bolded title (e.g. the school/
// university name, or the company name for work history).
function rowTitle(row, fields) {
	const [first] = displayableRowFields(row, fields)
	return first ? row[first.fieldname] : __("Untitled")
}

// Remaining populated fields (up to 3) are shown underneath as labeled
// "Field: value" chips, so it's clear which field each value came from
// (e.g. "Qualification: Bachelor's · Year of Passing: 2020").
function rowDetails(row, fields) {
	// No doctype context passed to __() here, matching how the Add/Edit
	// modal itself translates these same child-doctype field labels.
	return displayableRowFields(row, fields)
		.slice(1, 4)
		.map((f) => ({ label: __(f.label), value: row[f.fieldname] }))
}

function attachFieldLabel(doctype) {
	return __(ATTACH_FIELD_BY_DOCTYPE[doctype]?.label || "Attachment")
}

function rowHasAttachment(row, doctype) {
	const attachField = ATTACH_FIELD_BY_DOCTYPE[doctype]
	return Boolean(attachField && row[attachField.fieldname])
}

// Add/Edit row modal
const isRowModalOpen = ref(false)
const activeSection = ref(null)
const rowItem = ref({})
const editingRowIdx = ref(null)
const rowModalError = ref("")
const childTableSaving = ref(false)
const uploadingField = ref(null)

const activeChildFields = computed(() => {
	if (!activeSection.value) return []
	const doctype = activeSection.value.childDoctype
	const fields = (childFields[doctype] || []).filter((f) => !SKIP_FIELDTYPES.has(f.fieldtype))
	const attachField = ATTACH_FIELD_BY_DOCTYPE[doctype]
	if (attachField) {
		fields.push({
			fieldname: attachField.fieldname,
			fieldtype: "Attach",
			label: attachField.label,
			reqd: attachField.reqd,
		})
	}
	return fields
})

const rowModalTitle = computed(() => {
	if (!activeSection.value) return ""
	return editingRowIdx.value === null
		? __("New {0}", [activeSection.value.title])
		: __("Edit {0}", [activeSection.value.title])
})

const canSaveRow = computed(() =>
	activeChildFields.value.every((f) => !f.reqd || rowItem.value[f.fieldname])
)

function openRowModal(section, row, idx) {
	if (isReadOnly.value) return
	activeSection.value = section
	rowItem.value = row ? { ...row } : {}
	editingRowIdx.value = idx ?? null
	rowModalError.value = ""
	isRowModalOpen.value = true
}

function closeRowModal() {
	isRowModalOpen.value = false
	activeSection.value = null
	rowItem.value = {}
	editingRowIdx.value = null
	rowModalError.value = ""
}

function persistRows(fieldname, rows) {
	rowModalError.value = ""
	childTableSaving.value = true
	saveOnboardingValues(
		{ [fieldname]: rows },
		{
			onSuccess: () => {
				childTableSaving.value = false
				closeRowModal()
			},
			onError: (e) => {
				childTableSaving.value = false
				rowModalError.value = e.messages?.join(", ") || __("Failed to save. Please try again.")
			},
		}
	)
}

function saveActiveRow() {
	const section = activeSection.value
	const rows = [...(employeeDoc.doc[section.fieldname] || [])]
	if (editingRowIdx.value === null) {
		rows.push({ ...rowItem.value })
	} else {
		rows[editingRowIdx.value] = { ...rowItem.value }
	}
	persistRows(section.fieldname, rows)
}

function deleteActiveRow() {
	const section = activeSection.value
	const rows = [...(employeeDoc.doc[section.fieldname] || [])]
	rows.splice(editingRowIdx.value, 1)
	persistRows(section.fieldname, rows)
}

// Inline "trash" affordance on the row list, so removing an entry doesn't
// require opening the edit modal first. `quickDeletingKey` scopes the
// loading spinner to the one row being removed instead of the modal's
// shared `childTableSaving` flag.
const quickDeletingKey = ref(null)

function quickDeleteRow(section, idx) {
	if (isReadOnly.value) return
	const rows = [...(employeeDoc.doc[section.fieldname] || [])]
	rows.splice(idx, 1)

	stepError.value = ""
	quickDeletingKey.value = `${section.fieldname}:${idx}`
	saveOnboardingValues(
		{ [section.fieldname]: rows },
		{
			onSuccess: () => {
				quickDeletingKey.value = null
			},
			onError: (e) => {
				quickDeletingKey.value = null
				stepError.value = e.messages?.join(", ") || __("Failed to remove. Please try again.")
			},
		}
	)
}

async function handleRowFileSelect(e, fieldname) {
	const file = e.target.files[0]
	e.target.value = ""
	if (!file) return

	uploadingField.value = fieldname
	try {
		const fileDoc = await new FileAttachment(file).upload(DOCTYPE, employee.data.name, "")
		rowItem.value[fieldname] = fileDoc.file_url
	} catch (_e) {
		// FileAttachment.upload already toasts the error
	} finally {
		uploadingField.value = null
	}
}

// Submit for review
const missingMandatory = computed(() =>
	MANDATORY_FIELDNAMES.filter((fieldname) => !employeeDoc.doc?.[fieldname]).map(getFieldLabel)
)

const submitError = ref("")
const submitOnboarding = createResource({
	url: "hrms.onboarding.submit_onboarding",
	makeParams: () => ({ employee: employee.data.name }),
	onSuccess: () => {
		submitError.value = ""
		toast({
			title: __("Success"),
			text: __("Submitted for review."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		employeeDoc.reload()
		// Onboarding is done -- leave the Profile onboarding view and land the
		// employee on the app's home/dashboard instead of the (now read-only,
		// "awaiting HR review") wizard.
		router.push({ name: "Home" })
	},
	onError: (e) => {
		submitError.value =
			e.messages?.join(", ") || e.message || __("Something went wrong. Please try again.")
	},
})

function submit() {
	submitError.value = ""
	submitOnboarding.submit()
}

onMounted(() => {
	Object.values(CHILD_SECTIONS).forEach((section) => loadChildFields(section.childDoctype))
})
</script>
