<script setup>
import { ref, computed } from 'vue'
import { Users, ScrollText } from 'lucide-vue-next'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import UtilisateursAdmin from './admin/UtilisateursAdmin.vue'
import AuditAdmin from './admin/AuditAdmin.vue'

const utilisateur = lireUtilisateur()
const onglets = computed(() => [
  { cle: 'utilisateurs', libelle: 'Utilisateurs', icone: Users, visible: aLaPermission(utilisateur, 'gerer_utilisateurs') },
  { cle: 'audit', libelle: "Journal d'audit", icone: ScrollText, visible: aLaPermission(utilisateur, 'voir_audit') },
].filter((o) => o.visible))
const actif = ref(onglets.value[0]?.cle)
</script>

<template>
  <div class="page">
    <header>
      <h1>Administration</h1>
      <p class="sous-titre">Comptes, droits d'accès et traçabilité.</p>
    </header>
    <div class="onglets" role="tablist">
      <button v-for="o in onglets" :key="o.cle" role="tab" :aria-selected="actif === o.cle"
        :class="['onglet', { actif: actif === o.cle }]" @click="actif = o.cle">
        <component :is="o.icone" :size="16" />{{ o.libelle }}
      </button>
    </div>
    <UtilisateursAdmin v-if="actif === 'utilisateurs'" />
    <AuditAdmin v-else-if="actif === 'audit'" />
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap; }
.onglet { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; min-height: 44px; border: none; background: none; cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.onglet.actif { color: var(--color-brand-dark); border-bottom-color: var(--color-brand); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
