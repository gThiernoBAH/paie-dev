<script setup>
import { ref, watch } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'

// v-model = texte JSON du barème : [{"jusqu_a": 75000, "taux": 0}, ..., {"jusqu_a": null, "taux": 32}]
const props = defineProps({ modelValue: String, lectureSeule: Boolean })
const emit = defineEmits(['update:modelValue'])

const lignes = ref([])
function depuisTexte(t) {
  try { return JSON.parse(t).map((x) => ({ jusqu_a: x.jusqu_a ?? '', taux: x.taux ?? '' })) } catch { return [] }
}
watch(() => props.modelValue, (t) => {
  if (JSON.stringify(versTexte(lignes.value)) !== t) lignes.value = depuisTexte(t)
}, { immediate: true })

function versTexte(l) {
  return l.map((x, i) => ({
    jusqu_a: i === l.length - 1 ? null : x.jusqu_a === '' ? '' : Number(String(x.jusqu_a).replace(',', '.')),
    taux: x.taux === '' ? '' : Number(String(x.taux).replace(',', '.')),
  }))
}
function maj() { emit('update:modelValue', JSON.stringify(versTexte(lignes.value))) }
function ajouter() {
  // Nouvelle tranche insérée avant la dernière (qui reste « et au-delà »).
  lignes.value.splice(Math.max(lignes.value.length - 1, 0), 0, { jusqu_a: '', taux: '' })
  maj()
}
function retirer(i) { lignes.value.splice(i, 1); maj() }
</script>

<template>
  <div class="bareme">
    <div class="entete"><span>Jusqu'à (FCFA)</span><span>Taux (%)</span><span></span></div>
    <div v-for="(l, i) in lignes" :key="i" class="ligne">
      <input v-if="i < lignes.length - 1" v-model="l.jusqu_a" class="input" inputmode="decimal" :disabled="lectureSeule" :aria-label="`Limite de la tranche ${i + 1}`" @input="maj" />
      <span v-else class="et-au-dela">et au-delà</span>
      <input v-model="l.taux" class="input" inputmode="decimal" :disabled="lectureSeule" :aria-label="`Taux de la tranche ${i + 1}`" @input="maj" />
      <button v-if="!lectureSeule && lignes.length > 1" type="button" class="icone" :aria-label="`Supprimer la tranche ${i + 1}`" @click="retirer(i)"><Trash2 :size="16" /></button>
      <span v-else></span>
    </div>
    <button v-if="!lectureSeule" type="button" class="vbtn vbtn-secondary" @click="ajouter"><Plus :size="16" />Ajouter une tranche</button>
  </div>
</template>

<style scoped>
.bareme { display: flex; flex-direction: column; gap: var(--space-2); }
.entete, .ligne { display: grid; grid-template-columns: 1fr 90px 36px; gap: var(--space-2); align-items: center; }
.entete { font-size: var(--font-size-xs); font-weight: 600; color: var(--color-text-muted); }
.et-au-dela { font-size: var(--font-size-sm); color: var(--color-text-muted); padding-left: var(--space-3); }
.icone { border: none; background: none; cursor: pointer; color: var(--color-rouge); width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; }
.bareme .vbtn { align-self: flex-start; }
</style>
