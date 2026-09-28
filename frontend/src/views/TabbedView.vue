<template>
	<ion-page>
		<DesktopShell />
		<ion-tabs>
			<ion-router-outlet></ion-router-outlet>
			<BottomTabs />
		</ion-tabs>
	</ion-page>
</template>

<script setup>
import { IonTabs, IonPage, IonRouterOutlet } from "@ionic/vue"
import BottomTabs from "@/components/BottomTabs.vue"
import DesktopShell from "@/components/DesktopShell.vue"
</script>
