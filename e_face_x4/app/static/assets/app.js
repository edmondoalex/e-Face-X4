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
let activeRgbGroup = null
let lightFilterActive = false
let lightFilterRoom = ''
let devicePointerGesture = null
let avRoom = ''
let currentMediaGroups = []
let activeMediaPlayer = null
let selectedMediaId = ''

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
  currentMediaGroups = providers.find((provider) => provider.id === 'evoice')?.groups || []
  const navIcons = data.nav_icons || {}
  currentDevices = Array.isArray(dashboard.devices) ? dashboard.devices : []
  updateNavigationStates()
  if (activeDetailIds && !$('#detail-view').hidden) {
    renderActiveDeviceList()
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
  if (device.kind === 'media_player') {
    if (device.connection_status === 'offline' || device.availability !== 'available') return 'Non disponibile'
    return String(device.state || 'unknown').toLocaleUpperCase('it')
  }
  if (device.kind === 'climate') {
    const current = Number(device.temperature)
    const target = Number(device.target_temperature)
    return `${Number.isFinite(current) ? current.toFixed(1) + '°' : '--'} → ${Number.isFinite(target) ? target.toFixed(1) + '°' : '--'}`
  }
  const value = device.state
  if (value === null || value === undefined || value === '') return 'Stato non disponibile'
  if (typeof value === 'boolean') return value ? 'Attivo' : 'Disattivo'
  const numeric = Number(value)
  const shown = Number.isFinite(numeric) && ['temp', 'temperature'].includes(device.kind) ? numeric.toFixed(2) : String(value)
  return `${shown}${device.unit ? ` ${device.unit}` : ''}`
}

function stateIsActive(device) {
  const state = String(device.state ?? '').trim().toUpperCase()
  return ['ON','1','TRUE','OPEN','OPENING','UNLOCKED','PLAYING','HEATING','COOLING'].includes(state)
}

function updateNavigationStates() {
  const setState = (view, className, active) => {
    const button = document.querySelector(`.rail [data-view="${view}"]`)
    if (!button) return
    button.classList.remove('status-yellow','status-red','status-cyan','status-green')
    if (active) button.classList.add(className)
  }
  setState('lights', 'status-yellow', currentDevices.some((device) => device.kind === 'light' && lightIsOn(device)))
  setState('extra', 'status-red', currentDevices.some((device) => device.kind === 'switch' && stateIsActive(device)))
  setState('covers', 'status-cyan', currentDevices.some((device) => device.kind === 'cover' && (stateIsActive(device) || Number(device.position) > 0)))
  setState('security', 'status-red', currentDevices.some((device) => device.kind === 'lock' && ['OPEN','OPENING','UNLOCKED'].includes(String(device.state ?? '').trim().toUpperCase())))
  setState('listen', 'status-green', currentDevices.some((device) => ['media','media_player'].includes(device.kind) && stateIsActive(device)))
  setState('comfort', 'status-cyan', currentDevices.some((device) => device.kind === 'climate' && stateIsActive(device)))
  setState('scenarios', 'status-yellow', currentScenarios.some((scenario) => scenario.running || ['ON','1','TRUE'].includes(String(scenario.state ?? '').toUpperCase())))
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
  return `<article class="rgb-device ${master ? 'rgb-device-on' : ''}" style="--rgb-color:${color}" data-rgb-group="${esc(group)}" data-rgb-toggle tabindex="0">
    <button class="rgb-palette-open" data-rgb-open aria-label="Apri tavola colori"><span class="device-glyph mdi-mask" style="${mdiStyle(representative.icon, 'palette')}"></span></button>
    <div><strong>${esc(group)}</strong><small>${esc(representative.room)} · RGB</small></div>
    <em><i class="rgb-swatch"></i>${master ? 'ON' : 'OFF'}</em>
    <div class="rgb-card-master"><input type="range" min="1" max="255" value="${Math.max(1, master)}" data-rgb-brightness aria-label="Luminosità ${esc(group)}"><output>${Math.round(master / 255 * 100)}%</output></div>
  </article>`
}

const rgbPalette = ['#ff0000','#ff7a00','#ffd500','#42ed00','#00df70','#00dce5','#0874e8','#7137ed','#a800ff','#ed00bd','#ed3d78','#ffffff','#ffb766','#70edbf','#8ab6ff','#292929']

