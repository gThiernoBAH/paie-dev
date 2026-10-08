<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus, Check, X } from 'lucide-vue-next'

const onglet = ref('demandes')
const conges = ref([])
const soldes = ref([])
const erreur = ref('')
const message = ref('')
const recherche = ref('')
const filtre = ref('demande')
const nouveau = ref({ matricule: '', type_conge: 'annuel', debut: '', fin: '', motif: '' })
const LIB = { demande: 'À traiter', approuve: 'Approuvé', refuse: 'Refusé', annule: 'Annulé' }
const TYPES = { annuel: 'Congé annuel', maladie: 'Maladie', maternite: 'Maternité', exceptionnel: 'Exceptionnel', sans_solde: 'Sans solde' }
const dateFr = (d) => d.split('-').reverse().join('/')

async function trouver(matricule) {
  const { data } = await apiClient.get('/salaries', { params: { recherche: matricule.trim(), statut: 'tous', taille: 5 } })
  const m = data.elements.find((s) => s.matricule === matricule.trim().padStart(6, '0'))
  if (!m) throw new Error('Matricule introuvable.')
  return m
}
async function charger() {
  try { conges.value = (await apiClient.get('/conges', { params: filtre.value ? { statut: filtre.value } : {} })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function chargerSoldes() {
  try { soldes.value = (await apiClient.get('/conges/soldes', { params: recherche.value ? { recherche: recherche.value } : {} })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function demander() {
  erreur.value = ''; message.value = ''
  try {
    const s = await trouver(nouveau.value.matricule)
    const { data } = await apiClient.post('/conges', { salarie_id: s.id, type_conge: nouveau.value.type_conge, debut: nouveau.value.debut, fin: nouveau.value.fin, motif: nouveau.value.motif || null })
    message.value = `Demande enregistrée : ${data.jours_ouvrables} jour(s) ouvrable(s).`
    nouveau.value = { matricule: '', type_conge: 'annuel', debut: '', fin: '', motif: '' }
    await charger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function decider(c, decision) {
  erreur.value = ''; message.value = ''
  try { await apiClient.post(`/conges/${c.id}/decision`, { decision }); await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function definirSolde(s) {
  const v = window.prompt(`Solde de congés de ${s.matricule} à reprendre (jours ouvrables) :`, s.initial)
  if (v === null) return
  const d = window.prompt('À la date du (AAAA-MM-JJ) :', new Date().toLocaleDateString('sv-SE'))
  if (!d) return
  try { await apiClient.put(`/salaries/${s.salarie_id}/solde-conges`, { solde_initial: v.replace(',', '.'), date_reference: d }); await chargerSoldes() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(() => { charger(); chargerSoldes() })
</script>

<template>
  <div class="page">
    <header>
      <h1>Congés</h1>
      <p class="sous-titre">Demandes, approbation et soldes. Le solde acquis suit le paramètre « jours ouvrables acquis par mois » (Paramétrage → Congés).</p>
    </header>
    <div class="onglets" role="tablist">
      <button v-for="(lib, cle) in { demandes: 'Demandes', soldes: 'Soldes' }" :key="cle" role="tab" :class="['onglet', { actif: onglet === cle }]" @click="onglet = cle">{{ lib }}</button>
    </div>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <section v-if="onglet === 'demandes'" class="bloc">
      <form class="ligne card saisie" @submit.prevent="demander">
        <strong>Nouvelle demande</strong>
        <input v-model="nouveau.matricule" class="input" placeholder="Matricule" required inputmode="numeric" aria-label="Matricule" />
        <select v-model="nouveau.type_conge" class="input" aria-label="Type"><option v-for="(l, k) in TYPES" :key="k" :value="k">{{ l }}</option></select>
        <input v-model="nouveau.debut" type="date" class="input" required aria-label="Début" />
        <input v-model="nouveau.fin" type="date" class="input" required aria-label="Fin" />
        <input v-model="nouveau.motif" class="input" placeholder="Motif" aria-label="Motif" />
        <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Enregistrer</button>
      </form>
      <div class="ligne">
        <label class="field"><span class="field-label">Afficher</span>
          <select v-model="filtre" class="input" @change="charger"><option value="">Tous</option><option v-for="(l, k) in LIB" :key="k" :value="k">{{ l }}</option></select></label>
      </div>
      <div class="card cadre"><table>
        <thead><tr><th>Matricule</th><th>Salarié</th><th>Type</th><th>Du</th><th>Au</th><th class="num">Jours ouvrables</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in conges" :key="c.id">
            <td>{{ c.matricule }}</td><td>{{ c.nom }}</td><td>{{ TYPES[c.type_conge] }}</td><td class="nowrap">{{ dateFr(c.debut) }}</td><td class="nowrap">{{ dateFr(c.fin) }}</td>
            <td class="num">{{ c.jours_ouvrables }}</td><td><span class="badge">{{ LIB[c.statut] }}</span></td>
            <td class="nowrap">
              <template v-if="c.statut === 'demande'">
                <button class="icone-ok" :aria-label="`Approuver le congé de ${c.matricule}`" @click="decider(c, 'approuver')"><Check :size="16" /></button>
                <button class="icone" :aria-label="`Refuser le congé de ${c.matricule}`" @click="decider(c, 'refuser')"><X :size="16" /></button>
              </template>
              <button v-else-if="c.statut === 'approuve'" class="vbtn vbtn-secondary petit" @click="decider(c, 'annuler')">Annuler</button>
            </td>
          </tr>
          <tr v-if="!conges.length"><td colspan="8" class="vide">Aucune demande.</td></tr>
        </tbody></table></div>
    </section>

    <section v-if="onglet === 'soldes'" class="bloc">
      <form class="ligne" @submit.prevent="chargerSoldes">
        <label class="field"><span class="field-label">Recherche</span><input v-model="recherche" class="input" placeholder="Matricule ou nom" /></label>
        <button class="vbtn vbtn-secondary" type="submit">Filtrer</button>
      </form>
      <div class="card cadre"><table>
        <thead><tr><th>Matricule</th><th>Salarié</th><th class="num">Reprise</th><th class="num">Acquis</th><th class="num">Pris</th><th class="num">Solde</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in soldes" :key="s.salarie_id">
            <td>{{ s.matricule }}</td><td>{{ s.nom }}</td><td class="num">{{ s.initial }}</td><td class="num">{{ s.acquis }}</td><td class="num">{{ s.pris }}</td><td class="num"><strong>{{ s.solde }}</strong></td>
            <td><button class="vbtn vbtn-secondary petit" @click="definirSolde(s)">Reprendre un solde</button></td>
          </tr>
          <tr v-if="!soldes.length"><td colspan="7" class="vide">Aucun salarié.</td></tr>
        </tbody></table></div>
      <p class="aide">« Reprendre un solde » sert à la mise en route : le solde connu à une date donnée, les droits s'accumulant ensuite.</p>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 720px; }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); }
.onglet { padding: 10px 16px; min-height: 44px; border: none; background: none; cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.onglet.actif { color: var(--color-brand-dark); border-bottom-color: var(--color-brand); }
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.saisie { padding: var(--space-3) var(--space-4); align-items: center; } .saisie .input { width: auto; min-width: 120px; flex: 1; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 14px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; } .nowrap { white-space: nowrap; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.icone, .icone-ok { border: none; background: none; cursor: pointer; width: 36px; height: 36px; } .icone { color: var(--color-rouge); } .icone-ok { color: var(--color-vert); }
.petit { padding: 4px 10px; min-height: 32px; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
