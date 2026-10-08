<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { aLaPermission, lireUtilisateur } from '@/api/session'
import { Plus } from 'lucide-vue-next'

const router = useRouter()
const peutCreer = aLaPermission(lireUtilisateur(), 'lancer_paie')
const campagnes = ref([])
const erreur = ref('')
const aujourdhui = new Date()
const nouvelle = ref({ type_campagne: 'mensuelle', annee: aujourdhui.getFullYear(), mois: aujourdhui.getMonth() + 1, debut: '', fin: '' })
const LIBELLES = { ouverte: 'Ouverte', calculee: 'Calculée', validee: 'Validée', cloturee: 'Clôturée' }
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
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Campagnes de paie</h1>
      <p class="sous-titre">Une campagne = une période payée : le mois pour les mensuels, une quinzaine (ou autre découpage) pour les journaliers. Plusieurs campagnes par mois sont possibles.</p>
    </header>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form v-if="peutCreer" class="ligne card saisie" @submit.prevent="creer">
      <strong>Nouvelle campagne</strong>
      <select v-model="nouvelle.type_campagne" class="input" aria-label="Type">
        <option value="mensuelle">Mensuelle</option>
        <option value="journaliere">Journaliers (période libre)</option>
        <option value="exceptionnelle">Exceptionnelle (mensuels, période libre)</option>
      </select>
      <input v-model.number="nouvelle.annee" type="number" class="input court" aria-label="Année" required />
      <input v-model.number="nouvelle.mois" type="number" min="1" max="12" class="input court" aria-label="Mois" required />
      <template v-if="nouvelle.type_campagne !== 'mensuelle'">
        <input v-model="nouvelle.debut" type="date" class="input" aria-label="Début" required />
        <input v-model="nouvelle.fin" type="date" class="input" aria-label="Fin" required />
      </template>
      <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Créer</button>
    </form>

    <div class="card cadre">
      <table>
        <thead><tr><th>Campagne</th><th>Période</th><th>Statut</th><th class="num">Salariés</th><th class="num">Bulletins</th><th class="num">Net à payer</th></tr></thead>
        <tbody>
          <tr v-for="c in campagnes" :key="c.id" class="cliquable" @click="router.push(`/campagnes/${c.id}`)">
            <td><router-link :to="`/campagnes/${c.id}`">{{ c.libelle }}</router-link></td>
            <td class="nowrap">{{ c.debut.split('-').reverse().join('/') }} → {{ c.fin.split('-').reverse().join('/') }}</td>
            <td><span :class="['badge', 'st-' + c.statut]">{{ LIBELLES[c.statut] }}</span></td>
            <td class="num">{{ c.nb_salaries }}</td><td class="num">{{ c.nb_bulletins }}</td><td class="num">{{ fmt(c.total_net) }}</td>
          </tr>
          <tr v-if="!campagnes.length"><td colspan="6" class="vide">Aucune campagne. Créez la première ci-dessus.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 720px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.saisie { padding: var(--space-3) var(--space-4); align-items: center; }
.saisie .input { width: auto; min-width: 130px; } .saisie .court { min-width: 90px; max-width: 100px; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 10px 14px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; } .nowrap { white-space: nowrap; }
.cliquable { cursor: pointer; } .cliquable:hover { background: #F8FAFC; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.st-validee, .st-cloturee { background: var(--color-vert-bg); color: var(--color-vert); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
