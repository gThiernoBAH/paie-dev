import apiClient from './client'

/** Télécharge un fichier protégé (le jeton est dans l'en-tête, pas dans l'URL) et le propose à l'utilisateur. */
export async function telecharger(chemin, params = {}, nomParDefaut = 'fichier') {
  const reponse = await apiClient.get(chemin, { params, responseType: 'blob' })
  const dispo = reponse.headers['content-disposition'] || ''
  const nom = (/filename="?([^";]+)"?/.exec(dispo) || [])[1] || nomParDefaut
  const lien = document.createElement('a')
  lien.href = URL.createObjectURL(reponse.data)
  lien.download = nom
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  setTimeout(() => URL.revokeObjectURL(lien.href), 10000)
}
