<script setup>
import { ref, onMounted, computed } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Upload, Plus, Trash2, Calculator } from 'lucide-vue-next'

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
  if (!window.confirm(`Supprimer le pointage de ${p.matricule} du ${p.jour} ?`)) return
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
async function retirerFerie(f) { try { await apiClient.delete(`/jours-feries/${f.jour}`); await chargerFeries() } catch (e) { erreur.value = messageErreur(e) } }
const dateFr = (d) => new Date(d + 'T00:00:00').toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })

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
      <form class="ligne saisie card" @submit.prevent="enregistrerPointage">
        <strong>Saisie / correction</strong>
        <input v-model="saisie.matricule" class="input" placeholder="Matricule" required inputmode="numeric" aria-label="Matricule" />
        <input v-model="saisie.jour" type="date" class="input" required aria-label="Jour" />
        <input v-model="saisie.heure_entree" type="time" class="input" aria-label="Entrée" />
        <input v-model="saisie.heure_sortie" type="time" class="input" aria-label="Sortie" />
        <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Enregistrer</button>
      </form>
      <div class="card cadre">
        <table>
          <thead><tr><th>Jour</th><th>Matricule</th><th>Salarié</th><th>Entrée</th><th>Sortie</th><th>Source</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in pointages" :key="p.id">
              <td class="nowrap">{{ dateFr(p.jour) }}</td><td>{{ p.matricule }}</td><td>{{ p.nom }}</td>
              <td>{{ p.heure_entree || '—' }}</td>
              <td>{{ p.heure_sortie || '—' }} <span v-if="p.heure_entree && !p.heure_sortie" class="badge badge-attente">incomplet</span></td>
              <td><span class="badge">{{ p.source === 'import' ? 'Import' : 'Manuel' }}</span></td>
              <td><button class="icone" :aria-label="`Supprimer le pointage de ${p.matricule}`" @click="supprimer(p)"><Trash2 :size="16" /></button></td>
            </tr>
            <tr v-if="!pointages.length"><td colspan="7" class="vide">Aucun pointage sur la période.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="onglet === 'import'" class="bloc">
      <div class="card encart">
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
      <div class="card cadre"><table>
        <thead><tr><th>Date</th><th>Fichier</th><th>Par</th><th class="num">Lignes</th><th class="num">Jours</th><th class="num">Rejets</th></tr></thead>
        <tbody>
          <tr v-for="i in imports" :key="i.id"><td class="nowrap">{{ new Date(i.importe_le).toLocaleString('fr-FR') }}</td><td>{{ i.nom_fichier }}</td><td>{{ i.importe_par }}</td><td class="num">{{ i.nb_lignes }}</td><td class="num">{{ i.nb_jours }}</td><td class="num">{{ i.nb_rejets }}</td></tr>
          <tr v-if="!imports.length"><td colspan="6" class="vide">Aucun import.</td></tr>
        </tbody></table></div>
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
      <form class="ligne saisie card" @submit.prevent="ajouterFerie">
        <strong>Ajouter</strong>
        <input v-model="nouveauFerie.jour" type="date" class="input" required aria-label="Jour férié" />
        <input v-model="nouveauFerie.libelle" class="input" placeholder="Libellé (ex. Tabaski)" required aria-label="Libellé" />
        <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Ajouter</button>
      </form>
      <p class="aide">Les fêtes religieuses mobiles (Aïd, Tabaski, Maouloud…) se saisissent chaque année dès que la date est connue.</p>
      <div class="card cadre"><table>
        <thead><tr><th>Date</th><th>Libellé</th><th></th></tr></thead>
        <tbody>
          <tr v-for="f in feries" :key="f.jour"><td class="nowrap">{{ dateFr(f.jour) }}</td><td>{{ f.libelle }}</td><td><button class="icone" :aria-label="`Supprimer ${f.libelle}`" @click="retirerFerie(f)"><Trash2 :size="16" /></button></td></tr>
          <tr v-if="!feries.length"><td colspan="3" class="vide">Aucun jour férié enregistré pour {{ annee }}.</td></tr>
        </tbody></table></div>
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
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.saisie { padding: var(--space-3) var(--space-4); align-items: center; }
.saisie .input { width: auto; min-width: 130px; flex: 1; }
.encart { padding: var(--space-4) var(--space-6); font-size: var(--font-size-sm); display: flex; flex-direction: column; gap: var(--space-3); }
.encart p, .encart ul { margin: 0; } .encart ul { padding-left: 20px; line-height: 1.7; }
.kpis { display: flex; gap: var(--space-6); flex-wrap: wrap; }
.kpis div { display: flex; flex-direction: column; } .kpis span { font-size: var(--font-size-xs); color: var(--color-text-muted); } .kpis strong { font-size: var(--font-size-lg); }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 14px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; } .nowrap { white-space: nowrap; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.icone { border: none; background: none; cursor: pointer; color: var(--color-rouge); width: 36px; height: 36px; }
.rouge { color: var(--color-rouge); } .aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; }
.rejets { max-height: 180px; overflow: auto; color: var(--color-rouge); }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
