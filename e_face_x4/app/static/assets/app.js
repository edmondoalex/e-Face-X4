const $ = (selector) => document.querySelector(selector)
const glyph = { light: '✦', climate: '❄', shield: '⬡', energy: 'ϟ', cover: '▤', sensor: '◌' }
let refreshRunning = false
let currentDevices = []
let appVersion = '0'
let activeDetailIds = null
let realtimeSocket = null
let realtimeRetry = null
let detailRenderQueued = false
let snapshotRefreshTimer = null
let currentScenarios = []

function apiUrl(path) {
  const base = location.pathname.endsWith('/') ? location.pathname : `${location.pathname}/`
  return new URL(path.replace(/^\//, ''), `${location.origin}${base}`).toString()
}

function esc(value) {
  const node = document.createElement('span')
  node.textContent = String(value ?? '')
  return node.innerHTML
}

function mdiName(value, fallback = 'shape') {
  const match = /^mdi:([a-z0-9_-]+)$/i.exec(String(value || '').trim())
  return match ? match[1].toLowerCase() : fallback
}

function mdiStyle(value, fallback) {
  return `--icon:url('${apiUrl(`api/icons/mdi/${mdiName(value, fallback)}.svg`)}?v=${encodeURIComponent(appVersion)}')`
}

function tick() {
  const now = new Date()
  $('#clock').textContent = now.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  $('#date').textContent = now.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}

function render(data) {
  appVersion = data.version || appVersion
  const dashboard = data.dashboard || {}
  const home = dashboard.home || {}
  const widgets = dashboard.widgets || []
  const providers = data.providers || []
  const navIcons = data.nav_icons || {}
  currentDevices = Array.isArray(dashboard.devices) ? dashboard.devices : []
  if (activeDetailIds && !$('#detail-view').hidden) {
    renderDeviceList(currentDevices.filter((device) => activeDetailIds.has(String(device.id))))
  }
  const online = providers.filter((provider) => provider.status === 'online').length
  const enabled = providers.filter((provider) => provider.status !== 'disabled').length
  $('#home-name').textContent = home.name || 'Casa'
  $('#mode').textContent = data.mode === 'demo' ? 'ANTEPRIMA DEMO' : 'LIVE'
  $('#weather').textContent = home.temperature ? `${home.temperature}° · ${home.weather || 'Comfort'}` : 'Comfort'
  $('#temperature').textContent = `${home.temperature || 22}°`
  $('#lights-count').textContent = widgets.find((widget) => widget.id === 'lights')?.value || '0'
  $('#provider-state strong').textContent = enabled ? `${online}/${enabled}` : 'OFF'
  $('#provider-state').classList.toggle('provider-online', enabled > 0 && online === enabled)
  document.querySelectorAll('.nav-icon').forEach((node) => {
    node.setAttribute('style', mdiStyle(navIcons[node.dataset.icon], 'shape'))
  })
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

function stateLabel(device) {
  const value = device.state
  if (value === null || value === undefined || value === '') return 'Stato non disponibile'
  if (typeof value === 'boolean') return value ? 'Attivo' : 'Disattivo'
  const numeric = Number(value)
  const shown = Number.isFinite(numeric) && ['temp', 'temperature'].includes(device.kind) ? numeric.toFixed(2) : String(value)
  return `${shown}${device.unit ? ` ${device.unit}` : ''}`
}

function brightness255(device) {
  const value = Number(device.brightness)
  if (Number.isFinite(value)) return Math.max(0, Math.min(255, Math.round(value)))
  return ['ON', '1', 'TRUE'].includes(String(device.state).trim().toUpperCase()) ? 255 : 0
}

function rgbChannels(devices) {
  const groups = new Map()
  devices.forEach((device) => {
    if (device.kind !== 'light' || !device.rgb_group) return
    const channel = String(device.rgb_channel || '').toLowerCase()
    if (!['red', 'green', 'blue'].includes(channel)) return
    if (!groups.has(device.rgb_group)) groups.set(device.rgb_group, {})
    groups.get(device.rgb_group)[channel] = device
  })
  return groups
}

function rgbHex(channels) {
  return `#${['red', 'green', 'blue'].map((name) => brightness255(channels[name]).toString(16).padStart(2, '0')).join('')}`.toUpperCase()
}

function renderRgbCard(group, channels) {
  const color = rgbHex(channels)
  const master = Math.max(...Object.values(channels).map(brightness255))
  const representative = channels.red
  return `<article class="rgb-device ${master ? 'rgb-device-on' : ''}" style="--rgb-color:${color}" data-rgb-group="${esc(group)}">
    <span class="device-glyph mdi-mask" style="${mdiStyle(representative.icon, 'palette')}"></span>
    <div><strong>${esc(group)}</strong><small>${esc(representative.room)} · RGB</small></div>
    <em><i class="rgb-swatch"></i>${color}</em>
    <div class="rgb-controls"><input type="color" value="${color}" data-rgb-color aria-label="Colore ${esc(group)}"><input type="range" min="1" max="255" value="${Math.max(1, master)}" data-rgb-brightness aria-label="Luminosità ${esc(group)}"><output>${Math.round(master / 255 * 100)}%</output></div>
    <div class="device-actions"><button data-rgb-action="on">ON</button><button data-rgb-action="off">OFF</button></div>
  </article>`
}

function renderDeviceList(devices) {
  const groups = rgbChannels(devices)
  const completeGroups = new Map([...groups].filter(([, channels]) => channels.red && channels.green && channels.blue))
  const groupedIds = new Set([...completeGroups.values()].flatMap((channels) => Object.values(channels).map((device) => String(device.id))))
  const cards = devices.filter((device) => !groupedIds.has(String(device.id))).map((device) => `
    <article class="${deviceVisualClass(device)}" style="${deviceCardStyle(device)}" data-device-id="${esc(device.id)}"><span class="device-glyph mdi-mask" style="${mdiStyle(device.icon, device.kind === 'cover' ? 'blinds-horizontal' : device.kind === 'lock' ? 'lock' : 'lightbulb')}"></span><div><strong>${esc(device.name)}</strong><small>${esc(device.room)}</small></div><em>${esc(stateLabel(device))}</em>${deviceActions(device)}</article>
  `)
  completeGroups.forEach((channels, group) => cards.push(renderRgbCard(group, channels)))
  $('#detail-kicker').textContent = `${cards.length} dispositivi`
  $('#device-list').innerHTML = cards.join('') || '<p class="empty-state">Nessun dispositivo disponibile</p>'
}

function deviceCardStyle(device) {
  if (device.kind !== 'cover') return ''
  const state = String(device.state).trim().toUpperCase()
  const hasPosition = device.position !== null && device.position !== undefined && device.position !== '' && Number.isFinite(Number(device.position))
  const percent = Math.max(0, Math.min(100, hasPosition ? Number(device.position) : ['OPEN', 'OPENING'].includes(state) ? 100 : 0))
  const mix = percent / 100
  const from = [170, 181, 184]
  const to = [97, 216, 242]
  const color = from.map((channel, index) => Math.round(channel + (to[index] - channel) * mix))
  return `--cover-color:rgb(${color.join(',')});--cover-glow:${(2 + 5 * mix).toFixed(1)}px;--cover-alpha:${(.12 + .3 * mix).toFixed(2)}`
}

function deviceVisualClass(device) {
  const identity = `${device.name || ''} ${device.icon || ''} ${device.category || ''}`.toLocaleLowerCase('it')
  const isLight = device.kind === 'light' || (device.kind === 'switch' && /(luc[ei]|lamp|applique|light|bulb|sconce|chandelier)/.test(identity))
  const state = String(device.state).trim().toUpperCase()
  if (!state || ['UNKNOWN', 'UNAVAILABLE', '?'].includes(state)) return ''
  const active = ['ON', 'OPEN', 'OPENING', 'UNLOCKED', '1', 'TRUE'].includes(state)
  if (isLight) return active ? 'device-light-on' : ''
  if (device.kind === 'switch') return active ? 'device-switch-on' : 'device-switch-off'
  if (device.kind === 'cover') return ['OPEN', 'OPENING'].includes(state) || Number(device.position) > 0 ? 'device-cover-open' : 'device-cover-closed'
  if (device.kind === 'lock') return ['UNLOCKED', 'OPEN', 'OPENING'].includes(state) ? 'device-lock-open' : 'device-lock-closed'
  return ''
}

function deviceActions(device) {
  if (['light', 'switch'].includes(device.kind)) {
    const dimmer = device.kind === 'light' && device.dimmable ? `<label class="dimmer-control"><input type="range" min="1" max="255" value="${Math.max(1, brightness255(device))}" data-brightness><output>${Math.round(brightness255(device) / 255 * 100)}%</output></label>` : ''
    return `${dimmer}<div class="device-actions"><button data-action="on">ON</button><button data-action="off">OFF</button></div>`
  }
  if (device.kind === 'cover') return '<div class="device-actions"><button data-action="open">SU</button><button data-action="stop">STOP</button><button data-action="close">GIÙ</button></div>'
  if (device.kind === 'lock') return '<div class="device-actions"><button data-action="unlock">SBLOCCA</button><button data-action="lock">BLOCCA</button></div>'
  return ''
}

async function postDeviceCommand(deviceId, action, value) {
  const response = await fetch(apiUrl(`api/devices/${encodeURIComponent(deviceId)}/command`), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, value })
  })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
}

