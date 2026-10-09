<script setup>
/** Clôture annuelle : fige les cumuls de l'année et verrouille ses écritures ; réouverture réservée à l'administrateur. */
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur } from '@/api/session'
import { Lock, LockOpen, Download } from 'lucide-vue-next'
import { useConfirm } from '@/composables/useConfirm'
import { telecharger } from '@/api/telechargement'

const { confirm, saisir } = useConfirm()
const moi = lireUtilisateur()
const estAdmin = moi?.role === 'admin'
const annees = ref([])
const erreur = ref('')
const message = ref('')
const dateFr = (d) => (d ? new Date(d).toLocaleDateString('fr-FR') : '')
const LIB = { ouvert: 'Ouvert', cloture: 'Clôturé', rouvert: 'Rouvert' }

async function charger() { try { annees.value = (await apiClient.get('/exercices')).data } catch (e) { erreur.value = messageErreur(e) } }
async function cloturer(a) {
  if (!(await confirm({ title: `Clôturer l'exercice ${a.annee}`, message: `Les cumuls ${a.annee} de chaque salarié seront figés et l'année verrouillée : plus de campagne, de salaire ni de règlement de prêt daté dans ${a.annee}. Seul un administrateur pourra la rouvrir, avec un motif.`, confirmLabel: 'Clôturer', danger: true }))) return
  erreur.value = ''; message.value = ''
  try { const r = (await apiClient.post(`/exercices/${a.annee}/cloturer`)).data; message.value = `Exercice ${a.annee} clôturé (${r.salaries} salarié(s) figés).`; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function rouvrir(a) {
  const v = await saisir({ title: `Rouvrir l'exercice ${a.annee}`, message: 'La réouverture est tracée dans le journal d\'audit.', confirmLabel: 'Rouvrir', danger: true,
    champs: [{ cle: 'motif', label: 'Motif (5 caractères minimum)', obligatoire: true }] })
  if (!v) return
  erreur.value = ''; message.value = ''
  try { await apiClient.post(`/exercices/${a.annee}/rouvrir`, { motif: v.motif }); message.value = `Exercice ${a.annee} rouvert.`; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function exporter(a) {
  try { await telecharger('/rapports/cumuls-annuels', { annee: a.annee, format: 'xlsx' }, `cumuls-${a.annee}.xlsx`) } catch { erreur.value = 'Export impossible.' }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Clôture annuelle</h1>
      <p class="sous-titre">Une année clôturée a ses cumuls par salarié figés et ses écritures verrouillées. Prérequis : toutes les campagnes de l'année sont validées. Seul un administrateur peut rouvrir un exercice.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <div class="liste">
      <article v-for="a in annees" :key="a.annee" class="card ex">
        <div class="tete">
          <h2>{{ a.annee }}</h2>
          <span :class="['badge', a.statut === 'cloture' ? 'ferme' : 'ouvert']">{{ LIB[a.statut] }}</span>
        </div>
        <p class="detail">{{ a.campagnes_validees }} / {{ a.campagnes }} campagne(s) validée(s)</p>
        <p v-if="a.statut === 'cloture'" class="detail">Clôturé le {{ dateFr(a.cloture_le) }} par {{ a.cloture_par }}.</p>
        <p v-if="a.statut === 'rouvert'" class="detail">Rouvert par {{ a.rouvert_par }} : « {{ a.motif_reouverture }} ».</p>
        <ul v-if="a.statut !== 'cloture' && a.raisons.length" class="raisons"><li v-for="(r, i) in a.raisons" :key="i">{{ r }}</li></ul>
        <div class="actions">
          <button v-if="a.statut !== 'cloture'" class="vbtn vbtn-primary ecriture" :disabled="a.raisons.length > 0" :data-hint="a.raisons.length ? 'Prérequis non remplis (voir ci-dessus)' : 'Figer les cumuls et verrouiller l\'année'" @click="cloturer(a)"><Lock :size="15" />Clôturer</button>
          <button v-if="a.statut === 'cloture' && estAdmin" class="vbtn vbtn-secondary ecriture" @click="rouvrir(a)"><LockOpen :size="15" />Rouvrir</button>
          <button class="vbtn vbtn-secondary" data-hint="Télécharger les cumuls de l'année par salarié" @click="exporter(a)"><Download :size="15" />Cumuls</button>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); max-width: 1000px; }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-lg, 1.15rem); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.liste { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-4); }
.ex { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-2); }
.tete { display: flex; align-items: center; justify-content: space-between; }
.detail { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.raisons { margin: 0; padding: 8px 12px 8px 26px; background: var(--color-orange-bg); color: var(--color-orange); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.actions { display: flex; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-2); }
.badge.ferme { background: var(--color-rouge-bg); color: var(--color-rouge); } .badge.ouvert { background: var(--color-vert-bg); color: var(--color-vert); }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
