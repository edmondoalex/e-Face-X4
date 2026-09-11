const $ = (selector) => document.querySelector(selector)
const glyph = { light: '✦', climate: '❄', shield: '⬡', energy: 'ϟ', cover: '▤', sensor: '◌' }
let refreshRunning = false
let currentDevices = []

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
  currentDevices = Array.isArray(dashboard.devices) ? dashboard.devices : []
  const online = providers.filter((provider) => provider.status === 'online').length
  const enabled = providers.filter((provider) => provider.status !== 'disabled').length
  $('#home-name').textContent = home.name || 'Casa'
  $('#mode').textContent = data.mode === 'demo' ? 'ANTEPRIMA DEMO' : 'LIVE'
  $('#weather').textContent = home.temperature ? `${home.temperature}° · ${home.weather || 'Comfort'}` : 'Comfort'
  $('#temperature').textContent = `${home.temperature || 22}°`
  $('#lights-count').textContent = widgets.find((widget) => widget.id === 'lights')?.value || '0'
  $('#provider-state strong').textContent = enabled ? `${online}/${enabled}` : 'OFF'
  $('#provider-state').classList.toggle('provider-online', enabled > 0 && online === enabled)
  $('#demo-cameras').hidden = data.mode !== 'demo'
  const failedProvider = providers.find((provider) => provider.status === 'offline' || provider.status === 'misconfigured')
  if (data.mode === 'live' && failedProvider) {
    const notice = $('#notice')
    notice.textContent = `${failedProvider.label}: ${failedProvider.reason || 'connettore non disponibile'}. Controlla indirizzo, porta e autenticazione.`
    notice.hidden = false
  }
  $('#widgets').innerHTML = widgets.slice(0, 4).map((widget) => `
    <button class="quick-card" data-kind="${esc(widget.id)}">
      <span class="qicon">${glyph[widget.icon] || '◇'}</span>
      <span>${esc(widget.title)}<strong>${esc(widget.value)}</strong><small>${esc(widget.detail)}</small></span>
    </button>`).join('')
  $('#rooms').innerHTML = (dashboard.rooms || []).map((room) => `
    <button class="room-card" data-room="${esc(room.name)}"><span>${esc(room.name)}</span><small>${Number(room.devices) || 0} dispositivi</small></button>
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

function stateLabel(value) {
  if (value === null || value === undefined || value === '') return 'Stato non disponibile'
  if (typeof value === 'boolean') return value ? 'Attivo' : 'Disattivo'
  return String(value)
}

function openDevices(title, devices) {
  $('#dialog-title').textContent = title
  $('#dialog-kicker').textContent = `${devices.length} dispositivi`
  $('#device-list').innerHTML = devices.map((device) => `
    <article><span class="device-glyph">${glyph[device.kind] || '◇'}</span><div><strong>${esc(device.name)}</strong><small>${esc(device.room)}</small></div><em>${esc(stateLabel(device.state))}</em></article>
  `).join('') || '<p class="empty-state">Nessun dispositivo disponibile</p>'
  $('#device-dialog').showModal()
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
  if (button.dataset.view === 'rooms') $('.room-panel').scrollIntoView({ behavior: 'smooth', block: 'center' })
  if (button.dataset.view === 'security') openDevices('Sicurezza', currentDevices.filter((device) => device.kind === 'lock'))
  if (button.dataset.view === 'more') openDevices('Tutti i dispositivi', currentDevices)
}))
$('#widgets').addEventListener('click', (event) => {
  const button = event.target.closest('[data-kind]')
  if (!button) return
  const map = { lights: ['light', 'switch'], covers: ['cover'], locks: ['lock'], sensors: ['temp', 'temperature', 'humidity', 'illuminance', 'pir', 'ultrasonic', 'dry_contact', 'air_quality', 'gas_percent'] }
  const kinds = map[button.dataset.kind] || []
  openDevices(button.textContent.trim(), currentDevices.filter((device) => kinds.includes(device.kind)))
})
$('#rooms').addEventListener('click', (event) => {
  const button = event.target.closest('[data-room]')
  if (!button) return
  openDevices(button.dataset.room, currentDevices.filter((device) => device.room.toLocaleLowerCase('it') === button.dataset.room.toLocaleLowerCase('it')))
})
$('#dialog-close').addEventListener('click', () => $('#device-dialog').close())
$('#show-all-devices').addEventListener('click', () => openDevices('Tutti i dispositivi', currentDevices))
$('#volume').addEventListener('input', (event) => { $('#volume-value').textContent = `${event.target.value}%` })
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh() })
tick()
setInterval(tick, 30000)
setInterval(refresh, 10000)
refresh()
