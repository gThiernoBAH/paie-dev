<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Banknote, ChevronDown, PanelLeftClose, PanelLeftOpen, X } from 'lucide-vue-next'
import { lireUtilisateur } from '@/api/session'
import { construireMenu, trouverEntree } from '@/navigation'
import { useNavigation } from '@/composables/useNavigation'
import { useEcran } from '@/composables/useEcran'

const route = useRoute()
const { replie, tiroirOuvert, basculer, fermerTiroir } = useNavigation()
const { mobile } = useEcran()
const utilisateur = lireUtilisateur()

const groupes = computed(() => construireMenu(utilisateur, { mobile: mobile.value }))
const groupeActif = computed(() => trouverEntree(route.path)?.groupe.cle)
// Sur téléphone le menu est un tiroir toujours déplié ; sur PC il peut se réduire à ses icônes.
const reduit = computed(() => replie.value && !mobile.value)

// Accordéon : le groupe de la page courante est ouvert ; les autres à la demande.
const ouverts = ref(new Set([groupeActif.value].filter(Boolean)))
// Un seul groupe ouvert à la fois : en ouvrir un referme les autres (sidebar toujours lisible).
watch(groupeActif, (c) => { if (c) ouverts.value = new Set([c]) })
function basculerGroupe(cle) {
  ouverts.value = ouverts.value.has(cle) ? new Set() : new Set([cle])
}

// Menu volant (barre réduite) : liste des écrans du groupe au survol ou au focus de son icône.
const volant = ref(null)
let delai
function montrerVolant(g, ev) {
  if (!reduit.value) return
  clearTimeout(delai)
  const r = ev.currentTarget.getBoundingClientRect()
  volant.value = { groupe: g, top: r.top, left: r.right + 6 }
}
function cacherVolant() { clearTimeout(delai); delai = setTimeout(() => { volant.value = null }, 180) }
function garderVolant() { clearTimeout(delai) }
function fermerTout() { volant.value = null; fermerTiroir() }
watch(() => route.path, fermerTout)
watch(reduit, () => { volant.value = null })
const auClavier = (e) => { if (e.key === 'Escape') fermerTout() }
onMounted(() => window.addEventListener('keydown', auClavier))
onUnmounted(() => window.removeEventListener('keydown', auClavier))
</script>

<template>
  <div v-if="mobile && tiroirOuvert" class="voile-menu" @click="fermerTiroir"></div>
  <aside :class="['sidebar', { reduit, mobile, ouvert: tiroirOuvert }]" aria-label="Menu principal">
    <div class="marque">
      <div class="marque-icone"><Banknote :size="22" /></div>
      <div v-if="!reduit" class="marque-texte">
        <div class="marque-nom">SIVOP</div>
        <div class="marque-sous">Paie</div>
      </div>
      <button v-if="mobile" class="fermer" type="button" aria-label="Fermer le menu" @click="fermerTiroir"><X :size="20" /></button>
    </div>

    <nav class="menu">
      <div v-for="g in groupes" :key="g.cle" class="groupe">
        <button
          type="button" :class="['groupe-tete', { actif: groupeActif === g.cle }]"
          :aria-expanded="reduit ? undefined : ouverts.has(g.cle)" :aria-label="reduit ? g.libelle : undefined"
          @click="reduit ? null : basculerGroupe(g.cle)"
          @mouseenter="montrerVolant(g, $event)" @mouseleave="cacherVolant" @focus="montrerVolant(g, $event)" @blur="cacherVolant"
        >
          <component :is="g.icone" :size="19" />
          <span v-if="!reduit" class="groupe-libelle">{{ g.libelle }}</span>
          <ChevronDown v-if="!reduit" :size="15" :class="['chevron', { ouvert: ouverts.has(g.cle) }]" />
        </button>
        <div v-if="!reduit && ouverts.has(g.cle)" class="groupe-corps">
          <router-link v-for="e in g.entrees" :key="e.vers" :to="e.vers" class="entree" active-class="actif">
            <component :is="e.icone" :size="16" /><span>{{ e.libelle }}</span>
          </router-link>
        </div>
      </div>
    </nav>

    <div class="pied">
      <button v-if="!mobile" type="button" class="pied-bouton" :data-hint="reduit ? 'Déplier le menu' : undefined" :aria-label="reduit ? 'Déplier le menu' : 'Réduire le menu'" @click="basculer">
        <component :is="reduit ? PanelLeftOpen : PanelLeftClose" :size="18" /><span v-if="!reduit">Réduire le menu</span>
      </button>
    </div>
  </aside>

  <!-- Menu volant de la barre réduite -->
  <Teleport to="body">
    <div v-if="volant && reduit" class="volant" :style="{ top: volant.top + 'px', left: volant.left + 'px' }" role="menu" @mouseenter="garderVolant" @mouseleave="cacherVolant">
      <div class="volant-titre">{{ volant.groupe.libelle }}</div>
      <router-link v-for="e in volant.groupe.entrees" :key="e.vers" :to="e.vers" class="volant-entree" active-class="actif" role="menuitem" @click="volant = null">
        <component :is="e.icone" :size="16" /><span>{{ e.libelle }}</span>
      </router-link>
    </div>
  </Teleport>
