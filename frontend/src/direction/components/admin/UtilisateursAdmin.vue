<script setup>
import { ref, computed, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur } from '@/api/session'
import { Plus, KeyRound, ShieldCheck, X, Copy } from 'lucide-vue-next'

const moi = lireUtilisateur()
const comptes = ref([])
const referentiel = ref({ roles: [], permissions: [], permissions_par_defaut: {} })
const recherche = ref('')
const erreur = ref('')
const info = ref('')

// Panneau latéral : création ou édition d'un compte.
const panneau = ref(null) // null | 'creation' | 'edition'
const cible = ref(null)
const formulaire = ref({})
const permsChoisies = ref([])
const enCours = ref(false)
const erreurPanneau = ref('')
// Mot de passe temporaire : affiché une seule fois, jamais stocké.
const motDePasseTemp = ref(null)
const copie = ref(false)

const libelleRole = (cle) => referentiel.value.roles.find((r) => r.cle === cle)?.libelle || cle

async function charger() {
  erreur.value = ''
  try {
    const { data } = await apiClient.get('/admin/utilisateurs', { params: recherche.value ? { recherche: recherche.value } : {} })
    comptes.value = data
  } catch (e) { erreur.value = messageErreur(e) }
}
async function chargerReferentiel() {
  try { referentiel.value = (await apiClient.get('/admin/referentiel')).data } catch (e) { erreur.value = messageErreur(e) }
}

function ouvrirCreation() {
  panneau.value = 'creation'; cible.value = null; erreurPanneau.value = ''
  formulaire.value = { identifiant: '', nom: '', prenom: '', email: '', telephone: '', role: 'salarie', est_actif: true }
}
function ouvrirEdition(c) {
  panneau.value = 'edition'; cible.value = c; erreurPanneau.value = ''
  formulaire.value = { nom: c.nom, prenom: c.prenom || '', email: c.email || '', telephone: c.telephone || '', role: c.role, est_actif: c.est_actif }
  permsChoisies.value = [...c.permissions]
}
function fermer() { panneau.value = null; cible.value = null }

const nettoyer = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v === '' ? null : v]))

async function enregistrer() {
  if (enCours.value) return
  enCours.value = true; erreurPanneau.value = ''
  try {
    if (panneau.value === 'creation') {
      const { identifiant, nom, prenom, email, telephone, role } = formulaire.value
      const { data } = await apiClient.post('/admin/utilisateurs', nettoyer({ identifiant, nom, prenom, email, telephone, role }))
      motDePasseTemp.value = { identifiant: data.utilisateur.identifiant, mot_de_passe: data.mot_de_passe_temporaire }
      info.value = `Compte ${data.utilisateur.identifiant} créé.`
      fermer()
    } else {
      const c = cible.value
      await apiClient.patch(`/admin/utilisateurs/${c.id}`, nettoyer(formulaire.value))
      await apiClient.put(`/admin/utilisateurs/${c.id}/permissions`, { permissions: permsChoisies.value })
      info.value = `Compte ${c.identifiant} mis à jour.`
      fermer()
    }
    await charger()
  } catch (e) { erreurPanneau.value = messageErreur(e) } finally { enCours.value = false }
}

async function reinitialiser(c) {
  if (!window.confirm(`Réinitialiser le mot de passe de ${c.identifiant} ? Ses sessions seront coupées.`)) return
  erreur.value = ''
  try {
    const { data } = await apiClient.post(`/admin/utilisateurs/${c.id}/reinitialiser-mot-de-passe`)
    motDePasseTemp.value = { identifiant: c.identifiant, mot_de_passe: data.mot_de_passe_temporaire }
    await charger()
  } catch (e) { erreur.value = messageErreur(e) }
}

async function copier() {
  try { await navigator.clipboard.writeText(motDePasseTemp.value.mot_de_passe); copie.value = true } catch { /* copie manuelle */ }
}
function fermerMotDePasse() { motDePasseTemp.value = null; copie.value = false }

const formatDate = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR') : 'jamais')
const estMoi = (c) => c.id === moi?.id
onMounted(() => { chargerReferentiel(); charger() })
</script>

