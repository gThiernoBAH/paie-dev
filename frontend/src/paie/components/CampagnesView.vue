<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { aLaPermission, lireUtilisateur } from '@/api/session'
import { Plus, Eye, Calculator } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const router = useRouter()
const peutCreer = aLaPermission(lireUtilisateur(), 'lancer_paie')
const peutSolder = aLaPermission(lireUtilisateur(), 'gerer_conges')
const solde = ref({ matricule: '', date_sortie: '', motif: 'demission', jours_conges: '', preavis: '' })
const motifs = ref([])
const apercu = ref(null)
const campagnes = ref([])
const erreur = ref('')
const aujourdhui = new Date()
const nouvelle = ref({ type_campagne: 'mensuelle', annee: aujourdhui.getFullYear(), mois: aujourdhui.getMonth() + 1, debut: '', fin: '' })
const LIBELLES = { ouverte: 'Ouverte', calculee: 'Calculée', validee: 'Validée', cloturee: 'Clôturée' }
const dateFr = (d) => d.split('-').reverse().join('/')
const colonnes = [
  { cle: 'libelle', libelle: 'Campagne', tri: true },
  { cle: 'debut', libelle: 'Période', tri: true, texte: (c) => `${dateFr(c.debut)} → ${dateFr(c.fin)}` },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (c) => LIBELLES[c.statut] },
  { cle: 'nb_salaries', libelle: 'Salariés', tri: true, align: 'droite' },
  { cle: 'nb_bulletins', libelle: 'Bulletins', tri: true, align: 'droite' },
  { cle: 'total_net', libelle: 'Net à payer', tri: true, align: 'droite', format: (v) => fmt(v) },
]
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })

