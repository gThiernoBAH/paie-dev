<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { Plus } from 'lucide-vue-next'

const peutModifier = aLaPermission(lireUtilisateur(), 'modifier_salaries')
const TYPES = {
  service: 'Services', section: 'Sections', emploi: 'Emplois', categorie: 'Catégories',
  site: 'Sites', banque: 'Banques', type_contrat: 'Types de contrat',
}
const type = ref('service')
const lignes = ref([])
const nouveau = ref({ code: '', libelle: '' })
const erreur = ref('')
const enEdition = ref(null)

const visibles = computed(() => lignes.value.filter((l) => l.type_ref === type.value))
async function charger() {
  try { lignes.value = (await apiClient.get('/referentiels', { params: { inclure_inactifs: true } })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function ajouter() {
  erreur.value = ''
  try {
    await apiClient.post('/referentiels', { type_ref: type.value, code: nouveau.value.code, libelle: nouveau.value.libelle })
    nouveau.value = { code: '', libelle: '' }
    await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function basculer(l) {
  erreur.value = ''
  try { await apiClient.patch(`/referentiels/${l.id}`, { est_actif: !l.est_actif }); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function renommer(l) {
  erreur.value = ''
  try { await apiClient.patch(`/referentiels/${l.id}`, { libelle: enEdition.value.libelle }); enEdition.value = null; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Référentiels</h1>
      <p class="sous-titre">Listes utilisées dans la fiche salarié. Un élément déjà utilisé ne se supprime pas : on le désactive.</p>
    </header>
    <div class="puces">
      <button v-for="(lib, cle) in TYPES" :key="cle" :class="['puce', { active: type === cle }]" @click="type = cle">{{ lib }}</button>
    </div>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form v-if="peutModifier" class="ajout" @submit.prevent="ajouter">
      <input v-model="nouveau.code" class="input code" placeholder="Code" required maxlength="20" aria-label="Code" />
      <input v-model="nouveau.libelle" class="input" placeholder="Libellé" required aria-label="Libellé" />
      <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button>
    </form>

    <div class="card tableau-cadre">
      <table>
        <thead><tr><th>Code</th><th>Libellé</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          <tr v-for="l in visibles" :key="l.id">
            <td><code>{{ l.code }}</code></td>
            <td>
              <form v-if="enEdition?.id === l.id" class="edition" @submit.prevent="renommer(l)">
                <input v-model="enEdition.libelle" class="input" required aria-label="Nouveau libellé" /><button class="vbtn vbtn-primary" type="submit">OK</button>
              </form>
              <span v-else :class="{ inactif: !l.est_actif }">{{ l.libelle }}</span>
            </td>
            <td><span :class="['badge', l.est_actif ? 'badge-ok' : '']">{{ l.est_actif ? 'Actif' : 'Désactivé' }}</span></td>
            <td class="actions">
              <template v-if="peutModifier">
                <button class="vbtn vbtn-secondary" @click="enEdition = { id: l.id, libelle: l.libelle }">Renommer</button>
                <button class="vbtn vbtn-secondary" @click="basculer(l)">{{ l.est_actif ? 'Désactiver' : 'Réactiver' }}</button>
              </template>
            </td>
          </tr>
          <tr v-if="!visibles.length"><td colspan="4" class="vide">Liste vide.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.puces { display: flex; gap: 6px; flex-wrap: wrap; }
.puce { border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 999px; padding: 6px 14px; min-height: 36px; font-size: var(--font-size-sm); cursor: pointer; color: #475467; }
.puce.active { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.ajout { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.ajout .input { flex: 1; min-width: 180px; }
.ajout .code { flex: 0 0 140px; min-width: 100px; text-transform: uppercase; }
.tableau-cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 14px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.inactif { color: var(--color-text-muted); text-decoration: line-through; }
.actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
.edition { display: flex; gap: var(--space-2); }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
