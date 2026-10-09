<script setup>
import DataTable from '@/components/DataTable.vue'
import { useEcran } from '@/composables/useEcran'
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { X, AlertTriangle, CheckCircle2, Search } from 'lucide-vue-next'
import EditeurBareme from './parametrage/EditeurBareme.vue'

const utilisateur = lireUtilisateur()
const { mobile: surTelephone } = useEcran()
const peutModifier = computed(() => aLaPermission(utilisateur, 'gerer_parametres') && !surTelephone.value)

const CATEGORIES = {
  entreprise: 'Entreprise', general: 'Général', cnps: 'CNPS', fdfp: 'FDFP', its: 'ITS', cmu: 'CMU',
  heures_sup: 'Heures supplémentaires', anciennete: 'Ancienneté', indemnites: 'Indemnités', conges: 'Congés',
  journaliers: 'Journaliers', licenciement: 'Licenciement', pointages: 'Pointages', bulletin: 'Bulletin de paie', grille: 'Grille salariale', comptabilite: 'Comptabilité', email: 'E-mail',
}
const parametres = ref([])
const etat = ref(null)
const categorie = ref('')
const seulementAConfirmer = ref(false)
const recherche = ref('')
const erreur = ref('')
const message = ref('')

const categoriesPresentes = computed(() => {
  const n = {}
  for (const p of parametres.value) n[p.categorie] = (n[p.categorie] || 0) + (p.valeur_courante?.statut === 'a_confirmer' ? 1 : 0)
  return Object.keys(CATEGORIES).filter((c) => c in n).map((c) => ({ cle: c, libelle: CATEGORIES[c], aConfirmer: n[c] }))
})
const affiches = computed(() => {
  const m = recherche.value.trim().toLowerCase()
  return parametres.value.filter((p) =>
    (!categorie.value || p.categorie === categorie.value) &&
    (!seulementAConfirmer.value || p.valeur_courante?.statut === 'a_confirmer') &&
    (!m || p.libelle.toLowerCase().includes(m) || p.cle.includes(m)))
})

async function charger() {
  erreur.value = ''
  try {
    const [l, e] = await Promise.all([apiClient.get('/parametres'), apiClient.get('/parametres/etat')])
    const rang = Object.keys(CATEGORIES)
    parametres.value = [...l.data].sort((a, b) => rang.indexOf(a.categorie) - rang.indexOf(b.categorie)) // tri stable : l'ordre de l'API est conservé dans chaque catégorie
    etat.value = e.data
  } catch (e) { erreur.value = messageErreur(e) }
}

// ----- Affichage des valeurs -----
const nombre = (v) => Number(v).toLocaleString('fr-FR', { maximumFractionDigits: 4 })
function formater(p, v = p.valeur_courante?.valeur) {
  if (v == null) return '—'
  switch (p.type_valeur) {
    case 'montant': return `${nombre(v)} F`
    case 'pourcentage': return `${nombre(v)} %`
    case 'booleen': return v === 'true' ? 'Oui' : 'Non'
    case 'bareme': { try { return `${JSON.parse(v).length} tranches` } catch { return 'Barème' } }
    case 'decimal': case 'entier': return `${nombre(v)}${p.unite ? ' ' + p.unite : ''}`
    default: return v
  }
}
const dateFr = (d) => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR')

// ----- Panneau d'édition -----
const choisi = ref(null)         // détail (avec historique)
const saisie = ref({})
const confirmationSource = ref('')
const erreurPanneau = ref('')
const enCours = ref(false)
const aujourdhui = new Date().toISOString().slice(0, 10)

async function ouvrir(p) {
  erreurPanneau.value = ''; confirmationSource.value = ''
  try {
    const { data } = await apiClient.get(`/parametres/${p.cle}`)
    choisi.value = data
    saisie.value = { valeur: data.valeur_courante?.valeur ?? '', date_effet: aujourdhui, statut: 'confirme', source: '', commentaire: '' }
  } catch (e) { erreur.value = messageErreur(e) }
}
function fermer() { choisi.value = null }

