<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { Download, Mail, Send, XCircle, FolderOpen } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const route = useRoute()
const lots = ref([])
const lot = ref(null)
const erreur = ref('')
const message = ref('')
const LIB = { prepare: 'Préparé', lance: 'Lancé', annule: 'Annulé' }
const colonnesLots = [
  { cle: 'libelle', libelle: 'Lot', tri: true },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (l) => LIB[l.statut] },
  { cle: 'nombre_ordres', libelle: 'Ordres', tri: true, align: 'droite' },
  { cle: 'total', libelle: 'Total (FCFA)', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'nb_exclus', libelle: 'Exclus', tri: true, align: 'droite' },
]
const colonnesOrdres = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'banque', libelle: 'Banque', tri: true },
  { cle: 'montant', libelle: 'Montant', tri: true, align: 'droite', format: (v) => fmt(v) },
]
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })

async function charger() { try { lots.value = (await apiClient.get('/virements')).data } catch (e) { erreur.value = messageErreur(e) } }
async function ouvrir(id) { try { lot.value = (await apiClient.get(`/virements/${id}`)).data } catch (e) { erreur.value = messageErreur(e) } }
async function exporter(format) {
  erreur.value = ''
  try { await telecharger(`/virements/${lot.value.id}/fichier`, { format }, `virements.${format}`) } catch (e) { erreur.value = 'Export impossible.' }
}
async function lettres() {
  erreur.value = ''
  try { await telecharger(`/virements/${lot.value.id}/lettres.pdf`, {}, `lettres_virement_${lot.value.id}.pdf`) } catch (e) { erreur.value = 'Lettres impossibles à générer.' }
}
async function lancer() {
  if (!(await confirm({ title: 'Lancer le virement', message: `Confirmer le lancement du virement de ${fmt(lot.value.total)} FCFA (${lot.value.nombre_ordres} ordres) ? Vérifiez que le fichier a bien été transmis à la banque. Une alerte est envoyée aux responsables.`, confirmLabel: 'Lancer le virement' }))) return
  erreur.value = ''
  try { lot.value = (await apiClient.post(`/virements/${lot.value.id}/lancer`)).data; message.value = 'Virement lancé et tracé.'; await charger(); await ouvrir(lot.value.id) } catch (e) { erreur.value = messageErreur(e) }
}
async function annuler() {
  if (!(await confirm({ title: 'Annuler ce lot', message: 'Le lot de virements sera annulé ; vous pourrez en préparer un nouveau depuis la campagne.', danger: true, confirmLabel: 'Annuler le lot', cancelLabel: 'Conserver' }))) return
  try { await apiClient.post(`/virements/${lot.value.id}/annuler`); lot.value = null; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(async () => { await charger(); if (route.query.lot) await ouvrir(route.query.lot) })
</script>

<template>
  <div class="page">
    <header>
      <h1>Virements</h1>
      <p class="sous-titre">Un lot regroupe les virements d'une campagne validée. Les salariés sans RIB ou payés en espèces sont écartés et listés. Chaque export du fichier (RIB en clair) est tracé dans le journal d'audit.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <DataTable :colonnes="colonnesLots" :lignes="lots" vide="Aucun lot. Ouvrez une campagne validée et cliquez sur « Préparer les virements »." placeholder-recherche="Rechercher un lot">
      <template #cell-statut="{ ligne }"><span :class="['badge', 'st-' + ligne.statut]">{{ LIB[ligne.statut] }}</span></template>
      <template #actions="{ ligne }"><button class="vbtn vbtn-secondary petit" data-hint="Afficher le détail des ordres de ce lot" @click="ouvrir(ligne.id)"><FolderOpen :size="14" />Ouvrir</button></template>
    </DataTable>

    <section v-if="lot" class="card encart">
      <div class="entete">
        <h2>{{ lot.libelle }} <span :class="['badge', 'st-' + lot.statut]">{{ LIB[lot.statut] }}</span></h2>
        <div class="actions">
          <button v-if="lot.statut !== 'annule'" class="vbtn vbtn-secondary" data-hint="Télécharger le fichier de virement au format Excel (action tracée)" @click="exporter('xlsx')"><Download :size="16" />Excel</button>
          <button v-if="lot.statut !== 'annule'" class="vbtn vbtn-secondary" data-hint="Télécharger le fichier de virement au format CSV (action tracée)" @click="exporter('csv')"><Download :size="16" />CSV</button>
          <button v-if="lot.statut !== 'annule'" class="vbtn vbtn-secondary" data-hint="Générer les lettres de virement à remettre aux banques, une par banque (RIB en clair, action tracée)" @click="lettres"><Mail :size="16" />Lettres aux banques</button>
          <button v-if="lot.statut === 'prepare'" class="vbtn vbtn-primary ecriture" data-hint="Marquer le virement comme transmis à la banque et alerter les responsables" @click="lancer"><Send :size="16" />Lancer</button>
          <button v-if="lot.statut === 'prepare'" class="vbtn vbtn-secondary ecriture" data-hint="Annuler ce lot de virements" @click="annuler"><XCircle :size="16" />Annuler</button>
        </div>
      </div>
      <p>{{ lot.nombre_ordres }} ordre(s) pour <strong>{{ fmt(lot.total) }} FCFA</strong><span v-if="lot.lance_le"> — lancé par {{ lot.lance_par }} le {{ new Date(lot.lance_le).toLocaleString('fr-FR') }}</span></p>
      <div v-if="lot.exclus.length" class="bandeau avert"><strong>{{ lot.exclus.length }} salarié(s) non inclus :</strong>
        <ul><li v-for="(x, i) in lot.exclus" :key="i">{{ x.nom }} — {{ x.motif }} ({{ fmt(x.montant) }})</li></ul></div>
      <DataTable :colonnes="colonnesOrdres" :lignes="lot.ordres" cle-ligne="matricule" vide="Aucun ordre." placeholder-recherche="Rechercher un salarié" />
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); display: flex; gap: 8px; align-items: center; }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.entete { display: flex; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; } .actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.encart { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); } .encart p { margin: 0; }
.petit { padding: 4px 10px; min-height: 32px; }
.st-lance { background: var(--color-vert-bg); color: var(--color-vert); }
.bandeau { padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); } .bandeau.avert { background: var(--color-orange-bg); color: var(--color-orange); } .bandeau ul { margin: 6px 0 0; padding-left: 20px; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
