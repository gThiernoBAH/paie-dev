<script setup>
/**
 * DataTable : tableau commun à toute l'application -- recherche, tri par colonne, pagination.
 *
 *   <DataTable :colonnes="[{ cle:'nom', libelle:'Nom', tri:true }, …]" :lignes="liste" @ligne="ouvrir">
 *     <template #cell-statut="{ ligne }">…</template>     // rendu personnalisé d'une colonne
 *     <template #actions="{ ligne }">…</template>          // colonne d'actions en fin de ligne
 *     <template #outils>…filtres supplémentaires…</template>
 *   </DataTable>
 *
 * Colonne : { cle, libelle, tri?: bool, align?: 'droite', valeur?: (ligne)=>any, texte?: (ligne)=>string,
 *             format?: (valeur, ligne)=>string, classe?: string }
 *  - valeur : valeur brute utilisée pour le tri (par défaut ligne[cle]).
 *  - texte  : texte affiché et recherché (par défaut format(valeur) ou valeur).
 *
 * Mode `serveur` (listes volumineuses) : le tri, la recherche et la page sont délégués à l'API ;
 * le composant émet « changer » ({ page, taille, tri, sens, recherche }) et attend `lignes` + `total`.
 */
import { computed, ref, watch } from 'vue'
import { ChevronUp, ChevronDown, ChevronsUpDown, Search, ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  colonnes: { type: Array, required: true },
  lignes: { type: Array, default: () => [] },
  cleLigne: { type: String, default: 'id' },
  recherche: { type: Boolean, default: true },
  placeholderRecherche: { type: String, default: 'Rechercher…' },
  taillePage: { type: Number, default: 25 },
  vide: { type: String, default: 'Aucune donnée.' },
  ligneCliquable: { type: Boolean, default: false },
  classeLigne: { type: Function, default: null },
  serveur: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  chargement: { type: Boolean, default: false },
  triInitial: { type: String, default: '' },
  sensInitial: { type: String, default: 'asc' },
})
const emit = defineEmits(['ligne', 'changer'])

const terme = ref('')
const tri = ref(props.triInitial)
const sens = ref(props.sensInitial)
const page = ref(1)
const taille = ref(props.taillePage)
const TAILLES = [10, 25, 50, 100]

const valeurBrute = (c, l) => (c.valeur ? c.valeur(l) : l[c.cle])
function texteCellule(c, l) {
  if (c.texte) return c.texte(l)
  const v = valeurBrute(c, l)
  if (c.format) return c.format(v, l)
  return v === null || v === undefined || v === '' ? '' : String(v)
}
const normaliser = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

const filtrees = computed(() => {
  if (props.serveur || !terme.value.trim()) return props.lignes
  const t = normaliser(terme.value.trim())
  return props.lignes.filter((l) => props.colonnes.some((c) => normaliser(texteCellule(c, l)).includes(t)))
})
const triees = computed(() => {
  if (props.serveur || !tri.value) return filtrees.value
  const c = props.colonnes.find((x) => x.cle === tri.value)
  if (!c) return filtrees.value
  const f = sens.value === 'asc' ? 1 : -1
  return [...filtrees.value].sort((a, b) => {
    const va = valeurBrute(c, a), vb = valeurBrute(c, b)
    if (va === vb) return 0
    if (va === null || va === undefined || va === '') return 1      // les vides finissent toujours en bas
    if (vb === null || vb === undefined || vb === '') return -1
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * f
    return String(va).localeCompare(String(vb), 'fr', { numeric: true, sensitivity: 'base' }) * f
  })
})
const nbTotal = computed(() => (props.serveur ? props.total : triees.value.length))
const nbPages = computed(() => Math.max(1, Math.ceil(nbTotal.value / taille.value)))
const visibles = computed(() => {
  if (props.serveur) return props.lignes
  const d = (page.value - 1) * taille.value
  return triees.value.slice(d, d + taille.value)
})
const premier = computed(() => (nbTotal.value ? (page.value - 1) * taille.value + 1 : 0))
const dernier = computed(() => Math.min(nbTotal.value, page.value * taille.value))

