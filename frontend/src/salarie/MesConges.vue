<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Send, X } from 'lucide-vue-next'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const donnees = ref(null)
const erreur = ref('')
const message = ref('')
const demain = new Date(Date.now() + 86400000).toLocaleDateString('sv-SE')
const form = ref({ type_conge: 'annuel', debut: '', fin: '', motif: '' })
const TYPES = { annuel: 'Congé annuel', exceptionnel: 'Événement familial (permission exceptionnelle)', maladie: 'Maladie', sans_solde: 'Sans solde' }
const TYPES_COURT = { annuel: 'Congé annuel', exceptionnel: 'Événement familial', maladie: 'Maladie', maternite: 'Maternité', sans_solde: 'Sans solde' }
// « Mes demandes » : filtre par état et affichage progressif, pour rester lisible avec beaucoup de demandes.
const FILTRES = { toutes: 'Toutes', en_cours: 'En attente', approuve: 'Approuvées', autres: 'Refusées / annulées' }
const filtre = ref('toutes')
const affichees = ref(5)
const filtrees = computed(() => {
  const l = donnees.value?.demandes || []
  if (filtre.value === 'en_cours') return l.filter((c) => c.statut === 'demande')
  if (filtre.value === 'approuve') return l.filter((c) => c.statut === 'approuve')
  if (filtre.value === 'autres') return l.filter((c) => ['refuse', 'annule'].includes(c.statut))
  return l
})
const compte = (f) => (donnees.value?.demandes || []).filter((c) => (f === 'en_cours' ? c.statut === 'demande' : f === 'approuve' ? c.statut === 'approuve' : f === 'autres' ? ['refuse', 'annule'].includes(c.statut) : true)).length
const CLASSE = { demande: 'badge-attente', approuve: 'badge-ok', refuse: 'badge-erreur', annule: '' }
function choisir(f) { filtre.value = f; affichees.value = 5 }
const LIB = { demande: 'En attente', approuve: 'Approuvé', refuse: 'Refusé', annule: 'Annulé' }
const dateFr = (d) => d.split('-').reverse().join('/')

async function charger() { try { donnees.value = (await apiClient.get('/moi/conges')).data } catch (e) { erreur.value = messageErreur(e) } }
async function demander() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.post('/moi/conges', { ...form.value, motif: form.value.motif || null })
    message.value = `Demande envoyée (${data.jours_ouvrables} jour(s) ouvrable(s)). Elle sera traitée par le service Paie.`
    form.value = { type_conge: 'annuel', debut: '', fin: '', motif: '' }
    await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function retirer(c) {
  if (!(await confirm({ title: 'Annuler cette demande', message: `Votre demande du ${dateFr(c.debut)} au ${dateFr(c.fin)} sera retirée.`, danger: true, confirmLabel: 'Annuler la demande', cancelLabel: 'Conserver' }))) return
  try { await apiClient.delete(`/moi/conges/${c.id}`); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div>
    <h1>Mes congés</h1>
    <p v-if="message" class="ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <template v-if="donnees">
      <div class="card solde"><span>Solde de congés annuels</span><strong>{{ donnees.solde.solde }} jours ouvrables</strong></div>
      <form class="card form" @submit.prevent="demander">
        <h2>Nouvelle demande</h2>
        <label class="field"><span class="field-label">Type</span>
          <select v-model="form.type_conge" class="input"><option v-for="(l, k) in TYPES" :key="k" :value="k">{{ l }}</option></select></label>
        <div class="deux">
          <label class="field"><span class="field-label">Du</span><input v-model="form.debut" type="date" class="input" :min="demain" required /></label>
          <label class="field"><span class="field-label">Au</span><input v-model="form.fin" type="date" class="input" :min="form.debut || demain" required /></label>
        </div>
        <label class="field"><span class="field-label">Motif (facultatif)</span><input v-model="form.motif" class="input" maxlength="200" /></label>
        <button class="vbtn vbtn-primary" type="submit" data-hint="Envoyer la demande au service Paie"><Send :size="16" />Envoyer la demande</button>
      </form>
      <h2>Mes demandes</h2>
      <div class="puces" role="group" aria-label="Filtrer mes demandes">
        <button v-for="(l, k) in FILTRES" :key="k" type="button" :class="['puce', { active: filtre === k }]" @click="choisir(k)">{{ l }} <b>{{ compte(k) }}</b></button>
      </div>
      <p v-if="!filtrees.length" class="vide">{{ donnees.demandes.length ? 'Aucune demande dans cette catégorie.' : 'Aucune demande.' }}</p>
      <ul class="liste">
        <li v-for="c in filtrees.slice(0, affichees)" :key="c.id" class="card carte">
          <div class="corps-carte">
            <strong>{{ dateFr(c.debut) }} → {{ dateFr(c.fin) }}</strong>
            <small>{{ TYPES_COURT[c.type_conge] }} · {{ c.jours_ouvrables }} j ouvrable(s)</small>
          </div>
          <div class="droite">
            <span :class="['badge', CLASSE[c.statut]]">{{ LIB[c.statut] }}</span>
            <button v-if="c.statut === 'demande'" class="retirer" :data-hint="`Annuler ma demande du ${dateFr(c.debut)}`" @click="retirer(c)"><X :size="14" />Annuler</button>
          </div>
        </li>
      </ul>
      <button v-if="filtrees.length > affichees" class="vbtn vbtn-secondary plus" @click="affichees += 5">Voir plus ({{ filtrees.length - affichees }} restante(s))</button>
    </template>
  </div>
</template>

<style scoped>
h1 { font-size: var(--font-size-lg); margin: 0 0 var(--space-3); } h2 { font-size: var(--font-size-base); margin: var(--space-4) 0 var(--space-2); }
.solde { padding: var(--space-4); display: flex; flex-direction: column; gap: 4px; margin-bottom: var(--space-3); } .solde span { color: var(--color-text-muted); font-size: var(--font-size-sm); } .solde strong { font-size: var(--font-size-xl); }
.form { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); } .form h2 { margin: 0; }
.deux { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-3); }
.deux .input { min-width: 0; }
.liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.carte { padding: var(--space-3) var(--space-4); display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; } .droite { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.retirer { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--color-rouge); background: var(--color-surface); color: var(--color-rouge); cursor: pointer; border-radius: 8px; padding: 0 10px; min-height: 36px; font-size: var(--font-size-xs); font-weight: 600; }
.retirer:hover { background: var(--color-rouge-bg); }
.puces { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: var(--space-3); }
.puce { border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 999px; padding: 6px 12px; min-height: 36px; font-size: var(--font-size-xs); cursor: pointer; color: var(--color-text-muted); }
.puce b { margin-left: 3px; }
.puce.active { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.corps-carte { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.corps-carte small { color: var(--color-text-muted); }
.plus { width: 100%; margin-top: var(--space-3); }
.vide { color: var(--color-text-muted); } .ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); }
</style>