async function charger() {
  try { campagnes.value = (await apiClient.get('/campagnes')).data } catch (e) { erreur.value = messageErreur(e) }
}
async function creer() {
  erreur.value = ''
  try {
    const corps = { ...nouvelle.value }
    if (corps.type_campagne === 'mensuelle') { delete corps.debut; delete corps.fin }
    const { data } = await apiClient.post('/campagnes', corps)
    router.push(`/campagnes/${data.id}`)
  } catch (e) { erreur.value = messageErreur(e) }
}
async function salarieDuSolde() {
  const { data } = await apiClient.get('/salaries', { params: { recherche: solde.value.matricule.trim(), statut: 'tous', taille: 5 } })
  const s = data.elements.find((x) => x.matricule === solde.value.matricule.trim().padStart(6, '0'))
  if (!s) throw new Error('Matricule introuvable.')
  return s
}
async function voirApercu() {
  erreur.value = ''; apercu.value = null
  try {
    const s = await salarieDuSolde()
    apercu.value = (await apiClient.get('/soldes/apercu', { params: { salarie_id: s.id, date_sortie: solde.value.date_sortie, motif: solde.value.motif } })).data
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function creerSolde() {
  erreur.value = ''
  if (!(await confirm({ title: 'Créer le solde de tout compte', message: 'Le salarié sera marqué comme sorti à la date indiquée et une campagne dédiée sera créée.', confirmLabel: 'Créer le solde' }))) return
  try {
    const s = await salarieDuSolde()
    const corps = { salarie_id: s.id, date_sortie: solde.value.date_sortie, motif: solde.value.motif }
    if (solde.value.jours_conges !== '') corps.jours_conges = solde.value.jours_conges
    if (solde.value.preavis !== '') corps.preavis = solde.value.preavis
    const { data } = await apiClient.post('/soldes', corps)
    router.push(`/campagnes/${data.campagne_id}`)
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
onMounted(async () => {
  charger()
  if (peutSolder) { try { motifs.value = (await apiClient.get('/soldes/motifs')).data } catch { /* facultatif */ } }
})
</script>

<template>
  <div class="page">
    <header>
      <h1>Campagnes de paie</h1>
      <p class="sous-titre">Une campagne = une période payée : le mois pour les mensuels, une quinzaine (ou autre découpage) pour les journaliers. Plusieurs campagnes par mois sont possibles.</p>
    </header>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form v-if="peutCreer" class="card saisie ecriture" @submit.prevent="creer">
      <h2>Nouvelle campagne</h2>
      <div class="grille">
        <label class="field large"><span class="field-label">Type de campagne</span>
          <select v-model="nouvelle.type_campagne" class="input">
            <option value="mensuelle">Mensuelle (salariés mensuels)</option>
            <option value="journaliere">Journaliers (période libre)</option>
            <option value="exceptionnelle">Exceptionnelle (mensuels, période libre)</option>
          </select></label>
        <label class="field"><span class="field-label">Année</span><input v-model.number="nouvelle.annee" type="number" class="input" required /></label>
        <label class="field"><span class="field-label">Mois</span><input v-model.number="nouvelle.mois" type="number" min="1" max="12" class="input" required /></label>
        <template v-if="nouvelle.type_campagne !== 'mensuelle'">
          <label class="field"><span class="field-label">Début de période</span><input v-model="nouvelle.debut" type="date" class="input" required /></label>
          <label class="field"><span class="field-label">Fin de période</span><input v-model="nouvelle.fin" type="date" class="input" required /></label>
        </template>
        <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Créer la campagne</button></div>
      </div>
    </form>

    <details v-if="peutSolder" class="card encart ecriture">
      <summary>Solde de tout compte (salarié sortant)</summary>
      <form class="saisie" @submit.prevent="creerSolde">
        <div class="grille">
          <label class="field"><span class="field-label">Matricule</span><input v-model="solde.matricule" class="input" placeholder="000054" required inputmode="numeric" /></label>
          <label class="field"><span class="field-label">Date de sortie</span><input v-model="solde.date_sortie" type="date" class="input" required /></label>
          <label class="field"><span class="field-label">Motif de sortie</span><select v-model="solde.motif" class="input"><option v-for="m in motifs" :key="m.cle" :value="m.cle">{{ m.libelle }}</option></select></label>
          <label class="field"><span class="field-label">Jours de congés restants</span><input v-model="solde.jours_conges" type="number" step="0.5" min="0" class="input" placeholder="Auto" data-hint="Laisser vide pour utiliser le solde calculé" /></label>
          <label class="field"><span class="field-label">Indemnité de préavis</span><input v-model="solde.preavis" type="number" min="0" class="input" placeholder="Auto" data-hint="Laisser vide pour utiliser le montant calculé" /></label>
          <div class="field valider ligne"><button class="vbtn vbtn-secondary" type="button" data-hint="Calculer les indemnités sans rien créer" @click="voirApercu"><Eye :size="16" />Aperçu</button>
            <button class="vbtn vbtn-primary" type="submit"><Calculator :size="16" />Créer le solde</button></div>
        </div>
      </form>
      <div v-if="apercu" class="apercu">
        <span>Salaire de référence : <strong>{{ fmt(apercu.reference_mensuelle) }}</strong></span>
        <span>Congés : <strong>{{ apercu.jours_conges }} j = {{ fmt(apercu.indemnite_conges) }}</strong></span>
        <span>Ancienneté : <strong>{{ apercu.anciennete_mois }} mois</strong></span>
        <span>Licenciement : <strong>{{ fmt(apercu.indemnite_licenciement) }}</strong> (dont non imposable {{ fmt(apercu.licenciement_non_imposable) }})</span>
      </div>
      <p class="aide">Crée une campagne dédiée avec les indemnités calculées ; le reste dû des prêts y est retenu. Vous pouvez ensuite ajouter des rubriques, calculer et valider comme pour toute campagne.</p>
    </details>

    <DataTable :colonnes="colonnes" :lignes="campagnes" ligne-cliquable vide="Aucune campagne. Créez la première ci-dessus." placeholder-recherche="Rechercher une campagne" tri-initial="debut" sens-initial="desc" @ligne="(c) => router.push(`/campagnes/${c.id}`)">
      <template #cell-libelle="{ ligne }"><strong>{{ ligne.libelle }}</strong></template>
      <template #cell-statut="{ ligne }"><span :class="['badge', 'st-' + ligne.statut]">{{ LIBELLES[ligne.statut] }}</span></template>
    </DataTable>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 720px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; }
h2 { margin: 0; font-size: var(--font-size-base); }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: span 2; } .valider { justify-content: flex-end; }
@media (max-width: 560px) { .grille .large { grid-column: span 1; } }
.encart { padding: var(--space-3) var(--space-4); } summary { cursor: pointer; font-weight: 600; }
.apercu { display: flex; gap: var(--space-6); flex-wrap: wrap; font-size: var(--font-size-sm); padding: var(--space-2) 0; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.st-validee, .st-cloturee { background: var(--color-vert-bg); color: var(--color-vert); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
