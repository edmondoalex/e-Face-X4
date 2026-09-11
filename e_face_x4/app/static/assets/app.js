const $ = (selector) => document.querySelector(selector)
const glyph = { light: '✦', climate: '❄', shield: '⬡', energy: 'ϟ', cover: '▤', sensor: '◌' }
let refreshRunning = false

function apiUrl(path) {
  const base = location.pathname.endsWith('/') ? location.pathname : `${location.pathname}/`
  return new URL(path.replace(/^\//, ''), `${location.origin}${base}`).toString()
}

function esc(value) {
  const node = document.createElement('span')
  node.textContent = String(value ?? '')
  return node.innerHTML
}

function tick() {
  const now = new Date()
  $('#clock').textContent = now.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  $('#date').textContent = now.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}

function render(data) {
  const dashboard = data.dashboard || {}
  const home = dashboard.home || {}
  const widgets = dashboard.widgets || []
  const providers = data.providers || []
  const online = providers.filter((provider) => provider.status === 'online').length
  const enabled = providers.filter((provider) => provider.status !== 'disabled').length
  $('#home-name').textContent = home.name || 'Casa'
  $('#mode').textContent = data.mode === 'demo' ? 'ANTEPRIMA DEMO' : 'LIVE'
  $('#weather').textContent = home.temperature ? `${home.temperature}° · ${home.weather || 'Comfort'}` : 'Comfort'
  $('#temperature').textContent = `${home.temperature || 22}°`
  $('#lights-count').textContent = widgets.find((widget) => widget.id === 'lights')?.value || '0'
  $('#provider-state strong').textContent = enabled ? `${online}/${enabled}` : 'OFF'
  $('#provider-state').classList.toggle('provider-online', enabled > 0 && online === enabled)
  const failedProvider = providers.find((provider) => provider.status === 'offline' || provider.status === 'misconfigured')
  if (data.mode === 'live' && failedProvider) {
    const notice = $('#notice')
    notice.textContent = `${failedProvider.label}: ${failedProvider.reason || 'connettore non disponibile'}. Controlla indirizzo, porta e autenticazione.`
    notice.hidden = false
  }
  $('#widgets').innerHTML = widgets.slice(0, 4).map((widget) => `
    <button class="quick-card">
      <span class="qicon">${glyph[widget.icon] || '◇'}</span>
      <span>${esc(widget.title)}<strong>${esc(widget.value)}</strong><small>${esc(widget.detail)}</small></span>
    </button>`).join('')
  $('#rooms').innerHTML = (dashboard.rooms || []).map((room) => `
    <button class="room-card"><span>${esc(room.name)}</span><small>${Number(room.devices) || 0} dispositivi</small></button>
  `).join('') || '<span class="empty-state">Nessun ambiente disponibile</span>'
  const media = dashboard.media
  $('#media').hidden = !media
  if (media) {
    $('#track-title').textContent = media.title || 'Nessun titolo'
    $('#track-detail').textContent = [media.artist, media.room].filter(Boolean).join(' · ')
    $('#volume').value = Number(media.volume) || 0
    $('#volume-value').textContent = `${Number(media.volume) || 0}%`
  }
  $('#app').classList.remove('loading')
  if (!failedProvider) $('#notice').hidden = true
}

function fail(error) {
  $('#app').classList.remove('loading')
  const notice = $('#notice')
  notice.textContent = `Dati non disponibili (${error.message})`
  notice.hidden = false
}

async function refresh() {
  if (refreshRunning || document.hidden) return
  refreshRunning = true
  try {
    const response = await fetch(apiUrl('api/bootstrap'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    render(await response.json())
  } catch (error) {
    fail(error)
  } finally {
    refreshRunning = false
  }
}

document.querySelectorAll('.rail button').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('.rail button').forEach((item) => item.classList.remove('active'))
  button.classList.add('active')
  document.querySelector('main').classList.remove('app-view')
  requestAnimationFrame(() => document.querySelector('main').classList.add('app-view'))
  if (button.dataset.view === 'media') $('#media').scrollIntoView({ behavior: 'smooth', block: 'center' })
}))
$('#volume').addEventListener('input', (event) => { $('#volume-value').textContent = `${event.target.value}%` })
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh() })
tick()
setInterval(tick, 30000)
setInterval(refresh, 10000)
refresh()
