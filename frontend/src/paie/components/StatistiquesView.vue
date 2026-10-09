<script setup>
/** Onglets « Statistiques » (effectifs) et « Masse salariale » (réalisé, prêts, prévisionnel) du tableau de bord : même source, deux vues. */
import { ref, computed, watch, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import Graphique from '@/components/Graphique.vue'

const props = defineProps({ vue: { type: String, default: 'stats' } })   // 'stats' | 'masse'
const annee = ref(new Date().getFullYear())
const serviceId = ref('')
const d = ref(null)
const erreur = ref('')
const chargement = ref(false)
const fmt = (n) => (n === null || n === undefined ? '—' : Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 }))
const serie = (s, nom = 'Salariés') => [{ nom, valeurs: s?.valeurs || [] }]
const e = computed(() => d.value?.effectifs)
const m = computed(() => d.value?.masse)
const p = computed(() => d.value?.previsionnel)
const annees = computed(() => { const a = new Date().getFullYear(); return [a - 3, a - 2, a - 1, a, a + 1] })

async function charger() {
  chargement.value = true; erreur.value = ''
  try {
    d.value = (await apiClient.get('/tableau-de-bord/statistiques', { params: { annee: annee.value, ...(serviceId.value ? { service_id: serviceId.value } : {}) } })).data
  } catch (x) { erreur.value = messageErreur(x) } finally { chargement.value = false }
}
watch([annee, serviceId], charger)
onMounted(charger)
</script>

