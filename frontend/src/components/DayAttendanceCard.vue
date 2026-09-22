<template>
	<div class="flex flex-col gap-3 bg-white rounded-lg border p-3.5">
		<!-- Date + day status -->
		<div class="flex flex-row items-center justify-between">
			<div class="text-base font-semibold text-gray-900">
				{{ dayjs(props.date).format("MMM D, YYYY") }}
			</div>
			<Badge
				v-if="props.status"
				variant="outline"
				:theme="statusColorMap[props.status] || 'gray'"
				:label="__(props.status)"
				size="sm"
			/>
		</div>

		<!-- Check-in / Check-out, side by side -->
		<div class="grid grid-cols-2 gap-3">
			<div class="flex flex-col gap-1">
				<div class="text-xs text-gray-500">{{ __("Check-in") }}</div>
				<div class="text-base font-medium text-gray-900">
					{{ props.inTime ? dayjs(props.inTime).format("h:mm A") : "--" }}
				</div>
			</div>
			<div class="flex flex-col gap-1">
				<div class="text-xs text-gray-500">{{ __("Check-out") }}</div>
				<div class="text-base font-medium text-gray-900">
					{{ props.outTime ? dayjs(props.outTime).format("h:mm A") : "--" }}
				</div>
			</div>
		</div>

		<hr />

		<!-- Worked time. Not "Expected Time" alongside it -- that needs a
		     Shift Type with expected in/out timing assigned to the employee,
		     which isn't set up on this site yet. -->
		<div class="flex flex-col gap-1 bg-gray-50 rounded p-2.5">
			<div class="text-xs text-gray-500">{{ __("Worked Time") }}</div>
			<div class="text-base font-semibold text-gray-900">
				{{ props.workingHours ? formatWorkedTime(props.workingHours) : "--" }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { Badge } from "frappe-ui"

const dayjs = inject("$dayjs")
const __ = inject("$translate")

const props = defineProps({
	date: { type: [String, Date], required: true },
	inTime: { type: [String, Date], default: null },
	outTime: { type: [String, Date], default: null },
	workingHours: { type: Number, default: null },
	status: { type: String, default: null },
})

// Same status set as AttendanceCalendar's colorMap, kept in sync manually --
// no shared constant for this exists yet.
const statusColorMap = {
	Present: "green",
	"Work From Home": "green",
	"Half Day": "orange",
	Absent: "red",
	"On Leave": "blue",
}

const formatWorkedTime = (hours) => {
	const totalMinutes = Math.round(hours * 60)
	const h = Math.floor(totalMinutes / 60)
	const m = totalMinutes % 60
	return __("{0}h {1}m", [h, String(m).padStart(2, "0")])
}
</script>
