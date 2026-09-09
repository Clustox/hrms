<template>
	<div
		class="bg-white w-full flex flex-col pb-5 max-h-[calc(100vh-5rem)] overflow-y-auto"
	>
		<!-- Header -->
		<div
			class="w-full flex flex-row gap-2 pt-8 pb-5 border-b justify-center items-center sticky top-0 z-[100] bg-white"
		>
			<span class="text-gray-900 font-bold text-lg text-center">
				{{ title }}
			</span>
		</div>

		<div
			v-if="!rows || rows.length === 0"
			class="w-full text-center text-gray-500 text-base p-8"
		>
			{{ __("No records to show") }}
		</div>

		<div v-else class="w-full flex flex-col gap-4 p-4">
			<div
				v-for="(row, idx) in rows"
				:key="idx"
				class="w-full flex flex-col gap-3 border rounded-lg p-4"
			>
				<div
					v-for="col in visibleColumns(row)"
					:key="col.fieldname"
					class="flex flex-row items-center justify-between w-full gap-4"
				>
					<div class="text-gray-600 text-base shrink-0">{{ __(col.label) }}</div>
					<div class="text-right">
						<FormattedField
							:value="row[col.fieldname]"
							:fieldtype="col.fieldtype"
							:fieldname="col.fieldname"
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import FormattedField from "@/components/FormattedField.vue"

const __ = inject("$translate")

const props = defineProps({
	title: {
		type: String,
		required: true,
	},
	// child-table rows straight off the Employee doc (e.g. employeeDoc.doc.education)
	rows: {
		type: Array,
		default: () => [],
	},
	// field meta for the child doctype, from hrms.api.get_doctype_fields
	fields: {
		type: Array,
		default: () => [],
	},
})

// only show columns that have a value for this row, skipping layout/system fields
const SKIP = new Set(["column_break", "section_break", "html"])
const visibleColumns = (row) =>
	props.fields.filter((f) => {
		if (SKIP.has(f.fieldtype)) return false
		const v = row[f.fieldname]
		return v !== null && v !== undefined && v !== ""
	})
</script>