function openRgbDialog(group) {
  activeRgbGroup = group
  renderRgbDialog()
  $('#rgb-dialog').showModal()
}

function renderRgbDialog() {
  const channels = rgbChannels(currentDevices).get(activeRgbGroup)
  if (!channels?.red || !channels?.green || !channels?.blue) return
  const values = Object.fromEntries(Object.entries(channels).map(([name, device]) => [name, brightness255(device)]))
  const color = rgbHex(channels)
  const master = Math.max(...Object.values(values))
  $('#rgb-title').textContent = activeRgbGroup
  $('#rgb-master').value = Math.max(1, master)
  $('#rgb-master-value').textContent = `${Math.round(master / 255 * 100)}%`
  $('#rgb-preview').style.setProperty('--rgb-color', color)
  $('#rgb-palette').innerHTML = rgbPalette.map((item) => `<button style="--swatch:${item}" data-palette="${item}" aria-label="Colore ${item}"></button>`).join('')
  const labels = { red: 'Rosso', green: 'Verde', blue: 'Blu' }
  $('#rgb-channel-controls').innerHTML = ['red','green','blue'].map((name) => `<label class="rgb-channel ${name}"><span><i></i>${labels[name]}</span><output>${values[name]}</output><input type="range" min="0" max="255" value="${values[name]}" data-rgb-channel="${name}"></label>`).join('')
}

