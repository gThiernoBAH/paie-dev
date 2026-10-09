/**
 * Copie dans le presse-papiers. navigator.clipboard n'existe qu'en contexte sécurisé (HTTPS ou
 * localhost) : sur un serveur interne en http://, on retombe sur la méthode historique (textarea +
 * execCommand), qui fonctionne partout. Résout true si la copie a réussi.
 */
export async function copier(texte) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(texte)
      return true
    }
  } catch { /* on tente la méthode de secours */ }
  const zone = document.createElement('textarea')
  zone.value = texte
  zone.setAttribute('readonly', '')
  zone.style.cssText = 'position:fixed;top:0;left:0;opacity:0;'
  document.body.appendChild(zone)
  zone.focus(); zone.select(); zone.setSelectionRange(0, texte.length)
  let ok = false
  try { ok = document.execCommand('copy') } catch { ok = false }
  document.body.removeChild(zone)
  return ok
}
