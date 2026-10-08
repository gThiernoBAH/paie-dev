<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { lireUtilisateur, ouvrirSession, fermerSession } from '@/api/session'
import { KeyRound } from 'lucide-vue-next'

const router = useRouter()
const utilisateur = lireUtilisateur()
const obligatoire = !!utilisateur?.doit_changer_mot_de_passe

const ancien = ref('')
const nouveau = ref('')
const confirmation = ref('')
const erreur = ref('')
const enCours = ref(false)

const regles = computed(() => [
  { ok: nouveau.value.length >= 10, texte: 'au moins 10 caractères' },
  { ok: /[A-Za-z]/.test(nouveau.value), texte: 'au moins une lettre' },
  { ok: /\d/.test(nouveau.value), texte: 'au moins un chiffre' },
  { ok: nouveau.value !== '' && nouveau.value === confirmation.value, texte: 'confirmation identique' },
])
const valide = computed(() => regles.value.every((r) => r.ok) && ancien.value !== '')

async function valider() {
  if (!valide.value || enCours.value) return
  enCours.value = true
  erreur.value = ''
  try {
    const { data } = await apiClient.post('/auth/mot-de-passe', {
      ancien_mot_de_passe: ancien.value,
      nouveau_mot_de_passe: nouveau.value,
    })
    ouvrirSession(data) // l'ancien jeton est révoqué par le serveur : on garde le neuf
    router.push('/')
  } catch (e) {
    erreur.value = messageErreur(e)
  } finally {
    enCours.value = false
  }
}

function annuler() {
  if (!obligatoire) { router.push('/'); return }   // changement volontaire : on revient simplement
  fermerSession()
  router.push('/login')
}
</script>

<template>
  <div class="page">
    <form class="carte" @submit.prevent="valider">
      <div class="entete">
        <div class="icone"><KeyRound :size="24" /></div>
        <div>
          <h1>Changer le mot de passe</h1>
          <p v-if="obligatoire">Pour votre sécurité, choisissez un mot de passe personnel avant de continuer.</p>
        </div>
      </div>

      <label class="field"><span class="field-label">{{ obligatoire ? 'Mot de passe actuel (celui qui vous a été remis)' : 'Mot de passe actuel' }}</span>
        <input v-model="ancien" class="input" type="password" autocomplete="current-password" required />
      </label>
      <label class="field"><span class="field-label">Nouveau mot de passe</span>
        <input v-model="nouveau" class="input" type="password" autocomplete="new-password" required />
      </label>
      <label class="field"><span class="field-label">Confirmer le nouveau mot de passe</span>
        <input v-model="confirmation" class="input" type="password" autocomplete="new-password" required />
      </label>

      <ul class="regles">
        <li v-for="r in regles" :key="r.texte" :class="{ ok: r.ok }">{{ r.ok ? '✓' : '○' }} {{ r.texte }}</li>
      </ul>

      <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

      <div class="actions">
        <button type="button" class="vbtn vbtn-secondary" @click="annuler">{{ obligatoire ? 'Se déconnecter' : 'Annuler' }}</button>
        <button type="submit" class="vbtn vbtn-primary" :disabled="!valide || enCours">{{ enCours ? 'Enregistrement…' : 'Enregistrer' }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.page { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: var(--space-4); background: var(--color-bg); }
.carte { width: 100%; max-width: 440px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); padding: var(--space-8) var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); }
.entete { display: flex; gap: var(--space-3); align-items: flex-start; }
.icone { width: 44px; height: 44px; border-radius: var(--radius-md); background: var(--color-brand-light); color: var(--color-brand); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
h1 { margin: 0; font-size: var(--font-size-lg); }
p { margin: 4px 0 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.regles { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.regles .ok { color: var(--color-vert); font-weight: 600; }
.actions { display: flex; justify-content: flex-end; gap: var(--space-3); flex-wrap: wrap; }
</style>