</template>

<style scoped>
.sidebar { flex: 0 0 var(--sidebar-width); width: var(--sidebar-width); background: var(--nav-bg); color: var(--nav-texte); padding: var(--space-4) var(--space-3); display: flex; flex-direction: column; gap: 4px; height: 100%; overflow-y: auto; overflow-x: hidden; transition: width .18s ease, flex-basis .18s ease; }
.sidebar.reduit { flex-basis: var(--sidebar-width-replie); width: var(--sidebar-width-replie); padding-left: 10px; padding-right: 10px; align-items: center; }
.marque { display: flex; align-items: center; gap: 10px; padding: 4px 6px var(--space-4); width: 100%; }
.sidebar.reduit .marque { justify-content: center; padding-left: 0; padding-right: 0; }
.marque-icone { width: 40px; height: 40px; flex: 0 0 40px; border-radius: 10px; background: var(--color-brand); color: #fff; display: flex; align-items: center; justify-content: center; }
.marque-nom { font-size: var(--font-size-base); font-weight: 800; letter-spacing: 1px; color: #fff; }
.marque-sous { font-size: var(--font-size-xs); color: var(--nav-texte); }
.fermer { margin-left: auto; border: none; background: none; color: var(--nav-texte); width: 40px; height: 40px; cursor: pointer; }
.menu { display: flex; flex-direction: column; gap: 6px; flex: 1; width: 100%; }
.groupe { display: flex; flex-direction: column; gap: 2px; }
.groupe-tete { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 42px; padding: 0 12px; border: none; border-radius: 9px; background: none; color: var(--nav-texte); font-size: var(--font-size-sm); font-weight: 600; cursor: pointer; text-align: left; position: relative; }
.sidebar.reduit .groupe-tete { justify-content: center; padding: 0; width: 46px; }
.groupe-tete:hover { background: var(--nav-bg-actif); color: var(--nav-texte-actif); }
.groupe-tete.actif { color: var(--nav-texte-actif); }
.sidebar.reduit .groupe-tete.actif { background: var(--nav-bg-actif); box-shadow: inset 3px 0 0 var(--color-accent); }
.groupe-tete:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 1px; }
.groupe-libelle { flex: 1; letter-spacing: .02em; }
.chevron { transition: transform .15s; opacity: .7; } .chevron.ouvert { transform: rotate(180deg); }
.groupe-corps { display: flex; flex-direction: column; gap: 1px; margin: 0 0 4px 14px; padding-left: 10px; border-left: 1px solid var(--nav-bordure); }
.entree { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; font-size: var(--font-size-sm); font-weight: 500; color: var(--nav-texte); text-decoration: none; min-height: 38px; }
.entree:hover { background: var(--nav-bg-actif); color: var(--nav-texte-actif); }
.entree.actif { background: var(--nav-bg-actif); color: var(--nav-texte-actif); font-weight: 600; box-shadow: inset 3px 0 0 var(--color-accent); }
.pied { border-top: 1px solid var(--nav-bordure); padding-top: var(--space-3); width: 100%; display: flex; justify-content: center; }
.pied-bouton { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 40px; padding: 0 12px; border: none; background: none; border-radius: 9px; color: var(--nav-texte); font-size: var(--font-size-sm); cursor: pointer; }
.sidebar.reduit .pied-bouton { justify-content: center; padding: 0; width: 46px; }
.pied-bouton:hover { background: var(--nav-bg-actif); color: var(--nav-texte-actif); }
.pied-bouton:focus-visible { outline: 2px solid var(--color-accent); }
.volant { position: fixed; z-index: 900; min-width: 220px; background: var(--nav-bg); border: 1px solid var(--nav-bordure); border-radius: 12px; padding: 8px; box-shadow: 0 10px 28px rgba(0, 0, 0, .35); }
.volant-titre { padding: 6px 12px 8px; font-size: var(--font-size-xs); font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--nav-texte); opacity: .8; }
.volant-entree { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px; color: var(--nav-texte); text-decoration: none; font-size: var(--font-size-sm); min-height: 40px; }
.volant-entree:hover, .volant-entree.actif { background: var(--nav-bg-actif); color: var(--nav-texte-actif); }
.volant-entree.actif { box-shadow: inset 3px 0 0 var(--color-accent); }

/* Téléphone : tiroir par-dessus le contenu. */
.sidebar.mobile { position: fixed; z-index: 800; left: 0; top: 0; bottom: 0; width: min(300px, 86vw); flex: none; transform: translateX(-100%); transition: transform .2s ease; box-shadow: none; }
.sidebar.mobile.ouvert { transform: none; box-shadow: 0 0 40px rgba(0, 0, 0, .4); }
.voile-menu { position: fixed; inset: 0; z-index: 790; background: rgba(32, 26, 18, .5); }
@media (prefers-reduced-motion: reduce) { .sidebar, .sidebar.mobile, .chevron { transition: none; } }
</style>
