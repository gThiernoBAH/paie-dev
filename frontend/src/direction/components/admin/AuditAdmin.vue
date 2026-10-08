<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'

const elements = ref([])
const total = ref(0)
const page = ref(1)
const taille = 50
const filtres = ref({ action: '', acteur: '', du: '', au: '' })
const erreur = ref('')
const chargement = ref(false)

const pages = computed(() => Math.max(1, Math.ceil(total.value / taille)))

async function charger() {
  chargement.value = true
  erreur.value = ''
  try {
    const params = { page: page.value, taille }
    for (const [k, v] of Object.entries(filtres.value)) if (v) params[k] = v.trim?.() ?? v
    const { data } = await apiClient.get('/admin/audit', { params })
    elements.value = data.elements
    total.value = data.total
  } catch (e) {
    erreur.value = messageErreur(e)
  } finally {
    chargement.value = false
  }
}
function filtrer() { page.value = 1; charger() }
function aller(p) { page.value = Math.min(Math.max(1, p), pages.value); charger() }
const formatDate = (iso) => new Date(iso).toLocaleString('fr-FR')
const detailTexte = (d) => (d == null ? '' : typeof d === 'string' ? d : JSON.stringify(d))

onMounted(charger)
</script>

<template>
  <section class="bloc">
    <form class="filtres" @submit.prevent="filtrer">
      <label class="field"><span class="field-label">Action</span><input v-model="filtres.action" class="input" placeholder="ex. connexion_reussie" /></label>
      <label class="field"><span class="field-label">Acteur</span><input v-model="filtres.acteur" class="input" placeholder="matricule" /></label>
      <label class="field"><span class="field-label">Du</span><input v-model="filtres.du" class="input" type="date" /></label>
      <label class="field"><span class="field-label">Au</span><input v-model="filtres.au" class="input" type="date" /></label>
      <button class="vbtn vbtn-primary" type="submit">Filtrer</button>
    </form>

    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <div class="card tableau-cadre">
      <table>
        <thead><tr><th>Date</th><th>Acteur</th><th>Action</th><th>Cible</th><th>Détail</th><th>IP</th></tr></thead>
        <tbody>
          <tr v-for="l in elements" :key="l.id">
            <td class="nowrap">{{ formatDate(l.horodatage) }}</td>
            <td>{{ l.acteur_identifiant || '—' }}</td>
            <td><span class="badge badge-info">{{ l.action }}</span></td>
            <td>{{ [l.cible_type, l.cible_id].filter(Boolean).join(' #') || '—' }}</td>
            <td class="detail">{{ detailTexte(l.detail) }}</td>
            <td class="nowrap">{{ l.adresse_ip || '—' }}</td>
          </tr>
          <tr v-if="!chargement && !elements.length"><td colspan="6" class="vide">Aucune entrée.</td></tr>
        </tbody>
      </table>
    </div>

    <div class="pagination">
      <span>{{ total }} entrée(s)</span>
      <div>
        <button class="vbtn vbtn-secondary" :disabled="page <= 1" @click="aller(page - 1)">Précédent</button>
        <span class="page-n">{{ page }} / {{ pages }}</span>
        <button class="vbtn vbtn-secondary" :disabled="page >= pages" @click="aller(page + 1)">Suivant</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.filtres { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.filtres .field { min-width: 150px; }
.tableau-cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 10px 14px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.nowrap { white-space: nowrap; }
.detail { max-width: 340px; word-break: break-word; color: var(--color-text-muted); font-size: var(--font-size-xs); }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.pagination { display: flex; justify-content: space-between; align-items: center; font-size: var(--font-size-sm); color: var(--color-text-muted); flex-wrap: wrap; gap: var(--space-2); }
.pagination > div { display: flex; align-items: center; gap: var(--space-2); }
.page-n { min-width: 60px; text-align: center; }
</style>
