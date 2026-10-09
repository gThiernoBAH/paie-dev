<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus, CalendarDays, HandCoins, Undo2, Lock } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm, saisir } = useConfirm()

const prets = ref([])
const detail = ref(null)
const erreur = ref('')
const message = ref('')
const maintenant = new Date()
const nouveau = ref({ matricule: '', type_pret: 'pret', libelle: '', montant: '', nombre_echeances: 6, annee_debut: maintenant.getFullYear(), mois_debut: maintenant.getMonth() + 1 })
const MOIS = ['', 'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const LIB = { actif: 'En cours', solde: 'Soldé', annule: 'Annulé', cloture: 'Clôturé', prevue: 'Prévue', prelevee: 'Prélevée sur paie', annulee: 'Annulée', reglee: 'Réglée hors paie', abandonnee: 'Passée en perte' }
const CLASSE = { prelevee: 'ok', reglee: 'ok', solde: 'ok', abandonnee: 'perte', cloture: 'perte', annule: 'perte', annulee: 'perte' }
const MOTIFS = { depart: 'Départ du salarié', demission: 'Démission', deces: 'Décès', licenciement: 'Licenciement', autre: 'Autre' }
const MODES = { especes: 'Espèces', cheque: 'Chèque', virement: 'Virement', autre: 'Autre' }
const aujourdhui = () => new Date().toLocaleDateString('sv-SE')
const dateFr = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString('fr-FR') : '')
const colonnes = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'libelle', libelle: 'Libellé', tri: true },
  { cle: 'montant', libelle: 'Montant', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'regle', libelle: 'Remboursé', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'reste', libelle: 'Reste dû', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (p) => LIB[p.statut] },
]
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })

async function charger() { try { prets.value = (await apiClient.get('/prets')).data } catch (e) { erreur.value = messageErreur(e) } }
async function creer() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.get('/salaries', { params: { recherche: nouveau.value.matricule.trim(), statut: 'tous', taille: 5 } })
    const s = data.elements.find((x) => x.matricule === nouveau.value.matricule.trim().padStart(6, '0'))
    if (!s) throw new Error('Matricule introuvable.')
    const { matricule, ...corps } = nouveau.value
    const p = (await apiClient.post('/prets', { ...corps, salarie_id: s.id })).data
    message.value = `Prêt enregistré : ${p.nombre_echeances} échéance(s). Elles seront prélevées automatiquement sur les bulletins.`
    nouveau.value.matricule = ''; nouveau.value.libelle = ''; nouveau.value.montant = ''
    await charger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function voir(p) { try { detail.value = (await apiClient.get(`/prets/${p.id}`)).data } catch (e) { erreur.value = messageErreur(e) } }
