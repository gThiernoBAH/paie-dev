<script setup>
/** Simulation de bulletin : le moteur de paie sur des hypothèses, sans rien enregistrer. */
import { ref } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Calculator, Plus, Trash2 } from 'lucide-vue-next'
import BoutonIcone from '@/components/BoutonIcone.vue'

const maintenant = new Date()
const matricule = ref('')
const h = ref({ annee: maintenant.getFullYear(), mois: maintenant.getMonth() + 1, salaire_categoriel: '', sursalaire: '', parts: '', jours_payes: 30, jours_absence: 0, heures_absence: 0, hs1: 0, hs2: 0, hs3: 0, hs4: 0, inclure_rubriques_fixes: true })
const rubriques = ref([])
const nr = ref({ code: '', libelle: '', type: 'GI', montant: '' })
const resultat = ref(null)
const erreur = ref('')
const enCours = ref(false)
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const num = (v) => (v === '' || v === null ? undefined : Number(String(v).replace(',', '.')))
const TYPES = { GI: 'Gain imposable', GN: 'Gain non imposable', RI: 'Retenue imposable', RN: 'Retenue non imposable' }
const CHARGES = { total: 'Total des charges patronales' }

function ajouterRubrique() {
  if (!nr.value.code || nr.value.montant === '') return
  rubriques.value.push({ ...nr.value, code: nr.value.code.toUpperCase(), montant: num(nr.value.montant) })
  nr.value = { code: '', libelle: '', type: 'GI', montant: '' }
}
async function simuler() {
  erreur.value = ''; resultat.value = null; enCours.value = true
  try {
    let salarie_id
    if (matricule.value.trim()) {
      const { data } = await apiClient.get('/salaries', { params: { recherche: matricule.value.trim(), statut: 'tous', taille: 5 } })
      const s = data.elements.find((x) => x.matricule === matricule.value.trim().padStart(6, '0'))
      if (!s) throw new Error('Matricule introuvable.')
      salarie_id = s.id
    }
    const c = { ...h.value, salarie_id, rubriques: rubriques.value,
      salaire_categoriel: num(h.value.salaire_categoriel), sursalaire: num(h.value.sursalaire), parts: num(h.value.parts) }
    for (const k of ['jours_payes', 'jours_absence', 'heures_absence', 'hs1', 'hs2', 'hs3', 'hs4']) c[k] = num(h.value[k]) ?? 0
    resultat.value = (await apiClient.post('/simulation/bulletin', c)).data
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message } finally { enCours.value = false }
}
</script>

