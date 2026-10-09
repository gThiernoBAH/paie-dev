<script setup>
import { ref, onMounted, computed } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Upload, Plus, Trash2, Calculator } from 'lucide-vue-next'
import DataTable from '@/components/DataTable.vue'
import BoutonIcone from '@/components/BoutonIcone.vue'
import { useConfirm } from '@/composables/useConfirm'

const { confirm } = useConfirm()

const dateFr = (d) => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })
const colonnesPointages = [
  { cle: 'jour', libelle: 'Jour', tri: true, format: (v) => dateFr(v) },
  { cle: 'matricule', libelle: 'Matricule', tri: true },
  { cle: 'nom', libelle: 'Salarié', tri: true },
  { cle: 'heure_entree', libelle: 'Entrée', tri: true, format: (v) => v || '—' },
  { cle: 'heure_sortie', libelle: 'Sortie', tri: true, texte: (p) => (p.heure_sortie || '—') + (p.heure_entree && !p.heure_sortie ? ' incomplet' : '') },
  { cle: 'source', libelle: 'Source', tri: true, texte: (p) => (p.source === 'import' ? 'Import' : 'Manuel') },
]
const colonnesImports = [
  { cle: 'importe_le', libelle: 'Date', tri: true, format: (v) => new Date(v).toLocaleString('fr-FR') },
  { cle: 'nom_fichier', libelle: 'Fichier', tri: true },
  { cle: 'importe_par', libelle: 'Par', tri: true },
  { cle: 'nb_lignes', libelle: 'Lignes', tri: true, align: 'droite' },
  { cle: 'nb_jours', libelle: 'Jours', tri: true, align: 'droite' },
  { cle: 'nb_rejets', libelle: 'Rejets', tri: true, align: 'droite' },
]
const colonnesFeries = [
  { cle: 'jour', libelle: 'Date', tri: true, format: (v) => dateFr(v) },
  { cle: 'libelle', libelle: 'Libellé', tri: true },
]
const onglet = ref('pointages')
const erreur = ref('')
const message = ref('')
const aujourdhui = new Date()
const premierDuMois = new Date(aujourdhui.getFullYear(), aujourdhui.getMonth(), 1).toLocaleDateString('sv-SE')
const iso = (d) => d.toLocaleDateString('sv-SE')

