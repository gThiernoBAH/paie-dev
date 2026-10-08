<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { ArrowLeft, Eye, KeyRound, LogOut } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const moi = lireUtilisateur()
const peutModifier = aLaPermission(moi, 'modifier_salaries')
const peutSensible = aLaPermission(moi, 'voir_donnees_sensibles')
const peutComptes = aLaPermission(moi, 'gerer_utilisateurs')

const nouveau = route.params.id === 'nouveau'
const fiche = ref(null)            // fiche telle que renvoyée par le serveur
const f = ref({})                  // formulaire
const origine = ref({})            // copie pour n'envoyer que ce qui change
const refs = ref({})               // listes déroulantes par type
const erreur = ref('')
const message = ref('')
const enCours = ref(false)

const rib = ref(''); const cnps = ref(''); const sensibleCharge = ref(false)
let ribOrigine = ''; let cnpsOrigine = ''
const salaireInitial = ref('')
const sursalaireInitial = ref('')
const historique = ref([])
const nouvelleEvolution = ref({ date_effet: new Date().toISOString().slice(0, 10), montant: '', sursalaire: '', motif: '' })
const compteCree = ref(null)
const sortie = ref({ date_sortie: new Date().toISOString().slice(0, 10), motif_sortie: '' })
const afficherSortie = ref(false)
const partsSuggerees = ref(null)

const CHAMPS = ['nom', 'prenoms', 'sexe', 'date_naissance', 'lieu_naissance', 'nationalite', 'situation_matrimoniale',
  'nombre_enfants', 'nombre_parts', 'nombre_personnes_cmu', 'indemnite_transport', 'telephone', 'email', 'adresse', 'ville', 'date_embauche',
  'type_remuneration', 'eligible_heures_sup', 'mode_paiement']
const LIENS = ['type_contrat', 'service', 'section', 'emploi', 'categorie', 'site', 'banque']
const lectureSeule = computed(() => !peutModifier || (fiche.value && !fiche.value.est_actif))

function versFormulaire(d) {
  const o = {}
  for (const c of CHAMPS) o[c] = d[c] ?? (c === 'nationalite' ? 'Ivoirienne' : '')
  for (const l of LIENS) o[l + '_id'] = d[l]?.id ?? ''
  return o
}

async function charger() {
  try {
    const { data: liste } = await apiClient.get('/referentiels')
    for (const r of liste) (refs.value[r.type_ref] ||= []).push(r)
    if (nouveau) {
      f.value = versFormulaire({ situation_matrimoniale: 'celibataire', nombre_enfants: 0, nombre_parts: 1, nombre_personnes_cmu: 1, type_remuneration: 'mensuel', eligible_heures_sup: true, mode_paiement: 'virement', nationalite: 'Ivoirienne' })
      origine.value = {}
      return
    }
    const { data } = await apiClient.get(`/salaries/${route.params.id}`)
    appliquer(data)
    if (peutSensible) historique.value = (await apiClient.get(`/salaries/${route.params.id}/salaires`)).data
  } catch (e) { erreur.value = messageErreur(e) }
}
function appliquer(d) {
  fiche.value = d; f.value = versFormulaire(d); origine.value = { ...f.value }
}

async function suggererParts() {
  try {
    const { data } = await apiClient.get('/salaries/parts-suggerees', { params: { situation: f.value.situation_matrimoniale, enfants: f.value.nombre_enfants || 0 } })
    partsSuggerees.value = data.parts
  } catch { partsSuggerees.value = null }
}

const nul = (v) => (v === '' || v === undefined ? null : v)
function corps() {
  const out = {}
  for (const k of Object.keys(f.value)) {
    const v = nul(f.value[k])
    if (nouveau ? v !== null : v !== nul(origine.value[k])) out[k] = v
  }
  return out
}