const pagesAffichees = computed(() => {   // 1 … 4 5 6 … 12
  const n = nbPages.value, p = page.value, s = new Set([1, n, p, p - 1, p + 1])
  const liste = [...s].filter((x) => x >= 1 && x <= n).sort((a, b) => a - b)
  const sortie = []
  liste.forEach((x, i) => { if (i && x - liste[i - 1] > 1) sortie.push('…'); sortie.push(x) })
  return sortie
})

function notifier() { if (props.serveur) emit('changer', { page: page.value, taille: taille.value, tri: tri.value, sens: sens.value, recherche: terme.value.trim() }) }
function trier(c) {
  if (!c.tri) return
  if (tri.value === c.cle) sens.value = sens.value === 'asc' ? 'desc' : 'asc'
  else { tri.value = c.cle; sens.value = 'asc' }
  page.value = 1; notifier()
}
function aller(p) { page.value = Math.min(Math.max(1, p), nbPages.value); notifier() }
let minuteur
watch(terme, () => { page.value = 1; if (props.serveur) { clearTimeout(minuteur); minuteur = setTimeout(notifier, 300) } })
watch(taille, () => { page.value = 1; notifier() })
watch(() => props.lignes.length, () => { if (page.value > nbPages.value) page.value = nbPages.value })
const ariaTri = (c) => (tri.value === c.cle ? (sens.value === 'asc' ? 'ascending' : 'descending') : 'none')
defineExpose({ page, reinitialiser: () => { page.value = 1 } })
</script>

<template>
  <div class="dt">
    <div v-if="recherche || $slots.outils" class="dt-outils">
      <label v-if="recherche" class="dt-recherche"><Search :size="16" />
        <input v-model="terme" type="search" :placeholder="placeholderRecherche" aria-label="Rechercher dans le tableau" />
      </label>
      <slot name="outils" />
    </div>
    <div class="card dt-cadre">
      <table>
        <thead>
          <tr>
            <th v-for="c in colonnes" :key="c.cle" :class="[c.align === 'droite' ? 'droite' : '', c.tri ? 'triable' : '']" :aria-sort="ariaTri(c)" scope="col">
              <button v-if="c.tri" type="button" class="dt-tri" :data-hint="`Trier par ${c.libelle}`" @click="trier(c)">
                {{ c.libelle }}
                <ChevronUp v-if="tri === c.cle && sens === 'asc'" :size="14" class="actif" />
                <ChevronDown v-else-if="tri === c.cle" :size="14" class="actif" />
                <ChevronsUpDown v-else :size="14" />
              </button>
              <span v-else>{{ c.libelle }}</span>
            </th>
            <th v-if="$slots.actions" class="dt-col-actions" scope="col"><span class="sr-seul">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(l, i) in visibles" :key="l[cleLigne] ?? i" :class="[ligneCliquable ? 'cliquable' : '', classeLigne ? classeLigne(l) : '']"
              :tabindex="ligneCliquable ? 0 : undefined" @click="ligneCliquable && emit('ligne', l)" @keydown.enter="ligneCliquable && emit('ligne', l)">
            <td v-for="c in colonnes" :key="c.cle" :class="[c.align === 'droite' ? 'droite' : '', c.classe || '']">
              <slot :name="`cell-${c.cle}`" :ligne="l" :valeur="valeurBrute(c, l)">{{ texteCellule(c, l) }}</slot>
            </td>
            <td v-if="$slots.actions" class="dt-col-actions" @click.stop><div class="dt-actions"><slot name="actions" :ligne="l" /></div></td>
          </tr>
          <tr v-if="!visibles.length"><td :colspan="colonnes.length + ($slots.actions ? 1 : 0)" class="vide">{{ chargement ? 'Chargement…' : (terme ? 'Aucun résultat pour cette recherche.' : vide) }}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="dt-pied">
      <span>{{ nbTotal ? `Lignes ${premier}–${dernier} sur ${nbTotal}` : '0 ligne' }}</span>
      <label class="dt-taille">Par page
        <select v-model.number="taille" class="input" aria-label="Lignes par page"><option v-for="t in TAILLES" :key="t" :value="t">{{ t }}</option></select>
      </label>
      <nav class="dt-pages" aria-label="Pagination">
        <button type="button" class="dt-pg" :disabled="page <= 1" data-hint="Page précédente" aria-label="Page précédente" @click="aller(page - 1)"><ChevronLeft :size="16" /></button>
        <template v-for="(p, i) in pagesAffichees" :key="i">
          <span v-if="p === '…'" class="dt-points">…</span>
          <button v-else type="button" class="dt-pg" :class="{ courante: p === page }" :aria-current="p === page ? 'page' : undefined" @click="aller(p)">{{ p }}</button>
        </template>
        <button type="button" class="dt-pg" :disabled="page >= nbPages" data-hint="Page suivante" aria-label="Page suivante" @click="aller(page + 1)"><ChevronRight :size="16" /></button>
      </nav>
    </div>
  </div>
