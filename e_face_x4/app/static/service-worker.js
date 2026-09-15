self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(clients.claim()))
self.addEventListener('push', event => {
  let data = {}
  try { data = event.data?.json() || {} } catch (_) {}
  const target = new URL(`intercom?push=1&from=${encodeURIComponent(data.caller || '')}`, self.registration.scope).href
  event.waitUntil(self.registration.showNotification(data.title || 'Chiamata Intercom', {
    body: data.body || 'Tocca per rispondere', icon: 'assets/eface-x4-app-icon.png', badge: 'assets/eface-x4-app-icon.png',
    tag: `eface-call-${data.extension || 'incoming'}`, renotify: true, requireInteraction: true,
    vibrate: [500,250,500,900,500,250,500], data: {target}, actions: [{action:'answer', title:'APRI E RISPONDI'}, {action:'dismiss', title:'IGNORA'}]
  }))
})
self.addEventListener('notificationclick', event => {
  event.notification.close()
  if (event.action === 'dismiss') return
  event.waitUntil(clients.openWindow(event.notification.data.target))
})
