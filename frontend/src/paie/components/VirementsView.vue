<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { telecharger } from '@/api/telechargement'
import { Download, Send, XCircle } from 'lucide-vue-next'

const route = useRoute()
const lots = ref([])
const lot = ref(null)
const erreur = ref('')
const message = ref('')
const LIB = { prepare: 'Préparé', lance: 'Lancé', annule: 'Annulé' }
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })

async function charger() { try { lots.value = (await apiClient.get('/virements')).data } catch (e) { erreur.value = messageErreur(e) } }
async function ouvrir(id) { try { lot.value = (await apiClient.get(`/virements/${id}`)).data } catch (e) { erreur.value = messageErreur(e) } }
async function exporter(format) {
  erreur.value = ''
  try { await telecharger(`/virements/${lot.value.id}/fichier`, { format }, `virements.${format}`) } catch (e) { erreur.value = 'Export impossible.' }
}
async function lancer() {
  if (!window.confirm(`Confirmer le lancement du virement de ${fmt(lot.value.total)} FCFA (${lot.value.nombre_ordres} ordres) ? Vérifiez que le fichier a bien été transmis à la banque.`)) return
  erreur.value = ''
  try { lot.value = (await apiClient.post(`/virements/${lot.value.id}/lancer`)).data; message.value = 'Virement lancé et tracé.'; await charger(); await ouvrir(lot.value.id) } catch (e) { erreur.value = messageErreur(e) }
}
async function annuler() {
  if (!window.confirm('Annuler ce lot ?')) return
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

    <div class="card cadre"><table>
      <thead><tr><th>Lot</th><th>Statut</th><th class="num">Ordres</th><th class="num">Total (FCFA)</th><th class="num">Exclus</th><th></th></tr></thead>
      <tbody>
        <tr v-for="l in lots" :key="l.id"><td>{{ l.libelle }}</td><td><span :class="['badge', 'st-' + l.statut]">{{ LIB[l.statut] }}</span></td>
          <td class="num">{{ l.nombre_ordres }}</td><td class="num">{{ fmt(l.total) }}</td><td class="num">{{ l.nb_exclus }}</td>
          <td><button class="vbtn vbtn-secondary petit" @click="ouvrir(l.id)">Ouvrir</button></td></tr>
        <tr v-if="!lots.length"><td colspan="6" class="vide">Aucun lot. Ouvrez une campagne validée et cliquez sur « Préparer les virements ».</td></tr>
      </tbody></table></div>

    <section v-if="lot" class="card encart">
      <div class="entete">
        <h2>{{ lot.libelle }} <span :class="['badge', 'st-' + lot.statut]">{{ LIB[lot.statut] }}</span></h2>
        <div class="actions">
          <button v-if="lot.statut !== 'annule'" class="vbtn vbtn-secondary" @click="exporter('xlsx')"><Download :size="16" />Excel</button>
          <button v-if="lot.statut !== 'annule'" class="vbtn vbtn-secondary" @click="exporter('csv')"><Download :size="16" />CSV</button>
          <button v-if="lot.statut === 'prepare'" class="vbtn vbtn-primary" @click="lancer"><Send :size="16" />Lancer</button>
          <button v-if="lot.statut === 'prepare'" class="vbtn vbtn-secondary" @click="annuler"><XCircle :size="16" />Annuler</button>
        </div>
      </div>
      <p>{{ lot.nombre_ordres }} ordre(s) pour <strong>{{ fmt(lot.total) }} FCFA</strong><span v-if="lot.lance_le"> — lancé par {{ lot.lance_par }} le {{ new Date(lot.lance_le).toLocaleString('fr-FR') }}</span></p>
      <div v-if="lot.exclus.length" class="bandeau avert"><strong>{{ lot.exclus.length }} salarié(s) non inclus :</strong>
        <ul><li v-for="(x, i) in lot.exclus" :key="i">{{ x.nom }} — {{ x.motif }} ({{ fmt(x.montant) }})</li></ul></div>
      <div class="cadre"><table>
        <thead><tr><th>Matricule</th><th>Salarié</th><th>Banque</th><th class="num">Montant</th></tr></thead>
        <tbody><tr v-for="(o, i) in lot.ordres" :key="i"><td>{{ o.matricule }}</td><td>{{ o.nom }}</td><td>{{ o.banque }}</td><td class="num">{{ fmt(o.montant) }}</td></tr></tbody></table></div>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); display: flex; gap: 8px; align-items: center; }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.entete { display: flex; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; } .actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.encart { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); } .encart p { margin: 0; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 14px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.petit { padding: 4px 10px; min-height: 32px; }
.st-lance { background: var(--color-vert-bg); color: var(--color-vert); }
.bandeau { padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); } .bandeau.avert { background: #FEF3C7; color: #92400E; } .bandeau ul { margin: 6px 0 0; padding-left: 20px; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
