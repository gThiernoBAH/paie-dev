<script setup>
/** Bouton réduit à une icône : porte TOUJOURS une infobulle (survol/focus) et un libellé accessible. */
defineProps({
  icone: { type: [Object, Function], required: true },
  hint: { type: String, required: true },
  danger: { type: Boolean, default: false },
  taille: { type: Number, default: 16 },
})
</script>

<template>
  <button type="button" class="btn-icone" :class="{ danger }" :aria-label="hint" :data-hint="hint">
    <component :is="icone" :size="taille" />
  </button>
</template>

<style scoped>
.btn-icone { display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; border: 1px solid var(--color-border); border-radius: 9px; background: var(--color-surface); color: var(--color-text-muted); cursor: pointer; transition: background-color .15s, color .15s, border-color .15s; }
.btn-icone:hover:not(:disabled) { background: var(--color-brand-light); color: var(--color-brand-dark); border-color: var(--color-brand); }
.btn-icone.danger:hover:not(:disabled) { background: var(--color-rouge-bg); color: var(--color-rouge); border-color: var(--color-rouge); }
.btn-icone:focus-visible { outline: 2px solid var(--color-brand); outline-offset: 2px; }
.btn-icone:disabled { opacity: .45; cursor: not-allowed; }
@media (max-width: 760px) { .btn-icone { width: 40px; height: 40px; } }
</style>
