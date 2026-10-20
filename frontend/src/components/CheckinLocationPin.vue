<template>
	<span v-if="props.location" ref="rootRef" class="relative inline-flex">
		<button
			type="button"
			class="inline-flex items-center justify-center"
			:aria-label="ariaLabel"
			@click.stop="open = !open"
		>
			<FeatherIcon
				name="map-pin"
				class="h-3.5 w-3.5"
				:class="props.location.verified ? 'text-blue-500' : 'text-orange-500'"
			/>
		</button>
		<div
			v-if="open"
			class="absolute z-20 top-5 left-0 w-56 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg"
		>
			<div class="font-medium">
				{{ props.location.verified ? __("Office") : __("Remote") }}
			</div>
			<div class="mt-0.5 text-gray-400">{{ coordsLabel }}</div>
			<a
				:href="mapUrl"
				target="_blank"
				rel="noopener"
				class="mt-1 inline-block font-medium text-blue-300 hover:text-blue-200"
				@click.stop
			>
				{{ __("Open in Maps") }} →
			</a>
		</div>
	</span>
</template>

<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from "vue"
import { FeatherIcon } from "frappe-ui"

const __ = inject("$translate")

const props = defineProps({
	// { verified: Boolean, location_name: String|undefined, latitude: Number, longitude: Number } or null
	location: { type: Object, default: null },
	label: { type: String, default: "" },
})

const open = ref(false)
const rootRef = ref(null)

const coordsLabel = computed(() =>
	props.location ? `${props.location.latitude.toFixed(4)}, ${props.location.longitude.toFixed(4)}` : ""
)
const mapUrl = computed(() =>
	props.location ? `https://www.google.com/maps?q=${props.location.latitude},${props.location.longitude}` : "#"
)
const ariaLabel = computed(() => props.label || __("View location"))

function onDocumentClick(event) {
	if (open.value && rootRef.value && !rootRef.value.contains(event.target)) {
		open.value = false
	}
}
onMounted(() => document.addEventListener("click", onDocumentClick))
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick))
</script>
