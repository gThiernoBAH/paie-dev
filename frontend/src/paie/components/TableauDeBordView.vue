<script setup>
import { ref, onMounted } from 'vue'
import apiClient from '@/api/client'
import { lireUtilisateur } from '@/api/session'
import { Users, Wallet, CalendarRange, Palmtree, Landmark, Mail, SlidersHorizontal, ArrowRight } from 'lucide-vue-next'

const utilisateur = lireUtilisateur()
const t = ref(null)
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
onMounted(async () => { try { t.value = (await apiClient.get('/tableau-de-bord')).data } catch { /* indicateurs facultatifs */ } })

const attentes = [
  { cle: 'parametres_critiques_a_confirmer', icone: SlidersHorizontal, texte: (n) => `${n} paramètre(s) critique(s) à confirmer — la validation des bulletins est bloquée`, vers: '/parametrage' },
  { cle: 'conges_en_attente', icone: Palmtree, texte: (n) => `${n} demande(s) de congé à traiter`, vers: '/conges' },
  { cle: 'virements_a_lancer', icone: Landmark, texte: (n) => `${n} lot(s) de virement préparé(s), pas encore lancé(s)`, vers: '/virements' },
  { cle: 'envois_en_echec', icone: Mail, texte: (n) => `${n} envoi(s) de bulletin par e-mail en échec`, vers: '/campagnes' },
]
</script>

<template>
  <div class="page">
    <header>
      <h1>Tableau de bord</h1>
      <p class="sous-titre">Bonjour {{ utilisateur?.prenom || utilisateur?.nom }}.</p>
    </header>

    <section v-if="t" class="indicateurs">
      <article v-if="t.effectif_actif !== null" class="card kpi">
        <div class="icone"><Users :size="20" /></div><span>Effectif en activité</span><strong>{{ fmt(t.effectif_actif) }}</strong>
      </article>
      <router-link v-if="t.derniere_paie" :to="`/campagnes/${t.derniere_paie.campagne_id}`" class="card kpi lien">
        <div class="icone"><Wallet :size="20" /></div><span>Dernière paie validée</span>
        <strong>{{ fmt(t.derniere_paie.net) }} FCFA</strong><small>{{ t.derniere_paie.libelle }} · {{ t.derniere_paie.bulletins }} bulletin(s)</small>
      </router-link>
      <router-link v-if="t.campagne_en_cours" :to="`/campagnes/${t.campagne_en_cours.campagne_id}`" class="card kpi lien">
        <div class="icone"><CalendarRange :size="20" /></div><span>Campagne en cours</span>
        <strong>{{ t.campagne_en_cours.libelle }}</strong><small>{{ t.campagne_en_cours.statut === 'ouverte' ? 'À préparer et calculer' : 'Calculée — à valider' }}</small>
      </router-link>
    </section>

    <section v-if="t" class="attentes">
      <template v-for="a in attentes" :key="a.cle">
        <router-link v-if="t.a_traiter[a.cle]" :to="a.vers" class="alerte">
          <component :is="a.icone" :size="18" /><span>{{ a.texte(t.a_traiter[a.cle]) }}</span><ArrowRight :size="16" />
        </router-link>
      </template>
    </section>
    <p v-if="t && !t.effectif_actif && !t.derniere_paie && !t.campagne_en_cours && !Object.values(t.a_traiter).some(Boolean)" class="vide">
      Rien à signaler. Commencez par créer vos salariés, puis ouvrez une campagne de paie.
    </p>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-6); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); }
.indicateurs { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--space-4); }
.kpi { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: 4px; text-decoration: none; color: inherit; }
.kpi span { color: var(--color-text-muted); font-size: var(--font-size-sm); } .kpi strong { font-size: var(--font-size-xl); } .kpi small { color: var(--color-text-muted); }
.lien:hover { border-color: var(--color-brand); }
.icone { width: 40px; height: 40px; border-radius: var(--radius-md); background: var(--color-brand-light); color: var(--color-brand); display: flex; align-items: center; justify-content: center; margin-bottom: 4px; }
.attentes { display: flex; flex-direction: column; gap: var(--space-2); max-width: 860px; }
.alerte { display: flex; align-items: center; gap: var(--space-3); padding: 12px 16px; border-radius: var(--radius-md); background: var(--color-orange-bg); color: var(--color-orange); font-size: var(--font-size-sm); text-decoration: none; }
.alerte span { flex: 1; }
.vide { color: var(--color-text-muted); }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
