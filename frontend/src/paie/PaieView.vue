<script setup>
import Sidebar from '@/components/Sidebar.vue'
</script>

<template>
  <div class="coque">
    <Sidebar />
    <main class="contenu"><router-view /></main>
  </div>
</template>

<style scoped>
.coque { display: flex; height: 100%; }
.contenu { flex: 1; min-width: 0; overflow-y: auto; }

/* Téléphone : le menu passe au-dessus du contenu au lieu de le serrer. */
@media (max-width: 760px) {
  .coque { flex-direction: column; }
  .coque :deep(.sidebar) { width: 100%; flex: 0 0 auto; height: auto; max-height: 45%; border-right: none; border-bottom: 1px solid var(--color-border); }
}
</style>