function prevenir(r) {
  const l = r.campagnes_a_recalculer || []
  message.value = l.length ? `Enregistré. Paie déjà calculée à recalculer : ${l.join(', ')}.` : 'Enregistré.'
}
async function regler(p, e) {
  const v = await saisir({
    title: `Régler l'échéance de ${MOIS[e.mois]} ${e.annee}`,
    message: `${fmt(e.montant)} FCFA remboursés hors paie (espèces, chèque, virement…). L'échéance ne sera plus retenue sur le bulletin.`,
    confirmLabel: 'Marquer comme réglée',
    champs: [
      { cle: 'date_reglement', label: 'Date du règlement', type: 'date', obligatoire: true, valeur: aujourdhui() },
      { cle: 'mode_reglement', label: 'Mode', type: 'choix', valeur: 'especes', options: Object.entries(MODES).map(([valeur, libelle]) => ({ valeur, libelle })) },
      { cle: 'commentaire', label: 'Commentaire (facultatif)', type: 'text' },
    ],
  })
  if (!v) return
  erreur.value = ''
  try { const r = (await apiClient.post(`/prets/${p.id}/echeances/${e.id}/regler`, { ...v, commentaire: v.commentaire || null })).data; detail.value = r; prevenir(r); await charger() } catch (x) { erreur.value = messageErreur(x) }
}
async function rouvrir(p, e) {
  if (!(await confirm({ title: 'Annuler le règlement', message: `L'échéance de ${MOIS[e.mois]} ${e.annee} redeviendra « prévue » et sera de nouveau retenue sur la paie.`, confirmLabel: 'Annuler le règlement', cancelLabel: 'Conserver' }))) return
  erreur.value = ''
  try { const r = (await apiClient.post(`/prets/${p.id}/echeances/${e.id}/rouvrir`)).data; detail.value = r; prevenir(r); await charger() } catch (x) { erreur.value = messageErreur(x) }
}
async function cloturer(p) {
  const v = await saisir({
    title: `Clôturer le prêt « ${p.libelle} »`,
    message: `Reste dû : ${fmt(p.reste)} FCFA. Les échéances non prélevées sont retirées de la paie. « Passer en perte » solde le prêt sans remboursement (départ, démission, décès…) ; « régularisé » indique que le reste a été payé hors paie.`,
    confirmLabel: 'Clôturer le prêt', danger: true,
    champs: [
      { cle: 'motif', label: 'Motif', type: 'choix', valeur: 'depart', options: Object.entries(MOTIFS).map(([valeur, libelle]) => ({ valeur, libelle })) },
      { cle: 'issue', label: 'Issue du reste dû', type: 'choix', valeur: 'abandon', options: [{ valeur: 'abandon', libelle: 'Passé en perte (non remboursé)' }, { valeur: 'regularise', libelle: 'Régularisé hors paie (payé)' }] },
      { cle: 'date_cloture', label: 'Date de clôture', type: 'date', obligatoire: true, valeur: aujourdhui() },
      { cle: 'commentaire', label: 'Commentaire (facultatif)', type: 'text' },
    ],
  })
  if (!v) return
  erreur.value = ''
  try { const r = (await apiClient.post(`/prets/${p.id}/cloturer`, { ...v, commentaire: v.commentaire || null })).data; detail.value = r; prevenir(r); await charger() } catch (x) { erreur.value = messageErreur(x) }
}
async function annuler(p) {
  if (!(await confirm({ title: 'Annuler ce prêt', message: 'Les échéances non encore prélevées seront supprimées. Cette action est tracée dans le journal.', danger: true, confirmLabel: 'Annuler le prêt', cancelLabel: 'Conserver' }))) return
  try { detail.value = (await apiClient.post(`/prets/${p.id}/annuler`)).data; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Prêts et avances</h1>
      <p class="sous-titre">Chaque prêt génère un échéancier mensuel ; l'échéance du mois est retenue automatiquement au calcul de la paie (rubrique PRE) et marquée « prélevée » à la validation. Au solde de tout compte, le reste dû est retenu en une fois.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <form class="card saisie ecriture" @submit.prevent="creer">
      <h2>Nouveau prêt ou avance</h2>
      <div class="grille">
        <label class="field"><span class="field-label">Matricule</span><input v-model="nouveau.matricule" class="input" placeholder="000054" required inputmode="numeric" /></label>
        <label class="field"><span class="field-label">Type</span><select v-model="nouveau.type_pret" class="input"><option value="pret">Prêt</option><option value="avance">Avance</option></select></label>
        <label class="field large"><span class="field-label">Libellé</span><input v-model="nouveau.libelle" class="input" placeholder="Ex. Prêt scolarité" required /></label>
        <label class="field"><span class="field-label">Montant (FCFA)</span><input v-model="nouveau.montant" type="number" min="1" class="input" required /></label>
        <label class="field"><span class="field-label">Nombre d'échéances</span><input v-model.number="nouveau.nombre_echeances" type="number" min="1" max="120" class="input" required data-hint="Nombre de mois sur lesquels le remboursement est étalé" /></label>
        <label class="field"><span class="field-label">1er prélèvement : mois</span><input v-model.number="nouveau.mois_debut" type="number" min="1" max="12" class="input" required data-hint="Mois de la première retenue sur bulletin (1 à 12)" /></label>
        <label class="field"><span class="field-label">1er prélèvement : année</span><input v-model.number="nouveau.annee_debut" type="number" min="2000" max="2100" class="input" required /></label>
        <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Créer le prêt</button></div>
      </div>
    </form>
    <DataTable :colonnes="colonnes" :lignes="prets" vide="Aucun prêt." placeholder-recherche="Rechercher un matricule ou un nom">
      <template #cell-statut="{ ligne }"><span :class="['badge', CLASSE[ligne.statut]]">{{ LIB[ligne.statut] }}</span></template>
      <template #actions="{ ligne }">
        <button class="vbtn vbtn-secondary petit" data-hint="Voir les échéances de remboursement de ce prêt" @click="voir(ligne)"><CalendarDays :size="14" />Échéancier</button>
      </template>
    </DataTable>
    <div v-if="detail" class="card encart">
      <h2>{{ detail.libelle }} — {{ detail.matricule }} <span :class="['badge', CLASSE[detail.statut]]">{{ LIB[detail.statut] }}</span></h2>
      <p v-if="detail.statut === 'cloture'" class="note">
        Clôturé le {{ dateFr(detail.date_cloture) }} — {{ MOTIFS[detail.motif_cloture] }} ;
        {{ detail.issue_cloture === 'abandon' ? `${fmt(detail.abandonne)} FCFA passés en perte` : 'reste régularisé hors paie' }}.
      </p>
      <p class="resume">Remboursé {{ fmt(detail.regle) }} · Reste dû {{ fmt(detail.reste) }} FCFA</p>
      <div class="defile">
        <table><thead><tr><th>Échéance</th><th class="num">Montant</th><th>Statut</th><th>Réglée le</th><th class="act">Action</th></tr></thead>
          <tbody><tr v-for="e in detail.echeances" :key="e.id">
            <td>{{ MOIS[e.mois] }} {{ e.annee }}</td><td class="num">{{ fmt(e.montant) }}</td>
            <td><span :class="['badge', CLASSE[e.statut]]">{{ LIB[e.statut] }}</span>
              <span v-if="e.statut === 'prelevee' && e.campagne" class="discret"> · {{ e.campagne }}</span></td>
            <td>{{ dateFr(e.date_reglement) }}<span v-if="e.mode_reglement" class="discret"> · {{ MODES[e.mode_reglement] }}</span>
              <span v-if="e.commentaire" class="discret" :title="e.commentaire"> ✎</span></td>
            <td class="act">
              <BoutonIcone v-if="e.statut === 'prevue' && ['actif'].includes(detail.statut)" class="ecriture" :icone="HandCoins" hint="Marquer cette échéance comme réglée hors paie" @click="regler(detail, e)" />
              <BoutonIcone v-else-if="e.statut === 'reglee' && detail.statut !== 'cloture'" class="ecriture" :icone="Undo2" hint="Annuler ce règlement : l'échéance redevient prévue" @click="rouvrir(detail, e)" />
            </td></tr></tbody></table>
      </div>
      <div class="ligne">
        <button v-if="detail.statut === 'actif'" class="vbtn vbtn-secondary ecriture" data-hint="Départ, démission, décès… : solder le prêt en le passant en perte ou en le régularisant" @click="cloturer(detail)"><Lock :size="15" />Clôturer le prêt</button>
        <button v-if="detail.statut === 'actif'" class="vbtn vbtn-secondary ecriture" @click="annuler(detail)">Annuler le prêt</button>
        <button class="vbtn vbtn-secondary" @click="detail = null">Fermer</button></div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: span 2; }
.valider { justify-content: flex-end; }
@media (max-width: 560px) { .grille .large { grid-column: span 1; } }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; }
.encart { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); max-width: 760px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.encart table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.encart th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.encart th.num { text-align: right; }
.encart th.act, .encart td.act { text-align: center; white-space: nowrap; width: 1%; }
.defile { overflow-x: auto; }
.resume, .note { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.discret { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.badge.ok { background: var(--color-vert-bg); color: var(--color-vert); }
.badge.perte { background: var(--color-rouge-bg); color: var(--color-rouge); }
.encart td { padding: 7px 10px; border-bottom: 1px solid var(--color-border); }
.petit { padding: 4px 10px; min-height: 32px; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
