import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { installerInfobulles } from './utils/infobulle'

createApp(App).use(router).mount('#app')
installerInfobulles()

// Application installable (PWA) : le service worker ne met en cache que la coque, jamais les données.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => { /* facultatif */ }))
}
