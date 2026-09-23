self.EFACE_SERVICE_WORKER_VERSION = '2.21.258'
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(clients.claim()))
self.addEventListener('push', event => {
  let data = {}
  try { data = event.data?.json() || {} } catch (_) {}
  const target = new URL(data.target || `intercom?push=1&from=${encodeURIComponent(data.caller || '')}`, self.registration.scope).href
  event.waitUntil(self.registration.showNotification(data.title || 'Chiamata Intercom', {
    body: data.body || 'Tocca per rispondere', icon: 'assets/eface-x4-app-icon.png', badge: 'assets/eface-x4-app-icon.png',
    tag: `eface-call-${data.extension || 'incoming'}`, renotify: true, requireInteraction: true,
    vibrate: [500,250,500,900,500,250,500], data: {target}, actions: [{action:'answer', title:'APRI E RISPONDI'}, {action:'dismiss', title:'IGNORA'}]
  }))
})
self.addEventListener('notificationclick', event => {
  event.notification.close()
  if (event.action === 'dismiss') return
  event.waitUntil((async () => {
    const target = event.notification.data.target
    const targetUrl = new URL(target)
    const windows = await clients.matchAll({type:'window', includeUncontrolled:true})
    const sameOrigin = windows.filter(client => new URL(client.url).origin === targetUrl.origin)
    const current = sameOrigin.find(client => {
      const url = new URL(client.url)
      return url.pathname.includes('/intercom') && !url.pathname.includes('/intercom/wake/')
    }) || sameOrigin[0]
    if (current) {
      // Navigating an already running PWA destroys its WebSocket/SIP session
      // precisely while the INVITE is arriving. Focus it and let the existing
      // page (or its Intercom iframe) expose the answer controls instead.
      await current.focus()
      current.postMessage({type:'eface-open-intercom', target})
      return
    }
    await clients.openWindow(target)
  })())
})
