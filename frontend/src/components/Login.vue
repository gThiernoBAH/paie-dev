<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import apiClient, { messageErreur } from '@/api/client'
import { ouvrirSession } from '@/api/session'
import { User, Lock, Eye, EyeOff, Banknote } from 'lucide-vue-next'

const router = useRouter()

const identifiant = ref('')
const password = ref('')
const showPassword = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')

const handleLogin = async () => {
  if (!identifiant.value || !password.value || isLoading.value) return
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await apiClient.post('/auth/login', {
      identifiant: identifiant.value.trim(),
      password: password.value,
    })
    ouvrirSession(response.data)
    // Le guard du routeur redirige vers le changement de mot de passe si nécessaire.
    router.push(response.data.user.doit_changer_mot_de_passe ? '/changer-mot-de-passe' : '/')
  } catch (error) {
    errorMessage.value = messageErreur(error, 'Connexion impossible.')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-icon"><Banknote :size="28" /></div>
        <div>
          <div class="brand-name">SIVOP</div>
          <div class="brand-sub">Paie</div>
        </div>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <label class="field">
          <span class="field-label">Matricule</span>
          <div class="input-group">
            <User :size="18" class="input-icon" />
            <input v-model="identifiant" type="text" autocomplete="username" placeholder="Ex. 000101" autofocus required />
          </div>
        </label>

        <label class="field">
          <span class="field-label">Mot de passe</span>
          <div class="input-group">
            <Lock :size="18" class="input-icon" />
            <input v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="Mot de passe" required />
            <button type="button" class="toggle-pwd" :aria-label="showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'" @click="showPassword = !showPassword">
              <component :is="showPassword ? EyeOff : Eye" :size="18" />
            </button>
          </div>
        </label>

        <p v-if="errorMessage" class="message-erreur" role="alert">{{ errorMessage }}</p>

        <button type="submit" class="submit-btn" :disabled="isLoading">
          {{ isLoading ? 'Connexion…' : 'Se connecter' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page { height: 100%; width: 100%; display: flex; align-items: center; justify-content: center; background: var(--color-bg); padding: var(--space-4); }
.login-card { width: 100%; max-width: 400px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); box-shadow: var(--shadow-card); padding: var(--space-8) var(--space-6); }
.brand { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-8); }
.brand-icon { width: 48px; height: 48px; border-radius: var(--radius-md); background: var(--color-brand); color: var(--color-text-inverse); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.brand-name { font-size: var(--font-size-lg); font-weight: 800; letter-spacing: 1px; color: var(--color-brand-dark); }
.brand-sub { font-size: var(--font-size-sm); color: var(--color-text-muted); }
.login-form { display: flex; flex-direction: column; gap: var(--space-4); }
.input-group { position: relative; display: flex; align-items: center; }
.input-icon { position: absolute; left: 14px; color: var(--color-text-muted); pointer-events: none; }
.input-group input { width: 100%; height: var(--touch-target-min); padding: 0 var(--space-3) 0 44px; border: 1px solid #C9D2DD; border-radius: var(--radius-md); font-size: var(--font-size-base); color: var(--color-text); background: var(--color-surface); outline: none; transition: border-color 0.15s; }
.input-group input:focus { border-color: var(--color-brand); outline: 2px solid var(--color-brand); }
.toggle-pwd { position: absolute; right: 4px; width: 40px; height: 40px; background: none; border: none; color: var(--color-text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; }
.submit-btn { height: var(--touch-target-min); border: none; border-radius: var(--radius-md); background: var(--color-brand); color: var(--color-text-inverse); font-size: var(--font-size-base); font-weight: 700; cursor: pointer; transition: background 0.15s; }
.submit-btn:hover:not(:disabled) { background: var(--color-brand-dark); }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