async function sendDeviceCommand(deviceId, action, button, value) {
  if (button) button.disabled = true
  try {
    await postDeviceCommand(deviceId, action, value)
    await new Promise((resolve) => setTimeout(resolve, 400))
    await refresh()
  } catch (error) {
    fail(error)
  } finally {
    if (button) button.disabled = false
  }
}

async function sendRgbCommand(group, action, value, control) {
  const channels = rgbChannels(currentDevices).get(group)
  if (!channels || !channels.red || !channels.green || !channels.blue) return
  if (control) control.disabled = true
  try {
    let values
    if (action === 'color') {
      values = { red: parseInt(value.slice(1, 3), 16), green: parseInt(value.slice(3, 5), 16), blue: parseInt(value.slice(5, 7), 16) }
      localStorage.setItem(`eface-rgb:${group}`, JSON.stringify(values))
    } else if (action === 'brightness') {
      let base = { red: brightness255(channels.red), green: brightness255(channels.green), blue: brightness255(channels.blue) }
      if (!Math.max(...Object.values(base))) base = JSON.parse(localStorage.getItem(`eface-rgb:${group}`) || '{"red":255,"green":255,"blue":255}')
      const peak = Math.max(1, ...Object.values(base))
      values = Object.fromEntries(Object.entries(base).map(([name, channel]) => [name, Math.round(channel * Number(value) / peak)]))
    } else if (action === 'on') {
      values = JSON.parse(localStorage.getItem(`eface-rgb:${group}`) || '{"red":255,"green":255,"blue":255}')
    }
    await Promise.all(Object.entries(channels).map(([name, device]) => {
      const level = values?.[name] || 0
      return postDeviceCommand(device.id, action === 'off' || !level ? 'off' : 'brightness', level || undefined)
    }))
    await new Promise((resolve) => setTimeout(resolve, 300))
    await refresh()
  } catch (error) { fail(error) } finally { if (control) control.disabled = false }
}