async function enregistrer() {
  if (enCours.value) return
  enCours.value = true; erreurPanneau.value = ''
  try {
    const corps = { ...saisie.value, valeur: String(saisie.value.valeur) }
    const { data } = await apiClient.post(`/parametres/${choisi.value.cle}/valeurs`, corps)
    message.value = `« ${data.libelle} » : nouvelle valeur enregistrée.`
    choisi.value = null
    await charger()
  } catch (e) { erreurPanneau.value = messageErreur(e) } finally { enCours.value = false }
}
async function confirmerActuelle() {
  if (enCours.value) return
  enCours.value = true; erreurPanneau.value = ''
  try {
    const v = choisi.value.valeur_courante
    const { data } = await apiClient.post(`/parametres/${choisi.value.cle}/valeurs/${v.id}/confirmer`, { source: confirmationSource.value })
    message.value = `« ${data.libelle} » confirmé.`
    choisi.value = null
    await charger()
  } catch (e) { erreurPanneau.value = messageErreur(e) } finally { enCours.value = false }
}
const destTest = ref('')
async function testerEmail() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.post('/email/test', { destinataire: destTest.value })
    if (data.statut === 'envoye') message.value = `Message de test envoyé à ${destTest.value}.`
    else erreur.value = data.erreur || 'Le message de test n\'est pas parti.'
  } catch (e) { erreur.value = messageErreur(e) }
}
const colonnes = [
  { cle: 'libelle', libelle: 'Paramètre', tri: true, texte: (p) => `${p.libelle} ${p.cle}` , valeur: (p) => p.libelle },
  { cle: 'valeur', libelle: 'Valeur en vigueur', tri: true, align: 'droite', texte: (p) => formater(p), valeur: (p) => formater(p) },
  { cle: 'depuis', libelle: 'Depuis le', tri: true, texte: (p) => (p.valeur_courante ? dateFr(p.valeur_courante.date_effet) : '—'), valeur: (p) => p.valeur_courante?.date_effet || '' },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (p) => (p.valeur_courante?.statut === 'confirme' ? 'Confirmé' : 'À confirmer'), valeur: (p) => p.valeur_courante?.statut || '' },
  { cle: 'nb', libelle: 'Historique', tri: true, align: 'droite', texte: (p) => (p.nb_valeurs > 1 ? `${p.nb_valeurs} valeurs` : ''), valeur: (p) => p.nb_valeurs },
]
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Paramétrage</h1>
      <p class="sous-titre">Taux, plafonds, barèmes et règles utilisés par le calcul de la paie. Chaque changement est daté, justifié et tracé ; les bulletins déjà validés ne sont jamais modifiés.</p>
    </header>

    <div v-if="etat && etat.critiques_a_confirmer" class="bandeau attention" role="status">
      <AlertTriangle :size="18" />
      <span><strong>{{ etat.critiques_a_confirmer }} paramètre(s) critique(s)</strong> restent à confirmer ; la validation des bulletins sera bloquée tant qu'ils ne le sont pas.</span>
      <button class="vbtn vbtn-secondary" data-hint="Afficher uniquement les paramètres encore à confirmer" @click="seulementAConfirmer = true; categorie = ''">Voir ceux à confirmer</button>
    </div>
    <p v-if="message" class="bandeau ok" role="status"><CheckCircle2 :size="18" />{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <div class="filtres">
      <div class="puces">
        <button :class="['puce', { active: !categorie }]" @click="categorie = ''">Tous</button>
        <button v-for="c in categoriesPresentes" :key="c.cle" :class="['puce', { active: categorie === c.cle }]" @click="categorie = c.cle">
          {{ c.libelle }}<span v-if="c.aConfirmer" class="point" :title="`${c.aConfirmer} à confirmer`">{{ c.aConfirmer }}</span>
        </button>
      </div>
      <div class="outils">
        <label class="recherche"><Search :size="16" /><input v-model="recherche" placeholder="Rechercher…" aria-label="Rechercher un paramètre" /></label>
        <label class="case"><input v-model="seulementAConfirmer" type="checkbox" /> À confirmer seulement</label>
      </div>
    </div>

    <form v-if="categorie === 'email'" class="card test-email" @submit.prevent="testerEmail">
      <strong>Tester l'envoi</strong>
      <input v-model="destTest" type="email" class="input" placeholder="votre.adresse@exemple.ci" required aria-label="Adresse de test" />
      <button class="vbtn vbtn-secondary" type="submit">Envoyer un message de test</button>
      <span class="aide-mini">Le mot de passe du compte d'envoi se règle dans le fichier de configuration du serveur (SMTP_PASSWORD).</span>
    </form>

    <DataTable :colonnes="colonnes" :lignes="affiches" cle-ligne="cle" ligne-cliquable :recherche="false" :taille-page="50" vide="Aucun paramètre." @ligne="ouvrir">
      <template #cell-libelle="{ ligne }">
        <div class="lib">{{ ligne.libelle }}<span v-if="ligne.critique" class="badge badge-info critique" data-hint="Un paramètre critique « à confirmer » bloque la validation des bulletins">critique</span></div>
        <div class="cle">{{ ligne.cle }}</div>
      </template>
      <template #cell-valeur="{ ligne }"><strong>{{ formater(ligne) }}</strong></template>
      <template #cell-statut="{ ligne }"><span :class="['badge', ligne.valeur_courante?.statut === 'confirme' ? 'badge-ok' : 'badge-attente']">{{ ligne.valeur_courante?.statut === 'confirme' ? 'Confirmé' : 'À confirmer' }}</span></template>
      <template #cell-nb="{ ligne }"><span class="detail">{{ ligne.nb_valeurs > 1 ? `${ligne.nb_valeurs} valeurs` : '' }}</span></template>
    </DataTable>

    <div v-if="choisi" class="voile" @click.self="fermer">
      <aside class="panneau" role="dialog" aria-modal="true" :aria-label="choisi.libelle">
        <header class="panneau-tete">
          <div>
            <h2>{{ choisi.libelle }}</h2>
            <div class="cle">{{ choisi.cle }}</div>
          </div>
          <button class="fermer" aria-label="Fermer" @click="fermer"><X :size="20" /></button>
        </header>

        <div class="panneau-corps">
          <p v-if="choisi.description" class="desc">{{ choisi.description }}</p>

          <section class="actuelle">
            <div class="etiquette">Valeur en vigueur</div>
            <div class="grosse">{{ formater(choisi) }}</div>
            <div class="meta" v-if="choisi.valeur_courante">
              depuis le {{ dateFr(choisi.valeur_courante.date_effet) }} ·
              <span :class="['badge', choisi.valeur_courante.statut === 'confirme' ? 'badge-ok' : 'badge-attente']">{{ choisi.valeur_courante.statut === 'confirme' ? 'Confirmé' : 'À confirmer' }}</span>
              <div v-if="choisi.valeur_courante.source">Source : {{ choisi.valeur_courante.source }}</div>
            </div>
          </section>

          <template v-if="peutModifier">
            <section v-if="choisi.valeur_courante?.statut === 'a_confirmer'" class="bloc-confirmer">
              <strong>Cette valeur est la bonne ?</strong>
              <label class="field"><span class="field-label">Source de la confirmation</span>
                <input v-model="confirmationSource" class="input" placeholder="Ex. notification CNPS 2026, note de la direction" /></label>
              <button class="vbtn vbtn-secondary" :disabled="enCours || confirmationSource.trim().length < 3" @click="confirmerActuelle"><CheckCircle2 :size="16" />Confirmer la valeur actuelle</button>
            </section>

            <form class="formulaire" @submit.prevent="enregistrer">
              <h3>Nouvelle valeur</h3>
              <label class="field"><span class="field-label">Valeur{{ choisi.unite ? ` (${choisi.unite})` : '' }}</span>
                <EditeurBareme v-if="choisi.type_valeur === 'bareme'" v-model="saisie.valeur" />
                <select v-else-if="choisi.choix" v-model="saisie.valeur" class="input"><option v-for="c in choisi.choix" :key="c" :value="c">{{ c }}</option></select>
                <select v-else-if="choisi.type_valeur === 'booleen'" v-model="saisie.valeur" class="input"><option value="true">Oui</option><option value="false">Non</option></select>
                <input v-else-if="choisi.type_valeur === 'heure'" v-model="saisie.valeur" class="input" type="time" required />
                <input v-else v-model="saisie.valeur" class="input" :inputmode="['texte'].includes(choisi.type_valeur) ? 'text' : 'decimal'" required />
              </label>
              <label class="field"><span class="field-label">Applicable à partir du</span>
                <input v-model="saisie.date_effet" class="input" type="date" required /></label>
              <fieldset class="statut">
                <legend>Statut de cette valeur</legend>
                <label class="case"><input v-model="saisie.statut" type="radio" value="confirme" /> Confirmé (source obligatoire)</label>
                <label class="case"><input v-model="saisie.statut" type="radio" value="a_confirmer" /> À confirmer (provisoire)</label>
              </fieldset>
              <label class="field"><span class="field-label">Source {{ saisie.statut === 'confirme' ? '(obligatoire)' : '(facultative)' }}</span>
                <input v-model="saisie.source" class="input" placeholder="Ex. arrêté, courrier CNPS, note de la direction" :required="saisie.statut === 'confirme'" /></label>
              <label class="field"><span class="field-label">Commentaire</span>
                <input v-model="saisie.commentaire" class="input" /></label>
              <p v-if="erreurPanneau" class="message-erreur" role="alert">{{ erreurPanneau }}</p>
              <div class="actions">
                <button type="button" class="vbtn vbtn-secondary" @click="fermer">Annuler</button>
                <button type="submit" class="vbtn vbtn-primary" :disabled="enCours">{{ enCours ? 'Enregistrement…' : 'Enregistrer' }}</button>
              </div>
            </form>
          </template>
          <p v-else class="desc">{{ surTelephone ? 'Consultation seulement sur téléphone : la modification se fait depuis un ordinateur.' : 'Vous pouvez consulter ce paramètre ; sa modification nécessite le droit « Modifier les paramètres ».' }}</p>

          <section>
            <h3>Historique</h3>
            <ul class="histo">
              <li v-for="v in choisi.historique" :key="v.id">
                <div><strong>{{ formater(choisi, v.valeur) }}</strong> <span class="badge" :class="v.statut === 'confirme' ? 'badge-ok' : 'badge-attente'">{{ v.statut === 'confirme' ? 'Confirmé' : 'À confirmer' }}</span></div>
                <div class="meta">à partir du {{ dateFr(v.date_effet) }} · saisi par {{ v.cree_par || '—' }}<template v-if="v.confirme_par"> · confirmé par {{ v.confirme_par }}</template></div>
                <div v-if="v.source" class="meta">Source : {{ v.source }}</div>
                <div v-if="v.commentaire" class="meta">{{ v.commentaire }}</div>
              </li>
            </ul>
          </section>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 720px; }
