<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { Plus, FileText, Ban } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import { useConfirm } from '@/composables/useConfirm'

const { saisir } = useConfirm()
const onglet = ref('mesures')
const mesures = ref([])
const notes = ref([])
const services = ref([])
const erreur = ref('')
const message = ref('')
const aujourdhui = new Date().toISOString().slice(0, 10)

const TYPES = { avertissement: 'Avertissement', blame: 'Blâme', mise_a_pied: 'Mise à pied' }
const vide = () => ({ matricule: '', type_mesure: 'avertissement', date_faits: '', date_decision: aujourdhui, motif: '', debut_mise_a_pied: '', fin_mise_a_pied: '' })
const form = ref(vide())
const salarie = ref(null)          // fiche trouvée pour le matricule saisi
const formNote = ref({ objet: '', contenu: '', date_effet: aujourdhui, service_id: '' })
const fdate = (d) => (d ? new Date(d).toLocaleDateString('fr-FR') : '')

const colonnesMesures = [
  { cle: 'reference', libelle: 'Référence', tri: true },
  { cle: 'date_decision', libelle: 'Décision', tri: true, format: fdate },
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'type_libelle', libelle: 'Mesure', tri: true },
  { cle: 'periode', libelle: 'Mise à pied', texte: (m) => (m.debut_mise_a_pied ? `${fdate(m.debut_mise_a_pied)} → ${fdate(m.fin_mise_a_pied)} (${m.jours_non_payes} j non payés)` : '') },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (m) => (m.statut === 'active' ? 'Active' : 'Annulée') },
]
const colonnesNotes = [
  { cle: 'reference', libelle: 'Référence', tri: true },
  { cle: 'date_effet', libelle: 'Date d\'effet', tri: true, format: fdate },
  { cle: 'objet', libelle: 'Objet', tri: true },
  { cle: 'service', libelle: 'Destinataires', tri: true },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (n) => (n.statut === 'active' ? 'Active' : 'Annulée') },
]

const estMiseAPied = computed(() => form.value.type_mesure === 'mise_a_pied')

