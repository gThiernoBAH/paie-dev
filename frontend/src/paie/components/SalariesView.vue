<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { Plus, Search } from 'lucide-vue-next'

const router = useRouter()
const peutCreer = aLaPermission(lireUtilisateur(), 'modifier_salaries')

const page = ref(1)
const taille = 50
const total = ref(0)
const elements = ref([])
const services = ref([])
const filtres = ref({ recherche: '', service_id: '', type_remuneration: '', statut: 'actifs' })
const erreur = ref('')
const chargement = ref(false)
const pages = computed(() => Math.max(1, Math.ceil(total.value / taille)))

async function charger() {
  chargement.value = true; erreur.value = ''
  try {
    const params = { page: page.value, taille }
    for (const [k, v] of Object.entries(filtres.value)) if (v) params[k] = v
    const { data } = await apiClient.get('/salaries', { params })
    elements.value = data.elements; total.value = data.total
  } catch (e) { erreur.value = messageErreur(e) } finally { chargement.value = false }
}
let minuteur
watch(filtres, () => { clearTimeout(minuteur); minuteur = setTimeout(() => { page.value = 1; charger() }, 250) }, { deep: true })
function aller(p) { page.value = Math.min(Math.max(1, p), pages.value); charger() }
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
      <button v-if="peutCreer" class="vbtn vbtn-primary" @click="router.push('/salaries/nouveau')"><Plus :size="16" />Nouveau salarié</button>
    </header>

    <div class="filtres">
      <label class="recherche"><Search :size="16" /><input v-model="filtres.recherche" placeholder="Matricule ou nom…" aria-label="Rechercher un salarié" /></label>
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
    </div>

    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <div class="card tableau-cadre">
      <table>
        <thead><tr><th>Matricule</th><th>Nom</th><th>Service</th><th>Emploi</th><th>Type</th><th>Embauche</th><th>Statut</th></tr></thead>
        <tbody>
          <tr v-for="s in elements" :key="s.id" class="cliquable" tabindex="0" @click="router.push(`/salaries/${s.id}`)" @keydown.enter="router.push(`/salaries/${s.id}`)">
            <td><strong class="mat">{{ s.matricule }}</strong></td>
            <td>{{ s.nom }} {{ s.prenoms }}</td>
            <td>{{ s.service?.libelle || '—' }}</td>
            <td>{{ s.emploi?.libelle || '—' }}</td>
            <td><span class="badge" :class="s.type_remuneration === 'journalier' ? 'badge-info' : ''">{{ s.type_remuneration === 'journalier' ? 'Journalier' : 'Mensuel' }}</span></td>
            <td class="nowrap">{{ dateFr(s.date_embauche) }}</td>
            <td><span :class="['badge', s.est_actif ? 'badge-ok' : 'badge-erreur']">{{ s.est_actif ? 'En activité' : 'Sorti' }}</span></td>
          </tr>
          <tr v-if="!chargement && !elements.length"><td colspan="7" class="vide">Aucun salarié.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="pagination">
      <span>Page {{ page }} / {{ pages }}</span>
      <div>
        <button class="vbtn vbtn-secondary" :disabled="page <= 1" @click="aller(page - 1)">Précédent</button>
        <button class="vbtn vbtn-secondary" :disabled="page >= pages" @click="aller(page + 1)">Suivant</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
.entete { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); flex-wrap: wrap; }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.filtres { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.recherche { display: flex; align-items: center; gap: 8px; border: 1px solid #C9D2DD; border-radius: var(--radius-md); padding: 0 12px; background: var(--color-surface); min-height: var(--touch-target-min); color: var(--color-text-muted); }
.recherche input { border: none; outline: none; font-size: var(--font-size-sm); background: none; min-width: 200px; }
.court { width: auto; min-width: 190px; }
.tableau-cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 10px 14px; border-bottom: 1px solid var(--color-border); }
.mat { font-variant-numeric: tabular-nums; letter-spacing: .5px; }
.nowrap { white-space: nowrap; }
.cliquable { cursor: pointer; }
.cliquable:hover, .cliquable:focus-visible { background: #F6F9FC; outline: none; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.pagination { display: flex; justify-content: space-between; align-items: center; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.pagination > div { display: flex; gap: var(--space-2); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
