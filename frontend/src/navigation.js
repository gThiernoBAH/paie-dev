/**
 * navigation.js -- définition UNIQUE du menu : 5 groupes, leurs entrées, et les permissions requises.
 * La barre latérale, le fil d'Ariane et la navigation mobile lisent tous cette liste.
 * Ajouter un écran = ajouter une entrée ici (et sa route dans router/index.js).
 */
import {
  LayoutDashboard, BarChart3, Users, Palmtree, ShieldAlert, Clock, CalendarRange, Wallet, Gift,
  Landmark, FileBadge, FileText, ListChecks, SlidersHorizontal, ShieldCheck,
  Compass, UserRound, Calculator, Banknote, Settings2, TrendingUp, FlaskConical, CalendarCheck, Grid3x3,
} from 'lucide-vue-next'
import { aLaPermission } from '@/api/session'

const GROUPES = [
  {
    cle: 'paie', libelle: 'Paie', icone: Calculator,
    entrees: [
      { libelle: 'Pointages', icone: Clock, vers: '/pointages', perm: ['gerer_pointages'] },
      { libelle: 'Campagnes de paie', icone: CalendarRange, vers: '/campagnes', perm: ['lancer_paie', 'valider_bulletins', 'voir_rapports'] },
      { libelle: 'Simulation de bulletin', icone: FlaskConical, vers: '/simulation', perm: ['lancer_paie'] },
      { libelle: 'Clôture annuelle', icone: CalendarCheck, vers: '/exercices', perm: ['valider_bulletins'] },
      { libelle: 'Prêts et avances', icone: Wallet, vers: '/prets', perm: ['gerer_conges'] },
      { libelle: 'Gratifications', icone: Gift, vers: '/gratifications', perm: ['lancer_paie'] },
    ],
  },
  {
    cle: 'reglements', libelle: 'Règlements', icone: Banknote,
    entrees: [
      { libelle: 'Virements', icone: Landmark, vers: '/virements', perm: ['gerer_virements'] },
      { libelle: 'Déclarations', icone: FileBadge, vers: '/declarations', perm: ['voir_declarations'] },
    ],
  },
  {
    cle: 'personnel', libelle: 'Personnel', icone: UserRound,
    entrees: [
      { libelle: 'Salariés', icone: Users, vers: '/salaries', perm: ['voir_salaries'] },
      { libelle: 'Congés et absences', icone: Palmtree, vers: '/conges', perm: ['gerer_conges'] },
      { libelle: 'Augmentations', icone: TrendingUp, vers: '/augmentations', perm: ['modifier_salaries'] },
      { libelle: 'Dossier disciplinaire', icone: ShieldAlert, vers: '/discipline', perm: ['gerer_discipline'] },
    ],
  },
  {
    cle: 'pilotage', libelle: 'Pilotage', icone: Compass,
    entrees: [
      { libelle: 'Tableau de bord', icone: LayoutDashboard, vers: '/tableau-de-bord' },
      { libelle: 'Rapports', icone: BarChart3, vers: '/rapports', perm: ['voir_rapports'] },
    ],
  },
  {
    cle: 'configuration', libelle: 'Configuration', icone: Settings2,
    entrees: [
      { libelle: 'Référentiels', icone: ListChecks, vers: '/referentiels', perm: ['voir_salaries'] },
      { libelle: 'Grille salariale', icone: Grid3x3, vers: '/grille', perm: ['voir_donnees_sensibles'] },
      { libelle: 'Paramétrage', icone: SlidersHorizontal, vers: '/parametrage', perm: ['voir_parametres', 'gerer_parametres'] },
      { libelle: 'Administration', icone: ShieldCheck, vers: '/administration', perm: ['gerer_utilisateurs', 'voir_audit'], admin: true },
    ],
  },
]

/** Groupes et entrées visibles pour l'utilisateur (droits + écrans déjà livrés). */
export function construireMenu(utilisateur, { mobile = false } = {}) {
  return GROUPES.map((g) => ({
    ...g,
    entrees: g.entrees.filter((e) => {
      if (e.bientot && !e.livre) return false
      if (mobile && e.admin) return false          // pas d'administration depuis un téléphone
      return !e.perm || e.perm.some((p) => aLaPermission(utilisateur, p))
    }),
  })).filter((g) => g.entrees.length)
}

/** Groupe et entrée correspondant à un chemin (pour le fil d'Ariane et le groupe actif). */
export function trouverEntree(chemin) {
  for (const g of GROUPES) {
    for (const e of g.entrees) {
      if (chemin === e.vers || chemin.startsWith(`${e.vers}/`)) return { groupe: g, entree: e }
    }
  }
  return null
}

/** Marque un écran comme livré (menu visible) : appelé par les modules ajoutés plus tard. */
export function activerEntree(vers) {
  for (const g of GROUPES) for (const e of g.entrees) if (e.vers === vers) e.livre = true
}
