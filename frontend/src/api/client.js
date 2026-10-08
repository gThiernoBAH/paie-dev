import axios from 'axios'
import { formaterDetail } from './errors'

const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Le jeton signé renvoyé par POST /auth/login est gardé dans sessionStorage['token'] : la
// session disparaît à la fermeture de l'onglet (voulu : données de paie, postes partagés).
apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// Jeton expiré, révoqué (mot de passe changé, compte désactivé) ou invalide : on vide la session
// et on renvoie vers /login -- sauf pour /auth/login lui-même, où un 401 veut simplement dire
// « identifiants incorrects » et doit rester affiché par Login.vue.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    if (status === 401 && !url.includes('/auth/login')) {
      sessionStorage.removeItem('user')
      sessionStorage.removeItem('token')
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    if (Array.isArray(error.response?.data?.detail)) {
      error.response.data.detail = formaterDetail(error.response.data.detail)
    }
    return Promise.reject(error)
  },
)

export function messageErreur(e, defaut = 'Une erreur est survenue.') {
  if (!e.response) return 'Le serveur est injoignable.'
  return e.response.data?.detail || defaut
}

export default apiClient
