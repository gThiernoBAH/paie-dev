<script setup>
import { ref, computed } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { Download, Eye } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'

const maintenant = new Date()
const etat = ref('cnps')
const annee = ref(maintenant.getFullYear())
const mois = ref(maintenant.getMonth() + 1)
const apercu = ref(null)
const erreur = ref('')
const ETATS = { cnps: 'CNPS (mensuel)', its: 'ITS (mensuel)', fdfp: 'FDFP (mensuel)', disa: 'DISA (annuel)' }
const params = () => (etat.value === 'disa' ? { annee: annee.value } : { annee: annee.value, mois: mois.value })

async function voir() {
  erreur.value = ''; apercu.value = null
  try { apercu.value = (await apiClient.get(`/declarations/${etat.value}`, { params: { ...params(), format: 'json' } })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function exporter(format) {
  erreur.value = ''
  try { await telecharger(`/declarations/${etat.value}`, { ...params(), format }, `${etat.value}.${format}`) } catch (e) { erreur.value = 'Export impossible.' }
}
const colonnes = computed(() => (apercu.value?.entetes || []).map((e, j) => ({ cle: `c${j}`, libelle: e, tri: true, align: j >= 2 ? 'droite' : undefined, valeur: (l) => l.v[j], format: (v) => fmt(v) })))
const lignes = computed(() => (apercu.value?.lignes || []).map((v, i) => ({ id: i, v })))
const fmt = (v) => (/^-?\d+(\.\d+)?$/.test(String(v)) && String(v).length < 12 && String(v).includes('.') ? Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 2 }) : v)
</script>

<template>
  <div class="page">
    <header>
      <h1>Déclarations</h1>
      <p class="sous-titre">États établis à partir des bulletins <strong>validés</strong>. Les journaliers payés plusieurs fois dans le mois sont cumulés. La consultation des états contenant les numéros CNPS (CNPS, DISA) est tracée.</p>
    </header>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <form class="ligne" @submit.prevent="voir">
      <label class="field"><span class="field-label">État</span>
        <select v-model="etat" class="input"><option v-for="(l, k) in ETATS" :key="k" :value="k">{{ l }}</option></select></label>
      <label class="field"><span class="field-label">Année</span><input v-model.number="annee" type="number" class="input" required /></label>
      <label v-if="etat !== 'disa'" class="field"><span class="field-label">Mois</span><input v-model.number="mois" type="number" min="1" max="12" class="input" required /></label>
      <button class="vbtn vbtn-primary" type="submit"><Eye :size="16" />Afficher</button>
      <button class="vbtn vbtn-secondary" type="button" data-hint="Télécharger l'état au format Excel" @click="exporter('xlsx')"><Download :size="16" />Excel</button>
      <button class="vbtn vbtn-secondary" type="button" data-hint="Télécharger l'état au format CSV" @click="exporter('csv')"><Download :size="16" />CSV</button>
    </form>
    <template v-if="apercu">
      <DataTable :colonnes="colonnes" :lignes="lignes" vide="Aucun bulletin validé sur cette période." placeholder-recherche="Rechercher dans l'état" :taille-page="50" />
      <div v-if="apercu.lignes.length" class="card totaux">
        <strong>TOTAUX</strong>
        <span v-for="(e, j) in apercu.entetes.slice(2)" :key="e" class="tot"><small>{{ e }}</small> {{ fmt(apercu.totaux[e] ?? '') }}</span>
      </div>
    </template>
    <p class="aide">Les colonnes reprennent les informations demandées par la CNPS, la DGI et le FDFP. La mise en page des gabarits officiels est à valider avec les modèles en vigueur (voir la documentation).</p>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.totaux { padding: var(--space-3) var(--space-4); display: flex; gap: var(--space-4); flex-wrap: wrap; font-size: var(--font-size-sm); }
.tot small { display: block; color: var(--color-text-muted); font-size: var(--font-size-xs); }
.tot { font-variant-numeric: tabular-nums; font-weight: 600; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; max-width: 760px; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