async function charger() {
  try {
    mesures.value = (await apiClient.get('/discipline/mesures')).data
    notes.value = (await apiClient.get('/discipline/notes')).data
    services.value = (await apiClient.get('/referentiels', { params: { type_ref: 'service' } })).data.filter((r) => r.est_actif)
  } catch (e) { erreur.value = messageErreur(e) }
}
async function verifierMatricule() {
  salarie.value = null
  const m = form.value.matricule.trim()
  if (!m) return
  try {
    const { data } = await apiClient.get(`/admin/salarie-par-matricule/${m.padStart(6, '0')}`)
    salarie.value = data.existe ? data : { introuvable: true }
  } catch { salarie.value = null }
}
async function creer() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.get('/salaries', { params: { recherche: form.value.matricule.trim(), statut: 'tous', taille: 5 } })
    const s = data.elements.find((x) => x.matricule === form.value.matricule.trim().padStart(6, '0'))
    if (!s) throw new Error('Matricule introuvable.')
    const { matricule, ...corps } = form.value
    for (const k of ['date_faits', 'debut_mise_a_pied', 'fin_mise_a_pied']) if (!corps[k]) corps[k] = null
    const m = (await apiClient.post('/discipline/mesures', { ...corps, salarie_id: s.id })).data
    message.value = `Mesure enregistrée (${m.reference}). Vous pouvez imprimer la lettre.`
    form.value = vide(); salarie.value = null
    await charger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function annulerMesure(m) {
  const v = await saisir({ title: 'Annuler cette mesure', message: `${m.reference} — ${m.nom}. La mesure reste visible dans l'historique ; une mise à pied annulée n'est plus déduite de la paie.`, danger: true, confirmLabel: 'Annuler la mesure', cancelLabel: 'Conserver', champs: [{ cle: 'motif', label: 'Motif de l\'annulation', obligatoire: true }] })
  if (!v) return
  try { await apiClient.post(`/discipline/mesures/${m.id}/annuler`, { motif: v.motif }); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function creerNote() {
  erreur.value = ''; message.value = ''
  try {
    const corps = { ...formNote.value, service_id: formNote.value.service_id || null }
    const n = (await apiClient.post('/discipline/notes', corps)).data
    message.value = `Note de service enregistrée (${n.reference}).`
    formNote.value = { objet: '', contenu: '', date_effet: aujourdhui, service_id: '' }
    await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function annulerNote(n) {
  const v = await saisir({ title: 'Annuler cette note', message: `${n.reference} — ${n.objet}`, danger: true, confirmLabel: 'Annuler la note', cancelLabel: 'Conserver', champs: [] })
  if (!v) return
  try { await apiClient.post(`/discipline/notes/${n.id}/annuler`); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
const pdf = (chemin, nom) => telecharger(chemin, {}, nom).catch(() => { erreur.value = 'Le document n\'a pas pu être généré.' })
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Dossier disciplinaire</h1>
      <p class="sous-titre">Avertissements, blâmes et mises à pied rattachés au dossier du salarié, et notes de service. Une mise à pied est déduite automatiquement de la paie du mois (jours ouvrés, ligne « Absences (jours) »). Les lettres générées sont des modèles à faire valider par votre service juridique.</p>
    </header>
    <div class="onglets" role="tablist">
      <button role="tab" :aria-selected="onglet === 'mesures'" :class="{ actif: onglet === 'mesures' }" @click="onglet = 'mesures'">Mesures disciplinaires</button>
      <button role="tab" :aria-selected="onglet === 'notes'" :class="{ actif: onglet === 'notes' }" @click="onglet = 'notes'">Notes de service</button>
    </div>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <template v-if="onglet === 'mesures'">
      <form class="card saisie ecriture" @submit.prevent="creer">
        <h2>Nouvelle mesure</h2>
        <div class="grille">
          <label class="field"><span class="field-label">Matricule</span><input v-model="form.matricule" class="input" required inputmode="numeric" placeholder="000054" @blur="verifierMatricule" /></label>
          <label class="field"><span class="field-label">Mesure</span><select v-model="form.type_mesure" class="input"><option v-for="(l, k) in TYPES" :key="k" :value="k">{{ l }}</option></select></label>
          <label class="field"><span class="field-label">Date des faits</span><input v-model="form.date_faits" type="date" class="input" /></label>
          <label class="field"><span class="field-label">Date de la décision</span><input v-model="form.date_decision" type="date" class="input" required /></label>
          <template v-if="estMiseAPied">
            <label class="field"><span class="field-label">Mise à pied : du</span><input v-model="form.debut_mise_a_pied" type="date" class="input" required /></label>
            <label class="field"><span class="field-label">Mise à pied : au (inclus)</span><input v-model="form.fin_mise_a_pied" type="date" class="input" required /></label>
          </template>
          <label class="field large"><span class="field-label">Motif / faits reprochés</span><textarea v-model="form.motif" class="input" rows="3" required minlength="5" /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit" data-hint="Enregistrer la mesure dans le dossier du salarié"><Plus :size="16" />Enregistrer</button></div>
        </div>
        <p v-if="salarie && salarie.existe" class="info">{{ salarie.nom }} {{ salarie.prenom }}</p>
        <p v-else-if="salarie && salarie.introuvable" class="message-erreur">Aucun salarié avec ce matricule.</p>
      </form>
      <DataTable :colonnes="colonnesMesures" :lignes="mesures" vide="Aucune mesure disciplinaire." placeholder-recherche="Rechercher un salarié, une référence…">
        <template #cell-statut="{ ligne }"><span :class="['badge', ligne.statut === 'active' ? 'badge-attente' : '']">{{ ligne.statut === 'active' ? 'Active' : 'Annulée' }}</span></template>
        <template #actions="{ ligne }">
          <button class="vbtn vbtn-secondary petit" data-hint="Imprimer la lettre de notification (PDF)" @click="pdf(`/discipline/mesures/${ligne.id}/lettre.pdf`, ligne.reference + '.pdf')"><FileText :size="14" />Lettre</button>
          <button v-if="ligne.statut === 'active'" class="vbtn vbtn-secondary petit ecriture" data-hint="Annuler cette mesure (elle reste dans l'historique)" @click="annulerMesure(ligne)"><Ban :size="14" />Annuler</button>
        </template>
      </DataTable>
    </template>

    <template v-else>
      <form class="card saisie ecriture" @submit.prevent="creerNote">
        <h2>Nouvelle note de service</h2>
        <div class="grille">
          <label class="field large"><span class="field-label">Objet</span><input v-model="formNote.objet" class="input" required minlength="3" /></label>
          <label class="field"><span class="field-label">Date d'effet</span><input v-model="formNote.date_effet" type="date" class="input" required /></label>
          <label class="field"><span class="field-label">Destinataires</span>
            <select v-model="formNote.service_id" class="input"><option value="">Tout le personnel</option><option v-for="s in services" :key="s.id" :value="s.id">{{ s.libelle }}</option></select></label>
          <label class="field large"><span class="field-label">Contenu</span><textarea v-model="formNote.contenu" class="input" rows="5" required minlength="5" /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit" data-hint="Enregistrer la note de service"><Plus :size="16" />Enregistrer</button></div>
        </div>
      </form>
      <DataTable :colonnes="colonnesNotes" :lignes="notes" vide="Aucune note de service." placeholder-recherche="Rechercher une note">
        <template #cell-statut="{ ligne }"><span :class="['badge', ligne.statut === 'active' ? 'badge-ok' : '']">{{ ligne.statut === 'active' ? 'Active' : 'Annulée' }}</span></template>
        <template #actions="{ ligne }">
          <button class="vbtn vbtn-secondary petit" data-hint="Imprimer la note de service (PDF)" @click="pdf(`/discipline/notes/${ligne.id}/pdf`, ligne.reference + '.pdf')"><FileText :size="14" />PDF</button>
          <button v-if="ligne.statut === 'active'" class="vbtn vbtn-secondary petit ecriture" data-hint="Annuler cette note de service" @click="annulerNote(ligne)"><Ban :size="14" />Annuler</button>
        </template>
      </DataTable>
    </template>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap; }
.onglets button { background: none; border: 0; padding: 10px 16px; cursor: pointer; font: inherit; color: var(--color-text-muted); border-bottom: 2px solid transparent; }
.onglets button.actif { color: var(--color-brand); border-bottom-color: var(--color-brand); font-weight: 600; }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: 1 / -1; }
.valider { justify-content: flex-end; }
.info { margin: 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.petit { padding: 4px 10px; min-height: 32px; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