.bandeau { display: flex; align-items: center; gap: var(--space-3); padding: 12px 16px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; flex-wrap: wrap; }
.bandeau span { flex: 1; min-width: 200px; }
.bandeau.attention { background: var(--color-orange-bg); color: var(--color-orange); }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); }
.filtres { display: flex; flex-direction: column; gap: var(--space-3); }
.puces { display: flex; gap: 6px; flex-wrap: wrap; }
.puce { border: 1px solid var(--color-border); background: var(--color-surface); border-radius: 999px; padding: 6px 14px; min-height: 36px; font-size: var(--font-size-sm); cursor: pointer; color: var(--color-text-muted); display: inline-flex; align-items: center; gap: 6px; }
.puce.active { background: var(--color-brand); color: #fff; border-color: var(--color-brand); }
.point { background: var(--color-orange-bg); color: var(--color-orange); border-radius: 999px; font-size: 11px; font-weight: 700; padding: 1px 7px; }
.outils { display: flex; gap: var(--space-4); align-items: center; flex-wrap: wrap; }
.recherche { display: flex; align-items: center; gap: 8px; border: 1px solid var(--color-border-fort); border-radius: var(--radius-md); padding: 0 12px; background: var(--color-surface); min-height: 40px; color: var(--color-text-muted); }
.recherche input { border: none; outline: none; font-size: var(--font-size-sm); background: none; min-width: 180px; }
.case { display: flex; align-items: center; gap: 8px; font-size: var(--font-size-sm); min-height: 32px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.nowrap { white-space: nowrap; }
.cliquable { cursor: pointer; }
.cliquable:hover, .cliquable:focus-visible { background: var(--color-surface-2); outline: none; }
.lib { font-weight: 600; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.critique { font-size: 10px; padding: 1px 8px; }
.cle { font-size: var(--font-size-xs); color: var(--color-text-muted); font-family: ui-monospace, monospace; }
.detail { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.voile { position: fixed; inset: 0; background: rgba(15, 23, 42, .4); display: flex; justify-content: flex-end; z-index: 50; }
.panneau { width: 100%; max-width: 480px; background: var(--color-surface); height: 100%; overflow-y: auto; }
.panneau-tete { display: flex; justify-content: space-between; align-items: flex-start; padding: var(--space-4) var(--space-6); border-bottom: 1px solid var(--color-border); position: sticky; top: 0; background: var(--color-surface); z-index: 1; }
.panneau-tete h2 { margin: 0; font-size: var(--font-size-lg); }
.fermer { border: none; background: none; cursor: pointer; width: 40px; height: 40px; color: var(--color-text-muted); }
.panneau-corps { padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); }
.desc { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); line-height: 1.5; }
.actuelle { background: var(--color-brand-light); border-radius: var(--radius-md); padding: var(--space-4); }
.etiquette { font-size: var(--font-size-xs); font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .5px; }
.grosse { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-brand-dark); margin: 2px 0; }
.meta { font-size: var(--font-size-xs); color: var(--color-text-muted); line-height: 1.6; }
.bloc-confirmer { display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-4); border: 1px dashed #E0B34D; border-radius: var(--radius-md); background: #FFFAEF; font-size: var(--font-size-sm); }
.formulaire { display: flex; flex-direction: column; gap: var(--space-3); }
h3 { margin: 0; font-size: var(--font-size-base); }
.statut { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-2) var(--space-4); }
.statut legend { font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); padding: 0 6px; }
.actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
.histo { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
.histo li { border-left: 3px solid var(--color-border); padding-left: var(--space-3); font-size: var(--font-size-sm); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
.test-email { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; padding: var(--space-3) var(--space-4); }
.test-email .input { width: auto; min-width: 260px; }
.aide-mini { font-size: var(--font-size-xs); color: var(--color-text-muted); }
</style>
