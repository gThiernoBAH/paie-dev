<script setup>
/** Augmentations de salaire en masse : définir → aperçu (rien n'est écrit) → appliquer ; chaque lot peut être annulé tant qu'aucune paie validée ne le couvre. */
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Eye, Check, Undo2 } from 'lucide-vue-next'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()
const refs = ref({})
const lots = ref([])
const apercu = ref(null)
const erreur = ref('')
const message = ref('')
const enCours = ref(false)
const f = ref({ libelle: '', service_id: '', section_id: '', emploi_id: '', categorie_id: '', type_contrat_id: '', type_remuneration: '', mode: 'pourcentage', valeur: '', cible: 'salaire', date_effet: new Date().toLocaleDateString('sv-SE'), arrondi: 1 })
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const dateFr = (d) => new Date(`${d}T00:00:00`).toLocaleDateString('fr-FR')
const CIBLES = { salaire: 'Salaire catégoriel', sursalaire: 'Sursalaire', les_deux: 'Les deux (pourcentage seulement)' }

const corps = computed(() => {
  const filtres = {}
  for (const k of ['service_id', 'section_id', 'emploi_id', 'categorie_id', 'type_contrat_id']) if (f.value[k]) filtres[k] = Number(f.value[k])
  if (f.value.type_remuneration) filtres.type_remuneration = f.value.type_remuneration
  return { libelle: f.value.libelle.trim(), filtres, mode: f.value.mode, valeur: Number(String(f.value.valeur).replace(',', '.')), cible: f.value.cible, date_effet: f.value.date_effet, arrondi: Number(f.value.arrondi) }
})
const modifie = () => { apercu.value = null; message.value = '' }

