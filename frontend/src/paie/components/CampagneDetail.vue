<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { aLaPermission, lireUtilisateur } from '@/api/session'
import { telecharger } from '@/api/telechargement'
import { Calculator, CheckCircle2, Download, Printer, Unlock, Users, Clock, Trash2, Plus, Lock, Landmark, FileSpreadsheet, Mail, Eye } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useEcran } from '@/composables/useEcran'

const { confirm, saisir } = useConfirm()
const { mobile: lectureMobile } = useEcran()

const route = useRoute()
const router = useRouter()
const id = route.params.id
const u = lireUtilisateur()
const peutPreparer = aLaPermission(u, 'lancer_paie')
const peutValider = aLaPermission(u, 'valider_bulletins')
const estAdmin = u?.role === 'admin'
const envois = ref(null)
const peutVirer = aLaPermission(u, 'gerer_virements')
const peutDeclarer = aLaPermission(u, 'voir_declarations')

const campagne = ref(null)
const onglet = ref('presences')
const presences = ref([])
const saisies = ref([])
const bulletins = ref([])
const detail = ref(null)
const rubriques = ref([])
const erreur = ref('')
const message = ref('')
const enCours = ref(false)
const masse = ref({ code: '', mode: 'fixe', valeur: '', commentaire: '' })
const nouvelleSaisie = ref({ matricule: '', code: '', montant: '', commentaire: '' })

const CHAMPS_PRES = [
  ['jours_payes', 'Jours payés'], ['jours_presence', 'Jours présence'], ['heures_travaillees', 'Heures'], ['hs1', 'HS1'], ['hs2', 'HS2'],
  ['hs3', 'HS3'], ['hs4', 'HS4'], ['heures_absence', 'Abs. (h)'], ['jours_absence_ja', 'Abs. J.A. (j)'],
]
const colonnesPres = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  ...CHAMPS_PRES.map(([cle, libelle]) => ({ cle, libelle, tri: true, align: 'droite' })),
  { cle: 'source', libelle: 'Source', tri: true, texte: (p) => (p.source === 'pointage' ? 'Pointage' : 'Manuel') },
]
const colonnesSaisies = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'code', libelle: 'Rubrique', tri: true, texte: (s) => `${s.code} — ${s.libelle}` },
  { cle: 'type', libelle: 'Type', tri: true },
  { cle: 'montant', libelle: 'Montant', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'commentaire', libelle: 'Commentaire', tri: true },
  { cle: 'origine', libelle: 'Origine', tri: true },
]
const colonnesBulletins = [
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'total_imposable', libelle: 'Imposable', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'cnps', libelle: 'CNPS', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'its', libelle: 'ITS', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'net_a_payer', libelle: 'Net à payer', tri: true, align: 'droite', format: (v) => fmt(v) },
  { cle: 'statut', libelle: 'Statut', tri: true, texte: (b) => (b.statut === 'valide' ? 'Validé' : 'Brouillon') + (b.anomalies.length ? ' anomalie' : '') },
]
const LIBELLES = { ouverte: 'Ouverte', calculee: 'Calculée', validee: 'Validée', cloturee: 'Clôturée' }
const figee = computed(() => campagne.value && ['validee', 'cloturee'].includes(campagne.value.statut))
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
const coteGains = (l) => ['GI', 'GN'].includes(l.type) || (l.type === 'TO' && ['TIG', 'TI', 'TNG', 'TNI', 'NET'].includes(l.code))
const dateFr = (d) => d.split('-').reverse().join('/')

async function recharger() {
  erreur.value = ''
  try {
    campagne.value = (await apiClient.get(`/campagnes/${id}`)).data
    const [p, s, b] = await Promise.all([
      apiClient.get(`/campagnes/${id}/presences`), apiClient.get(`/campagnes/${id}/saisies`), apiClient.get(`/campagnes/${id}/bulletins`)])
    presences.value = p.data; saisies.value = s.data; bulletins.value = b.data
  } catch (e) { erreur.value = messageErreur(e) }
}
async function action(chemin, corps = {}, succes = '') {
  erreur.value = ''; message.value = ''; enCours.value = true
  try {
    const { data } = await apiClient.post(`/campagnes/${id}/${chemin}`, corps)
    message.value = succes ? succes(data) : ''
    await recharger()
  } catch (e) { erreur.value = messageErreur(e) } finally { enCours.value = false }
}
const initialiser = () => action('initialiser', {}, (d) => `${d.ajoutes} salarié(s) ajouté(s).`)
const depuisPointages = () => action('presences/depuis-pointages', { ecraser_manuel: false },
  (d) => `${d.mises_a_jour} salarié(s) mis à jour${d.ignorees_manuel ? `, ${d.ignorees_manuel} saisie(s) manuelle(s) conservée(s)` : ''}${d.incompletes ? `, ${d.incompletes} pointage(s) incomplet(s)` : ''}.`)
