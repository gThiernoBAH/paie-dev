<script setup>
/** Monté UNE SEULE FOIS dans App.vue. Voir composables/useConfirm.js. */
import { onMounted, onUnmounted, nextTick, ref, watch } from 'vue'
import { _etatConfirm, _repondre } from '@/composables/useConfirm'

const etat = _etatConfirm()
const boutonAnnuler = ref(null)
const premierChamp = ref(null)

function auClavier(e) {
  if (!etat.visible) return
  if (e.key === 'Escape') _repondre(false)
  if (e.key === 'Enter' && etat.champs.length && e.target.tagName !== 'TEXTAREA') { e.preventDefault(); _repondre(true) }
}
// Focus sur « Annuler » (ou le premier champ) : une action destructrice ne part jamais d'un Entrée trop rapide.
watch(() => etat.visible, async (v) => {
  if (!v) return
  await nextTick()
  ;(premierChamp.value?.[0] || premierChamp.value || boutonAnnuler.value)?.focus?.()
})
onMounted(() => window.addEventListener('keydown', auClavier))
onUnmounted(() => window.removeEventListener('keydown', auClavier))
</script>

<template>
  <Teleport to="body">
    <div v-if="etat.visible" class="conf-fond" @click.self="_repondre(false)">
      <div class="conf-boite" role="alertdialog" aria-modal="true" :aria-label="etat.titre">
        <h2 class="conf-titre">{{ etat.titre }}</h2>
        <p v-if="etat.message" class="conf-message">{{ etat.message }}</p>
        <div v-for="c in etat.champs" :key="c.cle" class="field conf-champ">
          <label class="field-label" :for="`conf-${c.cle}`">{{ c.label }}<span v-if="c.obligatoire"> *</span></label>
          <textarea v-if="c.type === 'texte-long'" :id="`conf-${c.cle}`" ref="premierChamp" v-model="etat.valeurs[c.cle]" class="input conf-zone" rows="3" :placeholder="c.placeholder || ''" />
          <select v-else-if="c.type === 'choix'" :id="`conf-${c.cle}`" v-model="etat.valeurs[c.cle]" class="input">
            <option v-for="o in c.options" :key="o.valeur" :value="o.valeur">{{ o.libelle }}</option>
          </select>
          <input v-else :id="`conf-${c.cle}`" ref="premierChamp" v-model="etat.valeurs[c.cle]" class="input" :type="c.type || 'text'" :placeholder="c.placeholder || ''" />
        </div>
        <p v-if="etat.erreur" class="message-erreur" role="alert">{{ etat.erreur }}</p>
        <div class="conf-actions">
          <button ref="boutonAnnuler" type="button" class="vbtn vbtn-secondary" @click="_repondre(false)">{{ etat.libelleAnnuler }}</button>
          <button type="button" :class="['vbtn', etat.danger ? 'vbtn-danger' : 'vbtn-primary']" @click="_repondre(true)">{{ etat.libelleConfirmer }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.conf-fond { position: fixed; inset: 0; background: rgba(32, 26, 18, .5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: var(--space-4); animation: conf-fondu .15s ease; }
.conf-boite { background: var(--color-surface); border-radius: var(--radius-lg); box-shadow: 0 12px 32px rgba(32, 26, 18, .3); padding: var(--space-6); width: 100%; max-width: 440px; animation: conf-pop .15s ease; }
.conf-titre { margin: 0 0 var(--space-2); font-size: var(--font-size-lg); }
.conf-message { margin: 0 0 var(--space-4); color: var(--color-text-muted); font-size: var(--font-size-sm); line-height: 1.5; }
.conf-champ { margin-bottom: var(--space-3); }
.conf-zone { min-height: 80px; padding: var(--space-2) var(--space-3); resize: vertical; }
.conf-actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-4); }
@keyframes conf-fondu { from { opacity: 0 } to { opacity: 1 } }
@keyframes conf-pop { from { opacity: 0; transform: scale(.96) translateY(4px) } to { opacity: 1; transform: none } }
@media (prefers-reduced-motion: reduce) { .conf-fond, .conf-boite { animation: none; } }
</style>
