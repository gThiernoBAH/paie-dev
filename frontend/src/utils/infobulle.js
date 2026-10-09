/**
 * Infobulle globale. Tout élément portant l'attribut data-hint affiche son texte au survol ou au
 * focus clavier, sans être coupé par un conteneur à défilement (la bulle est en position fixe).
 * Sur écran tactile, un appui long sur l'élément l'affiche brièvement.
 */
let bulle = null
let minuteur = null

function cacher() {
  clearTimeout(minuteur)
  if (bulle) { bulle.remove(); bulle = null }
}

function montrer(el) {
  const texte = el.getAttribute('data-hint')
  if (!texte) return
  cacher()
  bulle = document.createElement('div')
  bulle.className = 'infobulle'
  bulle.setAttribute('role', 'tooltip')
  bulle.textContent = texte
  document.body.appendChild(bulle)
  const r = el.getBoundingClientRect()
  const b = bulle.getBoundingClientRect()
  let x = r.left + r.width / 2 - b.width / 2
  x = Math.max(8, Math.min(x, window.innerWidth - b.width - 8))
  let y = r.top - b.height - 8
  if (y < 8) y = r.bottom + 8          // pas de place au-dessus : en dessous
  bulle.style.left = `${x}px`
  bulle.style.top = `${y}px`
}

export function installerInfobulles() {
  const cible = (e) => (e.target instanceof Element ? e.target.closest('[data-hint]') : null)
  document.addEventListener('mouseover', (e) => { const el = cible(e); if (el) montrer(el) })
  document.addEventListener('mouseout', (e) => { if (cible(e)) cacher() })
  document.addEventListener('focusin', (e) => { const el = cible(e); if (el) montrer(el) })
  document.addEventListener('focusout', cacher)
  document.addEventListener('click', cacher, true)
  document.addEventListener('scroll', cacher, true)
  document.addEventListener('touchstart', (e) => {
    const el = cible(e)
    if (!el) return
    clearTimeout(minuteur)
    minuteur = setTimeout(() => { montrer(el); minuteur = setTimeout(cacher, 2500) }, 500)
  }, { passive: true })
  document.addEventListener('touchend', () => clearTimeout(minuteur), { passive: true })
}
