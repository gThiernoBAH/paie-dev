<script setup>
import { ref, onMounted, watch } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import DataTable from '@/components/DataTable.vue'

const elements = ref([])
const total = ref(0)
const requete = ref({ page: 1, taille: 25, tri: 'horodatage', sens: 'desc' })
const tableau = ref(null)
const filtres = ref({ action: '', acteur: '', du: '', au: '' })
const erreur = ref('')
const chargement = ref(false)

const formatDate = (iso) => new Date(iso).toLocaleString('fr-FR')
const detailTexte = (d) => (d == null ? '' : typeof d === 'string' ? d : JSON.stringify(d))
const colonnes = [
  { cle: 'horodatage', libelle: 'Date', tri: true, format: (v) => formatDate(v) },
  { cle: 'acteur_identifiant', libelle: 'Acteur', tri: true, format: (v) => v || '—' },
  { cle: 'action', libelle: 'Action', tri: true },
  { cle: 'cible_type', libelle: 'Cible', tri: true },
  { cle: 'detail', libelle: 'Détail' },
  { cle: 'adresse_ip', libelle: 'IP', tri: true },
]

async function charger() {
  chargement.value = true; erreur.value = ''
  try {
    const r = requete.value
    const params = { page: r.page, taille: r.taille, tri: r.tri === 'horodatage' ? 'horodatage' : r.tri, sens: r.sens }
    for (const [k, v] of Object.entries(filtres.value)) if (v) params[k] = v.trim?.() ?? v
    const { data } = await apiClient.get('/admin/audit', { params })
    elements.value = data.elements; total.value = data.total
  } catch (e) { erreur.value = messageErreur(e) } finally { chargement.value = false }
}
function changer(e) { requete.value = { ...e, tri: e.tri || 'horodatage' }; charger() }
function filtrer() { tableau.value?.reinitialiser(); requete.value.page = 1; charger() }
onMounted(charger)
</script>

<template>
  <section class="bloc">
    <form class="filtres" @submit.prevent="filtrer">
      <label class="field"><span class="field-label">Action</span><input v-model="filtres.action" class="input" placeholder="ex. connexion_reussie" /></label>
      <label class="field"><span class="field-label">Acteur</span><input v-model="filtres.acteur" class="input" placeholder="matricule" /></label>
      <label class="field"><span class="field-label">Du</span><input v-model="filtres.du" class="input" type="date" /></label>
      <label class="field"><span class="field-label">Au</span><input v-model="filtres.au" class="input" type="date" /></label>
      <button class="vbtn vbtn-primary" type="submit" data-hint="Appliquer les filtres au journal">Filtrer</button>
    </form>

    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <DataTable ref="tableau" serveur :recherche="false" :colonnes="colonnes" :lignes="elements" :total="total" :chargement="chargement" tri-initial="horodatage" sens-initial="desc" vide="Aucune entrée." @changer="changer">
      <template #cell-action="{ ligne }"><span class="badge badge-info">{{ ligne.action }}</span></template>
      <template #cell-cible_type="{ ligne }">{{ [ligne.cible_type, ligne.cible_id].filter(Boolean).join(' #') || '—' }}</template>
      <template #cell-detail="{ ligne }"><span class="detail">{{ detailTexte(ligne.detail) }}</span></template>
    </DataTable>
  </section>
</template>

<style scoped>
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.filtres { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.filtres .field { min-width: 150px; }
.detail { display: block; max-width: 340px; word-break: break-word; color: var(--color-text-muted); font-size: var(--font-size-xs); }
</style>
