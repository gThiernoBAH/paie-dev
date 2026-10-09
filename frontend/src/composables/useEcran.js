/**
 * useEcran : détecte le « canal » d'utilisation. `mobile` = écran étroit (téléphone). Sert à adapter
 * l'interface (menu en tiroir, boutons d'écriture masqués) ; la règle de lecture seule est ENSUITE
 * imposée par le serveur (voir canal du jeton), pas seulement par l'interface.
 */
import { ref, onMounted, onUnmounted } from 'vue'

export const LARGEUR_MOBILE = 760
export const estMobile = () => (typeof window !== 'undefined' ? window.matchMedia(`(max-width: ${LARGEUR_MOBILE}px)`).matches : false)

const mobile = ref(estMobile())
let compteur = 0
let requete

function maj() { mobile.value = requete.matches }

export function useEcran() {
  onMounted(() => {
    if (!compteur) { requete = window.matchMedia(`(max-width: ${LARGEUR_MOBILE}px)`); requete.addEventListener('change', maj); maj() }
    compteur += 1
  })
  onUnmounted(() => {
    compteur -= 1
    if (!compteur && requete) requete.removeEventListener('change', maj)
  })
  return { mobile }
}
