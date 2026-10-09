<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { Plus, Pencil, Power } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import BoutonIcone from '@/components/BoutonIcone.vue'

const peutModifier = aLaPermission(lireUtilisateur(), 'modifier_salaries')
const peutRubriques = aLaPermission(lireUtilisateur(), 'gerer_parametres')

// Chaque onglet a un libellé, une aide courte (infobulle + phrase sous l'onglet).
const ONGLETS = {
  service: { libelle: 'Services', aide: 'Directions ou départements de l\'entreprise (Exploitation, Comptabilité…). Sert de filtre et de regroupement dans les rapports.' },
  section: { libelle: 'Sections', aide: 'Subdivisions d\'un service (atelier, équipe…).' },
  emploi: { libelle: 'Emplois', aide: 'Postes occupés par les salariés (chef d\'atelier, comptable…), affichés sur le bulletin.' },
  categorie: { libelle: 'Catégories', aide: 'Catégories professionnelles de la convention collective ; elles déterminent les grilles de salaire.' },
  site: { libelle: 'Sites', aide: 'Lieux de travail (usine, siège, chantier…).' },
  banque: { libelle: 'Banques', aide: 'Banques de domiciliation des salariés, utilisées pour les ordres de virement.' },
  type_contrat: { libelle: 'Types de contrat', aide: 'CDI, CDD, journalier… Détermine certaines règles (préavis, solde de tout compte).' },
  rub: { libelle: 'Rubriques de paie', aide: 'Lignes que le gestionnaire peut ajouter à un bulletin (primes, acomptes, retenues…). Le type décide de l\'effet sur l\'impôt et le net.' },
}
const TYPES_RUB = { GI: 'Gain imposable', GN: 'Gain non imposable', RI: 'Retenue imposable', RN: 'Retenue non imposable' }

const type = ref('service')
const lignes = ref([])
const rubriques = ref([])
const nouveau = ref({ code: '', libelle: '', type: 'GI' })
const erreur = ref('')
const enEdition = ref(null)

const estRub = computed(() => type.value === 'rub')
const peutAgir = computed(() => (estRub.value ? peutRubriques : peutModifier))
const donnees = computed(() => (estRub.value
  ? rubriques.value.map((r) => ({ ...r, id: r.code }))
  : lignes.value.filter((l) => l.type_ref === type.value)))
const colonnes = computed(() => [
  { cle: 'code', libelle: 'Code', tri: true },
  { cle: 'libelle', libelle: 'Libellé', tri: true },
  ...(estRub.value ? [{ cle: 'type', libelle: 'Type', tri: true, texte: (r) => `${r.type} ${TYPES_RUB[r.type]}` }] : []),
  { cle: 'est_actif', libelle: 'Statut', tri: true, texte: (l) => (l.est_actif ? 'Actif' : 'Désactivé') },
])