async function enregistrer() {
  if (enCours.value) return
  enCours.value = true; erreur.value = ''; message.value = ''
  try {
    const c = corps()
    // RIB / CNPS : envoyés seulement s'ils ont été saisis ou modifiés (vider un champ affiché l'efface).
    if (rib.value.trim() !== ribOrigine) c.rib = rib.value.trim() || null
    if (cnps.value.trim() !== cnpsOrigine) c.numero_cnps = cnps.value.trim() || null
    if (nouveau) {
      if (salaireInitial.value !== '') c.salaire_base = Number(String(salaireInitial.value).replace(',', '.'))
      if (sursalaireInitial.value !== '') c.sursalaire = Number(String(sursalaireInitial.value).replace(',', '.'))
      const { data } = await apiClient.post('/salaries', c)
      router.replace(`/salaries/${data.id}`)
      return
    }
    if (!Object.keys(c).length) { message.value = 'Aucune modification.'; return }
    const { data } = await apiClient.patch(`/salaries/${fiche.value.id}`, c)
    appliquer(data); rib.value = ''; cnps.value = ''; ribOrigine = ''; cnpsOrigine = ''; sensibleCharge.value = false
    message.value = 'Fiche enregistrée.'
  } catch (e) { erreur.value = messageErreur(e) } finally { enCours.value = false }
}

async function afficherSensibles() {
  try {
    const { data } = await apiClient.get(`/salaries/${fiche.value.id}/donnees-sensibles`)
    rib.value = ribOrigine = data.rib || ''; cnps.value = cnpsOrigine = data.numero_cnps || ''; sensibleCharge.value = true
  } catch (e) { erreur.value = messageErreur(e) }
}

async function ajouterEvolution() {
  erreur.value = ''
  try {
    const e = nouvelleEvolution.value
    const { data } = await apiClient.post(`/salaries/${fiche.value.id}/salaires`, { date_effet: e.date_effet, montant: Number(String(e.montant).replace(',', '.')), sursalaire: Number(String(e.sursalaire || 0).replace(',', '.')), motif: e.motif || null })
    historique.value = data
    nouvelleEvolution.value.montant = ''; nouvelleEvolution.value.sursalaire = ''; nouvelleEvolution.value.motif = ''
    appliquer((await apiClient.get(`/salaries/${fiche.value.id}`)).data)
  } catch (err) { erreur.value = messageErreur(err) }
}
async function creerCompte() {
  erreur.value = ''
  try {
    const { data } = await apiClient.post(`/salaries/${fiche.value.id}/creer-compte`)
    compteCree.value = data.mot_de_passe_temporaire
  } catch (e) { erreur.value = messageErreur(e) }
}
async function declarerSortie() {
  erreur.value = ''
  try { appliquer((await apiClient.post(`/salaries/${fiche.value.id}/sortie`, sortie.value)).data); afficherSortie.value = false } catch (e) { erreur.value = messageErreur(e) }
}
async function reactiver() {
  try { appliquer((await apiClient.post(`/salaries/${fiche.value.id}/reactiver`)).data) } catch (e) { erreur.value = messageErreur(e) }
}
const montant = (n) => Number(n).toLocaleString('fr-FR')
const dateFr = (d) => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR')
onMounted(charger)
</script>

