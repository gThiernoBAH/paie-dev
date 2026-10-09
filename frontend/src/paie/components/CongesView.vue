<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus, Check, X, Ban, Scale } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm, saisir } = useConfirm()
const onglet = ref('demandes')
const conges = ref([])
const soldes = ref([])
const erreur = ref('')
const message = ref('')
const filtre = ref('demande')
const filtreType = ref('')
const nouveau = ref({ matricule: '', type_conge: 'annuel', debut: '', fin: '', motif: '' })
const LIB = { demande: 'À traiter', approuve: 'Approuvé', refuse: 'Refusé', annule: 'Annulé' }
const CLASSE = { demande: 'badge-attente', approuve: 'badge-ok', refuse: 'badge-erreur', annule: '' }
// Libellé complet (formulaire, tableau) et libellé court (filtres).
const TYPES = {
  annuel: { libelle: 'Congé annuel', court: 'Congés annuels', aide: 'Congé payé, déduit du solde de congés.' },
  exceptionnel: { libelle: 'Permission exceptionnelle (événement familial…)', court: 'Permissions exceptionnelles', aide: 'Mariage, naissance, décès d\'un proche… accordé dans les limites de la convention collective.' },
  maladie: { libelle: 'Maladie', court: 'Maladies', aide: 'Absence pour maladie justifiée par un certificat médical.' },
  maternite: { libelle: 'Maternité', court: 'Maternités', aide: 'Congé de maternité.' },
  sans_solde: { libelle: 'Congé sans solde', court: 'Sans solde', aide: 'Absence non rémunérée ; la retenue suit les paramètres de paie.' },
}
const dateFr = (d) => d.split('-').reverse().join('/')

const compteurs = computed(() => {
  const c = { '': conges.value.length }
  for (const k of Object.keys(TYPES)) c[k] = conges.value.filter((x) => x.type_conge === k).length
  return c
})
const visibles = computed(() => (filtreType.value ? conges.value.filter((c) => c.type_conge === filtreType.value) : conges.value))
const colonnesDemandes = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'type_conge', libelle: 'Type d\'absence', tri: true, texte: (c) => TYPES[c.type_conge]?.libelle },
  { cle: 'debut', libelle: 'Du', tri: true, format: (v) => dateFr(v) },
  { cle: 'fin', libelle: 'Au', tri: true, format: (v) => dateFr(v) },
  { cle: 'jours_ouvrables', libelle: 'Jours ouvrables', tri: true, align: 'droite' },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (c) => LIB[c.statut] },
]
const colonnesSoldes = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'initial', libelle: 'Reprise', tri: true, align: 'droite' },
  { cle: 'acquis', libelle: 'Acquis', tri: true, align: 'droite' },
  { cle: 'pris', libelle: 'Pris', tri: true, align: 'droite' },
  { cle: 'solde', libelle: 'Solde', tri: true, align: 'droite' },
]

