<template>
  <div class="app-root">
    <router-view />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useEcran } from '@/composables/useEcran'
import { watchEffect } from 'vue'

// Téléphone : classe globale qui masque tout contrôle d'écriture (.ecriture) ; le serveur applique la même règle.
const { mobile } = useEcran()
watchEffect(() => document.documentElement.classList.toggle('lecture-seule', mobile.value))
</script>

<style scoped>
.app-root {
  height: 100%;
}
</style>