<template>
  <div class="page">
    <button class="retour" @click="router.push('/salaries')"><ArrowLeft :size="16" />Salariés</button>
    <header class="entete">
      <div>
        <h1>{{ nouveau ? 'Nouveau salarié' : `${fiche?.nom || ''} ${fiche?.prenoms || ''}` }}</h1>
        <p v-if="fiche" class="sous-titre">Matricule <strong>{{ fiche.matricule }}</strong>
          <span :class="['badge', fiche.est_actif ? 'badge-ok' : 'badge-erreur']">{{ fiche.est_actif ? 'En activité' : `Sorti le ${dateFr(fiche.date_sortie)}` }}</span></p>
        <p v-else class="sous-titre">Le matricule est attribué automatiquement (6 chiffres).</p>
      </div>
    </header>

    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <form class="grille" @submit.prevent="enregistrer">
      <fieldset class="card bloc" :disabled="lectureSeule"><legend>Identité</legend>
        <label v-if="nouveau" class="field"><span class="field-label">Matricule (facultatif)</span><input v-model="f.matricule" class="input" inputmode="numeric" maxlength="6" placeholder="Automatique" /></label>
        <label class="field"><span class="field-label">Nom</span><input v-model="f.nom" class="input" required /></label>
        <label class="field"><span class="field-label">Prénoms</span><input v-model="f.prenoms" class="input" /></label>
        <label class="field"><span class="field-label">Sexe</span><select v-model="f.sexe" class="input"><option value="">—</option><option value="M">Masculin</option><option value="F">Féminin</option></select></label>
        <label class="field"><span class="field-label">Date de naissance</span><input v-model="f.date_naissance" class="input" type="date" /></label>
        <label class="field"><span class="field-label">Lieu de naissance</span><input v-model="f.lieu_naissance" class="input" /></label>
        <label class="field"><span class="field-label">Nationalité</span><input v-model="f.nationalite" class="input" /></label>
      </fieldset>

      <fieldset class="card bloc" :disabled="lectureSeule"><legend>Coordonnées</legend>
        <label class="field"><span class="field-label">Téléphone</span><input v-model="f.telephone" class="input" inputmode="tel" /></label>
        <label class="field"><span class="field-label">E-mail (bulletins, espace salarié)</span><input v-model="f.email" class="input" type="email" /></label>
        <label class="field"><span class="field-label">Adresse</span><input v-model="f.adresse" class="input" /></label>
        <label class="field"><span class="field-label">Ville</span><input v-model="f.ville" class="input" /></label>
      </fieldset>

      <fieldset class="card bloc" :disabled="lectureSeule"><legend>Famille et impôt</legend>
        <label class="field"><span class="field-label">Situation matrimoniale</span>
          <select v-model="f.situation_matrimoniale" class="input" @change="suggererParts"><option value="celibataire">Célibataire</option><option value="marie">Marié(e)</option><option value="divorce">Divorcé(e)</option><option value="veuf">Veuf / veuve</option></select></label>
        <label class="field"><span class="field-label">Nombre d'enfants à charge</span><input v-model.number="f.nombre_enfants" class="input" type="number" min="0" max="30" @change="suggererParts" /></label>
        <label class="field"><span class="field-label">Nombre de parts (ITS)</span><input v-model.number="f.nombre_parts" class="input" type="number" min="1" max="5" step="0.5" />
          <small v-if="partsSuggerees !== null" class="aide">Suggestion : {{ partsSuggerees }} part(s) <button type="button" class="lien" @click="f.nombre_parts = partsSuggerees">appliquer</button></small>
          <small v-else-if="!nouveau" class="aide">Recalculé automatiquement si vous changez la situation ou les enfants (sauf saisie manuelle).</small></label>
        <label class="field"><span class="field-label">Personnes couvertes CMU</span><input v-model.number="f.nombre_personnes_cmu" class="input" type="number" min="0" max="30" /></label>
      </fieldset>

      <fieldset class="card bloc" :disabled="lectureSeule"><legend>Emploi</legend>
        <label class="field"><span class="field-label">Date d'embauche</span><input v-model="f.date_embauche" class="input" type="date" /></label>
        <label class="field"><span class="field-label">Type de contrat</span><select v-model="f.type_contrat_id" class="input"><option value="">—</option><option v-for="r in refs.type_contrat" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Service</span><select v-model="f.service_id" class="input"><option value="">—</option><option v-for="r in refs.service" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Section</span><select v-model="f.section_id" class="input"><option value="">—</option><option v-for="r in refs.section" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Emploi</span><select v-model="f.emploi_id" class="input"><option value="">—</option><option v-for="r in refs.emploi" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Catégorie</span><select v-model="f.categorie_id" class="input"><option value="">—</option><option v-for="r in refs.categorie" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <label class="field"><span class="field-label">Site</span><select v-model="f.site_id" class="input"><option value="">—</option><option v-for="r in refs.site" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
      </fieldset>

      <fieldset class="card bloc" :disabled="lectureSeule"><legend>Rémunération et paiement</legend>
        <label class="field"><span class="field-label">Type de rémunération</span>
          <select v-model="f.type_remuneration" class="input"><option value="mensuel">Mensuel</option><option value="journalier">Journalier (payé par quinzaine)</option></select></label>
        <label class="case"><input v-model="f.eligible_heures_sup" type="checkbox" /> Éligible aux heures supplémentaires</label>
        <label v-if="nouveau && peutSensible" class="field"><span class="field-label">Salaire catégoriel mensuel (FCFA){{ f.type_remuneration === 'journalier' ? ' — référence mensuelle du journalier (75 000)' : '' }}</span><input v-model="salaireInitial" class="input" inputmode="decimal" /></label>
        <label v-if="nouveau && peutSensible && f.type_remuneration === 'mensuel'" class="field"><span class="field-label">Sursalaire mensuel (FCFA)</span><input v-model="sursalaireInitial" class="input" inputmode="decimal" /></label>
        <label v-if="f.type_remuneration === 'mensuel'" class="field"><span class="field-label">Indemnité de transport convenue (FCFA / mois)</span><input v-model="f.indemnite_transport" class="input" inputmode="decimal" placeholder="Valeur du paramétrage" /></label>
        <label class="field"><span class="field-label">Mode de paiement</span>
          <select v-model="f.mode_paiement" class="input"><option value="virement">Virement</option><option value="especes">Espèces</option><option value="cheque">Chèque</option></select></label>
        <label class="field"><span class="field-label">Banque</span><select v-model="f.banque_id" class="input"><option value="">—</option><option v-for="r in refs.banque" :key="r.id" :value="r.id">{{ r.libelle }}</option></select></label>
        <template v-if="peutSensible">
          <label class="field"><span class="field-label">RIB</span>
            <input v-model="rib" class="input" autocomplete="off" :placeholder="fiche?.a_un_rib && !sensibleCharge ? '•••• enregistré (chiffré)' : 'CI008 01234 012345678901 23'" /></label>
          <label class="field"><span class="field-label">N° CNPS</span>
            <input v-model="cnps" class="input" autocomplete="off" :placeholder="fiche?.a_un_numero_cnps && !sensibleCharge ? '•••• enregistré (chiffré)' : ''" /></label>
          <button v-if="!nouveau && (fiche?.a_un_rib || fiche?.a_un_numero_cnps) && !sensibleCharge" type="button" class="vbtn vbtn-secondary" @click="afficherSensibles"><Eye :size="16" />Afficher RIB et CNPS (consultation tracée)</button>
        </template>
        <p v-else class="aide">RIB, n° CNPS et salaire : visibles uniquement avec le droit « données sensibles ».</p>
      </fieldset>

      <div class="barre-actions" v-if="!lectureSeule">
        <button type="button" class="vbtn vbtn-secondary" @click="router.push('/salaries')">Retour</button>
        <button type="submit" class="vbtn vbtn-primary" :disabled="enCours">{{ enCours ? 'Enregistrement…' : nouveau ? 'Créer le salarié' : 'Enregistrer' }}</button>
      </div>
    </form>

    <section v-if="!nouveau && peutSensible" class="card bloc large">
      <h2>Salaire</h2>
      <p v-if="fiche?.salaire_actuel" class="actuel">{{ montant(fiche.salaire_actuel.montant) }} F <small>catégoriel{{ fiche.salaire_actuel.sursalaire ? ` + ${montant(fiche.salaire_actuel.sursalaire)} F de sursalaire` : '' }} (par mois, depuis le {{ dateFr(fiche.salaire_actuel.date_effet) }})</small></p>
      <p v-else class="aide">Aucun salaire en vigueur.</p>
      <table v-if="historique.length" class="histo">
        <thead><tr><th>À partir du</th><th class="num">Catégoriel</th><th class="num">Sursalaire</th><th>Motif</th><th>Saisi par</th></tr></thead>
        <tbody><tr v-for="e in historique" :key="e.id"><td>{{ dateFr(e.date_effet) }}</td><td class="num">{{ montant(e.montant) }} F</td><td class="num">{{ montant(e.sursalaire) }} F</td><td>{{ e.motif || '' }}</td><td>{{ e.cree_par }}</td></tr></tbody>
      </table>
      <form v-if="peutModifier && fiche?.est_actif" class="ligne-evol" @submit.prevent="ajouterEvolution">
        <input v-model="nouvelleEvolution.date_effet" class="input" type="date" required aria-label="Date d'effet" />
        <input v-model="nouvelleEvolution.montant" class="input" inputmode="decimal" placeholder="Salaire catégoriel" required aria-label="Nouveau salaire catégoriel" />
        <input v-model="nouvelleEvolution.sursalaire" class="input" inputmode="decimal" placeholder="Sursalaire" aria-label="Nouveau sursalaire" />
        <input v-model="nouvelleEvolution.motif" class="input" placeholder="Motif (promotion, ajustement…)" aria-label="Motif" />
        <button class="vbtn vbtn-primary" type="submit">Ajouter</button>
      </form>
    </section>

    <section v-if="!nouveau && fiche && (peutComptes || peutModifier)" class="card bloc large">
      <h2>Accès et départ</h2>
      <div v-if="compteCree" class="mdp-bloc" role="status">Compte créé. Mot de passe temporaire (affiché une seule fois) : <code>{{ compteCree }}</code></div>
      <div class="actions-ligne">
        <button v-if="peutComptes && fiche.est_actif && !compteCree" class="vbtn vbtn-secondary" @click="creerCompte"><KeyRound :size="16" />Ouvrir l'accès espace salarié</button>
        <button v-if="peutModifier && fiche.est_actif" class="vbtn vbtn-secondary" @click="afficherSortie = !afficherSortie"><LogOut :size="16" />Déclarer un départ</button>
        <button v-if="peutModifier && !fiche.est_actif" class="vbtn vbtn-secondary" @click="reactiver">Réactiver le salarié</button>
      </div>
      <form v-if="afficherSortie" class="ligne-evol" @submit.prevent="declarerSortie">
        <input v-model="sortie.date_sortie" class="input" type="date" required aria-label="Date de sortie" />
        <input v-model="sortie.motif_sortie" class="input" placeholder="Motif (démission, licenciement, fin de contrat…)" required minlength="2" aria-label="Motif de sortie" />
        <button class="vbtn vbtn-danger" type="submit">Confirmer le départ</button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); max-width: 1200px; }
