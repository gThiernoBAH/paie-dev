<script setup>
/** Graphique Chart.js (ligne, barres, secteurs, anneau). Les couleurs suivent le thème clair/sombre de l'application. */
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import {
  Chart, LineController, BarController, PieController, DoughnutController, LineElement, BarElement, ArcElement, PointElement,
  CategoryScale, LinearScale, Tooltip, Legend, Filler,
} from 'chart.js'

Chart.register(LineController, BarController, PieController, DoughnutController, LineElement, BarElement, ArcElement, PointElement,
  CategoryScale, LinearScale, Tooltip, Legend, Filler)

const props = defineProps({
  type: { type: String, default: 'bar' },                 // line | bar | pie | doughnut
  labels: { type: Array, required: true },
  series: { type: Array, required: true },                // [{ nom, valeurs }]
  titre: { type: String, required: true },                // sert aussi d'étiquette accessible
  horizontal: { type: Boolean, default: false },
  empile: { type: Boolean, default: false },
  unite: { type: String, default: '' },                   // ajoutée aux valeurs des infobulles (ex. « FCFA »)
  hauteur: { type: Number, default: 280 },
})
const PALETTE = ['#2563eb', '#16a34a', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#db2777', '#4b5563', '#ca8a04']
const canvas = ref(null)
let graphe = null
const circulaire = computed(() => props.type === 'pie' || props.type === 'doughnut')
const vide = computed(() => !props.labels.length || props.series.every((s) => s.valeurs.every((v) => !v)))
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const resume = computed(() => props.labels.map((l, i) => `${l} : ${props.series.map((s) => fmt(s.valeurs[i] ?? 0)).join(' / ')}${props.unite ? ' ' + props.unite : ''}`).join(' ; '))

function css(nom, defaut) { return getComputedStyle(document.documentElement).getPropertyValue(nom).trim() || defaut }

function construire() {
  if (!canvas.value || vide.value) return
  graphe?.destroy()
  const texte = css('--color-text-muted', '#6b7280'), grille = css('--color-border', '#e5e7eb')
  const datasets = props.series.map((s, i) => {
    const couleur = PALETTE[i % PALETTE.length]
    if (circulaire.value) return { label: s.nom, data: s.valeurs, backgroundColor: props.labels.map((_, k) => PALETTE[k % PALETTE.length]), borderColor: css('--color-surface', '#fff'), borderWidth: 2 }
    if (props.type === 'line') return { label: s.nom, data: s.valeurs, borderColor: couleur, backgroundColor: couleur + '22', tension: 0.3, pointRadius: 3, fill: props.series.length === 1 }
    return { label: s.nom, data: s.valeurs, backgroundColor: props.series.length === 1 ? couleur : couleur, borderRadius: 4, maxBarThickness: 38 }
  })
  graphe = new Chart(canvas.value, {
    type: props.type,
    data: { labels: props.labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 400 },
      indexAxis: props.horizontal ? 'y' : 'x',
      plugins: {
        legend: { display: circulaire.value || props.series.length > 1, position: circulaire.value ? 'right' : 'bottom', labels: { color: texte, boxWidth: 12, font: { size: 12 } } },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label ? c.dataset.label + ' : ' : (circulaire.value ? c.label + ' : ' : '')}${fmt(c.parsed.y ?? c.parsed.x ?? c.parsed)}${props.unite ? ' ' + props.unite : ''}` } },
      },
      scales: circulaire.value ? {} : {
        x: { stacked: props.empile, ticks: { color: texte, callback: props.horizontal ? (v) => (v >= 1e6 ? fmt(v / 1e6) + ' M' : fmt(v)) : undefined }, grid: { color: grille } },
        y: { stacked: props.empile, beginAtZero: true, ticks: { color: texte, callback: props.horizontal ? undefined : (v) => (v >= 1e6 ? fmt(v / 1e6) + ' M' : fmt(v)) }, grid: { color: grille } },
      },
    },
  })
}
const surTheme = window.matchMedia('(prefers-color-scheme: dark)')
onMounted(() => { construire(); surTheme.addEventListener('change', construire) })
onBeforeUnmount(() => { surTheme.removeEventListener('change', construire); graphe?.destroy() })
watch(() => [props.type, props.labels, props.series, props.horizontal, props.empile], construire, { deep: true, flush: 'post' })
</script>

<template>
  <figure class="graphique">
    <figcaption>{{ titre }}</figcaption>
    <div v-if="vide" class="vide">Pas encore de données.</div>
    <div v-else class="zone" :style="{ height: hauteur + 'px' }">
      <canvas ref="canvas" role="img" :aria-label="`${titre}. ${resume}`"></canvas>
    </div>
  </figure>
</template>

<style scoped>
.graphique { margin: 0; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
figcaption { font-weight: 600; font-size: var(--font-size-sm); }
.zone { position: relative; width: 100%; }
.vide { color: var(--color-text-muted); font-size: var(--font-size-sm); padding: 40px 0; text-align: center; border: 1px dashed var(--color-border); border-radius: var(--radius-md); }
</style>
