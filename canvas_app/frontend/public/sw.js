const CACHE = 'hiil-v1'
const STATIC = ['/', '/canvas/', '/canvas/manifest.json', '/canvas/icon-192.svg', '/canvas/icon-512.svg']

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(STATIC))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
    ))
  )
})

self.addEventListener('fetch', (e) => {
  const { request } = e
  if (request.method !== 'GET') return
  e.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((res) => {
      if (res.ok && request.url.startsWith(self.location.origin)) {
        const clone = res.clone()
        caches.open(CACHE).then((c) => c.put(request, clone))
      }
      return res
    }))
  )
})
