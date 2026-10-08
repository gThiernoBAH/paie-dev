<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Send, X } from 'lucide-vue-next'

const donnees = ref(null)
const erreur = ref('')
const message = ref('')
const demain = new Date(Date.now() + 86400000).toLocaleDateString('sv-SE')
const form = ref({ type_conge: 'annuel', debut: '', fin: '', motif: '' })
const TYPES = { annuel: 'Congé annuel', maladie: 'Maladie', exceptionnel: 'Événement familial', sans_solde: 'Sans solde' }
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
  if (!window.confirm('Retirer cette demande ?')) return
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
        <button class="vbtn vbtn-primary" type="submit"><Send :size="16" />Envoyer la demande</button>
      </form>
      <h2>Mes demandes</h2>
      <p v-if="!donnees.demandes.length" class="vide">Aucune demande.</p>
      <ul class="liste">
        <li v-for="c in donnees.demandes" :key="c.id" class="card carte">
          <div><strong>{{ dateFr(c.debut) }} → {{ dateFr(c.fin) }}</strong><br /><small>{{ TYPES[c.type_conge] }} · {{ c.jours_ouvrables }} j ouvrable(s)</small></div>
          <div class="droite"><span class="badge">{{ LIB[c.statut] }}</span>
            <button v-if="c.statut === 'demande'" class="retirer" :aria-label="`Retirer la demande du ${dateFr(c.debut)}`" @click="retirer(c)"><X :size="16" /></button></div>
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
h1 { font-size: var(--font-size-lg); margin: 0 0 var(--space-3); } h2 { font-size: var(--font-size-base); margin: var(--space-4) 0 var(--space-2); }
.solde { padding: var(--space-4); display: flex; flex-direction: column; gap: 4px; margin-bottom: var(--space-3); } .solde span { color: var(--color-text-muted); font-size: var(--font-size-sm); } .solde strong { font-size: var(--font-size-xl); }
.form { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); } .form h2 { margin: 0; }
.deux { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.carte { padding: var(--space-3) var(--space-4); display: flex; justify-content: space-between; align-items: center; gap: 8px; } .droite { display: flex; gap: 6px; align-items: center; }
.retirer { border: none; background: none; color: var(--color-rouge); cursor: pointer; width: 36px; height: 36px; }
.vide { color: var(--color-text-muted); } .ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); }
</style>
