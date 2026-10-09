<script setup>
import { useRouter } from 'vue-router'
import { FileText, Palmtree, UserRound, LogOut, Banknote } from 'lucide-vue-next'
import { lireUtilisateur, fermerSession } from '@/api/session'

const router = useRouter()
const u = lireUtilisateur()
function deconnexion() { fermerSession(); router.push('/login') }
</script>

<template>
  <div class="espace">
    <header class="haut">
      <div class="marque"><Banknote :size="20" /><strong>SIVOP</strong><span>Espace salarié</span></div>
      <div class="droite">
        <span class="nom">{{ [u?.prenom, u?.nom].filter(Boolean).join(' ') }}</span>
        <button class="sortir" aria-label="Se déconnecter" @click="deconnexion"><LogOut :size="18" /></button>
      </div>
    </header>
    <main class="corps"><router-view /></main>
    <nav class="bas" aria-label="Navigation">
      <router-link to="/espace/bulletins" class="onglet" active-class="actif"><FileText :size="22" /><span>Bulletins</span></router-link>
      <router-link to="/espace/conges" class="onglet" active-class="actif"><Palmtree :size="22" /><span>Congés</span></router-link>
      <router-link to="/espace/profil" class="onglet" active-class="actif"><UserRound :size="22" /><span>Mon profil</span></router-link>
    </nav>
  </div>
</template>

<style scoped>
.espace { min-height: 100%; display: flex; flex-direction: column; background: var(--color-bg, var(--color-surface-2)); }
.haut { background: var(--color-brand-dark, #1B4D7A); color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; position: sticky; top: 0; z-index: 5; }
.marque { display: flex; align-items: center; gap: 8px; } .marque span { opacity: .8; font-size: var(--font-size-sm); }
.droite { display: flex; align-items: center; gap: 10px; } .nom { font-size: var(--font-size-sm); }
.sortir { border: none; background: rgba(255,255,255,.15); color: #fff; border-radius: 8px; width: 40px; height: 40px; cursor: pointer; }
.corps { flex: 1; width: 100%; max-width: 760px; margin: 0 auto; padding: var(--space-4) 16px 90px; }
.bas { position: fixed; bottom: 0; left: 0; right: 0; background: #fff; border-top: 1px solid var(--color-border); display: flex; justify-content: center; padding-bottom: env(safe-area-inset-bottom); z-index: 5; }
.onglet { flex: 1; max-width: 220px; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 0; min-height: 56px; color: var(--color-text-muted); text-decoration: none; font-size: var(--font-size-xs); font-weight: 600; }
.onglet.actif { color: var(--color-brand-dark, #1B4D7A); }
@media (max-width: 480px) { .nom { display: none; } }
</style>