<template>
  <section class="bloc">
    <div class="barre">
      <form class="recherche" @submit.prevent="charger">
        <input v-model="recherche" class="input" placeholder="Rechercher un matricule ou un nom" aria-label="Rechercher" />
        <button class="vbtn vbtn-secondary" type="submit">Rechercher</button>
      </form>
      <button class="vbtn vbtn-primary" @click="ouvrirCreation"><Plus :size="16" />Nouveau compte</button>
    </div>

    <p v-if="info" class="info" role="status">{{ info }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <div class="card tableau-cadre">
      <table>
        <thead><tr><th>Matricule</th><th>Nom</th><th>Rôle</th><th>Statut</th><th>Dernière connexion</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in comptes" :key="c.id">
            <td><strong>{{ c.identifiant }}</strong></td>
            <td>{{ [c.prenom, c.nom].filter(Boolean).join(' ') }}</td>
            <td>{{ libelleRole(c.role) }}</td>
            <td>
              <span :class="['badge', c.est_actif ? 'badge-ok' : 'badge-erreur']">{{ c.est_actif ? 'Actif' : 'Désactivé' }}</span>
              <span v-if="c.doit_changer_mot_de_passe" class="badge badge-attente espace">Mot de passe à changer</span>
            </td>
            <td class="nowrap">{{ formatDate(c.derniere_connexion) }}</td>
            <td class="actions">
              <button class="vbtn vbtn-secondary" @click="ouvrirEdition(c)"><ShieldCheck :size="16" />Droits</button>
              <button class="vbtn vbtn-secondary" :disabled="estMoi(c)" :title="estMoi(c) ? 'Utilisez « Mot de passe » dans le menu' : ''" @click="reinitialiser(c)"><KeyRound :size="16" />Réinitialiser</button>
            </td>
          </tr>
          <tr v-if="!comptes.length"><td colspan="6" class="vide">Aucun compte.</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Panneau latéral création / édition -->
    <div v-if="panneau" class="voile" @click.self="fermer">
      <aside class="panneau" role="dialog" aria-modal="true">
        <header class="panneau-tete">
          <h2>{{ panneau === 'creation' ? 'Nouveau compte' : `Compte ${cible.identifiant}` }}</h2>
          <button class="fermer" aria-label="Fermer" @click="fermer"><X :size="20" /></button>
        </header>
        <form class="panneau-corps" @submit.prevent="enregistrer">
          <label v-if="panneau === 'creation'" class="field"><span class="field-label">Matricule (identifiant)</span>
            <input v-model="formulaire.identifiant" class="input" required minlength="2" maxlength="20" pattern="[A-Za-z0-9_.\-]+" /></label>
          <label class="field"><span class="field-label">Nom</span><input v-model="formulaire.nom" class="input" required /></label>
          <label class="field"><span class="field-label">Prénom</span><input v-model="formulaire.prenom" class="input" /></label>
          <label class="field"><span class="field-label">E-mail</span><input v-model="formulaire.email" class="input" type="email" /></label>
          <label class="field"><span class="field-label">Téléphone</span><input v-model="formulaire.telephone" class="input" /></label>
          <label class="field"><span class="field-label">Rôle</span>
            <select v-model="formulaire.role" class="input">
              <option v-for="r in referentiel.roles" :key="r.cle" :value="r.cle">{{ r.libelle }}</option>
            </select></label>

          <template v-if="panneau === 'edition'">
            <label class="case"><input v-model="formulaire.est_actif" type="checkbox" :disabled="estMoi(cible)" /> Compte actif</label>
            <fieldset class="perms">
              <legend>Permissions</legend>
              <label v-for="p in referentiel.permissions" :key="p.cle" class="case">
                <input v-model="permsChoisies" type="checkbox" :value="p.cle" /> {{ p.libelle }}
              </label>
              <small v-if="formulaire.role === 'admin'">Un administrateur dispose de toutes les permissions.</small>
            </fieldset>
          </template>
          <p v-else class="aide">Un mot de passe temporaire sera généré ; il devra être changé à la première connexion.</p>

          <p v-if="erreurPanneau" class="message-erreur" role="alert">{{ erreurPanneau }}</p>
          <div class="panneau-actions">
            <button type="button" class="vbtn vbtn-secondary" @click="fermer">Annuler</button>
            <button type="submit" class="vbtn vbtn-primary" :disabled="enCours">{{ enCours ? 'Enregistrement…' : 'Enregistrer' }}</button>
          </div>
        </form>
      </aside>
    </div>

    <!-- Mot de passe temporaire : une seule fois -->
    <div v-if="motDePasseTemp" class="voile centre">
      <div class="modale card" role="alertdialog" aria-modal="true">
        <h2>Mot de passe temporaire</h2>
        <p>Compte <strong>{{ motDePasseTemp.identifiant }}</strong>. Transmettez-le de façon sûre : il ne sera <strong>plus affichable</strong>.</p>
        <code class="mdp">{{ motDePasseTemp.mot_de_passe }}</code>
        <div class="panneau-actions">
          <button class="vbtn vbtn-secondary" @click="copier"><Copy :size="16" />{{ copie ? 'Copié' : 'Copier' }}</button>
          <button class="vbtn vbtn-primary" @click="fermerMotDePasse">J'ai noté le mot de passe</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.bloc { display: flex; flex-direction: column; gap: var(--space-4); }
.barre { display: flex; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.recherche { display: flex; gap: var(--space-2); flex: 1; max-width: 480px; }
.info { margin: 0; padding: 10px 14px; background: var(--color-vert-bg); color: var(--color-vert); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.tableau-cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 10px 14px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.nowrap { white-space: nowrap; }
.espace { margin-left: 6px; }
.actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.voile { position: fixed; inset: 0; background: rgba(15, 23, 42, .4); display: flex; justify-content: flex-end; z-index: 50; }
.voile.centre { justify-content: center; align-items: center; padding: var(--space-4); }
.panneau { width: 100%; max-width: 440px; background: var(--color-surface); height: 100%; overflow-y: auto; display: flex; flex-direction: column; }
.panneau-tete { display: flex; justify-content: space-between; align-items: center; padding: var(--space-4) var(--space-6); border-bottom: 1px solid var(--color-border); }
.panneau-tete h2 { margin: 0; font-size: var(--font-size-lg); }
.fermer { border: none; background: none; cursor: pointer; width: 40px; height: 40px; color: var(--color-text-muted); }
.panneau-corps { padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); }
.panneau-actions { display: flex; justify-content: flex-end; gap: var(--space-3); flex-wrap: wrap; }
.case { display: flex; align-items: center; gap: 10px; font-size: var(--font-size-sm); min-height: 32px; }
.perms { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); display: flex; flex-direction: column; gap: 2px; }
.perms legend { font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-muted); padding: 0 6px; }
.perms small, .aide { color: var(--color-text-muted); font-size: var(--font-size-xs); margin: 0; }
.modale { max-width: 460px; width: 100%; padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); }
.modale h2 { margin: 0; font-size: var(--font-size-lg); }
.modale p { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.mdp { display: block; padding: 14px; background: #F8FAFC; border: 1px dashed #C9D2DD; border-radius: var(--radius-md); font-size: var(--font-size-lg); letter-spacing: 1px; text-align: center; user-select: all; }
</style>
