<script setup>
/** Personnes à charge (enfants, conjoint) : le compteur « enfants » de la fiche suit ce détail. */
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus, Trash2 } from 'lucide-vue-next'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const props = defineProps({ salarieId: { type: [Number, String], required: true }, peutModifier: Boolean })
const emit = defineEmits(['change'])
const { confirm } = useConfirm()
const data = ref({ elements: [], nombre_enfants: 0, parts_actuelles: 0, parts_suggerees: 0 })
const erreur = ref('')
const vide = () => ({ lien: 'enfant', nom: '', prenoms: '', sexe: '', date_naissance: '', a_charge: true, scolarise: false })
const n = ref(vide())
const dateFr = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('fr-FR') : '—')

async function charger() { try { data.value = (await apiClient.get(`/salaries/${props.salarieId}/enfants`)).data } catch (e) { erreur.value = messageErreur(e) } }
async function ajouter() {
  erreur.value = ''
  try {
    const c = { ...n.value, prenoms: n.value.prenoms || null, sexe: n.value.sexe || null, date_naissance: n.value.date_naissance || null }
    data.value = (await apiClient.post(`/salaries/${props.salarieId}/enfants`, c)).data
    n.value = vide(); emit('change')
  } catch (e) { erreur.value = messageErreur(e) }
}
async function basculer(e, champ) {
  try { data.value = (await apiClient.patch(`/salaries/${props.salarieId}/enfants/${e.id}`, { [champ]: !e[champ] })).data; emit('change') } catch (x) { erreur.value = messageErreur(x) }
}
async function supprimer(e) {
  if (!(await confirm({ title: 'Retirer cette personne', message: `${e.nom} ${e.prenoms || ''} sera retiré(e) des personnes à charge.`, danger: true, confirmLabel: 'Retirer' }))) return
  try { data.value = (await apiClient.delete(`/salaries/${props.salarieId}/enfants/${e.id}`)).data; emit('change') } catch (x) { erreur.value = messageErreur(x) }
}
onMounted(charger)
</script>

<template>
  <section class="card bloc">
    <h2>Personnes à charge</h2>
    <p class="aide">Enfants à charge comptés : <strong>{{ data.nombre_enfants }}</strong> · Parts ITS actuelles : <strong>{{ data.parts_actuelles }}</strong>
      <span v-if="data.parts_suggerees !== data.parts_actuelles"> — suggestion d'après la situation : <strong>{{ data.parts_suggerees }}</strong> (à reporter à la main dans la fiche, rien n'est modifié automatiquement).</span></p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <div class="defile">
      <table v-if="data.elements.length" class="t"><thead><tr><th>Lien</th><th>Nom</th><th>Naissance</th><th>Âge</th><th>À charge</th><th>Scolarisé</th><th class="act"></th></tr></thead>
        <tbody><tr v-for="e in data.elements" :key="e.id">
          <td>{{ e.lien === 'conjoint' ? 'Conjoint' : 'Enfant' }}</td><td>{{ e.nom }} {{ e.prenoms }}</td><td>{{ dateFr(e.date_naissance) }}</td><td>{{ e.age ?? '—' }}</td>
          <td><input type="checkbox" :checked="e.a_charge" :disabled="!peutModifier" :aria-label="`${e.nom} à charge`" @change="basculer(e, 'a_charge')" /></td>
          <td><input type="checkbox" :checked="e.scolarise" :disabled="!peutModifier" :aria-label="`${e.nom} scolarisé`" @change="basculer(e, 'scolarise')" /></td>
          <td class="act"><BoutonIcone v-if="peutModifier" class="ecriture" danger :icone="Trash2" hint="Retirer cette personne" @click="supprimer(e)" /></td></tr></tbody></table>
      <p v-else class="aide">Aucune personne enregistrée.</p>
    </div>
    <form v-if="peutModifier" class="ligne ecriture" @submit.prevent="ajouter">
      <select v-model="n.lien" class="input" aria-label="Lien"><option value="enfant">Enfant</option><option value="conjoint">Conjoint</option></select>
      <input v-model="n.nom" class="input" placeholder="Nom" required aria-label="Nom" />
      <input v-model="n.prenoms" class="input" placeholder="Prénoms" aria-label="Prénoms" />
      <select v-model="n.sexe" class="input" aria-label="Sexe"><option value="">Sexe</option><option value="M">M</option><option value="F">F</option></select>
      <input v-model="n.date_naissance" class="input" type="date" aria-label="Date de naissance" />
      <label class="case"><input v-model="n.scolarise" type="checkbox" /> Scolarisé</label>
      <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button>
    </form>
  </section>
</template>

<style scoped>
.bloc { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); border: 1px solid var(--color-border); min-width: 0; }
h2 { margin: 0; font-size: var(--font-size-base); }
.aide { font-size: var(--font-size-sm); color: var(--color-text-muted); margin: 0; }
.defile { overflow-x: auto; }
.t { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.t th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.t td { padding: 7px 10px; border-bottom: 1px solid var(--color-border); }
.act { width: 1%; text-align: center; }
.ligne { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
.ligne .input { flex: 1; min-width: 120px; }
.case { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-sm); }
</style>
