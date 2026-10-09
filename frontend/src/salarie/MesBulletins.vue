<script setup>
import { ref, onMounted } from 'vue'
import apiClient, { messageErreur } from '@/api/client'
import { Download, Eye, ChevronLeft } from 'lucide-vue-next'

const bulletins = ref([])
const detail = ref(null)
const erreur = ref('')
const chargement = ref(true)
const MOIS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
const fmt = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 })
const fmt2 = (n) => Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
const titre = (b) => (b.numero === 1 && b.mois ? `${MOIS[b.mois]} ${b.annee}` : `${b.debut.split('-').reverse().join('/')} → ${b.fin.split('-').reverse().join('/')}`)

async function charger() {
  try { bulletins.value = (await apiClient.get('/moi/bulletins')).data } catch (e) { erreur.value = messageErreur(e) } finally { chargement.value = false }
}
async function voir(b) {
  erreur.value = ''
  try { detail.value = { ...(await apiClient.get(`/moi/bulletins/${b.id}`)).data, titre: titre(b) } } catch (e) { erreur.value = messageErreur(e) }
}
async function pdf(b) {
  erreur.value = ''
  try {
    const { data } = await apiClient.get(`/moi/bulletins/${b.id}/pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url; a.download = `bulletin_${b.annee}_${String(b.mois).padStart(2, '0')}.pdf`; document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
    b.lu = true
  } catch (e) { erreur.value = 'Impossible de télécharger le bulletin.' }
}
onMounted(charger)
</script>

<template>
  <div>
    <h1>Mes bulletins de paie</h1>
    <p v-if="erreur" class="message-erreur" role="alert">{{ erreur }}</p>

    <template v-if="!detail">
      <p v-if="chargement" class="vide">Chargement…</p>
      <p v-else-if="!bulletins.length" class="vide">Aucun bulletin disponible pour l'instant.<br /><small>Un bulletin apparaît ici dès qu'il a été validé par le service Paie.</small></p>
      <ul class="liste">
        <li v-for="b in bulletins" :key="b.id" class="card carte">
          <div class="info">
            <strong>{{ titre(b) }}</strong>
            <span class="net">Net à payer : {{ fmt(b.net_a_payer) }} FCFA</span>
            <span v-if="!b.lu" class="badge nouveau">Nouveau</span>
          </div>
          <div class="actions">
            <button class="vbtn vbtn-secondary" data-hint="Afficher le détail de ce bulletin" @click="voir(b)"><Eye :size="16" />Voir</button>
            <button class="vbtn vbtn-primary" data-hint="Télécharger ce bulletin au format PDF" @click="pdf(b)"><Download :size="16" />PDF</button>
          </div>
        </li>
      </ul>
    </template>

    <div v-else class="card detail">
      <button class="retour" @click="detail = null"><ChevronLeft :size="18" />Retour</button>
      <h2>{{ detail.titre }}</h2>
      <div class="lignes">
        <div v-for="(l, i) in detail.lignes" :key="i" :class="['ligne-b', { total: l.type === 'TO' }]">
          <span>{{ l.libelle }}</span>
          <strong :class="{ ret: ['RI', 'RN'].includes(l.type) }">{{ ['RI', 'RN'].includes(l.type) ? '− ' : '' }}{{ fmt2(l.montant) }}</strong>
        </div>
      </div>
      <div class="totaux">
        <div><span>Total imposable</span><strong>{{ fmt(detail.total_imposable) }}</strong></div>
        <div><span>CNPS</span><strong>{{ fmt(detail.cnps) }}</strong></div>
        <div><span>Impôt (ITS)</span><strong>{{ fmt(detail.its) }}</strong></div>
        <div class="net-final"><span>Net à payer</span><strong>{{ fmt(detail.net_a_payer) }} FCFA</strong></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: var(--font-size-lg); margin: 0 0 var(--space-3); } h2 { font-size: var(--font-size-base); margin: 4px 0 var(--space-3); }
.liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
.carte { padding: var(--space-3) var(--space-4); display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.info { display: flex; flex-direction: column; gap: 4px; align-items: flex-start; } .net { color: var(--color-text-muted); font-size: var(--font-size-sm); }
.actions { display: flex; gap: var(--space-2); }
.nouveau { background: var(--color-vert-bg); color: var(--color-vert); }
.vide { text-align: center; color: var(--color-text-muted); padding: var(--space-6); }
.detail { padding: var(--space-4); } .retour { border: none; background: none; color: var(--color-brand-dark); display: inline-flex; align-items: center; cursor: pointer; padding: 6px 0; min-height: 40px; }
.lignes { display: flex; flex-direction: column; } .ligne-b { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.ret { color: var(--color-rouge); }
.total { background: var(--color-surface-2); font-weight: 600; }
.totaux { margin-top: var(--space-3); display: flex; flex-direction: column; gap: 6px; font-size: var(--font-size-sm); } .totaux div { display: flex; justify-content: space-between; }
.net-final { font-size: var(--font-size-base); padding: 10px; background: var(--color-brand-light); border-radius: var(--radius-md); }
</style>
