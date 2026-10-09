/**
 * useConfirm.js -- remplace window.confirm() et window.prompt() par une fenêtre intégrée à
 * l'application (même principe que vusine : une seule instance, montée dans App.vue).
 *
 *   const { confirm, saisir } = useConfirm()
 *   if (!(await confirm({ title: 'Supprimer', message: '…', danger: true, confirmLabel: 'Supprimer' }))) return
 *   const v = await saisir({ title: 'Rouvrir', message: '…', champs: [{ cle: 'motif', label: 'Motif', obligatoire: true }] })
 *   if (!v) return          // annulé ; sinon v = { motif: '…' }
 */
import { reactive } from 'vue'

const etat = reactive({
  visible: false, titre: '', message: '', danger: false,
  libelleConfirmer: 'Confirmer', libelleAnnuler: 'Annuler',
  champs: [], valeurs: {}, erreur: '', resolve: null,
})

function ouvrir(options, resolve) {
  if (etat.resolve) etat.resolve(null)   // une fenêtre jamais tranchée est annulée
  const champs = options.champs || []
  const valeurs = {}
  for (const c of champs) valeurs[c.cle] = c.valeur ?? ''
  Object.assign(etat, {
    visible: true, titre: options.title || 'Confirmer', message: options.message || '', danger: !!options.danger,
    libelleConfirmer: options.confirmLabel || 'Confirmer', libelleAnnuler: options.cancelLabel || 'Annuler',
    champs, valeurs, erreur: '', resolve,
  })
}

export function useConfirm() {
  /** Résout true / false. */
  function confirm(options = {}) {
    return new Promise((resolve) => ouvrir(options, (v) => resolve(v !== null && v !== false)))
  }
  /** Résout l'objet des valeurs saisies, ou null si annulé. */
  function saisir(options = {}) {
    return new Promise((resolve) => ouvrir(options, (v) => resolve(v === null || v === false ? null : v)))
  }
  return { confirm, saisir }
}

// Réservé à ConfirmDialog.vue.
export function _etatConfirm() { return etat }
export function _repondre(accepte) {
  if (accepte) {
    for (const c of etat.champs) {
      const v = String(etat.valeurs[c.cle] ?? '').trim()
      if (c.obligatoire && !v) { etat.erreur = `« ${c.label} » est obligatoire.`; return }
    }
  }
  const r = etat.resolve
  etat.visible = false; etat.resolve = null; etat.erreur = ''
  if (r) r(accepte ? (etat.champs.length ? { ...etat.valeurs } : true) : null)
}
