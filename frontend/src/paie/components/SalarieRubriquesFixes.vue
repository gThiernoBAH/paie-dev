<script setup>
/** Rubriques fixes : gains ou retenues récurrents ajoutés chaque mois au bulletin (prime d'ancienneté convenue, retenue mutuelle…). */
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus, CircleOff } from 'lucide-vue-next'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const props = defineProps({ salarieId: { type: [Number, String], required: true }, peutModifier: Boolean })
const { confirm } = useConfirm()
const lignes = ref([])
const rubriques = ref([])
const erreur = ref('')
const vide = () => ({ code: '', montant: '', date_debut: new Date().toLocaleDateString('sv-SE'), date_fin: '', commentaire: '' })
const n = ref(vide())
const fmt = (v) => Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const dateFr = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('fr-FR') : '')
const TYPES = { GI: 'Gain imposable', GN: 'Gain non imposable', RI: 'Retenue imposable', RN: 'Retenue non imposable' }

async function charger() {
  try {
    lignes.value = (await apiClient.get(`/salaries/${props.salarieId}/rubriques-fixes`)).data
    if (props.peutModifier && !rubriques.value.length) {
      const r = await apiClient.get('/rubriques').catch(() => ({ data: [] }))
      rubriques.value = (r.data.elements || r.data || []).filter((x) => x.est_actif !== false)
    }
  } catch (e) { erreur.value = messageErreur(e) }
}
async function ajouter() {
  erreur.value = ''
  try {
    await apiClient.post(`/salaries/${props.salarieId}/rubriques-fixes`, { ...n.value, montant: Number(String(n.value.montant).replace(',', '.')), date_fin: n.value.date_fin || null, commentaire: n.value.commentaire || null })
    n.value = vide(); await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function arreter(f) {
  if (!(await confirm({ title: 'Arrêter cette rubrique', message: `${f.libelle} ne sera plus ajoutée aux prochains bulletins. Les bulletins déjà validés ne changent pas.`, confirmLabel: 'Arrêter' }))) return
  try { await apiClient.delete(`/salaries/${props.salarieId}/rubriques-fixes/${f.id}`); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <section class="card bloc">
    <h2>Rubriques fixes</h2>
    <p class="aide">Montants récurrents ajoutés automatiquement à chaque bulletin mensuel pendant leur période de validité (prime convenue, retenue mutuelle…). Les avantages doivent figurer ici : ils sont ainsi déclarés sur le bulletin.</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <div class="defile">
      <table v-if="lignes.length" class="t"><thead><tr><th>Rubrique</th><th>Nature</th><th class="num">Montant</th><th>Du</th><th>Au</th><th>État</th><th class="act"></th></tr></thead>
        <tbody><tr v-for="f in lignes" :key="f.id" :class="{ off: !f.est_actif }">
          <td>{{ f.code }} — {{ f.libelle }}<small v-if="f.commentaire" class="aide"> · {{ f.commentaire }}</small></td><td>{{ TYPES[f.type] }}</td><td class="num">{{ fmt(f.montant) }}</td>
          <td>{{ dateFr(f.date_debut) }}</td><td>{{ dateFr(f.date_fin) || '—' }}</td><td>{{ f.est_actif ? 'Active' : 'Arrêtée' }}</td>
          <td class="act"><BoutonIcone v-if="peutModifier && f.est_actif" class="ecriture" danger :icone="CircleOff" hint="Arrêter cette rubrique fixe" @click="arreter(f)" /></td></tr></tbody></table>
      <p v-else class="aide">Aucune rubrique fixe.</p>
    </div>
    <form v-if="peutModifier" class="ligne ecriture" @submit.prevent="ajouter">
      <select v-model="n.code" class="input" required aria-label="Rubrique"><option value="" disabled>Rubrique…</option>
        <option v-for="r in rubriques" :key="r.code" :value="r.code">{{ r.code }} — {{ r.libelle }}</option></select>
      <input v-model="n.montant" class="input" inputmode="decimal" placeholder="Montant (FCFA)" required aria-label="Montant" />
      <input v-model="n.date_debut" class="input" type="date" required aria-label="À partir du" data-hint="À partir du" />
      <input v-model="n.date_fin" class="input" type="date" aria-label="Jusqu'au (facultatif)" data-hint="Jusqu'au (facultatif)" />
      <input v-model="n.commentaire" class="input" placeholder="Commentaire" aria-label="Commentaire" />
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
.t th.num, .t td.num { text-align: right; font-variant-numeric: tabular-nums; }
.off { opacity: .55; }
.act { width: 1%; text-align: center; }
.ligne { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
.ligne .input { flex: 1; min-width: 130px; }
</style>
