<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { Plus } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'

const router = useRouter()
const peutCreer = aLaPermission(lireUtilisateur(), 'modifier_salaries')

const total = ref(0)
const elements = ref([])
const services = ref([])
const filtres = ref({ service_id: '', type_remuneration: '', statut: 'actifs' })
const requete = ref({ page: 1, taille: 25, tri: 'matricule', sens: 'asc', recherche: '' })
const tableau = ref(null)
const erreur = ref('')
const chargement = ref(false)

const colonnes = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Nom', tri: true },
  { cle: 'service', libelle: 'Service', tri: true },
  { cle: 'emploi', libelle: 'Emploi', tri: true },
  { cle: 'type_remuneration', libelle: 'Type', tri: true },
  { cle: 'date_embauche', libelle: 'Embauche', tri: true },
  { cle: 'est_actif', libelle: 'Statut', tri: true },
]

async function charger() {
  chargement.value = true; erreur.value = ''
  try {
    const r = requete.value
    const params = { page: r.page, taille: r.taille, tri: r.tri, sens: r.sens }
    if (r.recherche) params.recherche = r.recherche
    for (const [k, v] of Object.entries(filtres.value)) if (v) params[k] = v
    const { data } = await apiClient.get('/salaries', { params })
    elements.value = data.elements; total.value = data.total
  } catch (e) { erreur.value = messageErreur(e) } finally { chargement.value = false }
}
function changer(e) { requete.value = { ...e }; charger() }
watch(filtres, () => { tableau.value?.reinitialiser(); requete.value.page = 1; charger() }, { deep: true })
const dateFr = (d) => (d ? new Date(d + 'T00:00:00').toLocaleDateString('fr-FR') : '—')

onMounted(async () => {
  charger()
  try { services.value = (await apiClient.get('/referentiels', { params: { type_ref: 'service' } })).data } catch { /* filtre facultatif */ }
})
</script>

<template>
  <div class="page">
    <header class="entete">
      <div>
        <h1>Salariés</h1>
        <p class="sous-titre">{{ total }} salarié(s) correspondent aux filtres.</p>
      </div>
      <button v-if="peutCreer" class="vbtn vbtn-primary ecriture" @click="router.push('/salaries/nouveau')"><Plus :size="16" />Nouveau salarié</button>
    </header>

    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <DataTable ref="tableau" serveur :colonnes="colonnes" :lignes="elements" :total="total" :chargement="chargement" ligne-cliquable
               placeholder-recherche="Matricule ou nom…" vide="Aucun salarié." @ligne="(s) => router.push(`/salaries/${s.id}`)" @changer="changer">
      <template #outils>
        <select v-model="filtres.service_id" class="input court" aria-label="Service">
          <option value="">Tous les services</option>
          <option v-for="s in services" :key="s.id" :value="s.id">{{ s.libelle }}</option>
        </select>
        <select v-model="filtres.type_remuneration" class="input court" aria-label="Type de rémunération">
          <option value="">Mensuels et journaliers</option><option value="mensuel">Mensuels</option><option value="journalier">Journaliers</option>
        </select>
        <select v-model="filtres.statut" class="input court" aria-label="Statut">
          <option value="actifs">En activité</option><option value="sortis">Sortis</option><option value="tous">Tous</option>
        </select>
      </template>
      <template #cell-matricule="{ ligne }"><strong class="mat">{{ ligne.matricule }}</strong></template>
      <template #cell-nom="{ ligne }">{{ ligne.nom }} {{ ligne.prenoms }}</template>
      <template #cell-service="{ ligne }">{{ ligne.service?.libelle || '—' }}</template>
      <template #cell-emploi="{ ligne }">{{ ligne.emploi?.libelle || '—' }}</template>
      <template #cell-type_remuneration="{ ligne }"><span class="badge" :class="ligne.type_remuneration === 'journalier' ? 'badge-info' : ''">{{ ligne.type_remuneration === 'journalier' ? 'Journalier' : 'Mensuel' }}</span></template>
      <template #cell-date_embauche="{ ligne }"><span class="nowrap">{{ dateFr(ligne.date_embauche) }}</span></template>
      <template #cell-est_actif="{ ligne }"><span :class="['badge', ligne.est_actif ? 'badge-ok' : 'badge-erreur']">{{ ligne.est_actif ? 'En activité' : 'Sorti' }}</span></template>
    </DataTable>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
.entete { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); flex-wrap: wrap; }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.court { width: auto; min-width: 190px; min-height: 40px; }
.mat { font-variant-numeric: tabular-nums; letter-spacing: .5px; }
.nowrap { white-space: nowrap; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
