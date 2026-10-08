<script setup>
import { ref, onMounted } from 'vue'
import apiClient from '@/api/client'
import { lireUtilisateur, aLaPermission } from '@/api/session'
import { ShieldCheck, Lock, KeyRound, ScrollText, SlidersHorizontal, AlertTriangle } from 'lucide-vue-next'

const utilisateur = lireUtilisateur()

// Alerte « paramètres à confirmer » : visible seulement pour qui peut consulter le paramétrage.
const etat = ref(null)
onMounted(async () => {
  if (!aLaPermission(utilisateur, 'voir_parametres')) return
  try { etat.value = (await apiClient.get('/parametres/etat')).data } catch { /* le bandeau est facultatif */ }
})

const livre = [
  { icone: Lock, titre: 'Connexion par matricule', texte: 'Jeton signé, verrouillage après échecs répétés, mot de passe personnel imposé à la première connexion.' },
  { icone: KeyRound, titre: 'Rôles et permissions', texte: 'Quatre rôles, des permissions fines par compte, aucune élévation de privilèges possible.' },
  { icone: ScrollText, titre: 'Journal d\'audit', texte: 'Connexions, créations de comptes, changements de droits : tracés et non modifiables.' },
  { icone: ShieldCheck, titre: 'Champs sensibles chiffrés', texte: 'Le chiffrement est prêt pour le RIB et le numéro CNPS, utilisé dès le lot 2 (salariés).' },
  { icone: SlidersHorizontal, titre: 'Paramétrage daté', texte: 'Taux, plafonds, barèmes : valeur en vigueur par date, historique, statut confirmé / à confirmer.', lot: 1 },
]
</script>

<template>
  <div class="page">
    <header>
      <h1>Tableau de bord</h1>
      <p class="sous-titre">Bonjour {{ utilisateur?.prenom || utilisateur?.nom }}. Le socle de l'application est en place ; les indicateurs de paie arriveront avec les lots suivants.</p>
    </header>

    <router-link v-if="etat && etat.a_confirmer" to="/parametrage" class="alerte">
      <AlertTriangle :size="18" />
      <span><strong>{{ etat.a_confirmer }} paramètre(s) à confirmer</strong>
        <template v-if="etat.critiques_a_confirmer"> dont {{ etat.critiques_a_confirmer }} critique(s) : la validation des bulletins sera bloquée tant qu'ils ne le sont pas.</template></span>
    </router-link>

    <section class="grille">
      <article v-for="b in livre" :key="b.titre" class="card bloc">
        <div class="icone"><component :is="b.icone" :size="20" /></div>
        <h2>{{ b.titre }}</h2>
        <p>{{ b.texte }}</p>
        <span class="badge badge-ok">Livré au lot {{ b.lot ?? 0 }}</span>
      </article>
    </section>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-6); }
h1 { margin: 0; font-size: var(--font-size-xl); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 640px; }
.alerte { display: flex; align-items: center; gap: var(--space-3); padding: 12px 16px; border-radius: var(--radius-md); background: var(--color-orange-bg); color: var(--color-orange); font-size: var(--font-size-sm); text-decoration: none; max-width: 860px; }
.grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--space-4); }
.bloc { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-2); align-items: flex-start; }
.icone { width: 40px; height: 40px; border-radius: var(--radius-md); background: var(--color-brand-light); color: var(--color-brand); display: flex; align-items: center; justify-content: center; }
h2 { margin: 4px 0 0; font-size: var(--font-size-base); }
p { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); line-height: 1.5; flex: 1; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