<template>
  <div class="stats">
    <div class="filtres">
      <label class="field"><span class="field-label">Année</span><select v-model.number="annee" class="input"><option v-for="a in annees" :key="a" :value="a">{{ a }}</option></select></label>
      <label v-if="d?.services?.length" class="field"><span class="field-label">Service</span>
        <select v-model="serviceId" class="input"><option value="">Tous les services</option><option v-for="s in d.services" :key="s.id" :value="s.id">{{ s.libelle }}</option></select></label>
      <span v-if="chargement" class="aide">Chargement…</span>
    </div>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <!-- Effectifs -->
    <template v-if="e && vue === 'stats'">
      <h2>Effectifs <small>au {{ new Date(e.au + 'T00:00:00').toLocaleDateString('fr-FR') }}</small></h2>
      <section class="kpis">
        <article class="card kpi"><span>Effectif</span><strong>{{ fmt(e.kpi.effectif) }}</strong></article>
        <article class="card kpi"><span>Âge moyen</span><strong>{{ e.kpi.age_moyen ?? '—' }}<small v-if="e.kpi.age_moyen"> ans</small></strong></article>
        <article class="card kpi"><span>Ancienneté moyenne</span><strong>{{ e.kpi.anciennete_moyenne ?? '—' }}<small v-if="e.kpi.anciennete_moyenne"> ans</small></strong></article>
        <article class="card kpi"><span>Entrées / sorties {{ annee }}</span><strong>{{ e.kpi.entrees }} / {{ e.kpi.sorties }}</strong></article>
        <article class="card kpi"><span>Taux de départ</span><strong>{{ e.kpi.taux_depart ?? '—' }}<small v-if="e.kpi.taux_depart !== null"> %</small></strong></article>
      </section>
      <section class="grille">
        <div class="card cadre"><Graphique type="doughnut" titre="Répartition par sexe" :labels="e.sexe.labels" :series="serie(e.sexe)" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Tranches d'âge" :labels="e.tranches_age.labels" :series="serie(e.tranches_age)" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Ancienneté" :labels="e.anciennete.labels" :series="serie(e.anciennete)" /></div>
        <div class="card cadre"><Graphique type="pie" titre="Types de contrat" :labels="e.type_contrat.labels" :series="serie(e.type_contrat)" /></div>
        <div class="card cadre"><Graphique type="doughnut" titre="Mensuels / journaliers" :labels="e.type_remuneration.labels" :series="serie(e.type_remuneration)" /></div>
        <div class="card cadre"><Graphique type="bar" horizontal titre="Effectif par service" :labels="e.services.labels" :series="serie(e.services)" /></div>
        <div class="card cadre"><Graphique type="bar" horizontal titre="Effectif par section" :labels="e.sections.labels" :series="serie(e.sections)" /></div>
        <div class="card cadre"><Graphique type="bar" horizontal titre="Effectif par emploi" :labels="e.emplois.labels" :series="serie(e.emplois)" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Effectif par catégorie" :labels="e.categories.labels" :series="serie(e.categories)" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Jours d'absence approuvés (année)" unite="jours" :labels="e.absences.labels" :series="serie(e.absences, 'Jours')" /></div>
        <div v-if="p" class="card cadre large"><Graphique type="bar" horizontal titre="Coût employeur annuel prévisionnel par service" unite="FCFA" :labels="p.par_service.labels" :series="[{ nom: 'Annuel', valeurs: p.par_service.annuel }]" /></div>
      </section>
    </template>

    <!-- Masse salariale réalisée -->
    <template v-if="m && vue === 'masse'">
      <h2>Masse salariale réalisée <small>bulletins validés {{ annee }}</small></h2>
      <section class="kpis">
        <article class="card kpi"><span>Brut cumulé</span><strong>{{ fmt(m.kpi.brut_total) }}<small> F</small></strong></article>
        <article class="card kpi"><span>Net payé cumulé</span><strong>{{ fmt(m.kpi.net_total) }}<small> F</small></strong></article>
        <article class="card kpi"><span>Coût employeur cumulé</span><strong>{{ fmt(m.kpi.cout_total) }}<small> F</small></strong></article>
        <article class="card kpi"><span>Coût moyen / salarié (dernier mois)</span><strong>{{ fmt(m.kpi.cout_moyen_par_salarie) }}<small v-if="m.kpi.cout_moyen_par_salarie"> F</small></strong></article>
        <article class="card kpi"><span>Mois payés</span><strong>{{ m.kpi.mois_payes }}</strong></article>
      </section>
      <p v-if="!m.kpi.mois_payes" class="aide">Aucune paie validée en {{ annee }} : les graphiques se rempliront à la validation des campagnes.</p>
      <section class="grille">
        <div class="card cadre large"><Graphique type="line" titre="Évolution mensuelle (brut, net, coût employeur)" unite="FCFA" :labels="m.evolution.labels"
          :series="[{ nom: 'Brut', valeurs: m.evolution.brut }, { nom: 'Net', valeurs: m.evolution.net }, { nom: 'Coût employeur', valeurs: m.evolution.cout }]" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Salariés payés par mois" :labels="m.effectif_paye.labels" :series="serie(m.effectif_paye)" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Coût employeur par trimestre" unite="FCFA" :labels="m.trimestres.labels" :series="serie(m.trimestres, 'Coût')" /></div>
        <div class="card cadre"><Graphique type="doughnut" titre="Où va le coût employeur" unite="FCFA" :labels="m.decomposition.labels" :series="serie(m.decomposition, 'FCFA')" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Heures supplémentaires payées" unite="F" :labels="m.heures_sup.labels" :series="serie(m.heures_sup, 'Montant')" /></div>
        <div class="card cadre large"><Graphique type="bar" horizontal titre="Par service (net et coût employeur)" unite="FCFA" :labels="m.par_service.labels"
          :series="[{ nom: 'Net', valeurs: m.par_service.net }, { nom: 'Coût employeur', valeurs: m.par_service.cout }]" /></div>
        <div class="card cadre"><Graphique type="bar" horizontal titre="Par section" unite="FCFA" :labels="m.par_section.labels" :series="[{ nom: 'Coût employeur', valeurs: m.par_section.cout }]" /></div>
        <div class="card cadre"><Graphique type="bar" horizontal titre="Par emploi" unite="FCFA" :labels="m.par_emploi.labels" :series="[{ nom: 'Coût employeur', valeurs: m.par_emploi.cout }]" /></div>
        <div class="card cadre"><Graphique type="bar" titre="Par catégorie" unite="FCFA" :labels="m.par_categorie.labels" :series="[{ nom: 'Coût employeur', valeurs: m.par_categorie.cout }]" /></div>
        <div class="card cadre"><Graphique type="pie" titre="Par nature de bulletin" unite="FCFA" :labels="m.par_nature.labels" :series="[{ nom: 'Coût employeur', valeurs: m.par_nature.cout }]" /></div>
      </section>
      <section class="kpis">
        <article class="card kpi"><span>Prêts en cours (reste dû)</span><strong>{{ fmt(m.prets.encours) }}<small> F</small></strong><small>{{ m.prets.prets_actifs }} prêt(s) actif(s)</small></article>
        <article class="card kpi"><span>Prêts passés en perte</span><strong>{{ fmt(m.prets.abandonne) }}<small> F</small></strong></article>
      </section>
    </template>

    <!-- Prévisionnel -->
    <template v-if="p && vue === 'masse'">
      <h2>Prévisionnel <small>barème en vigueur, salariés mensuels actuels — le détail par service est dans l'onglet Statistiques</small></h2>
      <section class="kpis">
        <article class="card kpi"><span>Coût employeur mensuel</span><strong>{{ fmt(p.kpi.cout_mensuel) }}<small> F</small></strong></article>
        <article class="card kpi"><span>Coût employeur annuel (× 12)</span><strong>{{ fmt(p.kpi.cout_annuel) }}<small> F</small></strong></article>
        <article class="card kpi"><span>Salariés chiffrés</span><strong>{{ p.kpi.salaries_chiffres }}</strong>
          <small v-if="p.kpi.journaliers_non_chiffres">+ {{ p.kpi.journaliers_non_chiffres }} journalier(s) non chiffré(s) (paie à l'heure)</small>
          <small v-if="p.kpi.sans_salaire">{{ p.kpi.sans_salaire }} sans salaire en vigueur</small></article>
      </section>
      <p class="aide">Estimation sur un mois complet, sans absence ni heures supplémentaires, avec les rubriques fixes ; ce n'est pas un engagement de paie.</p>
    </template>
  </div>
</template>

<style scoped>
.stats { display: flex; flex-direction: column; gap: var(--space-4); }
h2 { margin: var(--space-4) 0 0; font-size: var(--font-size-lg, 1.15rem); } h2 small { font-weight: 400; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.filtres { display: flex; gap: var(--space-4); align-items: flex-end; flex-wrap: wrap; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--space-3); }
.kpi { padding: var(--space-3) var(--space-4); display: flex; flex-direction: column; gap: 2px; }
.kpi span { color: var(--color-text-muted); font-size: var(--font-size-xs); } .kpi strong { font-size: var(--font-size-xl); } .kpi strong small, .kpi > small { font-size: var(--font-size-xs); font-weight: 400; color: var(--color-text-muted); }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: var(--space-4); }
.cadre { padding: var(--space-4); min-width: 0; } .cadre.large { grid-column: 1 / -1; }
.aide { font-size: var(--font-size-sm); color: var(--color-text-muted); margin: 0; }
@media (max-width: 760px) { .grille { grid-template-columns: minmax(0, 1fr); } }
</style>
