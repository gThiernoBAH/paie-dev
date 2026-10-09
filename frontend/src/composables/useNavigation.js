/** État partagé du menu : barre latérale pliée ou non (mémorisé), tiroir ouvert sur téléphone. */
import { ref, watch } from 'vue'

function lire() { try { return localStorage.getItem('paie.menu.replie') === '1' } catch { return false } }
const replie = ref(lire())
const tiroirOuvert = ref(false)
watch(replie, (v) => { try { localStorage.setItem('paie.menu.replie', v ? '1' : '0') } catch { /* facultatif */ } })

export function useNavigation() {
  return {
    replie, tiroirOuvert,
    basculer: () => { replie.value = !replie.value },
    ouvrirTiroir: () => { tiroirOuvert.value = true },
    fermerTiroir: () => { tiroirOuvert.value = false },
  }
}