async function trouver(matricule) {
  const { data } = await apiClient.get('/salaries', { params: { recherche: matricule.trim(), statut: 'tous', taille: 5 } })
  const m = data.elements.find((s) => s.matricule === matricule.trim().padStart(6, '0'))
  if (!m) throw new Error('Matricule introuvable.')
  return m
}
async function charger() {
  try { conges.value = (await apiClient.get('/conges', { params: filtre.value ? { statut: filtre.value } : {} })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function chargerSoldes() {
  try { soldes.value = (await apiClient.get('/conges/soldes')).data } catch (e) { erreur.value = messageErreur(e) }
}
async function demander() {
  erreur.value = ''; message.value = ''
  try {
    const s = await trouver(nouveau.value.matricule)
    const { data } = await apiClient.post('/conges', { salarie_id: s.id, type_conge: nouveau.value.type_conge, debut: nouveau.value.debut, fin: nouveau.value.fin, motif: nouveau.value.motif || null })
    message.value = `Demande enregistrée : ${data.jours_ouvrables} jour(s) ouvrable(s).`
    nouveau.value = { matricule: '', type_conge: 'annuel', debut: '', fin: '', motif: '' }
    await charger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function decider(c, decision) {
  erreur.value = ''; message.value = ''
  if (decision === 'refuser' && !(await confirm({ title: 'Refuser la demande', message: `Refuser la demande de ${c.nom} (${dateFr(c.debut)} → ${dateFr(c.fin)}) ?`, danger: true, confirmLabel: 'Refuser' }))) return
  if (decision === 'annuler' && !(await confirm({ title: 'Annuler un congé approuvé', message: `Le congé de ${c.nom} sera annulé et les jours reviendront dans son solde.`, danger: true, confirmLabel: 'Annuler le congé', cancelLabel: 'Conserver' }))) return
  try { await apiClient.post(`/conges/${c.id}/decision`, { decision }); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function definirSolde(s) {
  const v = await saisir({
    title: `Reprendre le solde de ${s.nom}`,
    message: 'À la mise en route : indiquez le solde connu à une date donnée ; les droits s\'accumulent ensuite.',
    confirmLabel: 'Enregistrer',
    champs: [
      { cle: 'solde', label: 'Solde (jours ouvrables)', type: 'text', obligatoire: true, valeur: String(s.initial ?? '') },
      { cle: 'date', label: 'À la date du', type: 'date', obligatoire: true, valeur: new Date().toLocaleDateString('sv-SE') },
    ],
  })
  if (!v) return
  try { await apiClient.put(`/salaries/${s.salarie_id}/solde-conges`, { solde_initial: String(v.solde).replace(',', '.'), date_reference: v.date }); await chargerSoldes() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(() => { charger(); chargerSoldes() })
</script>

<template>
  <div class="page">
    <header>
      <h1>Congés et absences</h1>
      <p class="sous-titre">Demandes de congé, permissions exceptionnelles (événements familiaux), maladies et autres absences : approbation et soldes. Le solde acquis suit le paramètre « jours ouvrables acquis par mois » (Paramétrage → Congés).</p>
    </header>
    <div class="onglets" role="tablist">
      <button v-for="(lib, cle) in { demandes: 'Demandes', soldes: 'Soldes de congés' }" :key="cle" role="tab" :class="['onglet', { actif: onglet === cle }]" @click="onglet = cle">{{ lib }}</button>
    </div>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <section v-if="onglet === 'demandes'" class="bloc">
      <form class="card saisie ecriture" @submit.prevent="demander">
        <h2>Nouvelle demande</h2>
        <div class="grille">
          <label class="field"><span class="field-label">Matricule</span><input v-model="nouveau.matricule" class="input" placeholder="000054" required inputmode="numeric" /></label>
          <label class="field large"><span class="field-label">Type d'absence</span><select v-model="nouveau.type_conge" class="input"><option v-for="(t, k) in TYPES" :key="k" :value="k">{{ t.libelle }}</option></select></label>
          <label class="field"><span class="field-label">Du</span><input v-model="nouveau.debut" type="date" class="input" required /></label>
          <label class="field"><span class="field-label">Au</span><input v-model="nouveau.fin" type="date" class="input" required /></label>
          <label class="field large"><span class="field-label">Motif (facultatif)</span><input v-model="nouveau.motif" class="input" /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Enregistrer la demande</button></div>
        </div>
      </form>

      <div class="filtres">
        <label class="field"><span class="field-label">Statut</span>
          <select v-model="filtre" class="input court" @change="charger"><option value="">Tous les statuts</option><option v-for="(l, k) in LIB" :key="k" :value="k">{{ l }}</option></select></label>
        <div class="puces" role="group" aria-label="Filtrer par type d'absence">
          <button type="button" :class="['puce', { active: filtreType === '' }]" @click="filtreType = ''">Tous les types <b>{{ compteurs[''] }}</b></button>
          <button v-for="(t, k) in TYPES" :key="k" type="button" :class="['puce', { active: filtreType === k }]" :data-hint="t.aide" @click="filtreType = k">{{ t.court }} <b>{{ compteurs[k] }}</b></button>
        </div>
      </div>

      <DataTable :colonnes="colonnesDemandes" :lignes="visibles" vide="Aucune demande." placeholder-recherche="Rechercher un matricule ou un nom">
        <template #cell-type_conge="{ ligne }"><span class="type" :class="`t-${ligne.type_conge}`">{{ TYPES[ligne.type_conge]?.court }}</span></template>
        <template #cell-statut="{ ligne }"><span :class="['badge', CLASSE[ligne.statut]]">{{ LIB[ligne.statut] }}</span></template>
        <template #actions="{ ligne }">
          <template v-if="ligne.statut === 'demande'">
            <BoutonIcone class="ecriture" :icone="Check" :hint="`Approuver : les jours sont déduits du solde de ${ligne.nom}`" @click="decider(ligne, 'approuver')" />
            <BoutonIcone class="ecriture" danger :icone="X" hint="Refuser cette demande (le salarié en est informé)" @click="decider(ligne, 'refuser')" />
          </template>
          <BoutonIcone v-else-if="ligne.statut === 'approuve'" class="ecriture" danger :icone="Ban" hint="Annuler ce congé déjà approuvé : les jours reviennent dans le solde" @click="decider(ligne, 'annuler')" />
        </template>
      </DataTable>
    </section>

    <section v-if="onglet === 'soldes'" class="bloc">
      <DataTable :colonnes="colonnesSoldes" :lignes="soldes" cle-ligne="salarie_id" vide="Aucun salarié." placeholder-recherche="Rechercher un matricule ou un nom">
        <template #cell-solde="{ ligne }"><strong>{{ ligne.solde }}</strong></template>
        <template #actions="{ ligne }">
          <BoutonIcone class="ecriture" :icone="Scale" hint="Reprendre un solde : à la mise en route, saisir le solde connu à une date donnée" @click="definirSolde(ligne)" />
        </template>
      </DataTable>
      <p class="aide">« Reprendre un solde » sert à la mise en route : le solde connu à une date donnée, les droits s'accumulant ensuite.</p>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); }
.onglet { padding: 10px 16px; min-height: 44px; border: none; background: none; cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.onglet.actif { color: var(--color-brand-dark); border-bottom-color: var(--color-brand); }
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: span 2; } .valider { justify-content: flex-end; }
.filtres { display: flex; gap: var(--space-4); flex-wrap: wrap; align-items: flex-end; }
.court { width: auto; min-width: 170px; min-height: 40px; }
.puces { display: flex; gap: 6px; flex-wrap: wrap; }
.puce { border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 999px; padding: 6px 12px; min-height: 36px; font-size: var(--font-size-sm); cursor: pointer; color: var(--color-text-muted); }
.puce b { margin-left: 4px; font-variant-numeric: tabular-nums; }
.puce.active { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.puce:hover:not(.active) { border-color: var(--color-brand); color: var(--color-brand-dark); }
.type { font-size: var(--font-size-xs); font-weight: 600; padding: 3px 10px; border-radius: 999px; background: var(--color-brand-light); color: var(--color-brand-dark); white-space: nowrap; }
.t-exceptionnel { background: var(--color-accent-bg); color: var(--color-orange); }
.t-maladie { background: var(--color-rouge-bg); color: var(--color-rouge); }
.t-maternite { background: #F3E8FF; color: #6B21A8; }
.t-sans_solde { background: #EEF0F2; color: var(--color-text-muted); }
.petit { padding: 4px 10px; min-height: 32px; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } .grille .large { grid-column: span 1; } }
</style>
