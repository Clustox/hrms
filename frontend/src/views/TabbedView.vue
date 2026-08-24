<template>
	<ion-page>
		<!--
			SidebarNav is viewport-fixed and layers above everything else
			(see its own root class) — it doesn't need ion-tabs to make room
			for it. The actual visible content is constrained to clear it
			via main.css's `.sm:w-96` override instead, since trying to
			resize ion-tabs itself had no effect (it manages its own box
			internally, opaque to a light-DOM width/margin override).
		-->
		<SidebarNav />
		<ion-tabs>
			<ion-router-outlet></ion-router-outlet>
			<BottomTabs />
		</ion-tabs>
	</ion-page>
</template>

<script setup>
import { IonTabs, IonPage, IonRouterOutlet } from "@ionic/vue"
import BottomTabs from "@/components/BottomTabs.vue"
import SidebarNav from "@/components/SidebarNav.vue"
</script>