// ---------- Pointages ----------
const periode = ref({ du: premierDuMois, au: iso(aujourdhui) })
const pointages = ref([])
const saisie = ref({ matricule: '', jour: iso(aujourdhui), heure_entree: '', heure_sortie: '' })
async function chargerPointages() {
  erreur.value = ''
  try { pointages.value = (await apiClient.get('/pointages', { params: periode.value })).data } catch (e) { erreur.value = messageErreur(e) }
}
async function trouverSalarie(matricule) {
  const { data } = await apiClient.get('/salaries', { params: { recherche: matricule.trim(), statut: 'tous', taille: 5 } })
  const m = data.elements.find((s) => s.matricule === matricule.trim().padStart(6, '0'))
  if (!m) throw new Error('Matricule introuvable.')
  return m
}
async function enregistrerPointage() {
  erreur.value = ''; message.value = ''
  try {
    const s = await trouverSalarie(saisie.value.matricule)
    await apiClient.put('/pointages', { salarie_id: s.id, jour: saisie.value.jour, heure_entree: saisie.value.heure_entree || null, heure_sortie: saisie.value.heure_sortie || null })
    message.value = `Pointage de ${s.matricule} enregistré.`
    await chargerPointages()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function supprimer(p) {
  if (!(await confirm({ title: 'Supprimer ce pointage', message: `Pointage de ${p.nom} (${p.matricule}) du ${dateFr(p.jour)}. Cette suppression est tracée.`, danger: true, confirmLabel: 'Supprimer' }))) return
  try { await apiClient.delete(`/pointages/${p.id}`); await chargerPointages() } catch (e) { erreur.value = messageErreur(e) }
}

// ---------- Import ----------
const fichier = ref(null)
const resultat = ref(null)
const imports = ref([])
const enCours = ref(false)
function choisirFichier(ev) {
  const f = ev.target.files[0]
  if (!f) return
  const lecteur = new FileReader()
  lecteur.onload = () => { fichier.value = { nom: f.name, contenu: lecteur.result } }
  lecteur.readAsText(f)
}
async function importer() {
  enCours.value = true; erreur.value = ''; resultat.value = null
  try {
    resultat.value = (await apiClient.post('/pointages/import', { nom_fichier: fichier.value.nom, contenu: fichier.value.contenu })).data
    fichier.value = null
    await chargerImports()
  } catch (e) { erreur.value = messageErreur(e) } finally { enCours.value = false }
}
async function chargerImports() { try { imports.value = (await apiClient.get('/pointages/imports')).data } catch { /* historique facultatif */ } }

// ---------- Présences (aperçu) ----------
const calc = ref({ matricule: '', du: premierDuMois, au: iso(aujourdhui) })
const apercu = ref(null)
async function calculer() {
  erreur.value = ''; apercu.value = null
  try {
    const s = await trouverSalarie(calc.value.matricule)
    apercu.value = { ...(await apiClient.get('/presences/calcul', { params: { salarie_id: s.id, du: calc.value.du, au: calc.value.au } })).data, nom: `${s.nom} ${s.prenoms || ''}` }
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}

// ---------- Jours fériés ----------
const annee = ref(aujourdhui.getFullYear())
const feries = ref([])
const nouveauFerie = ref({ jour: '', libelle: '' })
async function chargerFeries() { try { feries.value = (await apiClient.get('/jours-feries', { params: { annee: annee.value } })).data } catch (e) { erreur.value = messageErreur(e) } }
async function ajouterFerie() {
  erreur.value = ''
  try { await apiClient.post('/jours-feries', nouveauFerie.value); nouveauFerie.value = { jour: '', libelle: '' }; await chargerFeries() } catch (e) { erreur.value = messageErreur(e) }
}
async function retirerFerie(f) {
  if (!(await confirm({ title: 'Retirer ce jour férié', message: `${f.libelle} (${dateFr(f.jour)}) ne sera plus compté comme férié.`, danger: true, confirmLabel: 'Retirer' }))) return
  try { await apiClient.delete(`/jours-feries/${f.jour}`); await chargerFeries() } catch (e) { erreur.value = messageErreur(e) } }

onMounted(() => { chargerPointages(); chargerImports(); chargerFeries() })
</script>

<template>
  <div class="page">
    <header>
      <h1>Pointages</h1>
      <p class="sous-titre">Import des fichiers de la pointeuse, corrections manuelles et calcul automatique des présences (heures normales, heures supplémentaires, jours fériés).</p>
    </header>
    <div class="onglets" role="tablist">
      <button v-for="(lib, cle) in { pointages: 'Pointages', import: 'Import', presences: 'Calcul des présences', feries: 'Jours fériés' }" :key="cle" role="tab" :class="['onglet', { actif: onglet === cle }]" @click="onglet = cle">{{ lib }}</button>
    </div>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <section v-if="onglet === 'pointages'" class="bloc">
      <form class="ligne" @submit.prevent="chargerPointages">
        <label class="field"><span class="field-label">Du</span><input v-model="periode.du" type="date" class="input" required /></label>
        <label class="field"><span class="field-label">Au</span><input v-model="periode.au" type="date" class="input" required /></label>
        <button class="vbtn vbtn-secondary" type="submit">Afficher</button>
      </form>
      <form class="card saisie ecriture" @submit.prevent="enregistrerPointage">
        <h2>Saisie ou correction d'un pointage</h2>
        <div class="grille">
          <label class="field"><span class="field-label">Matricule</span><input v-model="saisie.matricule" class="input" placeholder="000054" required inputmode="numeric" /></label>
          <label class="field"><span class="field-label">Jour</span><input v-model="saisie.jour" type="date" class="input" required /></label>
          <label class="field"><span class="field-label">Heure d'entrée</span><input v-model="saisie.heure_entree" type="time" class="input" /></label>
          <label class="field"><span class="field-label">Heure de sortie</span><input v-model="saisie.heure_sortie" type="time" class="input" /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Enregistrer</button></div>
        </div>
      </form>
      <DataTable :colonnes="colonnesPointages" :lignes="pointages" vide="Aucun pointage sur la période." placeholder-recherche="Rechercher un matricule ou un nom" :taille-page="50">
        <template #cell-heure_entree="{ ligne }">{{ ligne.heure_entree || '—' }}</template>
        <template #cell-heure_sortie="{ ligne }">{{ ligne.heure_sortie || '—' }} <span v-if="ligne.heure_entree && !ligne.heure_sortie" class="badge badge-attente">incomplet</span></template>
        <template #cell-source="{ ligne }"><span class="badge">{{ ligne.source === 'import' ? 'Import' : 'Manuel' }}</span></template>
        <template #actions="{ ligne }"><BoutonIcone class="ecriture" :icone="Trash2" :hint="`Supprimer le pointage de ${ligne.nom} du ${dateFr(ligne.jour)}`" danger @click="supprimer(ligne)" /></template>
      </DataTable>
    </section>

    <section v-if="onglet === 'import'" class="bloc">
      <div class="card encart ecriture">
        <p>Fichier CSV (séparateur ; , ou tabulation). Deux formes acceptées :</p>
        <ul><li><code>matricule ; date ; heure</code> — un badgeage par ligne (première heure = entrée, dernière = sortie)</li>
          <li><code>matricule ; date ; entree ; sortie</code> — une ligne par jour</li></ul>
        <p>Les dates sont lues en <code>AAAA-MM-JJ</code> ou <code>JJ/MM/AAAA</code>. Un jour déjà pointé est remplacé.</p>
        <div class="ligne">
          <input type="file" accept=".csv,.txt" aria-label="Fichier de pointages" @change="choisirFichier" />
          <button class="vbtn vbtn-primary" :disabled="!fichier || enCours" @click="importer"><Upload :size="16" />{{ enCours ? 'Import…' : 'Importer' }}</button>
        </div>
      </div>
      <div v-if="resultat" class="card encart" role="status">
        <strong>{{ resultat.jours_importes }} jour(s) importé(s)</strong> sur {{ resultat.lignes_lues }} ligne(s) lue(s) ;
        <strong :class="{ rouge: resultat.nb_rejets }">{{ resultat.nb_rejets }} rejet(s)</strong>.
        <ul v-if="resultat.rejets.length" class="rejets"><li v-for="(r, i) in resultat.rejets" :key="i">{{ r.ligne ? `Ligne ${r.ligne} : ` : '' }}{{ r.motif }}</li></ul>
      </div>
      <h2>Historique des imports</h2>
      <DataTable :colonnes="colonnesImports" :lignes="imports" vide="Aucun import." placeholder-recherche="Rechercher un fichier" />
    </section>

    <section v-if="onglet === 'presences'" class="bloc">
      <form class="ligne" @submit.prevent="calculer">
        <label class="field"><span class="field-label">Matricule</span><input v-model="calc.matricule" class="input" required inputmode="numeric" /></label>
        <label class="field"><span class="field-label">Du</span><input v-model="calc.du" type="date" class="input" required /></label>
        <label class="field"><span class="field-label">Au</span><input v-model="calc.au" type="date" class="input" required /></label>
        <button class="vbtn vbtn-primary" type="submit"><Calculator :size="16" />Calculer</button>
      </form>
      <div v-if="apercu" class="card encart">
        <h2>{{ apercu.nom }} <small>({{ apercu.matricule }})</small></h2>
        <div class="kpis">
          <div><span>Jours de présence</span><strong>{{ apercu.jours_presence }}</strong></div>
          <div><span>Heures normales</span><strong>{{ apercu.heures_normales }}</strong></div>
          <div v-for="n in ['1','2','3','4']" :key="n"><span>HS{{ n }}</span><strong>{{ apercu.heures_sup[n] }}</strong></div>
        </div>
        <p v-if="apercu.absences_detectees.length" class="aide">Jours ouvrés sans pointage : {{ apercu.absences_detectees.map((j) => j.slice(8) + '/' + j.slice(5, 7)).join(', ') }}</p>
        <p v-if="apercu.pointages_incomplets.length" class="rouge">Pointages incomplets (sortie manquante) : {{ apercu.pointages_incomplets.join(', ') }}</p>
      </div>
    </section>

    <section v-if="onglet === 'feries'" class="bloc">
      <div class="ligne">
        <label class="field"><span class="field-label">Année</span><input v-model.number="annee" type="number" class="input" @change="chargerFeries" /></label>
      </div>
      <form class="card saisie ecriture" @submit.prevent="ajouterFerie">
        <h2>Ajouter un jour férié</h2>
        <div class="grille">
          <label class="field"><span class="field-label">Date</span><input v-model="nouveauFerie.jour" type="date" class="input" required /></label>
          <label class="field large"><span class="field-label">Libellé</span><input v-model="nouveauFerie.libelle" class="input" placeholder="Ex. Tabaski" required /></label>
          <div class="field valider"><button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button></div>
        </div>
      </form>
      <p class="aide">Les fêtes religieuses mobiles (Aïd, Tabaski, Maouloud…) se saisissent chaque année dès que la date est connue.</p>
      <DataTable :colonnes="colonnesFeries" :lignes="feries" cle-ligne="jour" :vide="`Aucun jour férié enregistré pour ${annee}.`" placeholder-recherche="Rechercher un jour férié">
        <template #actions="{ ligne }"><BoutonIcone class="ecriture" :icone="Trash2" :hint="`Retirer ${ligne.libelle}`" danger @click="retirerFerie(ligne)" /></template>
      </DataTable>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
h2 small { color: var(--color-text-muted); font-weight: 400; }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 720px; }
.onglets { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); flex-wrap: wrap; }
.onglet { padding: 10px 16px; min-height: 44px; border: none; background: none; cursor: pointer; font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.onglet.actif { color: var(--color-brand-dark); border-bottom-color: var(--color-brand); }
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.saisie { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-3) var(--space-4); align-items: end; }
.grille .large { grid-column: span 2; } .valider { justify-content: flex-end; }
@media (max-width: 560px) { .grille .large { grid-column: span 1; } }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.encart { padding: var(--space-4) var(--space-6); font-size: var(--font-size-sm); display: flex; flex-direction: column; gap: var(--space-3); }
.encart p, .encart ul { margin: 0; } .encart ul { padding-left: 20px; line-height: 1.7; }
.kpis { display: flex; gap: var(--space-6); flex-wrap: wrap; }
.kpis div { display: flex; flex-direction: column; } .kpis span { font-size: var(--font-size-xs); color: var(--color-text-muted); } .kpis strong { font-size: var(--font-size-lg); }
.rouge { color: var(--color-rouge); } .aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.rejets { max-height: 180px; overflow: auto; color: var(--color-rouge); }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
