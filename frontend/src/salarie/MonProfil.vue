<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { KeyRound } from 'lucide-vue-next'

const profil = ref(null)
const prets = ref([])
const erreur = ref('')
const MOIS = ['', 'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
onMounted(async () => {
  try { [profil.value, prets.value] = (await Promise.all([apiClient.get('/moi/profil'), apiClient.get('/moi/prets')])).map((r) => r.data) } catch (e) { erreur.value = messageErreur(e) }
})
</script>

<template>
  <div>
    <h1>Mon profil</h1>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <div v-if="profil" class="card bloc">
      <dl>
        <div><dt>Matricule</dt><dd>{{ profil.matricule }}</dd></div>
        <div><dt>Nom</dt><dd>{{ profil.nom }} {{ profil.prenoms }}</dd></div>
        <div v-if="profil.emploi"><dt>Emploi</dt><dd>{{ profil.emploi }}</dd></div>
        <div v-if="profil.service"><dt>Service</dt><dd>{{ profil.service }}</dd></div>
        <div v-if="profil.date_embauche"><dt>Embauché le</dt><dd>{{ profil.date_embauche.split('-').reverse().join('/') }}</dd></div>
        <div><dt>E-mail</dt><dd>{{ profil.email || 'Non renseigné' }}</dd></div>
        <div><dt>Paiement</dt><dd>{{ profil.mode_paiement === 'virement' ? (profil.a_un_rib ? 'Virement bancaire' : 'Virement (RIB manquant)') : profil.mode_paiement }}</dd></div>
      </dl>
      <p class="aide">Une information est incorrecte ? Contactez le service Paie.</p>
      <router-link to="/changer-mot-de-passe" class="vbtn vbtn-secondary"><KeyRound :size="16" />Changer mon mot de passe</router-link>
    </div>
    <template v-if="prets.length">
      <h2>Mes prêts et avances</h2>
      <div v-for="(p, i) in prets" :key="i" class="card bloc">
        <strong>{{ p.libelle }}</strong>
        <span>Montant {{ fmt(p.montant) }} FCFA · reste dû {{ fmt(p.reste) }} FCFA</span>
        <small>{{ p.echeances.map((e) => `${MOIS[e.mois]} ${e.annee} : ${fmt(e.montant)}${['prelevee', 'reglee'].includes(e.statut) ? ' ✓' : ''}`).join(' · ') }}</small>
      </div>
    </template>
  </div>
</template>

<style scoped>
h1 { font-size: var(--font-size-lg); margin: 0 0 var(--space-3); } h2 { font-size: var(--font-size-base); margin: var(--space-4) 0 var(--space-2); }
.bloc { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-2); }
dl { margin: 0; display: flex; flex-direction: column; } dl div { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
dt { color: var(--color-text-muted); } dd { margin: 0; font-weight: 600; text-align: right; }
.aide { font-size: var(--font-size-xs); color: var(--color-text-muted); margin: 0; } small { color: var(--color-text-muted); }
</style>
