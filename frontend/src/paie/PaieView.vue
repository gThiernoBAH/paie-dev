<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu, ChevronRight, KeyRound, LogOut, ChevronDown, Eye } from 'lucide-vue-next'
import Sidebar from '@/components/Sidebar.vue'
import { lireUtilisateur, fermerSession } from '@/api/session'
import { trouverEntree } from '@/navigation'
import { useNavigation } from '@/composables/useNavigation'
import { useEcran } from '@/composables/useEcran'

const route = useRoute()
const router = useRouter()
const utilisateur = lireUtilisateur()
const { ouvrirTiroir } = useNavigation()
const { mobile } = useEcran()

const position = computed(() => trouverEntree(route.path))
const nomComplet = computed(() => [utilisateur?.prenom, utilisateur?.nom].filter(Boolean).join(' '))
const initiales = computed(() => (utilisateur?.nom || '?').slice(0, 2).toUpperCase())

const menuOuvert = ref(false)
const zoneUtilisateur = ref(null)
function fermerSiExterieur(e) { if (zoneUtilisateur.value && !zoneUtilisateur.value.contains(e.target)) menuOuvert.value = false }
onMounted(() => document.addEventListener('click', fermerSiExterieur))
onUnmounted(() => document.removeEventListener('click', fermerSiExterieur))
function deconnexion() { fermerSession(); router.push('/login') }
</script>

<template>
  <div class="coque">
    <Sidebar />
    <div class="colonne">
      <header class="barre">
        <button v-if="mobile" class="burger" type="button" aria-label="Ouvrir le menu" @click="ouvrirTiroir"><Menu :size="22" /></button>
        <nav class="ariane" aria-label="Fil d'Ariane">
          <template v-if="position">
            <span class="ariane-groupe">{{ position.groupe.libelle }}</span><ChevronRight :size="14" />
            <strong>{{ position.entree.libelle }}</strong>
          </template>
        </nav>
        <div ref="zoneUtilisateur" class="utilisateur">
          <button class="utilisateur-bouton" type="button" :aria-expanded="menuOuvert" aria-haspopup="menu" @click.stop="menuOuvert = !menuOuvert">
            <span class="avatar">{{ initiales }}</span>
            <span v-if="!mobile" class="utilisateur-nom">{{ nomComplet }}</span>
            <ChevronDown :size="15" />
          </button>
          <div v-if="menuOuvert" class="utilisateur-menu" role="menu">
            <div class="utilisateur-id"><strong>{{ nomComplet }}</strong><small>{{ utilisateur?.identifiant }}</small></div>
            <router-link to="/changer-mot-de-passe" class="menu-ligne" role="menuitem"><KeyRound :size="16" />Changer mon mot de passe</router-link>
            <button type="button" class="menu-ligne" role="menuitem" @click="deconnexion"><LogOut :size="16" />Se déconnecter</button>
          </div>
        </div>
      </header>
      <p v-if="mobile" class="bandeau-lecture" role="status"><Eye :size="15" />Consultation seule sur téléphone. Pour modifier, utilisez un ordinateur.</p>
      <main class="contenu"><router-view /></main>
    </div>
  </div>
</template>

<style scoped>
.coque { display: flex; height: 100%; }
.colonne { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.contenu { flex: 1; min-width: 0; overflow-y: auto; }
.barre { flex: 0 0 56px; display: flex; align-items: center; gap: var(--space-3); padding: 0 var(--space-6); background: var(--color-surface); border-bottom: 1px solid var(--color-border); }
.burger { border: none; background: none; width: 44px; height: 44px; margin-left: -10px; cursor: pointer; color: var(--color-text); }
.ariane { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-sm); color: var(--color-text-muted); min-width: 0; flex: 1; white-space: nowrap; overflow: hidden; }
.ariane strong { color: var(--color-text); overflow: hidden; text-overflow: ellipsis; }
.utilisateur { position: relative; margin-left: auto; }
.utilisateur-bouton { display: flex; align-items: center; gap: 8px; border: 1px solid transparent; background: none; border-radius: 10px; padding: 4px 8px; min-height: 40px; cursor: pointer; color: var(--color-text); font-size: var(--font-size-sm); }
.utilisateur-bouton:hover { background: var(--color-surface-2); border-color: var(--color-border); }
.avatar { width: 32px; height: 32px; border-radius: 9px; background: var(--color-brand); color: #fff; font-weight: 700; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.utilisateur-menu { position: absolute; right: 0; top: calc(100% + 6px); width: 260px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; box-shadow: 0 12px 30px rgba(43, 38, 32, .18); padding: 6px; z-index: 40; }
.utilisateur-id { padding: 8px 12px 10px; display: flex; flex-direction: column; border-bottom: 1px solid var(--color-border); margin-bottom: 4px; }
.utilisateur-id small { color: var(--color-text-muted); }
.menu-ligne { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 42px; padding: 0 12px; border: none; background: none; border-radius: 8px; color: var(--color-text); text-decoration: none; font-size: var(--font-size-sm); cursor: pointer; text-align: left; }
.bandeau-lecture { margin: 0; display: flex; align-items: center; gap: 8px; padding: 8px var(--space-4); background: var(--color-accent-bg); color: var(--color-orange); font-size: var(--font-size-xs); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.menu-ligne:hover { background: var(--color-surface-2); }
@media (max-width: 760px) { .barre { padding: 0 var(--space-4); } .ariane-groupe { display: none; } .ariane svg { display: none; } }
</style>
