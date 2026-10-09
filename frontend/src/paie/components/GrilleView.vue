<script setup>
/** Grille salariale : tranches horaires (heures × coefficient), base horaire par catégorie, import depuis le legacy. */
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { Save, Upload, Eye, Check } from 'lucide-vue-next'

const moi = lireUtilisateur()
const peutEcrire = aLaPermission(moi, 'gerer_parametres')
const tranches = ref([])
const categories = ref([])
const erreur = ref('')
const message = ref('')
const dateEffet = ref(new Date().toLocaleDateString('sv-SE'))
const bases = ref({})              // saisies en cours : categorie_id -> texte
const import_ = ref({ contenu: '', apercu: null })
const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 }))
const nombre = (v) => Number(String(v).replace(/\s/g, '').replace(',', '.'))
const ETAT = { ok: 'Prête', categorie_inconnue: 'Catégorie inconnue', base_invalide: 'Base invalide' }
const vide = computed(() => categories.value.length && categories.value.every((c) => c.base_horaire === null))

async function charger() {
  erreur.value = ''
  try {
    tranches.value = (await apiClient.get('/grille/tranches')).data.map((t) => ({ ...t, heures: Number(t.heures), coefficient: Number(t.coefficient) }))
    categories.value = (await apiClient.get('/grille/categories', { params: { date_effet: dateEffet.value } })).data
  } catch (e) { erreur.value = messageErreur(e) }
}
async function enregistrerTranches() {
  erreur.value = ''; message.value = ''
  try { await apiClient.put('/grille/tranches', tranches.value); message.value = 'Tranches enregistrées.'; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function enregistrerBase(c) {
  const v = nombre(bases.value[c.categorie_id])
  if (!v || v <= 0) { erreur.value = 'Base horaire invalide.'; return }
  erreur.value = ''; message.value = ''
  try { await apiClient.put(`/grille/categories/${c.categorie_id}`, { date_effet: dateEffet.value, base_horaire: v }); delete bases.value[c.categorie_id]; message.value = `Base de « ${c.libelle} » enregistrée à partir du ${new Date(dateEffet.value).toLocaleDateString('fr-FR')}.`; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
async function apercu(appliquer) {
  erreur.value = ''; message.value = ''
  try {
    const r = (await apiClient.post('/grille/import', { contenu: import_.value.contenu, date_effet: dateEffet.value, appliquer })).data
    import_.value.apercu = r
    if (appliquer) { message.value = `${r.appliquees} catégorie(s) importée(s).`; await charger() }
  } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Grille salariale</h1>
      <p class="sous-titre">Salaire mensuel d'une catégorie pour une tranche = base horaire × heures de la tranche × coefficient (arrondi au franc). Chaque salarié a une catégorie et une tranche ; un salaire inférieur à la grille est signalé sur sa fiche. La grille est une référence : elle ne modifie aucun salaire.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <section class="card bloc">
      <h2>Tranches horaires</h2>
      <p class="aide">Valeurs de départ déduites de l'ancien logiciel : à confirmer avec le service de la paie.</p>
      <div class="defile"><table class="t"><thead><tr><th>N°</th><th>Libellé</th><th class="num">Heures / mois</th><th class="num">Coefficient</th></tr></thead>
        <tbody><tr v-for="t in tranches" :key="t.numero"><td>{{ t.numero }}</td>
          <td><input v-model="t.libelle" class="input" :disabled="!peutEcrire" aria-label="Libellé" /></td>
          <td class="num"><input v-model.number="t.heures" class="input num" type="number" step="0.0001" min="0" :disabled="!peutEcrire" aria-label="Heures" /></td>
          <td class="num"><input v-model.number="t.coefficient" class="input num" type="number" step="0.0001" min="0.0001" :disabled="!peutEcrire" aria-label="Coefficient" /></td></tr></tbody></table></div>
      <div v-if="peutEcrire" class="ecriture"><button class="vbtn vbtn-primary" @click="enregistrerTranches"><Save :size="15" />Enregistrer les tranches</button></div>
    </section>

    <section class="card bloc">
      <div class="entete-bloc">
        <h2>Base horaire par catégorie</h2>
        <label class="field inline"><span class="field-label">À la date du</span><input v-model="dateEffet" type="date" class="input" @change="charger" /></label>
      </div>
      <p v-if="vide" class="aide">Aucune base saisie : renseignez-les ci-dessous ou importez le tableau de l'ancien logiciel.</p>
      <div class="defile"><table class="t"><thead><tr><th>Catégorie</th><th>Libellé</th><th class="num">Salariés</th><th class="num">Base horaire</th>
        <th v-for="t in tranches" :key="t.numero" class="num">{{ t.libelle }}</th><th v-if="peutEcrire" class="act">Nouvelle base</th></tr></thead>
        <tbody><tr v-for="c in categories" :key="c.categorie_id"><td>{{ c.code }}</td><td>{{ c.libelle }}</td><td class="num">{{ c.nb_salaries }}</td>
          <td class="num">{{ c.base_horaire === null ? '—' : Number(c.base_horaire).toLocaleString('fr-FR', { maximumFractionDigits: 4 }) }}</td>
          <td v-for="(s, i) in c.salaires" :key="i" class="num">{{ fmt(s) }}</td>
          <td v-if="peutEcrire" class="act ecriture"><span class="saisie"><input v-model="bases[c.categorie_id]" class="input num" inputmode="decimal" placeholder="0,00" :aria-label="`Nouvelle base de ${c.libelle}`" @keyup.enter="enregistrerBase(c)" />
            <button class="vbtn vbtn-secondary petit" :disabled="!bases[c.categorie_id]" data-hint="Enregistrer à partir de la date choisie" @click="enregistrerBase(c)"><Check :size="14" /></button></span></td></tr></tbody></table></div>
    </section>

    <section v-if="peutEcrire" class="card bloc ecriture">
      <h2>Importer depuis l'ancien logiciel</h2>
      <p class="aide">Collez le tableau (copier depuis la grille ou un fichier Excel/CSV) avec une colonne CATEGORIE et une colonne BASE HEURE ; à défaut, SALAIRE MENSUEL TRANCHE 1 sert à déduire la base. Les bases sont enregistrées à la date choisie ci-dessus.</p>
      <textarea v-model="import_.contenu" class="input zone" rows="6" placeholder="CATEGORIE&#9;LIBELLE&#9;BASE HEURE&#10;1 A&#9;1 A&#9;667,53" aria-label="Tableau à importer"></textarea>
      <div class="ligne"><button class="vbtn vbtn-secondary" :disabled="!import_.contenu.trim()" @click="apercu(false)"><Eye :size="15" />Aperçu</button>
        <button class="vbtn vbtn-primary" :disabled="!import_.apercu || !import_.apercu.ok" @click="apercu(true)"><Upload :size="15" />Appliquer ({{ import_.apercu?.ok || 0 }})</button></div>
      <div v-if="import_.apercu" class="defile"><table class="t"><thead><tr><th>Catégorie</th><th>Libellé</th><th class="num">Base</th><th>État</th></tr></thead>
        <tbody><tr v-for="(l, i) in import_.apercu.lignes" :key="i" :class="{ off: l.etat !== 'ok' }"><td>{{ l.categorie }}</td><td>{{ l.libelle }}</td><td class="num">{{ l.base_horaire ?? '—' }}</td><td>{{ ETAT[l.etat] }}</td></tr></tbody></table></div>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); max-width: 1300px; }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 800px; }
.bloc { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); min-width: 0; }
.entete-bloc { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: var(--space-3); }
.aide { font-size: var(--font-size-sm); color: var(--color-text-muted); margin: 0; }
.defile { overflow-x: auto; }
.t { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.t th { text-align: left; padding: 8px 10px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); white-space: nowrap; }
.t td { padding: 5px 10px; border-bottom: 1px solid var(--color-border); }
.t th.num, .t td.num { text-align: right; font-variant-numeric: tabular-nums; }
.input.num { text-align: right; max-width: 130px; }
.saisie { display: inline-flex; gap: 6px; align-items: center; } .saisie .input { width: 100px; }
.zone { font-family: monospace; width: 100%; }
.ligne { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.off { opacity: .55; } .act { white-space: nowrap; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
