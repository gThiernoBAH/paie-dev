<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Plus } from 'lucide-vue-next'

const prets = ref([])
const detail = ref(null)
const erreur = ref('')
const message = ref('')
const maintenant = new Date()
const nouveau = ref({ matricule: '', type_pret: 'pret', libelle: '', montant: '', nombre_echeances: 6, annee_debut: maintenant.getFullYear(), mois_debut: maintenant.getMonth() + 1 })
const MOIS = ['', 'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const LIB = { actif: 'En cours', solde: 'Soldé', annule: 'Annulé', prevue: 'Prévue', prelevee: 'Prélevée', annulee: 'Annulée' }
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })

async function charger() { try { prets.value = (await apiClient.get('/prets')).data } catch (e) { erreur.value = messageErreur(e) } }
async function creer() {
  erreur.value = ''; message.value = ''
  try {
    const { data } = await apiClient.get('/salaries', { params: { recherche: nouveau.value.matricule.trim(), statut: 'tous', taille: 5 } })
    const s = data.elements.find((x) => x.matricule === nouveau.value.matricule.trim().padStart(6, '0'))
    if (!s) throw new Error('Matricule introuvable.')
    const { matricule, ...corps } = nouveau.value
    const p = (await apiClient.post('/prets', { ...corps, salarie_id: s.id })).data
    message.value = `Prêt enregistré : ${p.nombre_echeances} échéance(s). Elles seront prélevées automatiquement sur les bulletins.`
    nouveau.value.matricule = ''; nouveau.value.libelle = ''; nouveau.value.montant = ''
    await charger()
  } catch (e) { erreur.value = e.response ? messageErreur(e) : e.message }
}
async function voir(p) { try { detail.value = (await apiClient.get(`/prets/${p.id}`)).data } catch (e) { erreur.value = messageErreur(e) } }
async function annuler(p) {
  if (!window.confirm('Annuler ce prêt ? Les échéances non prélevées seront supprimées.')) return
  try { detail.value = (await apiClient.post(`/prets/${p.id}/annuler`)).data; await charger() } catch (e) { erreur.value = messageErreur(e) }
}
onMounted(charger)
</script>

<template>
  <div class="page">
    <header>
      <h1>Prêts et avances</h1>
      <p class="sous-titre">Chaque prêt génère un échéancier mensuel ; l'échéance du mois est retenue automatiquement au calcul de la paie (rubrique PRE) et marquée « prélevée » à la validation. Au solde de tout compte, le reste dû est retenu en une fois.</p>
    </header>
    <p v-if="message" class="bandeau ok" role="status">{{ message }}</p>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>
    <form class="ligne card saisie" @submit.prevent="creer">
      <strong>Nouveau</strong>
      <input v-model="nouveau.matricule" class="input" placeholder="Matricule" required inputmode="numeric" aria-label="Matricule" />
      <select v-model="nouveau.type_pret" class="input" aria-label="Type"><option value="pret">Prêt</option><option value="avance">Avance</option></select>
      <input v-model="nouveau.libelle" class="input" placeholder="Libellé" required aria-label="Libellé" />
      <input v-model="nouveau.montant" type="number" min="1" class="input" placeholder="Montant" required aria-label="Montant" />
      <input v-model.number="nouveau.nombre_echeances" type="number" min="1" max="120" class="input court" required aria-label="Nombre d'échéances" title="Nombre d'échéances" />
      <input v-model.number="nouveau.mois_debut" type="number" min="1" max="12" class="input court" required aria-label="Premier mois" title="Premier mois" />
      <input v-model.number="nouveau.annee_debut" type="number" class="input court" required aria-label="Première année" title="Première année" />
      <button class="vbtn vbtn-primary" type="submit"><Plus :size="16" />Créer</button>
    </form>
    <div class="card cadre"><table>
      <thead><tr><th>Matricule</th><th>Salarié</th><th>Libellé</th><th class="num">Montant</th><th class="num">Reste dû</th><th>Statut</th><th></th></tr></thead>
      <tbody>
        <tr v-for="p in prets" :key="p.id">
          <td>{{ p.matricule }}</td><td>{{ p.nom }}</td><td>{{ p.libelle }}</td><td class="num">{{ fmt(p.montant) }}</td><td class="num">{{ fmt(p.reste) }}</td>
          <td><span class="badge">{{ LIB[p.statut] }}</span></td><td><button class="vbtn vbtn-secondary petit" @click="voir(p)">Échéancier</button></td>
        </tr>
        <tr v-if="!prets.length"><td colspan="7" class="vide">Aucun prêt.</td></tr>
      </tbody></table></div>
    <div v-if="detail" class="card encart">
      <h2>{{ detail.libelle }} — {{ detail.matricule }}</h2>
      <table><thead><tr><th>Échéance</th><th class="num">Montant</th><th>Statut</th></tr></thead>
        <tbody><tr v-for="e in detail.echeances" :key="e.id"><td>{{ MOIS[e.mois] }} {{ e.annee }}</td><td class="num">{{ fmt(e.montant) }}</td><td>{{ LIB[e.statut] }}</td></tr></tbody></table>
      <div class="ligne"><button v-if="detail.statut === 'actif'" class="vbtn vbtn-secondary" @click="annuler(detail)">Annuler le prêt</button>
        <button class="vbtn vbtn-secondary" @click="detail = null">Fermer</button></div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: var(--space-6) var(--space-8); display: flex; flex-direction: column; gap: var(--space-4); }
h1 { margin: 0; font-size: var(--font-size-xl); } h2 { margin: 0; font-size: var(--font-size-base); }
.sous-titre { margin: 4px 0 0; color: var(--color-text-muted); font-size: var(--font-size-sm); max-width: 760px; }
.ligne { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; }
.saisie { padding: var(--space-3) var(--space-4); } .saisie .input { width: auto; min-width: 120px; flex: 1; } .saisie .court { min-width: 80px; max-width: 100px; flex: 0; }
.encart { padding: var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); max-width: 520px; }
.cadre { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
th { text-align: left; padding: 10px 14px; background: #F8FAFC; color: var(--color-text-muted); font-weight: 600; border-bottom: 1px solid var(--color-border); }
td { padding: 8px 14px; border-bottom: 1px solid var(--color-border); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.petit { padding: 4px 10px; min-height: 32px; }
.bandeau.ok { background: var(--color-vert-bg); color: var(--color-vert); padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--font-size-sm); margin: 0; }
@media (max-width: 760px) { .page { padding: var(--space-4); } }
</style>
