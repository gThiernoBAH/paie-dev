/**
 * errors.js -- rend lisibles les erreurs de validation du serveur.
 * FastAPI renvoie, pour une saisie invalide, un TABLEAU d'objets ([{ type, loc, msg }]) ;
 * centralisé dans le client d'API, tous les écrans affichent `e.response.data.detail` en phrase.
 */
const LIBELLES_CHAMPS = {
  identifiant: 'Identifiant', nom: 'Nom', prenom: 'Prénom', email: 'E-mail', telephone: 'Téléphone',
  role: 'Rôle', password: 'Mot de passe', nouveau_mot_de_passe: 'Nouveau mot de passe',
}

const TRADUCTIONS = [
  [/^Field required$/i, 'champ obligatoire'],
  [/^String should have at least (\d+) characters?/i, (m) => `doit contenir au moins ${m[1]} caractères`],
  [/^String should have at most (\d+) characters?/i, (m) => `ne peut pas dépasser ${m[1]} caractères`],
  [/^String should match pattern/i, 'caractères non autorisés'],
]

function traduire(msg) {
  for (const [motif, remplacement] of TRADUCTIONS) {
    const m = msg.match(motif)
    if (m) return typeof remplacement === 'function' ? remplacement(m) : remplacement
  }
  return msg
}

export function formaterDetail(detail) {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return detail
  return detail
    .map((item) => {
      if (!item || typeof item !== 'object') return String(item)
      const champ = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : ''
      const libelle = LIBELLES_CHAMPS[champ] || champ
      const message = traduire(String(item.msg ?? ''))
      return libelle ? `${libelle} : ${message}` : message
    })
    .join(' ; ')
}
