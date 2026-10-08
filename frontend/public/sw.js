/* Service worker SIVOP Paie : met en cache la coque de l'application (démarrage rapide, fonctionne hors ligne
   pour l'écran de connexion). Les données de paie (/api) ne sont JAMAIS mises en cache. */
const VERSION = 'paie-v1'
const COQUE = ['/', '/favicon.svg', '/manifest.webmanifest', '/icon-192.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(COQUE)).then(() => self.skipWaiting()))
})
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((cles) => Promise.all(cles.filter((c) => c !== VERSION).map((c) => caches.delete(c)))).then(() => self.clients.claim()))
})
self.addEventListener('fetch', (e) => {
  const req = e.request
  const url = new URL(req.url)
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api')) return
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/')))
    return
  }
  e.respondWith(
    caches.match(req).then((en_cache) => {
      const reseau = fetch(req).then((rep) => {
        if (rep.ok) { const copie = rep.clone(); caches.open(VERSION).then((c) => c.put(req, copie)) }
        return rep
      }).catch(() => en_cache)
      return en_cache || reseau
    }),
  )
})