function openDevices(title, devices) {
  activeDetailIds = new Set(devices.map((device) => String(device.id)))
  $('#detail-title').textContent = title
  renderDeviceList(devices)
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openScenariosPage() {
  activeDetailIds = null
  $('#detail-title').textContent = 'Scenari'
  $('#detail-kicker').textContent = 'Automazioni e-HDL'
  $('#device-list').hidden = true
  $('#scenario-panel').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  loadScenarios()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadScenarios() {
  try {
    const response = await fetch(apiUrl('api/scenarios'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    currentScenarios = (await response.json()).items || []
    renderScenarios()
  } catch (error) { fail(error) }
}

function renderScenarios() {
  $('#scenario-list').innerHTML = currentScenarios.map((scenario) => {
    const active = String(scenario.state).toUpperCase() === 'ON'
    const controls = []
    if (scenario.run_enabled) controls.push(`<button data-scenario-action="${scenario.running ? 'stop' : 'run'}">${scenario.running ? 'STOP' : 'ESEGUI'}</button>`)
    if (scenario.onoff_enabled) controls.push(`<button data-scenario-action="${active ? 'off' : 'on'}">${active ? 'SPEGNI' : 'ACCENDI'}</button>`)
    return `<article class="scenario-card ${active ? 'active' : ''}" data-scenario-id="${esc(scenario.id)}"><span class="scenario-glyph mdi-mask" style="${mdiStyle('mdi:creation', 'creation')}"></span><div><strong>${esc(scenario.name)}</strong><small>${scenario.lights} luci · ${scenario.covers} cover</small></div><div class="scenario-actions">${controls.join('')}</div></article>`
  }).join('') || '<span class="empty-state">Nessuno scenario configurato in e-HDL</span>'
}

async function sendScenarioCommand(id, action, button) {
  button.disabled = true
  try {
    const response = await fetch(apiUrl(`api/scenarios/${encodeURIComponent(id)}/command`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) })
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
    await loadScenarios()
  } catch (error) { fail(error) } finally { button.disabled = false }
}

function showHome() {
  activeDetailIds = null
  $('#detail-view').hidden = true
  $('#home-view').hidden = false
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  document.querySelectorAll('.rail button').forEach((item) => item.classList.remove('active'))
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

function realtimeUrl() {
  const url = new URL(apiUrl('api/realtime'))
  url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

function connectRealtime() {
  if (realtimeSocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(realtimeSocket.readyState)) return
  realtimeSocket = new WebSocket(realtimeUrl())
  realtimeSocket.onmessage = (message) => {
    try { applyRealtimeEvent(JSON.parse(message.data)) } catch (_) {}
  }
  realtimeSocket.onclose = () => {
    realtimeSocket = null
    clearTimeout(realtimeRetry)
    realtimeRetry = setTimeout(connectRealtime, 1500)
  }
  realtimeSocket.onerror = () => realtimeSocket.close()
}

function applyRealtimeEvent(event) {
  if (event.type === 'devices_changed') {
    clearTimeout(snapshotRefreshTimer)
    snapshotRefreshTimer = setTimeout(refresh, 500)
    return
  }
  const data = event.data || {}
  if (event.type === 'light_scenario_state' || event.type === 'light_scenario_running') {
    const scenario = currentScenarios.find((item) => item.id === String(data.id || ''))
    if (scenario) {
      if (data.state !== undefined) scenario.state = data.state
      if (data.running !== undefined) scenario.running = data.running
      renderScenarios()
    }
    return
  }
  const key = data.entity_id || [data.subnet_id, data.device_id, data.channel].join('.')
  const device = currentDevices.find((item) => item.state_key === key)
  if (!device) return
  if (data.state !== undefined) device.state = data.state
  if (data.value !== undefined) device.state = data.value
  if (data.position !== undefined) device.position = data.position
  if (data.brightness !== undefined) device.brightness = data.brightness
  if (!detailRenderQueued && activeDetailIds && !$('#detail-view').hidden) {
    detailRenderQueued = true
    requestAnimationFrame(() => {
      renderDeviceList(currentDevices.filter((item) => activeDetailIds.has(String(item.id))))
      detailRenderQueued = false
    })
  }
}

document.querySelectorAll('.rail button').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('.rail button').forEach((item) => item.classList.remove('active'))
  button.classList.add('active')
  document.querySelector('main').classList.remove('app-view')
  requestAnimationFrame(() => document.querySelector('main').classList.add('app-view'))
  if (button.dataset.view === 'watch') openDevices('Guarda', currentDevices.filter((device) => ['camera', 'doorbell'].includes(device.kind)))
  if (button.dataset.view === 'listen') openDevices('Ascolta', currentDevices.filter((device) => ['media_player', 'media'].includes(device.kind)))
  if (button.dataset.view === 'lights') openDevices('Luci', currentDevices.filter((device) => device.kind === 'light'))
  if (button.dataset.view === 'extra') openDevices('Extra', currentDevices.filter((device) => device.kind === 'switch'))
  if (button.dataset.view === 'scenarios') openScenariosPage()
  if (button.dataset.view === 'covers') openDevices('Oscuranti', currentDevices.filter((device) => device.kind === 'cover'))
  if (button.dataset.view === 'comfort') openDevices('Comfort', currentDevices.filter((device) => ['climate', 'temp', 'temperature', 'humidity', 'air', 'air_quality'].includes(device.kind)))
  if (button.dataset.view === 'security') openDevices('Sicurezza', currentDevices.filter((device) => device.kind === 'lock'))
}))
$('#widgets').addEventListener('click', (event) => {
  const button = event.target.closest('[data-kind]')
  if (!button) return
  const map = { lights: ['light'], extra: ['switch'], covers: ['cover'], locks: ['lock'], sensors: ['temp', 'temperature', 'humidity', 'illuminance', 'pir', 'ultrasonic', 'dry_contact', 'air', 'air_quality', 'gas_percent'] }
  const kinds = map[button.dataset.kind] || []
  openDevices(button.textContent.trim(), currentDevices.filter((device) => kinds.includes(device.kind)))
})
$('#rooms').addEventListener('click', (event) => {
  const button = event.target.closest('[data-room]')
  if (!button) return
  openDevices(button.dataset.room, currentDevices.filter((device) => device.room.toLocaleLowerCase('it') === button.dataset.room.toLocaleLowerCase('it')))
})
$('#detail-back').addEventListener('click', showHome)
$('#scenario-refresh').addEventListener('click', loadScenarios)
$('#scenario-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-scenario-action]')
  const card = event.target.closest('[data-scenario-id]')
  if (button && card) sendScenarioCommand(card.dataset.scenarioId, button.dataset.scenarioAction, button)
})
$('#device-list').addEventListener('click', (event) => {
  const rgbButton = event.target.closest('[data-rgb-action]')
  const rgbCard = event.target.closest('[data-rgb-group]')
  if (rgbButton && rgbCard) return sendRgbCommand(rgbCard.dataset.rgbGroup, rgbButton.dataset.rgbAction, null, rgbButton)
  const button = event.target.closest('[data-action]')
  const card = event.target.closest('[data-device-id]')
  if (button && card) sendDeviceCommand(card.dataset.deviceId, button.dataset.action, button)
})
$('#device-list').addEventListener('input', (event) => {
  if (event.target.matches('[data-brightness],[data-rgb-brightness]')) event.target.nextElementSibling.textContent = `${Math.round(Number(event.target.value) / 255 * 100)}%`
})
$('#device-list').addEventListener('change', (event) => {
  const card = event.target.closest('[data-device-id],[data-rgb-group]')
  if (event.target.matches('[data-brightness]')) sendDeviceCommand(card.dataset.deviceId, 'brightness', event.target, event.target.value)
  if (event.target.matches('[data-rgb-brightness]')) sendRgbCommand(card.dataset.rgbGroup, 'brightness', event.target.value, event.target)
  if (event.target.matches('[data-rgb-color]')) sendRgbCommand(card.dataset.rgbGroup, 'color', event.target.value, event.target)
})
$('.home-title').addEventListener('click', showHome)
$('#show-all-devices').addEventListener('click', () => openDevices('Tutti i dispositivi', currentDevices))
$('#volume').addEventListener('input', (event) => { $('#volume-value').textContent = `${event.target.value}%` })
document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); connectRealtime() } })
tick()
setInterval(tick, 30000)
setInterval(() => {
  if (!realtimeSocket || realtimeSocket.readyState !== WebSocket.OPEN) refresh()
}, 30000)
refresh()
connectRealtime()
