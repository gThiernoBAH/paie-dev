<script setup>
import { ref, computed } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { aLaPermission, lireUtilisateur } from '@/api/session'
import { Eye, Download } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'

const u = lireUtilisateur()
const maintenant = new Date()
const RAPPORTS = {
  'masse-salariale': { libelle: 'Masse salariale (par mois)', params: ['annee'], graphique: 'Coût employeur' },
  'par-service': { libelle: 'Répartition par service', params: ['annee', 'mois'] },
  'heures-supplementaires': { libelle: 'Heures supplémentaires', params: ['annee'] },
  effectif: { libelle: 'Effectif et structure', params: ['au'] },
  mouvements: { libelle: 'Entrées et sorties', params: ['du', 'au'] },
  'liste-personnel': { libelle: 'Liste du personnel', params: ['au'] },
  'situation-famille': { libelle: 'Situation de famille (parts, enfants à charge)', params: ['au'] },
  'journal-presences': { libelle: 'Journal des présences', params: ['annee', 'mois'] },
  'journal-conges': { libelle: 'Journal des congés et absences', params: ['annee'] },
  ...(aLaPermission(u, 'voir_donnees_sensibles') ? {
    'livre-de-paie': { libelle: 'Livre de paie (nominatif)', params: ['annee', 'mois'] },
    'journal-rubriques': { libelle: 'Journal des rubriques (contrôle)', params: ['annee', 'mois'] },
    'journal-prets': { libelle: 'Journal des prêts et avances', params: [] },
    'hors-grille': { libelle: 'Salariés et grille salariale', params: ['au'] },
    'bulletins-a-controler': { libelle: 'Bulletins à contrôler (anomalies)', params: ['annee', 'mois'] },
    'cumuls-annuels': { libelle: 'Cumuls annuels par salarié (clôture)', params: ['annee'] },
  } : {}),
}
const choix = ref('masse-salariale')
const p = ref({ annee: maintenant.getFullYear(), mois: maintenant.getMonth() + 1, au: maintenant.toLocaleDateString('sv-SE'), du: `${maintenant.getFullYear()}-01-01` })
const donnees = ref(null)
const erreur = ref('')
const requete = () => Object.fromEntries(RAPPORTS[choix.value].params.map((k) => [k, p.value[k]]))

async function voir() {
  erreur.value = ''; donnees.value = null
  try { donnees.value = (await apiClient.get(`/rapports/${choix.value}`, { params: { ...requete(), format: 'json' } })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function exporter(format) {
  try { await telecharger(`/rapports/${choix.value}`, { ...requete(), format }, `${choix.value}.${format}`) } catch (e) { erreur.value = 'Export impossible.' }
}
const nombre = (v) => (/^-?\d+(\.\d+)?$/.test(String(v)) && String(v).includes('.') ? Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 2 }) : v)
const colonnes = computed(() => (donnees.value?.entetes || []).map((e, j) => ({ cle: `c${j}`, libelle: e, tri: true, align: j > 0 ? 'droite' : undefined, valeur: (l) => (j > 0 && /^-?\d+(\.\d+)?$/.test(String(l.v[j])) ? Number(l.v[j]) : l.v[j]), format: (v) => nombre(v) })))
const lignes = computed(() => (donnees.value?.lignes || []).map((v, i) => ({ id: i, v })))
const barres = computed(() => {
  const g = RAPPORTS[choix.value].graphique
  if (!g || !donnees.value?.lignes.length) return []
  const i = donnees.value.entetes.indexOf(g)
  const max = Math.max(...donnees.value.lignes.map((l) => Number(l[i])), 1)
  return donnees.value.lignes.map((l) => ({ mois: l[0], valeur: Number(l[i]), pct: Math.round((Number(l[i]) / max) * 100) }))
})
</script>

<template>
  <div class="page">
    <header>
      <h1>Rapports</h1>
      <p class="sous-titre">Pilotage de la masse salariale, des effectifs et des heures supplémentaires, à partir des bulletins validés. Chaque rapport s'exporte en Excel ou en CSV.</p>
    </header>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <form class="ligne" @submit.prevent="voir">
      <label class="field"><span class="field-label">Rapport</span>
        <select v-model="choix" class="input" @change="donnees = null"><option v-for="(r, k) in RAPPORTS" :key="k" :value="k">{{ r.libelle }}</option></select></label>
      <label v-if="RAPPORTS[choix].params.includes('annee')" class="field"><span class="field-label">Année</span><input v-model.number="p.annee" type="number" class="input court" required /></label>
      <label v-if="RAPPORTS[choix].params.includes('mois')" class="field"><span class="field-label">Mois</span><input v-model.number="p.mois" type="number" min="1" max="12" class="input court" required /></label>
      <label v-if="RAPPORTS[choix].params.includes('du')" class="field"><span class="field-label">Du</span><input v-model="p.du" type="date" class="input" required /></label>
      <label v-if="RAPPORTS[choix].params.includes('au')" class="field"><span class="field-label">{{ RAPPORTS[choix].params.includes('du') ? 'Au' : 'À la date du' }}</span><input v-model="p.au" type="date" class="input" required /></label>
      <button class="vbtn vbtn-primary" type="submit"><Eye :size="16" />Afficher</button>
      <button class="vbtn vbtn-secondary" type="button" data-hint="Télécharger ce rapport au format Excel" @click="exporter('xlsx')"><Download :size="16" />Excel</button>
      <button class="vbtn vbtn-secondary" type="button" data-hint="Télécharger ce rapport au format CSV" @click="exporter('csv')"><Download :size="16" />CSV</button>
    </form>

    <template v-if="donnees">
      <h2>{{ donnees.titre }}</h2>
      <div v-if="barres.length" class="card graphe" role="img" :aria-label="`Graphique : ${RAPPORTS[choix].graphique} par mois`">
        <div v-for="b in barres" :key="b.mois" class="colonne">
          <span class="valeur">{{ Math.round(b.valeur / 1000).toLocaleString('fr-FR') }} k</span>
          <div class="barre" :style="{ height: b.pct + '%' }"></div>
          <span class="libelle">{{ b.mois.slice(0, 4) }}</span>
        </div>
      </div>
      <DataTable :colonnes="colonnes" :lignes="lignes" :taille-page="50" vide="Aucune donnée sur cette période (seuls les bulletins validés sont comptés)." placeholder-recherche="Rechercher dans le rapport" />
      <div v-if="donnees.lignes.length && Object.keys(donnees.totaux).length" class="card totaux">
        <strong>TOTAL</strong>
        <span v-for="e in donnees.entetes.slice(1)" :key="e" class="tot"><small>{{ e }}</small> {{ nombre(donnees.totaux[e] ?? '') }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; } .court { max-width: 110px; }
.graphe { display: flex; align-items: flex-end; gap: 8px; height: 200px; padding: var(--space-4) var(--space-4) var(--space-2); }
.colonne { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; min-width: 0; }
.barre { width: 70%; max-width: 48px; background: var(--color-brand); border-radius: 4px 4px 0 0; min-height: 2px; }
.totaux { padding: var(--space-3) var(--space-4); display: flex; gap: var(--space-4); flex-wrap: wrap; font-size: var(--font-size-sm); }
.tot small { display: block; color: var(--color-text-muted); font-size: var(--font-size-xs); }
.tot { font-variant-numeric: tabular-nums; font-weight: 600; }
.valeur, .libelle { font-size: var(--font-size-xs); color: var(--color-text-muted); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