const calculer = () => action('calculer', {}, (d) => `${d.calcules} bulletin(s) calculé(s)${d.erreurs.length ? ` — ${d.erreurs.length} erreur(s) : ${d.erreurs.map((x) => x.motif).join(' ')}` : ''}${d.anomalies ? ` — ${d.anomalies} avec anomalie` : ''}.`)
async function valider() {
  if (!(await confirm({ title: 'Valider la campagne', message: 'Les bulletins seront figés : ils ne pourront plus être modifiés (seul un administrateur peut rouvrir la campagne, avec un motif tracé).', confirmLabel: 'Valider la campagne' }))) return
  action('valider', {}, (d) => `${d.bulletins_valides} bulletin(s) validé(s).`)
}
async function preparerVirements() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.post(`/campagnes/${id}/virements`, {})
    router.push('/virements?lot=' + data.id)
  } catch (e) { erreur.value = messageErreur(e) }
}
async function chargerEnvois() {
  try { envois.value = (await apiClient.get(`/campagnes/${id}/envois`)).data } catch { envois.value = null }
}
async function envoyerBulletins() {
  if (!(await confirm({ title: 'Envoyer les bulletins par e-mail', message: 'Chaque salarié ayant une adresse e-mail et une date de naissance recevra son bulletin en PDF protégé. Les salariés sans e-mail sont ignorés.', confirmLabel: 'Envoyer' }))) return
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.post(`/campagnes/${id}/envoyer-bulletins`, {})
    message.value = `${data.en_attente} envoi(s) lancé(s), ${data.ignores} ignoré(s) (e-mail ou date de naissance manquant), ${data.deja_envoyes} déjà envoyé(s).`
    setTimeout(chargerEnvois, 2500)
  } catch (e) { erreur.value = messageErreur(e) }
}
async function relancerEnvois() {
  try { await apiClient.post(`/campagnes/${id}/relancer-envois`); setTimeout(chargerEnvois, 2500) } catch (e) { erreur.value = messageErreur(e) }
}
async function journal(format) {
  try { await telecharger(`/campagnes/${id}/journal-comptable`, { format }, `journal.${format}`) } catch (e) { erreur.value = 'Journal indisponible.' }
}
async function cloturer() {
  if (!(await confirm({ title: 'Clôturer la campagne', message: 'La clôture est définitive : plus aucune opération n\'est possible sur cette campagne.', danger: true, confirmLabel: 'Clôturer' }))) return
  action('cloturer', {}, () => 'Campagne clôturée.')
}
async function rouvrir() {
  const v = await saisir({ title: 'Rouvrir la campagne', message: 'Les bulletins repasseront en brouillon. Le motif est obligatoire et tracé dans le journal d\'audit.', danger: true, confirmLabel: 'Rouvrir', champs: [{ cle: 'motif', label: 'Motif de la réouverture', type: 'texte-long', obligatoire: true }] })
  if (!v) return
  action('rouvrir', { motif: v.motif.trim() }, () => 'Campagne rouverte : les bulletins sont repassés en brouillon.')
}
async function enregistrerPresence(p) {
  erreur.value = ''
  try {
    const { salarie_id, matricule, nom, source, ...champs } = p
    await apiClient.put(`/campagnes/${id}/presences/${salarie_id}`, champs)
    await recharger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function retirer(p) {
  if (!(await confirm({ title: 'Retirer de la campagne', message: `Retirer ${p.nom} (${p.matricule}) de cette campagne ? Son bulletin éventuel sera supprimé.`, danger: true, confirmLabel: 'Retirer' }))) return
  try { await apiClient.delete(`/campagnes/${id}/salaries/${p.salarie_id}`); await recharger() } catch (e) { erreur.value = messageErreur(e) }
}
async function ajouterSaisie() {
  erreur.value = ''
  try {
    const m = nouvelleSaisie.value.matricule.trim().padStart(6, '0')
    const p = presences.value.find((x) => x.matricule === m)
    if (!p) throw new Error(`Le matricule ${m} n'est pas dans la campagne.`)
    await apiClient.post(`/campagnes/${id}/saisies`, { salarie_id: p.salarie_id, code: nouvelleSaisie.value.code, montant: nouvelleSaisie.value.montant, commentaire: nouvelleSaisie.value.commentaire || null })
    nouvelleSaisie.value = { matricule: '', code: nouvelleSaisie.value.code, montant: '', commentaire: '' }
    await recharger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function saisieEnMasse() {
  erreur.value = ''; message.value = ''
  if (!(await confirm({ title: 'Appliquer à tous', message: 'Cette rubrique sera ajoutée à tous les salariés de la campagne.', confirmLabel: 'Appliquer à tous' }))) return
  try {
    const { data } = await apiClient.post(`/campagnes/${id}/saisies/en-masse`, { ...masse.value, commentaire: masse.value.commentaire || null })
    message.value = `${data.ajoutees} saisie(s) ajoutée(s)${data.ignores_sans_salaire.length ? ` — sans salaire en vigueur : ${data.ignores_sans_salaire.join(', ')}` : ''}.`
    await recharger()
  } catch (e) { erreur.value = messageErreur(e) }
}
async function supprimerSaisie(s) {
  if (!(await confirm({ title: 'Supprimer cette saisie', message: `${s.code} — ${s.libelle} de ${s.matricule} (${fmt(s.montant)}).`, danger: true, confirmLabel: 'Supprimer' }))) return
  try { await apiClient.delete(`/campagnes/${id}/saisies/${s.id}`); await recharger() } catch (e) { erreur.value = messageErreur(e) }
}
async function voirBulletin(b) {
  try { detail.value = (await apiClient.get(`/bulletins/${b.id}`)).data } catch (e) { erreur.value = messageErreur(e) }
}
async function ouvrirPdf(chemin) {
  try {
    const { data } = await apiClient.get(chemin, { responseType: 'blob' })
    window.open(URL.createObjectURL(new Blob([data], { type: 'application/pdf' })), '_blank')
  } catch (e) { erreur.value = 'Impossible de générer le PDF.' }
}
onMounted(async () => {
  await recharger()
  if (campagne.value && ['validee', 'cloturee'].includes(campagne.value.statut)) chargerEnvois()
  try { rubriques.value = (await apiClient.get('/rubriques')).data.filter((r) => r.est_actif) } catch { /* facultatif */ }
})
</script>

<template>
  <div v-if="campagne" class="page">
    <header class="entete">
      <div>
        <button class="lien" @click="router.push('/campagnes')">← Campagnes</button>
        <h1>{{ campagne.libelle }} <span :class="['badge', 'st-' + campagne.statut]">{{ LIBELLES[campagne.statut] }}</span></h1>
        <p class="sous-titre">Du {{ dateFr(campagne.debut) }} au {{ dateFr(campagne.fin) }} · {{ campagne.nature_bulletin === 'journalier' ? 'bulletins journaliers' : 'bulletins mensuels' }}</p>
      </div>
      <div class="actions">
        <template v-if="peutPreparer && !figee">
          <button class="ecriture vbtn vbtn-secondary" :disabled="enCours" data-hint="Ajouter à la campagne tous les salariés concernés par cette période" @click="initialiser"><Users :size="16" />Ajouter les salariés concernés</button>
          <button class="ecriture vbtn vbtn-secondary" :disabled="enCours" data-hint="Calculer jours et heures de chaque salarié à partir des pointages importés" @click="depuisPointages"><Clock :size="16" />Présences depuis les pointages</button>
          <button class="ecriture vbtn vbtn-primary" :disabled="enCours || !presences.length" data-hint="Calculer tous les bulletins de la campagne (brouillon, modifiable)" @click="calculer"><Calculator :size="16" />Calculer</button>
        </template>
        <button v-if="peutValider && campagne.statut === 'calculee'" class="ecriture vbtn vbtn-primary" :disabled="enCours" data-hint="Figer les bulletins : ils ne pourront plus être modifiés" @click="valider"><CheckCircle2 :size="16" />Valider</button>
        <button v-if="peutValider && campagne.statut === 'validee'" class="ecriture vbtn vbtn-secondary" data-hint="Clôturer définitivement la campagne" @click="cloturer"><Lock :size="16" />Clôturer</button>
        <button v-if="estAdmin && campagne.statut === 'validee'" class="ecriture vbtn vbtn-secondary" data-hint="Rouvrir la campagne (administrateur, motif obligatoire)" @click="rouvrir"><Unlock :size="16" />Rouvrir</button>
        <button v-if="peutVirer && campagne.statut === 'validee'" class="ecriture vbtn vbtn-primary" data-hint="Créer le lot de virements bancaires de cette campagne" @click="preparerVirements"><Landmark :size="16" />Préparer les virements</button>
        <button v-if="peutValider && figee" class="ecriture vbtn vbtn-secondary" data-hint="Envoyer à chaque salarié son bulletin en PDF protégé par e-mail" @click="envoyerBulletins"><Mail :size="16" />Envoyer par e-mail</button>
        <button v-if="peutDeclarer && figee" class="vbtn vbtn-secondary" data-hint="Télécharger le journal comptable (écritures de paie) au format Excel" @click="journal('xlsx')"><FileSpreadsheet :size="16" />Journal comptable</button>
        <button v-if="bulletins.length" class="vbtn vbtn-secondary" data-hint="Ouvrir tous les bulletins de la campagne dans un seul PDF" @click="ouvrirPdf(`/campagnes/${id}/bulletins.pdf`)"><Printer :size="16" />Tous les bulletins (PDF)</button>
      </div>
    </header>

    <div class="kpis card">
      <div><span>Salariés</span><strong>{{ campagne.nb_salaries }}</strong></div>
      <div><span>Bulletins</span><strong>{{ campagne.nb_bulletins }}</strong></div>
      <div><span>Total imposable</span><strong>{{ fmt(campagne.total_imposable) }}</strong></div>
      <div><span>Net à payer</span><strong>{{ fmt(campagne.total_net) }}</strong></div>
    </div>

    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <p v-if="envois && Object.keys(envois).length" class="bandeau ok" role="status">
      Envois par e-mail :
      <span v-for="(n, s) in envois" :key="s" class="envoi">{{ n }} {{ { envoye: 'envoyé(s)', echec: 'en échec', ignore: 'ignoré(s)', desactive: 'non partis (e-mail désactivé)', en_attente: 'en cours' }[s] || s }}</span>
      <button v-if="envois.echec || envois.desactive" class="lien" @click="relancerEnvois">Relancer</button>
    </p>
    <div v-if="campagne.validation?.raisons?.length" class="bandeau avert" role="alert">
      <strong>Validation impossible pour l'instant :</strong>
      <ul><li v-for="(r, i) in campagne.validation.raisons" :key="i">{{ r }}</li></ul>
    </div>

    <div class="onglets" role="tablist">
      <button v-for="(lib, cle) in { presences: 'Présences', saisies: 'Rubriques variables', bulletins: 'Bulletins' }" :key="cle" role="tab" :class="['onglet', { actif: onglet === cle }]" @click="onglet = cle">{{ lib }}</button>
    </div>

    <section v-if="onglet === 'presences'" class="bloc">
      <DataTable :colonnes="colonnesPres" :lignes="presences" cle-ligne="salarie_id" :taille-page="50" vide="Aucun salarié. Cliquez sur « Ajouter les salariés concernés »." placeholder-recherche="Rechercher un matricule ou un nom">
        <template v-for="[c] in CHAMPS_PRES" :key="c" #[`cell-${c}`]="{ ligne }">
          <input v-if="!figee && peutPreparer && !lectureMobile" v-model.number="ligne[c]" type="number" step="0.5" min="0" class="input saisie-num" :aria-label="`${c} de ${ligne.matricule}`" @change="enregistrerPresence(ligne)" />
          <template v-else>{{ ligne[c] }}</template>
        </template>
        <template #cell-source="{ ligne }"><span class="badge">{{ ligne.source === 'pointage' ? 'Pointage' : 'Manuel' }}</span></template>
        <template v-if="!figee && peutPreparer && !lectureMobile" #actions="{ ligne }"><BoutonIcone class="ecriture" :icone="Trash2" :hint="`Retirer ${ligne.nom} de la campagne`" danger @click="retirer(ligne)" /></template>
      </DataTable>
      <p class="aide">Les mensuels : jours payés = 30 pour un mois entier. Les journaliers : les heures et jours viennent des pointages. Toute modification manuelle est tracée.</p>
    </section>

    <section v-if="onglet === 'saisies'" class="bloc">
      <form v-if="!figee && peutPreparer" class="card saisie ecriture" @submit.prevent="ajouterSaisie">
        <h2>Ajouter une rubrique à un salarié</h2>
        <div class="grille">
          <label class="field"><span class="field-label">Matricule</span><input v-model="nouvelleSaisie.matricule" class="input" placeholder="000054" required inputmode="numeric" /></label>
          <label class="field large"><span class="field-label">Rubrique</span>
            <select v-model="nouvelleSaisie.code" class="input" required><option value="" disabled>Choisir…</option>
              <option v-for="r in rubriques" :key="r.code" :value="r.code">{{ r.code }} — {{ r.libelle }} ({{ r.type }})</option></select></label>
          <label class="field"><span class="field-label">Montant (FCFA)</span><input v-model="nouvelleSaisie.montant" type="number" step="0.01" min="0" class="input" required /></label>
          <label class="field large"><span class="field-label">Commentaire (facultatif)</span><input v-model="nouvelleSaisie.commentaire" class="input" /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button></div>
        </div>
      </form>
      <form v-if="!figee && peutPreparer" class="card saisie ecriture" @submit.prevent="saisieEnMasse">
        <h2>Appliquer une rubrique à tous les salariés</h2>
        <div class="grille">
          <label class="field large"><span class="field-label">Rubrique</span>
            <select v-model="masse.code" class="input" required><option value="" disabled>Choisir…</option>
              <option v-for="r in rubriques" :key="r.code" :value="r.code">{{ r.code }} — {{ r.libelle }} ({{ r.type }})</option></select></label>
          <label class="field"><span class="field-label">Mode de calcul</span><select v-model="masse.mode" class="input"><option value="fixe">Montant fixe</option><option value="pourcentage_salaire">% du salaire</option></select></label>
          <label class="field"><span class="field-label">{{ masse.mode === 'fixe' ? 'Montant (FCFA)' : 'Pourcentage (ex. 10)' }}</span><input v-model="masse.valeur" type="number" step="0.01" min="0" class="input" required /></label>
          <label class="field large"><span class="field-label">Commentaire (facultatif)</span><input v-model="masse.commentaire" class="input" /></label>
          <div class="field valider"><button class="vbtn vbtn-secondary" type="submit">Appliquer à tous</button></div>
        </div>
      </form>
      <DataTable :colonnes="colonnesSaisies" :lignes="saisies" vide="Aucune rubrique variable (primes, acomptes, retenues…)." placeholder-recherche="Rechercher une saisie">
        <template #cell-origine="{ ligne }"><span class="badge">{{ ligne.origine }}</span></template>
        <template #actions="{ ligne }"><BoutonIcone class="ecriture" v-if="!figee && peutPreparer && ligne.origine === 'manuelle'" :icone="Trash2" :hint="`Supprimer la saisie ${ligne.code} de ${ligne.matricule}`" danger @click="supprimerSaisie(ligne)" /></template>
      </DataTable>
      <p class="aide">GI = gain imposable, GN = gain non imposable, RI = retenue imposable, RN = retenue non imposable.</p>
    </section>

    <section v-if="onglet === 'bulletins'" class="bloc">
      <DataTable :colonnes="colonnesBulletins" :lignes="bulletins" :taille-page="50" vide="Aucun bulletin calculé." placeholder-recherche="Rechercher un matricule ou un nom">
        <template #cell-net_a_payer="{ ligne }"><strong>{{ fmt(ligne.net_a_payer) }}</strong></template>
        <template #cell-statut="{ ligne }">
          <span :class="['badge', ligne.statut === 'valide' ? 'st-validee' : '']">{{ ligne.statut === 'valide' ? 'Validé' : 'Brouillon' }}</span>
          <span v-if="ligne.anomalies.length" class="badge badge-attente" :data-hint="ligne.anomalies.join(' ')">anomalie</span>
        </template>
        <template #actions="{ ligne }">
          <BoutonIcone :icone="Eye" :hint="`Voir le détail du bulletin de ${ligne.nom}`" @click="voirBulletin(ligne)" />
          <BoutonIcone :icone="Download" :hint="`Télécharger le bulletin de ${ligne.nom} (PDF)`" @click="ouvrirPdf(`/bulletins/${ligne.id}/pdf`)" />
        </template>
      </DataTable>
    </section>

    <div v-if="detail" class="voile" role="dialog" aria-modal="true" aria-label="Bulletin" @click.self="detail = null">
      <div class="fenetre card">
        <header class="entete">
          <h2>{{ detail.matricule }} — {{ detail.nom }}</h2>
          <button class="vbtn vbtn-secondary" @click="detail = null">Fermer</button>
        </header>
        <div class="cadre"><table>
          <thead><tr><th>Code</th><th>Désignation</th><th class="num">Qté</th><th class="num">Taux</th><th class="num">Gains</th><th class="num">Retenues</th></tr></thead>
          <tbody>
            <tr v-for="(l, i) in detail.lignes" :key="i">
              <td>{{ l.code }}</td><td>{{ l.libelle }}</td><td class="num">{{ l.quantite ? fmt(l.quantite) : '' }}</td><td class="num">{{ l.taux ? fmt(l.taux) : '' }}</td>
              <td class="num">{{ coteGains(l) ? fmt(l.montant) : '' }}</td><td class="num">{{ coteGains(l) ? '' : fmt(l.montant) }}</td>
            </tr>
          </tbody></table></div>
        <div class="kpis">
          <div><span>Total imposable</span><strong>{{ fmt(detail.total_imposable) }}</strong></div>
          <div><span>CNPS</span><strong>{{ fmt(detail.cnps) }}</strong></div>
          <div><span>ITS</span><strong>{{ fmt(detail.its) }}</strong></div>
          <div><span>Net à payer</span><strong>{{ fmt(detail.net_a_payer) }}</strong></div>
        </div>
        <p v-if="detail.anomalies.length" class="rouge">{{ detail.anomalies.join(' ') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 4px 0 0; font-size: var(--font-size-xl); display: flex; gap: 10px; align-items: center; flex-wrap: wrap; } h2 { margin: 0; font-size: var(--font-size-base); }
.entete { display: flex; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; align-items: flex-start; }
.actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.lien { border: none; background: none; color: var(--color-brand-dark); cursor: pointer; padding: 0; font-size: var(--font-size-sm); }
.kpis { display: flex; gap: var(--space-8); flex-wrap: wrap; padding: var(--space-3) var(--space-4); }
.kpis div { display: flex; flex-direction: column; } .kpis span { font-size: var(--font-size-xs); color: var(--color-text-muted); } .kpis strong { font-size: var(--font-size-lg); }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap; }
.onglet { padding: 10px 16px; min-height: 44px; border: none; background: none; cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.onglet.actif { color: var(--color-brand-dark); border-bottom-color: var(--color-brand); }
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 12px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); white-space: nowrap; }
td { padding: 6px 12px; border-bottom: 1px solid var(--color-border); }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: span 2; } .valider { justify-content: flex-end; }
@media (max-width: 560px) { .grille .large { grid-column: span 1; } }
.saisie-num { width: 74px; padding: 4px 6px; text-align: right; }
.petit { padding: 4px 10px; min-height: 32px; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; } .pad { padding: var(--space-3) var(--space-4); }
.envoi { margin-right: 12px; font-weight: 600; }
.rouge { color: var(--color-rouge); }
.st-validee, .st-cloturee { background: var(--color-vert-bg); color: var(--color-vert); }
.bandeau { padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); }
.bandeau.avert { background: var(--color-orange-bg); color: var(--color-orange); } .bandeau ul { margin: 6px 0 0; padding-left: 20px; }
.voile { position: fixed; inset: 0; background: rgba(32, 26, 18, .5); display: flex; align-items: center; justify-content: center; padding: var(--space-4); z-index: 50; }
.fenetre { background: #fff; max-width: 820px; width: 100%; max-height: 90vh; overflow: auto; padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
