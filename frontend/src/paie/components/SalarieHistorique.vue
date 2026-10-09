<script setup>
/** Frise des mutations (service, section, emploi, catégorie, site, contrat, salaire) + synthèse du dossier. */
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'

const props = defineProps({ salarieId: { type: [Number, String], required: true } })
const frise = ref([])
const dossier = ref(null)
const erreur = ref('')
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const dateFr = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('fr-FR') : '')
const MOIS = ['', 'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const CONGE = { demande: 'Demandé', approuve: 'Approuvé', refuse: 'Refusé', annule: 'Annulé' }

function texte(l) {
  if (l.nature === 'embauche') return 'Embauche'
  if (l.nature === 'sortie') return `Départ${l.motif ? ` — ${l.motif}` : ''}`
  if (l.avant && l.apres) return `${l.avant} → ${l.apres}`
  return l.apres || l.avant || ''
}
onMounted(async () => {
  try {
    frise.value = (await apiClient.get(`/salaries/${props.salarieId}/historique`)).data
    dossier.value = (await apiClient.get(`/salaries/${props.salarieId}/dossier`)).data
  } catch (e) { erreur.value = messageErreur(e) }
})
</script>

<template>
  <div class="pile">
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <section class="card bloc">
      <h2>Historique des mutations</h2>
      <p class="aide">Changements de service, de section, d'emploi, de catégorie, de site, de contrat ou de salaire, du plus récent au plus ancien.</p>
      <ol v-if="frise.length" class="frise">
        <li v-for="(l, i) in frise" :key="i">
          <span class="date">{{ dateFr(l.date) }}</span>
          <span class="nature">{{ l.libelle }}</span>
          <span class="detail">{{ texte(l) }}<em v-if="l.motif && l.nature !== 'sortie'"> — {{ l.motif }}</em></span>
          <span v-if="l.par" class="par">{{ l.par }}</span>
        </li>
      </ol>
      <p v-else class="aide">Aucun mouvement enregistré.</p>
    </section>

    <section v-if="dossier?.bulletins" class="card bloc">
      <h2>Bulletins validés</h2>
      <p v-if="!dossier.bulletins.length" class="aide">Aucun bulletin validé.</p>
      <div v-else class="defile"><table class="t"><thead><tr><th>Période</th><th class="num">Total imposable</th><th class="num">Net à payer</th></tr></thead>
        <tbody><tr v-for="b in dossier.bulletins" :key="b.id"><td>{{ b.libelle }}</td><td class="num">{{ fmt(b.total_imposable) }}</td><td class="num">{{ fmt(b.net_a_payer) }}</td></tr></tbody></table></div>
    </section>

    <section v-if="dossier?.conges" class="card bloc">
      <h2>Congés <small v-if="dossier.conges.solde" class="aide">— solde : {{ dossier.conges.solde.solde ?? '' }} jour(s)</small></h2>
      <p v-if="!dossier.conges.elements.length" class="aide">Aucune absence enregistrée.</p>
      <div v-else class="defile"><table class="t"><thead><tr><th>Du</th><th>Au</th><th>Type</th><th class="num">Jours</th><th>Statut</th></tr></thead>
        <tbody><tr v-for="c in dossier.conges.elements" :key="c.id"><td>{{ dateFr(c.debut) }}</td><td>{{ dateFr(c.fin) }}</td><td>{{ c.type_conge }}</td><td class="num">{{ c.jours_ouvrables }}</td><td>{{ CONGE[c.statut] || c.statut }}</td></tr></tbody></table></div>
    </section>

    <section v-if="dossier?.prets" class="card bloc">
      <h2>Prêts et avances</h2>
      <p v-if="!dossier.prets.length" class="aide">Aucun prêt.</p>
      <div v-else class="defile"><table class="t"><thead><tr><th>Libellé</th><th class="num">Montant</th><th class="num">Remboursé</th><th class="num">Reste dû</th><th>Statut</th></tr></thead>
        <tbody><tr v-for="p in dossier.prets" :key="p.id"><td>{{ p.libelle }}</td><td class="num">{{ fmt(p.montant) }}</td><td class="num">{{ fmt(p.regle) }}</td><td class="num">{{ fmt(p.reste) }}</td><td>{{ p.statut }}</td></tr></tbody></table></div>
    </section>

    <section v-if="dossier?.sanctions" class="card bloc">
      <h2>Dossier disciplinaire</h2>
      <p v-if="!dossier.sanctions.length" class="aide">Aucune mesure.</p>
      <div v-else class="defile"><table class="t"><thead><tr><th>Date</th><th>Référence</th><th>Mesure</th><th>Motif</th></tr></thead>
        <tbody><tr v-for="m in dossier.sanctions" :key="m.id"><td>{{ dateFr(m.date_decision) }}</td><td>{{ m.reference }}</td><td>{{ m.type_mesure }}</td><td>{{ m.motif }}</td></tr></tbody></table></div>
    </section>
  </div>
</template>

<style scoped>
.pile { display: flex; flex-direction: column; gap: var(--space-4); }
.bloc { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); border: 1px solid var(--color-border); min-width: 0; }
h2 { margin: 0; font-size: var(--font-size-base); }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.frise { list-style: none; margin: 0; padding: 0 0 0 14px; border-left: 2px solid var(--color-border); display: flex; flex-direction: column; gap: 10px; }
.frise li { display: grid; grid-template-columns: 92px 150px 1fr auto; gap: 10px; align-items: baseline; font-size: var(--font-size-sm); position: relative; }
.frise li::before { content: ''; position: absolute; left: -20px; top: 7px; width: 10px; height: 10px; border-radius: 50%; background: var(--color-brand); }
.date { color: var(--color-text-muted); font-variant-numeric: tabular-nums; } .nature { font-weight: 600; } .par { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.detail em { color: var(--color-text-muted); }
.defile { overflow-x: auto; }
.t { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.t th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.t td { padding: 7px 10px; border-bottom: 1px solid var(--color-border); }
.t th.num, .t td.num { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 760px) { .frise li { grid-template-columns: 1fr; gap: 0; } }
</style>
