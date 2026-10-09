<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Calculator, Save } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'

const campagnes = ref([])
const cid = ref('')
const lignes = ref([])
const campagne = ref(null)
const erreur = ref('')
const message = ref('')
const services = ref([])
const prop = ref({ mode: 'pourcentage_salaire', valeur: '', service_id: '' })
const modifie = ref(false)

const fmt = (n) => (n === null || n === undefined || n === '' ? '' : Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 }))
const colonnes = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'service', libelle: 'Service', tri: true },
  { cle: 'montant', libelle: 'Gratification (FCFA)', tri: true, align: 'droite', valeur: (l) => Number(l.montant || 0), texte: (l) => fmt(l.montant) },
]
const verrouille = computed(() => !campagne.value || ['validee', 'cloturee'].includes(campagne.value.statut))
const total = computed(() => lignes.value.reduce((t, l) => t + (Number(l.montant) || 0), 0))

async function init() {
  try {
    campagnes.value = (await apiClient.get('/campagnes')).data.filter((c) => !['validee', 'cloturee'].includes(c.statut))
    services.value = (await apiClient.get('/referentiels', { params: { type_ref: 'service' } })).data.filter((r) => r.est_actif)
    if (campagnes.value.length) cid.value = campagnes.value[0].id
  } catch (e) { erreur.value = messageErreur(e) }
}
async function charger() {
  if (!cid.value) { lignes.value = []; return }
  try { const { data } = await apiClient.get(`/campagnes/${cid.value}/gratifications`); campagne.value = data.campagne; lignes.value = data.salaries; modifie.value = false } catch (e) { erreur.value = messageErreur(e) }
}
async function proposer() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.post(`/campagnes/${cid.value}/gratifications/proposer`, { mode: prop.value.mode, valeur: prop.value.valeur, service_id: prop.value.service_id || null })
    for (const l of lignes.value) if (data.montants[l.salarie_id] !== undefined) l.montant = data.montants[l.salarie_id]
    modifie.value = true
    message.value = `Montants proposés pour ${Object.keys(data.montants).length} salarié(s). Ajustez si besoin puis enregistrez.` + (data.sans_salaire.length ? ` Sans salaire en vigueur : ${data.sans_salaire.join(', ')}.` : '')
  } catch (e) { erreur.value = messageErreur(e) }
}
async function enregistrer() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.put(`/campagnes/${cid.value}/gratifications`, { lignes: lignes.value.map((l) => ({ salarie_id: l.salarie_id, montant: l.montant === '' || l.montant === null ? null : l.montant })) })
    message.value = `${data.enregistrees} gratification(s) enregistrée(s) — total ${fmt(data.total)} FCFA. Relancez le calcul de la campagne pour les voir sur les bulletins.`
    await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}
watch(cid, charger)
onMounted(init)
</script>

<template>
  <div class="page">
    <header>
      <h1>Gratifications</h1>
      <p class="sous-titre">Saisie groupée de la rubrique « Gratification » (GRT) pour les salariés d'une campagne non validée. Proposez un montant fixe ou un pourcentage du salaire, ajustez ligne par ligne, puis enregistrez. Un montant vide supprime la gratification du salarié.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <section class="card saisie">
      <div class="grille">
        <label class="field large"><span class="field-label">Campagne</span>
          <select v-model="cid" class="input"><option v-for="c in campagnes" :key="c.id" :value="c.id">{{ c.libelle }}</option></select></label>
        <template v-if="!verrouille">
          <label class="field"><span class="field-label">Mode</span>
            <select v-model="prop.mode" class="input"><option value="pourcentage_salaire">% du salaire</option><option value="fixe">Montant fixe</option></select></label>
          <label class="field"><span class="field-label">{{ prop.mode === 'fixe' ? 'Montant (FCFA)' : 'Pourcentage' }}</span><input v-model="prop.valeur" type="number" min="0" step="any" class="input" /></label>
          <label class="field"><span class="field-label">Service</span>
            <select v-model="prop.service_id" class="input"><option value="">Tous</option><option v-for="s in services" :key="s.id" :value="s.id">{{ s.libelle }}</option></select></label>
          <div class="field valider"><button class="vbtn vbtn-secondary" type="button" :disabled="!prop.valeur" data-hint="Remplir le tableau avec les montants calculés (rien n'est enregistré)" @click="proposer"><Calculator :size="16" />Proposer</button></div>
        </template>
      </div>
    </section>
    <DataTable :colonnes="colonnes" :lignes="lignes" cle-ligne="salarie_id" vide="Aucun salarié dans cette campagne." placeholder-recherche="Rechercher un salarié">
      <template #cell-montant="{ ligne }">
        <input v-if="!verrouille" v-model="ligne.montant" type="number" min="0" step="any" class="input saisie-montant" :aria-label="'Gratification de ' + ligne.nom" @input="modifie = true" />
        <span v-else>{{ fmt(ligne.montant) }}</span>
      </template>
    </DataTable>
    <div v-if="!verrouille" class="barre ecriture">
      <strong>Total : {{ fmt(total) }} FCFA</strong>
      <button class="vbtn vbtn-primary" :disabled="!modifie" data-hint="Enregistrer les gratifications dans la campagne" @click="enregistrer"><Save :size="16" />Enregistrer</button>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.saisie { padding: var(--space-4) var(--space-6); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: 1 / -1; }
.saisie-montant { width: 150px; text-align: right; min-height: 34px; padding: 4px 8px; }
.barre { display: flex; justify-content: flex-end; align-items: center; gap: var(--space-4); }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