async function charger() {
  try {
    const { data } = await apiClient.get('/referentiels')
    const r = {}
    for (const x of data) (r[x.type_ref] ||= []).push(x)
    refs.value = r
    lots.value = (await apiClient.get('/augmentations')).data
  } catch (e) { erreur.value = messageErreur(e) }
}
async function voir() {
  erreur.value = ''; message.value = ''; apercu.value = null; enCours.value = true
  try { apercu.value = (await apiClient.post('/augmentations/apercu', corps.value)).data } catch (e) { erreur.value = messageErreur(e) } finally { enCours.value = false }
}
async function appliquer() {
  if (!f.value.libelle.trim() || f.value.libelle.trim().length < 3) { erreur.value = 'Donnez un libellé au lot (3 caractères minimum).'; return }
  if (!(await confirm({ title: 'Appliquer l\'augmentation', message: `${apercu.value.nombre} salarié(s) seront augmentés à partir du ${dateFr(f.value.date_effet)} : +${fmt(apercu.value.total_mensuel)} FCFA par mois (${fmt(apercu.value.total_annuel)} par an). Le lot reste annulable tant qu'aucune paie validée ne le couvre.`, confirmLabel: 'Appliquer' }))) return
  erreur.value = ''; enCours.value = true
  try {
    const l = (await apiClient.post('/augmentations', corps.value)).data
    message.value = `Lot « ${l.libelle} » appliqué à ${l.nb_salaries} salarié(s).`
    apercu.value = null; f.value.libelle = ''; await charger()
  } catch (e) { erreur.value = messageErreur(e) } finally { enCours.value = false }
}
async function annuler(l) {
  if (!(await confirm({ title: 'Annuler ce lot', message: `Les nouveaux salaires du lot « ${l.libelle} » seront supprimés ; chaque salarié retrouve son salaire précédent.`, danger: true, confirmLabel: 'Annuler le lot', cancelLabel: 'Conserver' }))) return
  erreur.value = ''
  try { await apiClient.post(`/augmentations/${l.id}/annuler`); message.value = 'Lot annulé.'; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Augmentations en masse</h1>
      <p class="sous-titre">Applique une augmentation (pourcentage ou montant fixe) à un groupe de salariés en activité. L'aperçu ne modifie rien ; l'historique des salaires est conservé et chaque lot est annulable.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form class="card saisie ecriture" @submit.prevent="voir" @input="modifie" @change="modifie">
      <h2>Définir l'augmentation</h2>
      <div class="grille">
        <label class="field large"><span class="field-label">Libellé du lot</span><input v-model="f.libelle" class="input" placeholder="Ex. Révision annuelle 2027" /></label>
        <label class="field"><span class="field-label">À partir du</span><input v-model="f.date_effet" type="date" class="input" required /></label>
        <label class="field"><span class="field-label">Mode</span><select v-model="f.mode" class="input"><option value="pourcentage">Pourcentage (%)</option><option value="montant">Montant fixe (FCFA)</option></select></label>
        <label class="field"><span class="field-label">{{ f.mode === 'pourcentage' ? 'Taux (%)' : 'Montant (FCFA)' }}</span><input v-model="f.valeur" class="input" inputmode="decimal" required /></label>
        <label class="field"><span class="field-label">Appliquer sur</span><select v-model="f.cible" class="input"><option v-for="(l, k) in CIBLES" :key="k" :value="k" :disabled="f.mode === 'montant' && k === 'les_deux'">{{ l }}</option></select></label>
        <label class="field"><span class="field-label">Arrondi au</span><select v-model="f.arrondi" class="input"><option v-for="a in [1, 5, 10, 50, 100]" :key="a" :value="a">{{ a }} F</option></select></label>
      </div>
      <h3>Salariés concernés <small>(vide = tous les salariés en activité)</small></h3>
      <div class="grille">
        <label class="field"><span class="field-label">Service</span><select v-model="f.service_id" class="input"><option value="">Tous</option><option v-for="r in refs.service" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Section</span><select v-model="f.section_id" class="input"><option value="">Toutes</option><option v-for="r in refs.section" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Emploi</span><select v-model="f.emploi_id" class="input"><option value="">Tous</option><option v-for="r in refs.emploi" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Catégorie</span><select v-model="f.categorie_id" class="input"><option value="">Toutes</option><option v-for="r in refs.categorie" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Contrat</span><select v-model="f.type_contrat_id" class="input"><option value="">Tous</option><option v-for="r in refs.type_contrat" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Rémunération</span><select v-model="f.type_remuneration" class="input"><option value="">Toutes</option><option value="mensuel">Mensuelle</option><option value="journalier">Journalière</option></select></label>
      </div>
      <div><button class="vbtn vbtn-primary" type="submit" :disabled="enCours"><Eye :size="16" />Voir l'aperçu</button></div>
    </form>

    <section v-if="apercu" class="card res">
      <h2>Aperçu <small>— rien n'est encore enregistré</small></h2>
      <p class="resume"><strong>{{ apercu.nombre }}</strong> salarié(s) · +<strong>{{ fmt(apercu.total_mensuel) }}</strong> FCFA / mois · +<strong>{{ fmt(apercu.total_annuel) }}</strong> FCFA / an</p>
      <div class="defile"><table class="t"><thead><tr><th>Matricule</th><th>Nom</th><th class="num">Salaire actuel</th><th class="num">Nouveau salaire</th><th class="num">Sursalaire actuel</th><th class="num">Nouveau sursalaire</th><th class="num">Écart</th></tr></thead>
        <tbody><tr v-for="l in apercu.lignes" :key="l.salarie_id"><td>{{ l.matricule }}</td><td>{{ l.nom }}</td><td class="num">{{ fmt(l.ancien_salaire) }}</td><td class="num">{{ fmt(l.nouveau_salaire) }}</td>
          <td class="num">{{ fmt(l.ancien_sursalaire) }}</td><td class="num">{{ fmt(l.nouveau_sursalaire) }}</td><td class="num">+{{ fmt(l.difference) }}</td></tr></tbody></table></div>
      <div v-if="apercu.ignores.length" class="ignores"><strong>{{ apercu.ignores.length }} salarié(s) ignoré(s)</strong>
        <ul><li v-for="i in apercu.ignores" :key="i.matricule">{{ i.matricule }} {{ i.nom }} — {{ i.motif }}</li></ul></div>
      <div v-if="apercu.nombre" class="ecriture"><button class="vbtn vbtn-primary" :disabled="enCours" @click="appliquer"><Check :size="16" />Appliquer l'augmentation</button></div>
    </section>

    <section class="card res">
      <h2>Lots appliqués</h2>
      <p v-if="!lots.length" class="aide">Aucune augmentation en masse pour l'instant.</p>
      <div v-else class="defile"><table class="t"><thead><tr><th>Lot</th><th>Effet</th><th>Règle</th><th class="num">Salariés</th><th class="num">+ / mois</th><th>Statut</th><th class="act"></th></tr></thead>
        <tbody><tr v-for="l in lots" :key="l.id" :class="{ off: l.statut !== 'applique' }">
          <td>{{ l.libelle }}<small class="aide"> · {{ l.cree_par }}</small></td><td>{{ dateFr(l.date_effet) }}</td>
          <td>{{ l.mode === 'pourcentage' ? `${l.valeur} %` : `${fmt(l.valeur)} F` }} · {{ CIBLES[l.cible] }}</td><td class="num">{{ l.nb_salaries }}</td><td class="num">{{ fmt(l.total_mensuel) }}</td>
          <td>{{ l.statut === 'applique' ? 'Appliqué' : 'Annulé' }}</td>
          <td class="act"><BoutonIcone v-if="l.statut === 'applique'" class="ecriture" danger :icone="Undo2" hint="Annuler ce lot : chaque salarié retrouve son salaire précédent" @click="annuler(l)" /></td></tr></tbody></table></div>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); max-width: 1200px; }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); } h2 small, h3 small { font-weight: 400; color: var(--color-text-muted); }
h3 { margin: var(--space-2) 0 0; font-size: var(--font-size-sm); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.saisie, .res { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); min-width: 0; }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); }
.grille .large { grid-column: span 2; }
.resume { margin: 0; font-size: var(--font-size-sm); }
.aide { font-size: var(--font-size-sm); color: var(--color-text-muted); margin: 0; }
.ignores { font-size: var(--font-size-sm); background: var(--color-orange-bg); color: var(--color-orange); padding: 10px 14px; border-radius: var(--radius-md); } .ignores ul { margin: 4px 0 0; padding-left: 20px; }
.defile { overflow-x: auto; }
.t { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.t th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.t td { padding: 6px 10px; border-bottom: 1px solid var(--color-border); }
.t th.num, .t td.num { text-align: right; font-variant-numeric: tabular-nums; }
.off { opacity: .55; } .act { width: 1%; text-align: center; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } .grille .large { grid-column: span 1; } }
</style>