function wheelColor(event) {
  const rect = $('#rgb-wheel').getBoundingClientRect()
  const x = event.clientX - rect.left - rect.width / 2
  const y = event.clientY - rect.top - rect.height / 2
  const saturation = Math.min(1, Math.hypot(x, y) / (rect.width / 2))
  const hue = (Math.atan2(y, x) * 180 / Math.PI + 450) % 360
  const f = (n) => { const k = (n + hue / 60) % 6; return Math.round(255 * (1 - saturation * Math.max(0, Math.min(k, 4 - k, 1)))) }
  return `#${[f(5), f(3), f(1)].map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

function renderDeviceList(devices) {
  if (devices.length && devices.every((device) => device.kind === 'media_player')) {
    renderMediaExperience(devices)
    return
  }
  const groups = rgbChannels(devices)
  const completeGroups = new Map([...groups].filter(([, channels]) => channels.red && channels.green && channels.blue))
  const groupedIds = new Set([...completeGroups.values()].flatMap((channels) => Object.values(channels).map((device) => String(device.id))))
  const cards = devices.filter((device) => !groupedIds.has(String(device.id))).map((device) => `
    <article class="${deviceVisualClass(device)} ${device.kind === 'media_player' ? 'media-player-card' : ''}" style="${deviceCardStyle(device)}" data-device-id="${esc(device.id)}" ${['light','switch'].includes(device.kind) ? 'data-device-toggle tabindex="0"' : ''}>${mediaArtwork(device)}<span class="device-glyph mdi-mask" style="${mdiStyle(device.icon, device.kind === 'cover' ? 'blinds-horizontal' : device.kind === 'lock' ? 'lock' : device.kind === 'media_player' ? 'speaker' : 'lightbulb')}"></span><div><strong>${esc(device.name)}</strong><small>${esc(device.room)}</small>${device.kind === 'media_player' ? `<span class="media-track">${esc(device.title || 'Nessuna riproduzione')}</span><span class="media-artist">${esc([device.artist, device.album].filter(Boolean).join(' · '))}</span>` : ''}</div><em>${esc(stateLabel(device))}</em>${deviceActions(device)}</article>
  `)
  completeGroups.forEach((channels, group) => cards.push(renderRgbCard(group, channels)))
  $('#device-list').innerHTML = cards.join('') || '<p class="empty-state">Nessun dispositivo disponibile</p>'
}

function renderMediaExperience(devices) {
  let selected = devices.find((device) => String(device.id) === selectedMediaId)
  selected = selected || devices.find((device) => String(device.state).toLowerCase() === 'playing') || devices[0]
  selectedMediaId = String(selected.id)
  const players = devices.map((device) => `<button class="media-service-tile ${device.id === selected.id ? 'active' : ''}" data-media-select="${esc(device.id)}"><span class="mdi-mask" style="${mdiStyle(device.icon, 'speaker')}"></span><b>${esc(device.name)}</b><small>${esc(device.room)}</small></button>`).join('')
  const sources = (selected.source_list || []).map((source) => `<button class="media-service-tile ${source === selected.source ? 'active' : ''}" data-device-id="${esc(selected.id)}" data-media-source="${esc(source)}"><span class="mdi-mask" style="${mdiStyle('mdi:play-box', 'play-box')}"></span><b>${esc(source)}</b><small>Sorgente</small></button>`).join('')
  $('#device-list').innerHTML = `<article class="media-session ${deviceVisualClass(selected)}" data-device-id="${esc(selected.id)}">${mediaArtwork(selected)}<span class="device-glyph mdi-mask" style="${mdiStyle(selected.icon, 'speaker')}"></span><div class="media-session-info"><strong>${esc(selected.name)}</strong><small>${esc(selected.room)}</small><span class="media-track">${esc(selected.title || 'Nessuna riproduzione')}</span><span class="media-artist">${esc([selected.artist, selected.album].filter(Boolean).join(' · '))}</span></div><em>${esc(stateLabel(selected))}</em>${deviceActions(selected)}</article><div class="media-library"><h3>Dispositivi e servizi</h3><div class="media-service-grid">${players}${sources}</div></div>`
}

function mediaArtwork(device) {
  if (device.kind !== 'media_player') return ''
  if (!device.content_fingerprint) return '<span class="media-artwork missing" aria-hidden="true"></span>'
  const source = apiUrl(`api/media/${encodeURIComponent(device.registry_id)}/artwork?fingerprint=${encodeURIComponent(device.content_fingerprint)}`)
  return `<img class="media-artwork" src="${esc(source)}" alt="" loading="lazy" onerror="this.classList.add('missing');this.removeAttribute('src')">`
}

function lightIsOn(device) {
  const state = String(device.state ?? '').trim().toUpperCase()
  if (['ON','1','TRUE'].includes(state)) return true
  if (['OFF','0','FALSE'].includes(state)) return false
  return Number(device.brightness) > 0
}

function renderActiveDeviceList() {
  let devices = currentDevices.filter((device) => activeDetailIds?.has(String(device.id)))
  if (!$('#light-filters').hidden) {
    if (lightFilterRoom) devices = devices.filter((device) => device.room === lightFilterRoom)
    if (lightFilterActive) devices = devices.filter(lightIsOn)
  }
  if (!$('#av-filters').hidden && avRoom) devices = devices.filter((device) => device.room === avRoom)
  renderDeviceList(devices)
}

function configureAvRooms(devices) {
  const rooms = [...new Set(devices.map((device) => device.room).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  if (avRoom && !rooms.includes(avRoom)) avRoom = ''
  $('#av-room-label').textContent = avRoom || 'Tutte le stanze'
  $('#av-room-menu').innerHTML = `<button data-av-room="" class="${avRoom ? '' : 'active'}">Tutte le stanze</button>${rooms.map((room) => `<button data-av-room="${esc(room)}" class="${room === avRoom ? 'active' : ''}">${esc(room)}</button>`).join('')}`
}

function configureLightFilters(devices) {
  const rooms = [...new Set(devices.map((device) => device.room).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  $('#light-room-menu').innerHTML = rooms.map((room) => `<button data-light-room="${esc(room)}" class="${room === lightFilterRoom ? 'active' : ''}">${esc(room)}</button>`).join('')
  $('#light-room-toggle').classList.toggle('active', Boolean(lightFilterRoom))
  $('#light-all-filter').classList.toggle('active', !lightFilterRoom)
}

function deviceCardStyle(device) {
  const state = String(device.state).trim().toUpperCase()
  if (device.kind === 'light' && device.dimmable) {
    const active = ['ON', '1', 'TRUE'].includes(state)
    const mix = active ? brightness255(device) / 255 : 0
    const from = [151, 160, 163]
    const to = [255, 211, 78]
    const color = from.map((channel, index) => Math.round(channel + (to[index] - channel) * mix))
    return `--light-color:rgb(${color.join(',')});--light-glow:${(1 + 11 * mix).toFixed(1)}px;--light-alpha:${(.08 + .72 * mix).toFixed(2)}`
  }
  if (device.kind !== 'cover') return ''
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
  if (device.kind === 'climate') return state === 'HEATING' ? 'device-climate-heat' : state === 'COOLING' ? 'device-climate-cool' : 'device-climate-off'
  if (device.kind === 'media_player') return state === 'PLAYING' ? 'device-media-playing' : ''
  return ''
}

function deviceActions(device) {
  if (['light', 'switch'].includes(device.kind)) {
    const active = ['ON','1','TRUE'].includes(String(device.state).trim().toUpperCase())
    const level = active ? brightness255(device) : 0
    const percent = Math.round(level / 255 * 100)
    const dimmer = device.kind === 'light' && device.dimmable ? `<label class="dimmer-control ${active ? 'active' : ''}" style="--level:${percent}%"><input type="range" min="0" max="255" value="${level}" data-brightness><output>${percent}%</output></label>` : ''
    return dimmer
  }
  if (device.kind === 'cover') return '<div class="device-actions"><button data-action="open">SU</button><button data-action="stop">STOP</button><button data-action="close">GIÙ</button></div>'
  if (device.kind === 'lock') return '<div class="device-actions"><button data-action="unlock">SBLOCCA</button><button data-action="lock">BLOCCA</button></div>'
  if (device.kind === 'climate') {
    const target = Number(device.target_temperature)
    const value = Number.isFinite(target) ? target : 20
    return `<div class="climate-summary"><span>UR ${device.humidity ?? '--'}%</span><span>${device.season === 'SUM' ? 'ESTATE' : 'INVERNO'}</span><span>PWM ${device.pwm ?? 0}%</span></div><div class="device-actions"><button data-climate-target="${(value - .5).toFixed(1)}">−</button><strong>${value.toFixed(1)}°</strong><button data-climate-target="${(value + .5).toFixed(1)}">＋</button></div>`
  }
  if (device.kind === 'media_player') {
    const caps = device.capabilities || {}
    const disabled = device.connection_status === 'offline' || device.availability !== 'available'
    const button = (operation, icon, label, enabled = true) => enabled ? `<button data-media-action="${operation}" aria-label="${label}" ${disabled ? 'disabled' : ''}>${icon}</button>` : ''
    const controls = [button('media_previous', '◀', 'Precedente', caps.previous), String(device.state).toLowerCase() === 'playing' ? button('media_pause', 'Ⅱ', 'Pausa', caps.pause) : button('media_play', '▶', 'Riproduci', caps.play), button('media_stop', '■', 'Stop', caps.stop), button('media_next', '▶|', 'Successivo', caps.next), device.muted ? button('volume_unmute', '🔇', 'Riattiva audio', caps.mute) : button('volume_mute', '🔊', 'Disattiva audio', caps.mute), button('media_zones', '▣+', 'Aggiungi stanze', caps.grouping)].join('')
    const volume = caps.set_volume ? `<label class="media-volume"><input type="range" min="0" max="100" value="${Number(device.volume) || 0}" data-media-volume ${disabled ? 'disabled' : ''}><output>${Number(device.volume) || 0}%</output></label>` : ''
    const sources = caps.select_source && Array.isArray(device.source_list) && device.source_list.length ? `<div class="media-sources">${device.source_list.map((source) => `<button data-media-source="${esc(source)}" class="${source === device.source ? 'active' : ''}" ${disabled ? 'disabled' : ''}><span class="mdi-mask" style="${mdiStyle('mdi:play-box', 'play-box')}"></span><b>${esc(source)}</b></button>`).join('')}</div>` : ''
    return `<div class="media-controls">${controls}</div>${volume}${sources}`
  }
  return ''
}

async function postDeviceCommand(deviceId, action, value, resourceRevision = null) {
  const response = await fetch(apiUrl(`api/devices/${encodeURIComponent(deviceId)}/command`), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, value, resource_revision: resourceRevision })
  })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
}

function openMediaZones(device) {
  activeMediaPlayer = device
  renderMediaZones()
  $('#media-zones-dialog').showModal()
}

function mediaGroupFor(device) {
  const groupId = device?.group?.group_id
  return currentMediaGroups.find((group) => group.group_id === groupId) || device?.group || null
}

function renderMediaZones() {
  const selected = activeMediaPlayer
  if (!selected) return
  const group = mediaGroupFor(selected)
  const members = new Set(group?.member_registry_ids || [selected.registry_id])
  const players = currentDevices.filter((item) => item.kind === 'media_player')
  const volumes = players.filter((item) => members.has(item.registry_id) && Number.isFinite(Number(item.volume))).map((item) => Number(item.volume))
  const average = volumes.length ? Math.round(volumes.reduce((sum, value) => sum + value, 0) / volumes.length) : 0
  $('#zones-master').innerHTML = group?.group_id ? `<label><span class="mdi-mask" style="${mdiStyle(selected.muted ? 'mdi:volume-off' : 'mdi:volume-high', 'volume-high')}"></span><input type="range" min="0" max="100" value="${average}" data-group-volume ${group.completeness !== 'complete' ? 'disabled' : ''}><output>${average}%</output></label>${group.completeness !== 'complete' ? `<small>Gruppo ${esc(group.completeness)}</small>` : ''}` : '<small>Seleziona una o più stanze per creare la sessione.</small>'
  $('#media-zones-list').innerHTML = players.map((player) => {
    const checked = members.has(player.registry_id)
    const unavailable = player.connection_status === 'offline' || player.availability !== 'available'
    return `<label class="media-zone ${checked ? 'active' : ''} ${unavailable ? 'unavailable' : ''}"><span><b>${esc(player.room)}</b><small>${esc(player.name)}</small></span><em>${Number.isFinite(Number(player.volume)) ? `${Number(player.volume)}%` : '—'}</em><input type="checkbox" value="${esc(player.registry_id)}" ${checked ? 'checked' : ''} ${player.registry_id === selected.registry_id || unavailable ? 'disabled' : ''}><i></i></label>`
  }).join('')
}

async function saveMediaZones(button) {
  if (!activeMediaPlayer) return
  button.disabled = true
  const group = mediaGroupFor(activeMediaPlayer)
  const current = new Set(group?.member_registry_ids || [activeMediaPlayer.registry_id])
  const desired = new Set([...document.querySelectorAll('#media-zones-list input:checked')].map((input) => input.value))
  const additions = [...desired].filter((id) => !current.has(id))
  const removals = [...current].filter((id) => !desired.has(id) && id !== activeMediaPlayer.registry_id)
  try {
    for (const registryId of removals) {
      const player = currentDevices.find((item) => item.registry_id === registryId)
      await postDeviceCommand(`media:${registryId}`, 'media_unjoin', null, player?.resource_revision)
    }
    if (additions.length) await postDeviceCommand(activeMediaPlayer.id, 'media_join', additions, activeMediaPlayer.resource_revision)
    $('#media-zones-dialog').close()
    await refresh()
  } catch (error) { fail(error) } finally { button.disabled = false }
}

async function setMediaGroupVolume(input) {
  const group = mediaGroupFor(activeMediaPlayer)
  if (!group?.group_id) return
  input.disabled = true
  try {
    const response = await fetch(apiUrl(`api/media/groups/${encodeURIComponent(group.group_id)}/command`), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'set_group_volume', value:Number(input.value), resource_revision:group.resource_revision})})
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
    await refresh()
  } catch (error) { fail(error) } finally { input.disabled = false }
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

function openDevices(title, devices, options = {}) {
  activeDetailIds = new Set(devices.map((device) => String(device.id)))
  $('#detail-title').textContent = title
  $('#light-filters').hidden = !options.lights
  $('#av-filters').hidden = !options.av
  if (options.lights) configureLightFilters(devices)
  if (options.av) configureAvRooms(devices)
  renderActiveDeviceList()
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  $('#detail-view').classList.toggle('av-view', Boolean(options.av))
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openScenariosPage() {
  activeDetailIds = null
  $('#detail-title').textContent = 'Scenari'
  $('#light-filters').hidden = true
  $('#av-filters').hidden = true
  $('#device-list').hidden = true
  $('#scenario-panel').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  $('#detail-view').classList.remove('av-view')
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
  updateNavigationStates()
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
  $('#detail-view').classList.remove('av-view')
  $('#home-view').hidden = false
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  $('#light-filters').hidden = true
  $('#av-filters').hidden = true
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
  if (event.type === 'devices_changed' || event.type === 'thermostats_changed' || event.type === 'media_changed') {
    clearTimeout(snapshotRefreshTimer)
    snapshotRefreshTimer = setTimeout(refresh, 500)
    return
  }
  const data = event.data || {}
  if (event.type === 'media_state') {
    const device = currentDevices.find((item) => item.kind === 'media_player' && item.entity_id === data.entity_id)
    if (!device) {
      clearTimeout(snapshotRefreshTimer)
      snapshotRefreshTimer = setTimeout(refresh, 500)
      return
    }
    let changed = false
    for (const field of ['state','title','artist','album','volume','muted','source']) {
      if (data[field] !== undefined && data[field] !== device[field]) {
        device[field] = data[field]
        changed = true
      }
    }
    if (!changed) return
    updateNavigationStates()
    if (activeDetailIds && !$('#detail-view').hidden) requestAnimationFrame(renderActiveDeviceList)
    return
  }
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
  updateNavigationStates()
  if (activeRgbGroup && $('#rgb-dialog').open && device.rgb_group === activeRgbGroup) renderRgbDialog()
  if (!detailRenderQueued && activeDetailIds && !$('#detail-view').hidden) {
    detailRenderQueued = true
    requestAnimationFrame(() => {
      renderActiveDeviceList()
      detailRenderQueued = false
    })
  }
}

document.querySelectorAll('.rail button').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('.rail button').forEach((item) => item.classList.remove('active'))
  button.classList.add('active')
  document.querySelector('main').classList.remove('app-view')
  requestAnimationFrame(() => document.querySelector('main').classList.add('app-view'))
  if (button.dataset.view === 'watch') openDevices('Guarda', currentDevices.filter((device) => ['camera', 'doorbell'].includes(device.kind) || (device.kind === 'media_player' && device.experiences?.includes('watch'))), { av: true })
  if (button.dataset.view === 'listen') openDevices('Ascolta', currentDevices.filter((device) => ['media_player', 'media'].includes(device.kind) && (!device.experiences?.length || device.experiences.includes('listen'))), { av: true })
  if (button.dataset.view === 'lights') openDevices('Luci', currentDevices.filter((device) => device.kind === 'light'), { lights: true })
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
$('#light-room-toggle').addEventListener('click', (event) => {
  const open = $('#light-room-menu').hidden
  $('#light-room-menu').hidden = !open
  event.currentTarget.setAttribute('aria-expanded', String(open))
})
$('#light-room-menu').addEventListener('click', (event) => {
  const button = event.target.closest('[data-light-room]')
  if (!button) return
  lightFilterRoom = button.dataset.lightRoom
  $('#light-room-toggle').classList.add('active')
  $('#light-all-filter').classList.remove('active')
  $('#light-room-toggle').setAttribute('aria-expanded', 'false')
  $('#light-room-menu').hidden = true
  configureLightFilters(currentDevices.filter((device) => device.kind === 'light'))
  renderActiveDeviceList()
})
$('#light-on-filter').addEventListener('click', (event) => {
  lightFilterActive = !lightFilterActive
  event.currentTarget.setAttribute('aria-pressed', String(lightFilterActive))
  event.currentTarget.classList.toggle('active', lightFilterActive)
  renderActiveDeviceList()
})
$('#light-all-filter').addEventListener('click', () => {
  lightFilterRoom = ''
  lightFilterActive = false
  $('#light-room-toggle').classList.remove('active')
  $('#light-all-filter').classList.add('active')
  $('#light-room-toggle').setAttribute('aria-expanded', 'false')
  $('#light-room-menu').hidden = true
  $('#light-on-filter').classList.remove('active')
  $('#light-on-filter').setAttribute('aria-pressed', 'false')
  renderActiveDeviceList()
})
$('#av-room-toggle').addEventListener('click', (event) => {
  const open = $('#av-room-menu').hidden
  $('#av-room-menu').hidden = !open
  event.currentTarget.setAttribute('aria-expanded', String(open))
})
$('#av-room-menu').addEventListener('click', (event) => {
  const button = event.target.closest('[data-av-room]')
  if (!button) return
  avRoom = button.dataset.avRoom || ''
  $('#av-room-menu').hidden = true
  $('#av-room-toggle').setAttribute('aria-expanded', 'false')
  configureAvRooms(currentDevices.filter((device) => activeDetailIds?.has(String(device.id))))
  renderActiveDeviceList()
})
document.addEventListener('click', (event) => {
  if (!event.target.closest('.room-filter')) {
    $('#light-room-menu').hidden = true
    $('#light-room-toggle').setAttribute('aria-expanded', 'false')
  }
})
$('#scenario-refresh').addEventListener('click', loadScenarios)
$('#scenario-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-scenario-action]')
  const card = event.target.closest('[data-scenario-id]')
  if (button && card) sendScenarioCommand(card.dataset.scenarioId, button.dataset.scenarioAction, button)
})
$('#device-list').addEventListener('click', (event) => {
  if (devicePointerGesture?.moved) { devicePointerGesture = null; return }
  const rgbOpen = event.target.closest('[data-rgb-open]')
  if (rgbOpen) return openRgbDialog(rgbOpen.closest('[data-rgb-group]').dataset.rgbGroup)
  const rgbButton = event.target.closest('[data-rgb-action]')
  const rgbCard = event.target.closest('[data-rgb-group]')
  if (rgbButton && rgbCard) return sendRgbCommand(rgbCard.dataset.rgbGroup, rgbButton.dataset.rgbAction, null, rgbButton)
  const climateButton = event.target.closest('[data-climate-target]')
  const climateCard = event.target.closest('[data-device-id]')
  if (climateButton && climateCard) return sendDeviceCommand(climateCard.dataset.deviceId, 'set_target', climateButton, climateButton.dataset.climateTarget)
  const mediaButton = event.target.closest('[data-media-action]')
  const mediaCard = event.target.closest('[data-device-id]')
  if (mediaButton?.dataset.mediaAction === 'media_zones' && mediaCard) return openMediaZones(currentDevices.find((item) => String(item.id) === mediaCard.dataset.deviceId))
  if (mediaButton && mediaCard) return sendDeviceCommand(mediaCard.dataset.deviceId, mediaButton.dataset.mediaAction, mediaButton)
  const sourceButton = event.target.closest('button[data-media-source]')
  if (sourceButton && mediaCard) return sendDeviceCommand(mediaCard.dataset.deviceId, 'select_source', sourceButton, sourceButton.dataset.mediaSource)
  const playerButton = event.target.closest('[data-media-select]')
  if (playerButton) {
    selectedMediaId = playerButton.dataset.mediaSelect
    renderActiveDeviceList()
    return
  }
  const button = event.target.closest('[data-action]')
  const card = event.target.closest('[data-device-id]')
  if (button && card) sendDeviceCommand(card.dataset.deviceId, button.dataset.action, button)
  if (!button && card?.matches('[data-device-toggle]') && !event.target.closest('input,label')) {
    const device = currentDevices.find((item) => String(item.id) === card.dataset.deviceId)
    const active = ['ON','1','TRUE'].includes(String(device?.state).trim().toUpperCase())
    sendDeviceCommand(card.dataset.deviceId, active ? 'off' : 'on', card)
  }
  const rgbToggle = event.target.closest('[data-rgb-toggle]')
  if (rgbToggle && !event.target.closest('button,input,label')) {
    const channels = rgbChannels(currentDevices).get(rgbToggle.dataset.rgbGroup)
    const active = channels && Math.max(...Object.values(channels).map(brightness255)) > 0
    sendRgbCommand(rgbToggle.dataset.rgbGroup, active ? 'off' : 'on', null, rgbToggle)
  }
  devicePointerGesture = null
})
$('#device-list').addEventListener('pointerdown', (event) => {
  if (!event.target.closest('[data-device-toggle],[data-rgb-toggle]')) return
  devicePointerGesture = { x: event.clientX, y: event.clientY, moved: false }
}, { passive: true })
$('#device-list').addEventListener('pointermove', (event) => {
  if (!devicePointerGesture) return
  if (Math.hypot(event.clientX - devicePointerGesture.x, event.clientY - devicePointerGesture.y) > 7) devicePointerGesture.moved = true
}, { passive: true })
$('#device-list').addEventListener('pointercancel', () => { devicePointerGesture = { moved: true } }, { passive: true })
$('#device-list').addEventListener('keydown', (event) => {
  if (!['Enter',' '].includes(event.key) || !event.target.matches('[data-device-toggle],[data-rgb-toggle]')) return
  event.preventDefault()
  event.target.click()
})
$('#rgb-close').addEventListener('click', () => $('#rgb-dialog').close())
$('#rgb-dialog').addEventListener('click', (event) => { if (event.target === $('#rgb-dialog')) $('#rgb-dialog').close() })
$('#media-zones-close').addEventListener('click', () => $('#media-zones-dialog').close())
$('#media-zones-save').addEventListener('click', (event) => saveMediaZones(event.currentTarget))
$('#media-zones-list').addEventListener('change', (event) => { if (event.target.matches('input[type=checkbox]')) { event.target.closest('.media-zone').classList.toggle('active', event.target.checked) } })
$('#zones-master').addEventListener('input', (event) => { if (event.target.matches('[data-group-volume]')) event.target.nextElementSibling.textContent = `${event.target.value}%` })
$('#zones-master').addEventListener('change', (event) => { if (event.target.matches('[data-group-volume]')) setMediaGroupVolume(event.target) })
$('#rgb-palette').addEventListener('click', (event) => { const button = event.target.closest('[data-palette]'); if (button) sendRgbCommand(activeRgbGroup, 'color', button.dataset.palette, button) })
$('#rgb-master').addEventListener('input', (event) => { $('#rgb-master-value').textContent = `${Math.round(Number(event.target.value) / 255 * 100)}%` })
$('#rgb-master').addEventListener('change', (event) => sendRgbCommand(activeRgbGroup, 'brightness', event.target.value, event.target))
$('#rgb-channel-controls').addEventListener('input', (event) => { if (event.target.matches('[data-rgb-channel]')) event.target.previousElementSibling.textContent = event.target.value })
$('#rgb-channel-controls').addEventListener('change', (event) => {
  if (!event.target.matches('[data-rgb-channel]')) return
  const values = Object.fromEntries([...document.querySelectorAll('[data-rgb-channel]')].map((input) => [input.dataset.rgbChannel, Number(input.value)]))
  const color = `#${['red','green','blue'].map((name) => values[name].toString(16).padStart(2,'0')).join('')}`
  sendRgbCommand(activeRgbGroup, 'color', color, event.target)
})
$('#rgb-dialog').addEventListener('click', (event) => { const button = event.target.closest('[data-popup-rgb-action]'); if (button) sendRgbCommand(activeRgbGroup, button.dataset.popupRgbAction, null, button) })
$('#rgb-wheel').addEventListener('pointerdown', (event) => { event.currentTarget.setPointerCapture(event.pointerId); sendRgbCommand(activeRgbGroup, 'color', wheelColor(event), event.currentTarget) })
$('#device-list').addEventListener('input', (event) => {
  if (event.target.matches('[data-media-volume]')) event.target.nextElementSibling.textContent = `${event.target.value}%`
  if (event.target.matches('[data-brightness],[data-rgb-brightness]')) {
    const percent = Math.round(Number(event.target.value) / 255 * 100)
    event.target.nextElementSibling.textContent = `${percent}%`
    if (event.target.matches('[data-brightness]')) {
      event.target.closest('.dimmer-control').style.setProperty('--level', `${percent}%`)
      event.target.closest('.dimmer-control').classList.toggle('active', Number(event.target.value) > 0)
    }
  }
})
$('#device-list').addEventListener('change', (event) => {
  const card = event.target.closest('[data-device-id],[data-rgb-group]')
  if (event.target.matches('[data-brightness]')) sendDeviceCommand(card.dataset.deviceId, Number(event.target.value) === 0 ? 'off' : 'brightness', event.target, event.target.value)
  if (event.target.matches('[data-rgb-brightness]')) sendRgbCommand(card.dataset.rgbGroup, 'brightness', event.target.value, event.target)
  if (event.target.matches('[data-rgb-color]')) sendRgbCommand(card.dataset.rgbGroup, 'color', event.target.value, event.target)
  if (event.target.matches('[data-media-volume]')) sendDeviceCommand(card.dataset.deviceId, 'set_volume', event.target, event.target.value)
  if (event.target.matches('select[data-media-source]')) sendDeviceCommand(card.dataset.deviceId, 'select_source', event.target, event.target.value)
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
setInterval(refresh, 60000)
refresh()
connectRealtime()