async function charger() {
  try { lignes.value = (await apiClient.get('/referentiels', { params: { inclure_inactifs: true } })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function chargerRub() {
  try { rubriques.value = (await apiClient.get('/rubriques', { params: { inclure_inactives: true } })).data } catch (e) { erreur.value = messageErreur(e) }
}
const base = (l) => (estRub.value ? `/rubriques/${l.code}` : `/referentiels/${l.id}`)
const recharger = () => (estRub.value ? chargerRub() : charger())

async function ajouter() {
  erreur.value = ''
  try {
    if (estRub.value) await apiClient.post('/rubriques', nouveau.value)
    else await apiClient.post('/referentiels', { type_ref: type.value, code: nouveau.value.code, libelle: nouveau.value.libelle })
    nouveau.value = { code: '', libelle: '', type: 'GI' }
    await recharger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function basculer(l) {
  erreur.value = ''
  try { await apiClient.patch(base(l), { est_actif: !l.est_actif }); await recharger() } catch (e) { erreur.value = messageErreur(e) }
}
async function renommer(l) {
  erreur.value = ''
  try { await apiClient.patch(base(l), { libelle: enEdition.value.libelle }); enEdition.value = null; await recharger() } catch (e) { erreur.value = messageErreur(e) }
}
function choisir(cle) { type.value = cle; enEdition.value = null; erreur.value = '' }
onMounted(() => { charger(); chargerRub() })
</script>

<template>
  <div class="page">
    <header>
      <h1>Référentiels</h1>
      <p class="sous-titre">Listes utilisées dans la fiche salarié et les bulletins. Un élément déjà utilisé ne se supprime pas : on le désactive.</p>
    </header>
    <div class="puces" role="tablist">
      <button v-for="(o, cle) in ONGLETS" :key="cle" role="tab" :aria-selected="type === cle" :class="['puce', { active: type === cle }]" :data-hint="o.aide" @click="choisir(cle)">{{ o.libelle }}</button>
    </div>
    <p class="aide-onglet">{{ ONGLETS[type].aide }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form v-if="peutAgir" class="ajout ecriture" @submit.prevent="ajouter">
      <input v-model="nouveau.code" class="input code" placeholder="Code" required :maxlength="estRub ? 6 : 20" aria-label="Code" />
      <input v-model="nouveau.libelle" class="input libelle" placeholder="Libellé" required aria-label="Libellé" />
      <select v-if="estRub" v-model="nouveau.type" class="input type" aria-label="Type de rubrique" data-hint="Le type décide de l'effet sur l'impôt et sur le net à payer">
        <option v-for="(l, k) in TYPES_RUB" :key="k" :value="k">{{ k }} — {{ l }}</option>
      </select>
      <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button>
    </form>

    <DataTable :key="type" :colonnes="colonnes" :lignes="donnees" cle-ligne="id" vide="Liste vide." placeholder-recherche="Rechercher un code ou un libellé">
      <template #cell-code="{ ligne }"><code>{{ ligne.code }}</code></template>
      <template #cell-libelle="{ ligne }">
        <form v-if="enEdition?.id === ligne.id" class="edition" @submit.prevent="renommer(ligne)">
          <input v-model="enEdition.libelle" class="input" required aria-label="Nouveau libellé" />
          <button class="vbtn vbtn-primary" type="submit">Enregistrer</button>
          <button class="vbtn vbtn-secondary" type="button" @click="enEdition = null">Annuler</button>
        </form>
        <span v-else :class="{ inactif: !ligne.est_actif }">{{ ligne.libelle }}</span>
      </template>
      <template #cell-type="{ ligne }"><span class="badge badge-info">{{ ligne.type }}</span> <small>{{ TYPES_RUB[ligne.type] }}</small></template>
      <template #cell-est_actif="{ ligne }"><span :class="['badge', ligne.est_actif ? 'badge-ok' : '']">{{ ligne.est_actif ? 'Actif' : 'Désactivé' }}</span></template>
      <template v-if="peutAgir" #actions="{ ligne }">
        <BoutonIcone class="ecriture" :icone="Pencil" hint="Renommer (modifier le libellé)" @click="enEdition = { id: ligne.id, libelle: ligne.libelle }" />
        <BoutonIcone class="ecriture" :icone="Power" :hint="ligne.est_actif ? 'Désactiver : n\'apparaîtra plus dans les listes de choix' : 'Réactiver cet élément'" :danger="ligne.est_actif" @click="basculer(ligne)" />
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.puces { display: flex; gap: 6px; flex-wrap: wrap; }
.puce { border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 999px; padding: 6px 14px; min-height: 36px; font-size: var(--font-size-sm); cursor: pointer; color: var(--color-text-muted); }
.puce:hover:not(.active) { border-color: var(--color-brand); color: var(--color-brand-dark); }
.puce.active { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.aide-onglet { margin: -4px 0 0; padding: 8px 12px; border-left: 3px solid var(--color-accent); background: var(--color-accent-bg); border-radius: 0 var(--radius-md) var(--radius-md) 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.ajout { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.ajout .code { flex: 0 0 120px; min-width: 90px; text-transform: uppercase; }
.ajout .libelle { flex: 0 1 280px; min-width: 160px; }
.ajout .type { flex: 1 1 260px; min-width: 220px; }
.inactif { color: var(--color-text-muted); text-decoration: line-through; }
.edition { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
.edition .input { flex: 1; min-width: 160px; min-height: 36px; }
@media (max-width: 760px) { .page { padding: var(--space-4); } .ajout .code, .ajout .libelle, .ajout .type { flex: 1 1 100%; } }
</style>