.retour { align-self: flex-start; border: none; background: none; color: var(--color-brand); cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: var(--font-size-sm); min-height: 36px; padding: 0; }
h1 { margin: 0; font-size: var(--font-size-xl); }
h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); display: flex; gap: 10px; align-items: center; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: var(--space-4); align-items: start; }
.bloc { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); border: 1px solid var(--color-border); min-width: 0; }
fieldset.bloc { margin: 0; }
legend { font-weight: 700; font-size: var(--font-size-base); padding: 0 8px; color: var(--color-brand-dark); }
.large { grid-column: 1 / -1; }
.case { display: flex; align-items: center; gap: 10px; font-size: var(--font-size-sm); min-height: 36px; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.lien { border: none; background: none; color: var(--color-brand); cursor: pointer; text-decoration: underline; padding: 0; font-size: inherit; }
.barre-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-3); }
.actuel { margin: 0; font-size: var(--font-size-xl); font-weight: 700; color: var(--color-brand-dark); }
.actuel small { font-size: var(--font-size-sm); font-weight: 400; color: var(--color-text-muted); }
.histo { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.histo th { text-align: left; color: var(--color-text-muted); padding: 8px 10px; border-bottom: 1px solid var(--color-border); }
.histo td { padding: 8px 10px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.ligne-evol { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.ligne-evol .input { flex: 1; min-width: 150px; }
.actions-ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.mdp-bloc { background: var(--color-orange-bg); color: var(--color-orange); padding: 12px 16px; border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.mdp-bloc code { font-size: var(--font-size-base); font-weight: 700; user-select: all; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
