<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Banknote, LayoutDashboard, Users, Clock, CalendarRange, FileText, Palmtree, Landmark,
  FileBadge, BarChart3, Wallet, ListChecks, SlidersHorizontal, ShieldCheck, LogOut, KeyRound,
} from 'lucide-vue-next'
import { lireUtilisateur, fermerSession, aLaPermission } from '@/api/session'

const router = useRouter()
const utilisateur = lireUtilisateur()

// Menu complet de l'application. Les écrans pas encore livrés sont affichés grisés avec leur lot :
// on voit où va le projet sans promettre ce qui n'existe pas.
const entrees = computed(() => {
  const u = utilisateur
  return [
    { cle: 'tableau', libelle: 'Tableau de bord', icone: LayoutDashboard, vers: '/tableau-de-bord' },
    { cle: 'salaries', libelle: 'Salariés', icone: Users, vers: '/salaries', masque: !aLaPermission(u, 'voir_salaries') },
    { cle: 'referentiels', libelle: 'Référentiels', icone: ListChecks, vers: '/referentiels', masque: !aLaPermission(u, 'voir_salaries') },
    { cle: 'pointages', libelle: 'Pointages', icone: Clock, vers: '/pointages', masque: !aLaPermission(u, 'gerer_pointages') },
    { cle: 'campagnes', libelle: 'Campagnes de paie', icone: CalendarRange, vers: '/campagnes', masque: !(aLaPermission(u, 'lancer_paie') || aLaPermission(u, 'valider_bulletins') || aLaPermission(u, 'voir_rapports')) },
    { cle: 'conges', libelle: 'Congés', icone: Palmtree, vers: '/conges', masque: !aLaPermission(u, 'gerer_conges') },
    { cle: 'prets', libelle: 'Prêts et avances', icone: Wallet, vers: '/prets', masque: !aLaPermission(u, 'gerer_conges') },
    { cle: 'virements', libelle: 'Virements', icone: Landmark, vers: '/virements', masque: !aLaPermission(u, 'gerer_virements') },
    { cle: 'declarations', libelle: 'Déclarations', icone: FileBadge, vers: '/declarations', masque: !aLaPermission(u, 'voir_declarations') },
    { cle: 'rapports', libelle: 'Rapports', icone: BarChart3, lot: 10 },
    {
      cle: 'parametrage', libelle: 'Paramétrage', icone: SlidersHorizontal, vers: '/parametrage',
      masque: !(aLaPermission(u, 'voir_parametres') || aLaPermission(u, 'gerer_parametres')),
    },
    {
      cle: 'administration', libelle: 'Administration', icone: ShieldCheck, vers: '/administration',
      masque: !(aLaPermission(u, 'gerer_utilisateurs') || aLaPermission(u, 'voir_audit')),
    },
  ].filter((e) => !e.masque)
})

function deconnexion() {
  fermerSession()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="marque">
      <div class="marque-icone"><Banknote :size="22" /></div>
      <div>
        <div class="marque-nom">SIVOP</div>
        <div class="marque-sous">Paie</div>
      </div>
    </div>

    <nav class="menu" aria-label="Navigation principale">
      <template v-for="e in entrees" :key="e.cle">
        <router-link v-if="e.vers" :to="e.vers" class="entree" active-class="actif">
          <component :is="e.icone" :size="18" /><span>{{ e.libelle }}</span>
        </router-link>
        <span v-else class="entree inactive" :title="`Disponible au lot ${e.lot}`" aria-disabled="true">
          <component :is="e.icone" :size="18" /><span>{{ e.libelle }}</span><small>Lot {{ e.lot }}</small>
        </span>
      </template>
    </nav>

    <div class="pied">
      <div class="profil">
        <div class="avatar">{{ (utilisateur?.nom || '?').slice(0, 2).toUpperCase() }}</div>
        <div class="profil-texte">
          <div class="profil-nom">{{ [utilisateur?.prenom, utilisateur?.nom].filter(Boolean).join(' ') }}</div>
          <div class="profil-sous">{{ utilisateur?.identifiant }}</div>
        </div>
      </div>
      <router-link to="/changer-mot-de-passe" class="pied-lien"><KeyRound :size="16" />Mot de passe</router-link>
      <button type="button" class="pied-lien" @click="deconnexion"><LogOut :size="16" />Se déconnecter</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar { flex: 0 0 var(--sidebar-width); width: var(--sidebar-width); background: var(--color-surface); border-right: 1px solid var(--color-border); padding: var(--space-4) var(--space-3); display: flex; flex-direction: column; gap: 4px; height: 100%; overflow-y: auto; }
.marque { display: flex; align-items: center; gap: 10px; padding: 4px 8px var(--space-4); }
.marque-icone { width: 40px; height: 40px; border-radius: 10px; background: var(--color-brand); color: #fff; display: flex; align-items: center; justify-content: center; }
.marque-nom { font-size: var(--font-size-base); font-weight: 800; letter-spacing: 1px; color: var(--color-brand-dark); }
.marque-sous { font-size: var(--font-size-xs); color: var(--color-text-muted); }
.menu { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.entree { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px; font-size: var(--font-size-sm); font-weight: 500; color: #475467; text-decoration: none; min-height: 40px; }
.entree span { flex: 1; }
.entree:hover:not(.inactive) { background: #F2F5F9; }
.entree.actif { background: var(--color-brand-light); color: var(--color-brand-dark); font-weight: 600; }
.entree.inactive { color: #8A94A3; cursor: not-allowed; }
.entree small { font-size: 10px; font-weight: 600; background: #EEF1F5; color: #5B6778; padding: 2px 6px; border-radius: 999px; }
.pied { border-top: 1px solid var(--color-border); padding-top: var(--space-3); display: flex; flex-direction: column; gap: 2px; }
.profil { display: flex; align-items: center; gap: 10px; padding: 4px 8px 8px; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--color-brand-light); color: var(--color-brand-dark); font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.profil-texte { min-width: 0; line-height: 1.3; }
.profil-nom { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.profil-sous { font-size: var(--font-size-xs); color: var(--color-text-muted); }
.pied-lien { display: flex; align-items: center; gap: 10px; padding: 8px 12px; min-height: 40px; border: none; background: none; border-radius: 8px; font-size: var(--font-size-sm); color: #475467; text-decoration: none; cursor: pointer; text-align: left; }
.pied-lien:hover { background: #F2F5F9; }
</style>
