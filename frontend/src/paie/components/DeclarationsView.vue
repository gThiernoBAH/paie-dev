<script setup>
import { ref } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { Download, Eye } from 'lucide-vue-next'

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
      <button class="vbtn vbtn-secondary" type="button" @click="exporter('xlsx')"><Download :size="16" />Excel</button>
      <button class="vbtn vbtn-secondary" type="button" @click="exporter('csv')"><Download :size="16" />CSV</button>
    </form>
    <div v-if="apercu" class="card cadre">
      <table>
        <thead><tr><th v-for="e in apercu.entetes" :key="e">{{ e }}</th></tr></thead>
        <tbody>
          <tr v-for="(l, i) in apercu.lignes" :key="i"><td v-for="(v, j) in l" :key="j" :class="{ num: j >= 2 }">{{ fmt(v) }}</td></tr>
          <tr v-if="!apercu.lignes.length"><td :colspan="apercu.entetes.length" class="vide">Aucun bulletin validé sur cette période.</td></tr>
          <tr v-else class="total"><td v-for="(e, j) in apercu.entetes" :key="e" :class="{ num: j >= 2 }">{{ j === 0 ? 'TOTAL' : fmt(apercu.totaux[e] ?? '') }}</td></tr>
        </tbody>
      </table>
    </div>
    <p class="aide">Les colonnes reprennent les informations demandées par la CNPS, la DGI et le FDFP. La mise en page des gabarits officiels est à valider avec les modèles en vigueur (voir la documentation).</p>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 12px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 12px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; } .total td { font-weight: 700; background: #F8FAFC; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; max-width: 760px; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