</template>

<style scoped>
.dt { display: flex; flex-direction: column; gap: var(--space-3); min-width: 0; }
.dt-outils { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; }
.dt-recherche { display: flex; align-items: center; gap: 8px; border: 1px solid var(--color-border-fort); border-radius: var(--radius-md); padding: 0 12px; background: var(--color-surface); min-height: 40px; color: var(--color-text-muted); }
.dt-recherche input { border: none; outline: none; font-size: var(--font-size-sm); background: none; min-width: 280px; color: var(--color-text); }
.dt-cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: var(--color-surface-2); color: var(--color-text-muted); font-weight: 600; font-size: var(--font-size-xs); letter-spacing: .03em; border-bottom: 1px solid var(--color-border); white-space: nowrap; }
td { padding: 9px 14px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
.droite { text-align: right; font-variant-numeric: tabular-nums; }
.dt-tri { display: inline-flex; align-items: center; gap: 4px; background: none; border: none; padding: 0; font: inherit; color: inherit; cursor: pointer; letter-spacing: inherit; }
.dt-tri svg { opacity: .45; } .dt-tri svg.actif { opacity: 1; color: var(--color-brand); }
.dt-tri:hover { color: var(--color-brand-dark); }
.dt-tri:focus-visible { outline: 2px solid var(--color-brand); outline-offset: 2px; border-radius: 4px; }
.cliquable { cursor: pointer; }
.cliquable:hover, .cliquable:focus-visible { background: var(--color-surface-2); outline: none; }
.dt-col-actions { width: 1%; white-space: nowrap; }
.dt-actions { display: flex; gap: 6px; justify-content: flex-end; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.dt-pied { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.dt-taille { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.dt-taille .input { min-height: 34px; width: auto; padding: 0 8px; font-size: var(--font-size-sm); }
.dt-pages { display: flex; gap: 4px; align-items: center; }
.dt-pg { min-width: 34px; height: 34px; padding: 0 8px; border: 1px solid var(--color-border); border-radius: 9px; background: var(--color-surface); color: var(--color-text); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; font-size: var(--font-size-sm); }
.dt-pg:hover:not(:disabled):not(.courante) { background: var(--color-brand-light); border-color: var(--color-brand); }
.dt-pg.courante { background: var(--color-brand); border-color: var(--color-brand); color: var(--color-text-inverse); font-weight: 600; }
.dt-pg:disabled { opacity: .4; cursor: not-allowed; }
.dt-points { padding: 0 4px; }
.sr-seul { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@media (max-width: 760px) { .dt-taille { margin-left: 0; } .dt-recherche input { min-width: 0; width: 100%; } .dt-recherche { flex: 1; } }
</style>
