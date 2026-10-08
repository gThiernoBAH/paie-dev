/** session.js -- lecture/écriture de la session (utilisateur + jeton) dans sessionStorage. */

export function lireUtilisateur() {
  const brut = sessionStorage.getItem('user')
  if (!brut || !sessionStorage.getItem('token')) return null
  try { return JSON.parse(brut) } catch { return null }
}

export function ouvrirSession(session) {
  sessionStorage.setItem('user', JSON.stringify(session.user))
  sessionStorage.setItem('token', session.access_token)
}

export function fermerSession() {
  sessionStorage.removeItem('user')
  sessionStorage.removeItem('token')
}

export function aLaPermission(user, cle) {
  return !!user && (user.role === 'admin' || (user.permissions || []).includes(cle))
}
