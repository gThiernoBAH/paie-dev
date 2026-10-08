import { createRouter, createWebHistory } from 'vue-router'

import Login from '../components/Login.vue'
import ChangerMotDePasse from '../components/ChangerMotDePasse.vue'
import PaieView from '../paie/PaieView.vue'
import TableauDeBordView from '../paie/components/TableauDeBordView.vue'
import SalariesView from '../paie/components/SalariesView.vue'
import SalarieFiche from '../paie/components/SalarieFiche.vue'
import ReferentielsView from '../direction/components/ReferentielsView.vue'
import PointagesView from '../paie/components/PointagesView.vue'
import CampagnesView from '../paie/components/CampagnesView.vue'
import CampagneDetail from '../paie/components/CampagneDetail.vue'
import CongesView from '../paie/components/CongesView.vue'
import PretsView from '../paie/components/PretsView.vue'
import VirementsView from '../paie/components/VirementsView.vue'
import DeclarationsView from '../paie/components/DeclarationsView.vue'
import EspaceView from '../salarie/EspaceView.vue'
import MesBulletins from '../salarie/MesBulletins.vue'
import MesConges from '../salarie/MesConges.vue'
import MonProfil from '../salarie/MonProfil.vue'
import ParametrageView from '../direction/components/ParametrageView.vue'
import AdminView from '../direction/components/AdminView.vue'
import { lireUtilisateur, aLaPermission } from '../api/session'

const routes = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  { path: '/changer-mot-de-passe', name: 'changer-mot-de-passe', component: ChangerMotDePasse, meta: { requiresAuth: true } },
  {
    path: '/',
    component: PaieView,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/tableau-de-bord' },
      { path: 'tableau-de-bord', name: 'tableau-de-bord', component: TableauDeBordView },
      { path: 'salaries', name: 'salaries', component: SalariesView, meta: { requiresAnyPermission: ['voir_salaries'] } },
      { path: 'salaries/:id', name: 'salarie', component: SalarieFiche, meta: { requiresAnyPermission: ['voir_salaries'] } },
      { path: 'referentiels', name: 'referentiels', component: ReferentielsView, meta: { requiresAnyPermission: ['voir_salaries'] } },
      { path: 'pointages', name: 'pointages', component: PointagesView, meta: { requiresAnyPermission: ['gerer_pointages'] } },
      { path: 'campagnes', name: 'campagnes', component: CampagnesView, meta: { requiresAnyPermission: ['lancer_paie', 'valider_bulletins', 'voir_rapports'] } },
      { path: 'campagnes/:id', name: 'campagne', component: CampagneDetail, meta: { requiresAnyPermission: ['lancer_paie', 'valider_bulletins', 'voir_rapports'] } },
      { path: 'conges', name: 'conges', component: CongesView, meta: { requiresAnyPermission: ['gerer_conges'] } },
      { path: 'prets', name: 'prets', component: PretsView, meta: { requiresAnyPermission: ['gerer_conges'] } },
      { path: 'virements', name: 'virements', component: VirementsView, meta: { requiresAnyPermission: ['gerer_virements'] } },
      { path: 'declarations', name: 'declarations', component: DeclarationsView, meta: { requiresAnyPermission: ['voir_declarations'] } },
      { path: 'parametrage', name: 'parametrage', component: ParametrageView, meta: { requiresAnyPermission: ['voir_parametres', 'gerer_parametres'] } },
      // Administration : comptes, droits, journal d'audit (au moins l'une des deux permissions).
      { path: 'administration', name: 'administration', component: AdminView, meta: { requiresAnyPermission: ['gerer_utilisateurs', 'voir_audit'] } },
    ],
  },
  {
    path: '/espace',
    component: EspaceView,
    meta: { requiresAuth: true, espaceSalarie: true },
    children: [
      { path: '', redirect: '/espace/bulletins' },
      { path: 'bulletins', name: 'mes-bulletins', component: MesBulletins },
      { path: 'conges', name: 'mes-conges', component: MesConges },
      { path: 'profil', name: 'mon-profil', component: MonProfil },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: () => (lireUtilisateur() ? '/' : '/login') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const user = lireUtilisateur()

  if (to.meta.public) {
    if (user && to.name === 'login') return user.doit_changer_mot_de_passe ? '/changer-mot-de-passe' : '/'
    return true
  }
  if (!user) return '/login'

  // Premier accès ou mot de passe réinitialisé : rien d'autre n'est accessible avant le changement.
  if (user.doit_changer_mot_de_passe && to.name !== 'changer-mot-de-passe') return '/changer-mot-de-passe'

  // Un salarié n'a accès qu'à son espace ; les autres comptes n'y ont pas accès.
  if (user.role === 'salarie' && !to.path.startsWith('/espace') && to.name !== 'changer-mot-de-passe') return '/espace'
  if (user.role !== 'salarie' && to.path.startsWith('/espace')) return '/'

  const requises = to.meta.requiresAnyPermission
  if (requises && !requises.some((cle) => aLaPermission(user, cle))) return '/'
  return true
})

export default router