<template>
  <div class="page">
    <header>
      <h1>Simulation de bulletin</h1>
      <p class="sous-titre">Calcule un bulletin hypothétique avec le moteur de paie et les paramètres en vigueur. Rien n'est enregistré : utile pour estimer un recrutement, une augmentation ou une prime. Laissez le matricule vide pour simuler un salarié fictif.</p>
    </header>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <form class="card saisie" @submit.prevent="simuler">
      <div class="grille">
        <label class="field"><span class="field-label">Matricule (facultatif)</span><input v-model="matricule" class="input" inputmode="numeric" placeholder="000054" /></label>
        <label class="field"><span class="field-label">Année</span><input v-model.number="h.annee" type="number" class="input" min="2000" max="2100" required /></label>
        <label class="field"><span class="field-label">Mois</span><input v-model.number="h.mois" type="number" class="input" min="1" max="12" required /></label>
        <label class="field"><span class="field-label">Salaire catégoriel</span><input v-model="h.salaire_categoriel" class="input" inputmode="decimal" :placeholder="matricule ? 'Celui de la fiche' : 'Obligatoire'" :required="!matricule" /></label>
        <label class="field"><span class="field-label">Sursalaire</span><input v-model="h.sursalaire" class="input" inputmode="decimal" placeholder="0" /></label>
        <label class="field"><span class="field-label">Parts ITS</span><input v-model="h.parts" class="input" inputmode="decimal" placeholder="1" /></label>
        <label class="field"><span class="field-label">Jours payés</span><input v-model="h.jours_payes" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">Jours d'absence</span><input v-model="h.jours_absence" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">Heures d'absence</span><input v-model="h.heures_absence" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">H. sup. 15 %</span><input v-model="h.hs1" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">H. sup. 50 %</span><input v-model="h.hs2" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">H. sup. nuit / jour férié</span><input v-model="h.hs3" class="input" inputmode="decimal" /></label>
        <label class="field"><span class="field-label">H. sup. 4</span><input v-model="h.hs4" class="input" inputmode="decimal" /></label>
      </div>
      <label v-if="matricule" class="case"><input v-model="h.inclure_rubriques_fixes" type="checkbox" /> Inclure les rubriques fixes du salarié</label>
      <div class="rub">
        <strong>Rubriques supplémentaires</strong>
        <ul v-if="rubriques.length" class="liste">
          <li v-for="(r, i) in rubriques" :key="i"><span>{{ r.code }} · {{ TYPES[r.type] }}</span><span class="num">{{ fmt(r.montant) }}</span>
            <BoutonIcone danger :icone="Trash2" hint="Retirer cette rubrique" @click="rubriques.splice(i, 1)" /></li>
        </ul>
        <div class="ligne">
          <input v-model="nr.code" class="input" placeholder="Code (ex. PRI)" maxlength="6" aria-label="Code de la rubrique" />
          <select v-model="nr.type" class="input" aria-label="Nature"><option v-for="(l, k) in TYPES" :key="k" :value="k">{{ l }}</option></select>
          <input v-model="nr.montant" class="input" inputmode="decimal" placeholder="Montant" aria-label="Montant" />
          <button type="button" class="vbtn vbtn-secondary" @click="ajouterRubrique"><Plus :size="16" />Ajouter</button>
        </div>
      </div>
      <div><button class="vbtn vbtn-primary" type="submit" :disabled="enCours"><Calculator :size="16" />{{ enCours ? 'Calcul…' : 'Simuler' }}</button></div>
    </form>

    <section v-if="resultat" class="card res">
      <h2>Résultat <small>{{ resultat.periode.nature === 'journalier' ? 'journalier' : 'mensuel' }} — simulation, sans valeur de bulletin</small></h2>
      <div class="defile"><table class="t"><thead><tr><th>Code</th><th>Libellé</th><th class="num">Quantité</th><th class="num">Taux</th><th class="num">Montant</th></tr></thead>
        <tbody><tr v-for="(l, i) in resultat.lignes" :key="i"><td>{{ l.code }}</td><td>{{ l.libelle }}</td><td class="num">{{ l.quantite ?? '' }}</td><td class="num">{{ l.taux ?? '' }}</td><td class="num">{{ fmt(l.montant) }}</td></tr></tbody></table></div>
      <div class="kpis">
        <div class="kpi"><span>Total imposable</span><strong>{{ fmt(resultat.totaux.total_imposable) }}</strong></div>
        <div class="kpi"><span>CNPS salarié</span><strong>{{ fmt(resultat.totaux.cnps) }}</strong></div>
        <div class="kpi"><span>ITS</span><strong>{{ fmt(resultat.totaux.its) }}</strong></div>
        <div class="kpi net"><span>Net à payer</span><strong>{{ fmt(resultat.totaux.net_a_payer) }} F</strong></div>
        <div class="kpi"><span>Charges patronales</span><strong>{{ fmt(resultat.charges_patronales.total) }}</strong></div>
        <div class="kpi"><span>Coût employeur</span><strong>{{ fmt(resultat.cout_employeur) }} F</strong></div>
      </div>
      <ul v-if="resultat.anomalies?.length" class="anomalies"><li v-for="(a, i) in resultat.anomalies" :key="i">{{ a }}</li></ul>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); max-width: 1100px; }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); } h2 small { font-weight: 400; color: var(--color-text-muted); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.saisie, .res { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-3) var(--space-4); }
.case { display: flex; align-items: center; gap: 8px; font-size: var(--font-size-sm); }
.rub { display: flex; flex-direction: column; gap: var(--space-2); font-size: var(--font-size-sm); }
.liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.liste li { display: flex; align-items: center; gap: var(--space-3); } .liste li span:first-child { flex: 1; }
.ligne { display: flex; gap: var(--space-2); flex-wrap: wrap; } .ligne .input { flex: 1; min-width: 130px; }
.defile { overflow-x: auto; }
.t { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.t th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.t td { padding: 6px 10px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; } .t th.num { text-align: right; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-3); }
.kpi { display: flex; flex-direction: column; padding: 10px 14px; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.kpi span { font-size: var(--font-size-xs); color: var(--color-text-muted); } .kpi strong { font-size: var(--font-size-lg, 1.15rem); }
.kpi.net { background: var(--color-brand-light); border-color: var(--color-brand); }
.anomalies { margin: 0; padding: 10px 14px 10px 30px; background: var(--color-orange-bg); color: var(--color-orange); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
