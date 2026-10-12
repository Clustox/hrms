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
				<span
					v-if="checkinStatus()"
					class="inline-flex self-start rounded-full px-2 py-0.5 text-[11px] font-medium"
					:class="PUNCH_COLORS[checkinStatus()]"
				>
					{{ __(checkinStatus()) }}
				</span>
			</div>
			<div class="flex flex-col gap-1">
				<div class="text-xs text-gray-500">{{ __("Check-out") }}</div>
				<div class="text-base font-medium text-gray-900">
					{{ props.outTime ? dayjs(props.outTime).format("h:mm A") : "--" }}
				</div>
				<span
					v-if="checkoutStatus()"
					class="inline-flex self-start rounded-full px-2 py-0.5 text-[11px] font-medium"
					:class="PUNCH_COLORS[checkoutStatus()]"
				>
					{{ __(checkoutStatus()) }}
				</span>
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
	shiftStart: { type: [String, Date], default: null },
	shiftEnd: { type: [String, Date], default: null },
})

// Check-in / check-out status vs the employee's actual shift (10-min buffer).
const SHIFT_BUFFER_MINUTES = 10
const PUNCH_COLORS = {
	Late: "bg-amber-50 text-amber-700",
	Early: "bg-amber-50 text-amber-700",
	"On time": "bg-green-50 text-green-700",
	Overtime: "bg-sky-50 text-sky-700",
}
const checkinStatus = () => {
	if (!props.inTime || !props.shiftStart) return null
	const diff = dayjs(props.inTime).diff(dayjs(props.shiftStart), "minute")
	if (diff > SHIFT_BUFFER_MINUTES) return "Late"
	if (diff < -SHIFT_BUFFER_MINUTES) return "Early"
	return "On time"
}
const checkoutStatus = () => {
	if (!props.outTime || !props.shiftEnd) return null
	const diff = dayjs(props.outTime).diff(dayjs(props.shiftEnd), "minute")
	if (diff < -SHIFT_BUFFER_MINUTES) return "Early"
	if (diff > SHIFT_BUFFER_MINUTES) return "Overtime"
	return "On time"
}

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
