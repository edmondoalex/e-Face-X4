const $ = (selector) => document.querySelector(selector)
const glyph = { light: '✦', climate: '❄', shield: '⬡', energy: 'ϟ', cover: '▤', sensor: '◌' }
let refreshRunning = false
let currentDevices = []
let appVersion = '0'
let loggedUser = ''
let activeDetailIds = null
let realtimeSocket = null
let realtimeRetry = null
let detailRenderQueued = false
let lastDetailSignature = ''
let snapshotRefreshTimer = null
let currentScenarios = []
let activeRgbGroup = null
let lightFilterActive = false
let lightFilterRoom = ''
let sectionFilterDevices = []
let sectionFilterMode = 'devices'
let devicePointerGesture = null
let recentDrag = null
let recentDragSuppressUntil = 0
let avRoom = ''
let currentMediaGroups = []
let currentMediaExperience = ''
let activeMediaPlayer = null
let activeVideoRemote = null
let selectedMediaId = ''
let activeMediaRoom = ''
let currentBackgrounds = {global:{mode:'preset',preset:'teal'},rooms:{}}
let activeBackgroundRoom = ''
let activeEnergyDashboard = null
let energyRefreshTimer = null
let energyRefreshRunning = false
let energyMasterInitialized = false
let energyMasterColors = []
let energyMasterPending = { signature:'', confirmations:0 }
const securitySections = { areas: false, zones: false }
let currentSecurityOrder = ['scenarios', 'areas', 'zones', 'locks']
const mediaSections = { rooms: true, playing: true }
const isSecurityGarage = (device) => device.kind === 'cover' && /garage|portone/i.test(`${device.icon || ''} ${device.name || ''}`)
const mediaTransportOverrides = new Map()
const recentCache = new Map()
let favoritesCache = null
let favoritesPending = null
let hiddenSourceIds = new Set()
let wiimTimelineTimer = null
let wiimTimelineRequest = 0
let wiimTimelineDragging = false
let wiimLoopMode = 4
const recentPending = new Map()
const ttsVolumeRestores = new Map()

function setMediaOverride(deviceId, values) {
  const key = String(deviceId)
  mediaTransportOverrides.set(key, { ...(mediaTransportOverrides.get(key) || {}), ...values })
}

$('#tools-open')?.addEventListener('click', () => { location.href = apiUrl('tools') })

document.querySelectorAll('dialog').forEach((dialog) => dialog.addEventListener('click', (event) => {
  if (event.target !== dialog) return
  const rect = dialog.getBoundingClientRect()
  const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom
  if (outside) dialog.close()
}))

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

function mediaSourceIcon(source) {
  const value = String(source || '').toLowerCase()
  if (value.includes('spotify')) return 'mdi:spotify'
  if (value.includes('apple')) return 'mdi:apple'
  if (value.includes('youtube')) return 'mdi:youtube'
  if (value.includes('radio') || value.includes('tunein')) return 'mdi:radio'
  if (value.includes('tv') || value.includes('video')) return 'mdi:television'
  return 'mdi:music-circle'
}

function mediaSourceMarkup(source, provider = '') {
  const fallback = `<span class="mdi-mask" style="${mdiStyle(source.icon, 'play-box')}"></span>`
  if (provider !== 'control4' || !source.source_id) return fallback
  return `<span class="media-source-native">${fallback}<img src="${apiUrl(`api/control4/source-icon/${source.source_id}?v=${encodeURIComponent(appVersion)}`)}" alt="" loading="eager" onload="this.parentElement.classList.add('loaded')" onerror="this.parentElement.classList.add('failed');this.hidden=true"></span>`
}

function activeMediaSourceMarkup(device, className, fallbackIcon) {
  const fallback = `<span class="mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')}"></span>`
  const sourceId = Number(device.active_source_id || 0)
  if (device.provider !== 'control4' || !Number.isSafeInteger(sourceId) || sourceId <= 0) return `<span class="${className} mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')}"></span>`
  return `<span class="${className} media-active-source">${fallback}<img src="${apiUrl(`api/control4/source-icon/${sourceId}?v=${encodeURIComponent(appVersion)}`)}" alt="" loading="eager" onload="this.parentElement.classList.add('loaded')" onerror="this.hidden=true"></span>`
}

function deviceGlyph(device) {
  const fallback = device.kind === 'climate' ? 'thermostat' : device.kind === 'cover' ? 'blinds-horizontal' : device.kind === 'lock' ? 'lock' : device.kind === 'media_player' ? 'speaker' : 'lightbulb'
  return `<span class="device-glyph mdi-mask" style="${mdiStyle(device.icon, fallback)}"></span>`
}

function lockActionIcon(device, open) {
  const icon = String(device.icon || '').toLocaleLowerCase('it')
  if (/gate|cancello/.test(icon)) return open ? 'mdi:gate-open' : 'mdi:gate'
  if (/garage|portone/.test(icon)) return open ? 'mdi:garage-open' : 'mdi:garage'
  if (/door|porta/.test(icon) && !/lock/.test(icon)) return open ? 'mdi:door-open' : 'mdi:door-closed'
  return open ? 'mdi:lock-open-outline' : 'mdi:lock-outline'
}

const roomFeatureDefinitions = [
  { id: 'audio', label: 'Audio', icon: 'mdi:music-note', matches: (device) => ['media', 'media_player'].includes(device.kind) && (!device.experiences?.length || device.experiences.includes('listen')) },
  { id: 'video', label: 'Video', icon: 'mdi:television', matches: (device) => ['camera', 'doorbell'].includes(device.kind) || (['media', 'media_player'].includes(device.kind) && device.experiences?.includes('watch')) },
  { id: 'lights', label: 'Luci', icon: 'mdi:lightbulb', matches: (device) => device.kind === 'light' },
  { id: 'climate', label: 'Clima', icon: 'mdi:thermometer', matches: (device) => ['climate', 'temp', 'temperature', 'humidity', 'air', 'air_quality'].includes(device.kind) },
  { id: 'covers', label: 'Oscuranti', icon: 'mdi:blinds-horizontal', matches: (device) => device.kind === 'cover' },
  { id: 'security', label: 'Sicurezza', icon: 'mdi:shield-home', matches: (device) => ['lock', 'alarm', 'security', 'alarm_partition', 'alarm_zone', 'camera', 'doorbell'].includes(device.kind) },
  { id: 'extra', label: 'Extra', icon: 'mdi:power-socket-eu', matches: (device) => device.kind === 'switch' },
]

function roomFeatureIcons(roomName) {
  const normalizedRoom = String(roomName || '').trim().toLocaleLowerCase('it')
  const roomDevices = currentDevices.filter((device) => String(device.room || '').trim().toLocaleLowerCase('it') === normalizedRoom)
  return roomFeatureDefinitions.filter((feature) => roomDevices.some(feature.matches)).map((feature) => `
    <i class="room-feature room-feature-${feature.id}" title="${feature.label}" aria-label="${feature.label}" style="${mdiStyle(feature.icon, 'shape')}"></i>
  `).join('')
}

function tick() {
  const now = new Date()
  $('#clock').textContent = now.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  $('#date').textContent = now.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })
}

function render(data) {
  appVersion = data.version || appVersion
  currentBackgrounds = data.backgrounds || currentBackgrounds
  document.body.dataset.cardTheme = data.appearance?.card_theme || 'graphite'
  document.body.dataset.cardGlow = data.appearance?.card_glow === false ? 'off' : 'on'
  currentSecurityOrder = data.appearance?.security_order || currentSecurityOrder
  applyBackground()
  const dashboard = data.dashboard || {}
  const home = dashboard.home || {}
  const providers = data.providers || []
  currentMediaGroups = providers.filter((provider) => ['control4','evoice'].includes(provider.id)).flatMap((provider) => provider.groups || [])
  const navIcons = data.nav_icons || {}
  currentDevices = Array.isArray(dashboard.devices) ? dashboard.devices : []
  currentDevices.forEach((device) => {
    const override = mediaTransportOverrides.get(String(device.id))
    if (!override || device.kind !== 'media_player') return
    const trackChanged = override.fingerprint && device.content_fingerprint && override.fingerprint !== device.content_fingerprint
    if (String(device.state).toLowerCase() === 'off' || trackChanged) {
      mediaTransportOverrides.delete(String(device.id))
      return
    }
    if (override.expires && Date.now() > override.expires) {
      delete override.state
      delete override.expires
    }
    if (override.state) device.state = override.state
    if (Object.hasOwn(override, 'muted')) {
      if (device.muted === override.muted) delete override.muted
      else device.muted = override.muted
    }
    if (Object.hasOwn(override, 'volume')) {
      if (Number(device.volume) === override.volume) delete override.volume
      else device.volume = override.volume
    }
    if (!override.state && !Object.hasOwn(override, 'muted') && !Object.hasOwn(override, 'volume')) mediaTransportOverrides.delete(String(device.id))
  })
  updateGlobalMediaSession()
  if (!energyMasterInitialized) { energyMasterInitialized = true; loadEnergyDashboards(false) }
  renderHomeMediaSessions()
  updateNavigationStates()
  if (activeDetailIds && !$('#detail-view').hidden) {
    renderActiveDeviceList()
  }
  $('#home-name').textContent = home.name || 'Casa'
  $('#mode').textContent = `${data.mode === 'demo' ? 'ANTEPRIMA DEMO' : 'LIVE'}${loggedUser ? ` · ${loggedUser}` : ''}`
  renderHomeComfort()
  renderHomeSecurity()
  document.querySelectorAll('.nav-icon').forEach((node) => {
    node.setAttribute('style', mdiStyle(navIcons[node.dataset.icon], 'shape'))
  })
  paintEnergyMasterIcon()
  $('#demo-cameras').hidden = data.mode !== 'demo'
  const failedProvider = providers.find((provider) => provider.status === 'offline' || provider.status === 'misconfigured')
  if (data.mode === 'live' && failedProvider) {
    const notice = $('#notice')
    notice.textContent = `${failedProvider.label}: ${failedProvider.reason || 'connettore non disponibile'}. Controlla indirizzo, porta e autenticazione.`
    notice.hidden = false
  }
  renderHomeStatusCounters()
  const visibleRoomNames = new Set(currentDevices
    .filter((device) => !['alarm_partition', 'alarm_scenario', 'alarm_system'].includes(device.kind))
    .map((device) => String(device.room || '').trim().toLocaleLowerCase('it'))
    .filter(Boolean))
  const roomOrder = new Map((data.appearance?.room_order || []).map((name, index) => [String(name).trim().toLocaleLowerCase('it'), index]))
  const visibleRooms = (dashboard.rooms || []).filter((room) => visibleRoomNames.has(String(room.name || '').trim().toLocaleLowerCase('it'))).sort((a, b) => {
    const aOrder = roomOrder.get(String(a.name || '').trim().toLocaleLowerCase('it')) ?? Number.MAX_SAFE_INTEGER
    const bOrder = roomOrder.get(String(b.name || '').trim().toLocaleLowerCase('it')) ?? Number.MAX_SAFE_INTEGER
    return aOrder - bOrder || String(a.name || '').localeCompare(String(b.name || ''), 'it')
  })
  $('#rooms').innerHTML = visibleRooms.map((room) => `
    <button class="room-card" data-room="${esc(room.name)}"><span>${esc(String(room.name).toLocaleUpperCase('it'))}</span><small class="room-features">${roomFeatureIcons(room.name)}</small></button>
  `).join('') || '<span class="empty-state">Nessun ambiente disponibile</span>'
  $('#app').classList.remove('loading')
  if (!failedProvider) $('#notice').hidden = true
}

function renderHomeStatusCounters() {
  const statusCounters = [
    { kind: 'lights', label: 'Luci', icon: 'mdi:lightbulb', color: 'yellow', devices: currentDevices.filter((device) => device.kind === 'light'), active: (device) => lightIsOn(device) },
    { kind: 'extra', label: 'Extra', icon: 'mdi:power-socket-eu', color: 'red', devices: currentDevices.filter((device) => device.kind === 'switch'), active: stateIsActive },
    { kind: 'covers', label: 'Oscuranti', icon: 'mdi:blinds-horizontal', color: 'cyan', devices: currentDevices.filter((device) => device.kind === 'cover'), active: (device) => stateIsActive(device) || Number(device.position) > 0 },
    { kind: 'security', label: 'Sicurezza', icon: 'mdi:shield-home', color: 'red', devices: currentDevices.filter((device) => ['lock','alarm_partition','alarm_zone'].includes(device.kind) || isSecurityGarage(device)), active: (device) => ['OPEN','OPENING','UNLOCKED','ARMED','ALARM','TAMPER'].includes(String(device.state ?? '').trim().toUpperCase()) },
  ]
  $('#widgets').innerHTML = statusCounters.map((counter) => {
    const count = counter.devices.filter(counter.active).length
    return `<button class="quick-card status-counter ${count ? `active status-counter-${counter.color}` : ''}" data-kind="${counter.kind}" data-label="${counter.label}" aria-label="${counter.label}: ${count}"><span class="qicon mdi-mask" style="${mdiStyle(counter.icon, 'shape')}"></span><strong>${count}</strong></button>`
  }).join('')
}

function renderHomeComfort() {
  const card = $('#home-comfort-summary')
  if (!card) return
  const thermostats = currentDevices.filter((device) => device.kind === 'climate' && !device.read_only)
  const temperatures = thermostats.map((device) => Number(device.temperature)).filter(Number.isFinite)
  const external = currentDevices.find((device) => device.read_only && device.kind === 'climate') || currentDevices.find((device) => ['temp','temperature'].includes(device.kind) && /estern|external/i.test(`${device.name || ''} ${device.room || ''}`))
  const heating = thermostats.filter((device) => String(device.state).toUpperCase() === 'HEATING').length
  const cooling = thermostats.filter((device) => String(device.state).toUpperCase() === 'COOLING').length
  const mode = heating && cooling ? 'mixed' : heating ? 'heat' : cooling ? 'cool' : 'idle'
  const heatingStatus = `${heating} ${heating === 1 ? 'zona' : 'zone'} in riscaldamento`
  const coolingStatus = `${cooling} ${cooling === 1 ? 'zona' : 'zone'} in raffrescamento`
  const status = heating && cooling ? `<span class="comfort-heating">${heatingStatus}</span><span class="comfort-cooling">${coolingStatus}</span>` : heating ? `<span class="comfort-heating">${heatingStatus}</span>` : cooling ? `<span class="comfort-cooling">${coolingStatus}</span>` : 'Nessuna richiesta'
  const average = temperatures.length ? temperatures.reduce((sum, value) => sum + value, 0) / temperatures.length : NaN
  card.className = `climate-card home-comfort-summary xcard comfort-${mode}`
  $('#home-comfort-icon').setAttribute('style', mdiStyle('mdi:coolant-temperature', 'thermostat'))
  $('#home-comfort-state').innerHTML = status
  $('#home-comfort-inside').textContent = Number.isFinite(average) ? `${average.toFixed(1)}°` : '--'
  const outside = Number(external?.temperature ?? external?.state ?? external?.value)
  $('#home-comfort-outside').textContent = Number.isFinite(outside) ? `${outside.toFixed(1)}°` : '--'
}

function renderHomeSecurity() {
  const card = $('#home-security-summary')
  if (!card) return
  const partitions = currentDevices.filter((device) => device.kind === 'alarm_partition')
  const system = currentDevices.find((device) => device.kind === 'alarm_system')
  const issues = partitions.filter((device) => device.alarm || device.tamper || ['ALARM', 'TAMPER'].includes(String(device.state || '').toUpperCase())).length
  const armed = partitions.filter((device) => String(device.state || '').toUpperCase() === 'ARMED').length
  const hasInstant = partitions.some((device) => String(device.state || '').toUpperCase() === 'ARMED' && device.arm_mode === 'instant')
  const hasDelayed = partitions.some((device) => String(device.state || '').toUpperCase() === 'ARMED' && device.arm_mode !== 'instant')
  const state = issues ? `${issues} ${issues === 1 ? 'allarme attivo' : 'allarmi attivi'}` : armed ? `${armed} ${armed === 1 ? 'area inserita' : 'aree inserite'}` : 'Tutto sotto controllo'
  const mode = system?.arm_description || (armed ? 'Inserimento attivo' : 'Disinserito')
  const visual = issues || hasInstant ? 'alarm' : hasDelayed ? 'armed' : 'safe'
  const icon = issues ? 'mdi:shield-alert' : armed ? 'mdi:shield-lock' : 'mdi:shield-check'
  card.className = `home-security-summary security-${visual}`
  $('#home-security-icon').setAttribute('style', mdiStyle(icon, 'shield-home'))
  $('#home-security-state').textContent = state
  $('#home-security-mode').textContent = mode
}

function stateLabel(device) {
  if (device.kind === 'media_player') {
    if (device.connection_status === 'offline' || device.availability !== 'available') return 'Non disponibile'
    return String(device.state || 'unknown').toLocaleUpperCase('it')
  }
  if (device.kind === 'climate') {
    const current = Number(device.temperature)
    const target = Number(device.target_temperature)
    if (device.read_only) return Number.isFinite(current) ? `${current.toFixed(1)}°` : '--'
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
    button.classList.remove('status-yellow','status-red','status-cyan','status-green','status-amber','status-comfort-mixed')
    if (active) button.classList.add(className)
  }
  setState('lights', 'status-yellow', currentDevices.some((device) => device.kind === 'light' && lightIsOn(device)))
  setState('extra', 'status-red', currentDevices.some((device) => device.kind === 'switch' && stateIsActive(device)))
  setState('covers', 'status-cyan', currentDevices.some((device) => device.kind === 'cover' && (stateIsActive(device) || Number(device.position) > 0)))
  const securityPartitions = currentDevices.filter((device) => device.kind === 'alarm_partition')
  const securityAlarm = securityPartitions.some((device) => device.alarm || device.tamper || ['ALARM','TAMPER'].includes(String(device.state || '').toUpperCase()))
  const securityInstant = securityPartitions.some((device) => String(device.state || '').toUpperCase() === 'ARMED' && device.arm_mode === 'instant')
  const securityDelayed = securityPartitions.some((device) => String(device.state || '').toUpperCase() === 'ARMED' && device.arm_mode !== 'instant')
  setState('security', securityAlarm || securityInstant ? 'status-red' : securityDelayed ? 'status-yellow' : 'status-green', securityPartitions.length > 0)
  setState('watch', 'status-cyan', currentDevices.some((device) => ['media','media_player'].includes(device.kind) && device.active_experience === 'watch' && stateIsActive(device)))
  setState('listen', 'status-green', currentDevices.some((device) => ['media','media_player'].includes(device.kind) && device.active_experience === 'listen' && stateIsActive(device)))
  const comfortStates = currentDevices.filter((device) => device.kind === 'climate' && !device.read_only).map((device) => String(device.state).toUpperCase())
  const comfortHeating = comfortStates.includes('HEATING')
  const comfortCooling = comfortStates.includes('COOLING')
  setState('comfort', comfortHeating && comfortCooling ? 'status-comfort-mixed' : comfortHeating ? 'status-amber' : 'status-cyan', comfortHeating || comfortCooling)
  setState('scenarios', 'status-yellow', currentScenarios.some((scenario) => scenario.running || ['ON','1','TRUE'].includes(String(scenario.state ?? '').toUpperCase())))
}

function brightness255(device) {
  const value = device.brightness === null || device.brightness === undefined || device.brightness === '' ? NaN : Number(device.brightness)
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
  if (devices.length && devices.every((device) => ['lock','alarm_partition','alarm_zone','alarm_scenario','alarm_system'].includes(device.kind) || isSecurityGarage(device))) {
    renderSecurityDevices(devices)
    return
  }
  if (devices.length && devices.every((device) => device.kind === 'media_player')) {
    renderMediaExperience(devices)
    return
  }
  const groups = rgbChannels(devices)
  const completeGroups = new Map([...groups].filter(([, channels]) => channels.red && channels.green && channels.blue))
  const groupedIds = new Set([...completeGroups.values()].flatMap((channels) => Object.values(channels).map((device) => String(device.id))))
  const cards = devices.filter((device) => !groupedIds.has(String(device.id))).map((device) => `
    <article class="${deviceVisualClass(device)} ${device.kind === 'media_player' ? `media-player-card media-player-card-${device.active_experience === 'watch' ? 'watch' : 'listen'}` : ''}" style="${deviceCardStyle(device)}" data-device-id="${esc(device.id)}" ${['light','switch'].includes(device.kind) ? 'data-device-toggle tabindex="0"' : ''}>${mediaArtwork(device)}${deviceGlyph(device)}<div><strong>${esc(device.name)}</strong><small>${esc(device.room)}</small>${device.kind === 'media_player' ? `<span class="media-track">${esc(device.title || 'Nessuna riproduzione')}</span><span class="media-artist">${esc([device.artist, device.album].filter(Boolean).join(' · '))}</span>` : ''}</div><em>${esc(stateLabel(device))}</em>${deviceActions(device)}</article>
  `)
  completeGroups.forEach((channels, group) => cards.push(renderRgbCard(group, channels)))
  $('#device-list').innerHTML = cards.join('') || '<p class="empty-state">Nessun dispositivo disponibile</p>'
}

function renderSecurityDevices(devices) {
  const partitions = devices.filter((device) => device.kind === 'alarm_partition')
  const zones = devices.filter((device) => device.kind === 'alarm_zone')
  const scenarios = devices.filter((device) => device.kind === 'alarm_scenario')
  const locks = devices.filter((device) => device.kind === 'lock' || isSecurityGarage(device))
  const system = devices.find((device) => device.kind === 'alarm_system')
  const issueCount = [...partitions, ...zones].filter((item) => ['ALARM','TAMPER'].includes(String(item.state).toUpperCase())).length
  const memoryCount = partitions.filter((area) => area.alarm_memory || area.tamper_memory).length
  const armedCount = partitions.filter((area) => area.state === 'ARMED').length
  const hasInstant = partitions.some((area) => area.state === 'ARMED' && area.arm_mode === 'instant')
  const hasDelayed = partitions.some((area) => area.state === 'ARMED' && area.arm_mode !== 'instant')
  const modeName = system?.arm_description || (armedCount ? 'Inserimento attivo' : 'Disinserito')
  const activeScenarioId = String(system?.active_scenario_id || '')
  const summaryClass = issueCount || hasInstant ? 'instant' : hasDelayed ? 'delayed' : 'ready'
  const summary = `<section class="security-summary security-summary-${summaryClass}"><span class="mdi-mask" style="${mdiStyle(issueCount ? 'mdi:shield-alert-outline' : armedCount ? 'mdi:shield-lock-outline' : 'mdi:shield-check-outline', 'shield-home')}"></span><strong class="security-summary-state">${issueCount ? `${issueCount} ${issueCount === 1 ? 'allarme attivo' : 'allarmi attivi'}` : armedCount ? `${armedCount} ${armedCount === 1 ? 'area inserita' : 'aree inserite'}` : 'Tutto sotto controllo'}</strong><div class="security-summary-mode"><small>MODALITÀ</small><strong>${esc(modeName)}</strong></div></section>`
  const areaCards = partitions.map((device) => {
    const alarm = device.state === 'ALARM'; const tamper = device.state === 'TAMPER'; const armed = device.state === 'ARMED'; const memory = device.alarm_memory || device.tamper_memory
    const state = alarm ? 'Allarme attivo' : tamper ? 'Sabotaggio attivo' : armed ? device.arm_mode === 'instant' ? 'Inserita immediata' : 'Inserita con ritardo' : 'Disinserita'
    const iconTitle = memory && !alarm && !tamper ? device.alarm_memory ? 'Memoria allarme' : 'Memoria sabotaggio' : state
    const visualClass = alarm || tamper ? 'alarm' : armed ? `armed ${device.arm_mode === 'instant' ? 'armed-instant' : 'armed-delayed'}` : memory ? 'memory' : 'ready'
    return `<article class="security-area ${visualClass}" data-device-id="${esc(device.id)}" tabindex="0" role="button"><span class="mdi-mask" style="${mdiStyle(alarm || tamper ? 'mdi:shield-alert' : armed ? 'mdi:shield-lock' : memory ? 'mdi:history' : 'mdi:shield-check', 'shield-home')}" role="img" aria-label="${esc(iconTitle)}" title="${esc(iconTitle)}"></span><strong>${esc(device.name)}</strong></article>`
  }).join('')
  const zoneIcon = (device) => {
    const active = device.state === 'ACTIVE'
    if (device.sensor_type === 'door') return active ? 'mdi:door-open' : 'mdi:door-closed'
    if (device.sensor_type === 'window') return active ? 'mdi:window-open-variant' : 'mdi:window-closed-variant'
    if (device.sensor_type === 'shutter') return active ? 'mdi:window-shutter-open' : 'mdi:window-shutter'
    if (device.sensor_type === 'motion_outdoor') return active ? 'mdi:cctv' : 'mdi:cctv-off'
    if (device.sensor_type === 'motion_indoor') return active ? 'mdi:motion-sensor' : 'mdi:motion-sensor-off'
    return device.icon || 'mdi:access-point'
  }
  const zoneCards = zones.map((device) => {
    const bad = device.state === 'TAMPER'
    const visualState = bad ? 'tamper' : device.bypassed ? 'bypassed' : device.state === 'MASKED' ? 'masked' : device.memory ? 'memory' : device.state === 'ACTIVE' ? 'active' : 'ready'
    const stateTitle = bad ? 'Sabotaggio' : device.bypassed ? 'Zona esclusa' : device.state === 'MASKED' ? 'Zona mascherata' : device.memory ? 'Memoria presente' : device.state === 'ACTIVE' ? 'Sensore attivo' : 'Zona a riposo'
    const actionTitle = device.bypassed ? 'Includi zona' : 'Escludi zona'
    return `<article class="security-zone zone-${visualState}" data-device-id="${esc(device.id)}" tabindex="0" role="button" aria-expanded="false"><span class="security-zone-sensor mdi-mask" style="${mdiStyle(zoneIcon(device), 'access-point')}" role="img" aria-label="${stateTitle}" title="${stateTitle}"></span><strong>${esc(device.name)}</strong><i class="security-zone-state" aria-hidden="true">${device.bypassed ? '!' : ''}</i><button data-action="${device.bypassed ? 'bypass_off' : 'bypass_on'}">${device.bypassed ? 'INCLUDI' : 'ESCLUDI'}</button></article>`
  }).join('')
  const lockCards = locks.map((device) => {
    const state = String(device.state || '').trim().toUpperCase()
    const stateClass = ['LOCKED','CLOSED','OFF','0'].includes(state) ? 'locked' : ['UNLOCKED','UNLOCKING','LOCKING','OPEN','OPENING','CLOSING','ON','1'].includes(state) ? 'unlocked' : 'unknown'
    const rawBattery = device.battery_percent ?? device.battery_percentage ?? device.battery_level ?? device.battery
    const battery = rawBattery !== null && rawBattery !== undefined && rawBattery !== '' && Number.isFinite(Number(rawBattery)) ? Math.max(0, Math.min(100, Math.round(Number(rawBattery)))) : null
    const batteryMarkup = battery === null ? '' : `<span class="security-lock-battery ${battery <= 20 ? 'low' : ''}" title="Batteria ${battery}%"><i class="mdi-mask" style="${mdiStyle(battery <= 20 ? 'mdi:battery-alert-variant-outline' : 'mdi:battery', 'battery')}"></i>${battery}%</span>`
    return `<article class="security-lock security-lock-${stateClass}" data-device-id="${esc(device.id)}">${deviceGlyph(device)}<div class="security-lock-name"><strong>${esc(device.name)}</strong><small>${esc(device.room)}</small></div><b>${esc(stateLabel(device))}${batteryMarkup}</b>${deviceActions(device)}</article>`
  }).join('')
  const scenarioCards = scenarios.map((device) => { const disarm = device.category === 'DISARM'; const partial = device.category === 'PARTIAL'; const active = String(device.id) === activeScenarioId; return `<button class="security-scenario ${disarm ? 'disarm' : partial ? 'partial' : 'arm'} ${active ? 'active' : ''}" data-security-scenario data-device-id="${esc(device.id)}" data-action="execute"><span class="mdi-mask" style="${mdiStyle(disarm ? 'mdi:shield-off-outline' : partial ? 'mdi:shield-half-full' : 'mdi:shield-lock-outline', 'shield-key-outline')}"></span><strong>${esc(device.name)}</strong></button>` }).join('')
  const section = (key, title, content, className) => `<section class="security-section security-collapsible"><button class="security-section-toggle" data-security-toggle="${key}" aria-expanded="${securitySections[key]}"><strong>${title}</strong><span class="mdi-mask" style="${mdiStyle(securitySections[key] ? 'mdi:chevron-up' : 'mdi:chevron-down', 'chevron-down')}"></span></button><div class="${className}" ${securitySections[key] ? '' : 'hidden'}>${content}</div></section>`
  const blocks = {
    scenarios: scenarios.length ? `<section class="security-section"><h3>Scenari di inserimento</h3><div class="security-scenario-grid">${scenarioCards}</div></section>` : '',
    areas: partitions.length ? section('areas', 'Stato aree', areaCards, 'security-area-grid') : '',
    zones: zones.length ? section('zones', 'Zone', zoneCards, 'security-zone-grid') : '',
    locks: locks.length ? `<section class="security-section"><h3>Accessi e portoni</h3><div class="security-zone-grid">${lockCards}</div></section>` : ''
  }
  const container = $('#device-list')
  const desired = document.createElement('div')
  desired.innerHTML = summary + currentSecurityOrder.map((key) => blocks[key] || '').join('')
  const nextChildren = [...desired.children]
  // Preserve unchanged cards: replacing the whole list on every state update restarts their visual transitions.
  nextChildren.forEach((next, index) => {
    const previous = container.children[index]
    if (!previous) container.append(next)
    else if (previous.outerHTML !== next.outerHTML) previous.replaceWith(next)
  })
  while (container.children.length > nextChildren.length) container.lastElementChild.remove()
}

function renderMediaExperience(devices) {
  let selected = devices.find((device) => String(device.id) === selectedMediaId)
  selected = selected || devices.find((device) => String(device.state).toLowerCase() === 'playing') || devices[0]
  selectedMediaId = String(selected.id)
  const players = devices.map((device) => {
    const state = String(device.state).toLowerCase()
    const experience = device.active_experience || (['playing', 'buffering'].includes(state) ? 'listen' : '')
    const operating = !['off', 'unavailable', 'unknown'].includes(state) && Boolean(experience)
    const mode = experience === 'watch' ? 'Video attivo' : 'Audio attivo'
    return `<button class="media-service-tile media-room-tile ${device.id === selected.id ? 'active' : ''} ${operating ? `media-room-on media-room-${experience}` : ''}" data-media-select="${esc(device.id)}"><span class="mdi-mask" style="${mdiStyle(device.icon, 'speaker')}"></span><b>${esc(device.name)}</b>${device.source ? `<small>${esc(device.source)}</small>` : ''}${operating ? `<i class="media-room-state" aria-label="${mode}" title="${mode}"></i>` : ''}</button>`
  }).join('')
  const options = selected.source_options?.length ? selected.source_options.filter((source) => (!currentMediaExperience || source.experience === currentMediaExperience) && !hiddenSourceIds.has(Number(source.source_id))) : (selected.source_list || []).map((source) => ({key:source,label:source}))
  const sources = options.map((source) => {
    return `<button class="media-service-tile ${source.label === selected.source ? 'active' : ''}" data-device-id="${esc(selected.id)}" data-media-source="${esc(source.key)}">${mediaSourceMarkup(source, selected.provider)}<b>${esc(source.label)}</b></button>`
  }).join('')
  const caps = selected.capabilities || {}
  const disabled = selected.connection_status === 'offline' || selected.availability !== 'available'
  const power = caps.turn_off ? `<button class="media-session-power" data-media-action="turn_off" aria-label="Spegni stanza" ${disabled ? 'disabled' : ''}><span class="mdi-mask" style="${mdiStyle('mdi:power', 'power')}"></span></button>` : ''
  const experienceClass = selected.active_experience === 'watch' ? 'media-session-watch' : 'media-session-listen'
  const mainIcon = selected.active_experience === 'watch' ? 'mdi:video' : mediaSourceIcon(selected.source)
  const mainArtwork = selected.active_experience === 'watch' && !selected.content_fingerprint && selected.active_source_id ? `<span class="media-artwork media-video-source"><img src="${apiUrl(`api/control4/source-icon/${selected.active_source_id}?v=${encodeURIComponent(appVersion)}`)}" alt="${esc(selected.source || '')}" onerror="this.hidden=true"></span>` : mediaArtwork(selected)
  const recentRoomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
  const recentScope = (avRoom || activeMediaRoom) && recentRoomId ? `room-${recentRoomId}` : 'global'
  const cachedRecent = recentCache.get(recentScope)
  const recentContent = cachedRecent ? recentlyPlayedHtml(cachedRecent.items, recentRoomId) : '<span class="empty-state">Caricamento…</span>'
  const showRecent = selected.provider === 'control4' && (currentMediaExperience === 'listen' || (activeMediaRoom && selected.active_experience !== 'watch'))
  const recent = showRecent ? `<div class="media-recent" data-recently-played data-recent-scope="${recentScope}" ${cachedRecent && !cachedRecent.items.length && !cachedRecent.hiddenCount ? 'hidden' : ''}><header><h3>Ascoltati di recente</h3><button type="button" data-recent-show-hidden ${cachedRecent?.hiddenCount ? '' : 'hidden'}>Nascosti (${cachedRecent?.hiddenCount || 0})</button></header><div class="media-recent-strip">${recentContent}</div><div class="media-recent-hidden" hidden>${hiddenRecentlyPlayedHtml(cachedRecent?.hiddenItems || [])}</div></div>` : ''
  const favorites = showRecent ? `<div class="media-recent media-favorites" data-media-favorites data-favorite-room="${recentRoomId}"><header><h3>Preferiti</h3></header><div class="media-recent-strip">${favoritesCache ? mediaFavoritesHtml(favoritesCache, recentRoomId) : '<span class="empty-state">Caricamento…</span>'}</div></div>` : ''
  const ttsPlayers = currentDevices.filter((device) => device.kind === 'media_player' && device.provider === 'evoice' && device.tts_enabled)
  const ttsVolume = Math.max(0, Math.min(100, Number(localStorage.getItem('eface-tts-volume') ?? 50)))
  const voicePanel = selected.provider === 'evoice' && selected.tts_enabled && ttsPlayers.length ? `<section class="evoice-panel"><div class="evoice-heading"><h3>Messaggio vocale</h3><label><input type="checkbox" data-tts-select-all ${ttsPlayers.length === 1 ? 'checked' : ''}> Seleziona tutti</label></div><div class="evoice-targets">${ttsPlayers.map((device) => `<div class="evoice-target"><label><input type="checkbox" data-tts-target value="${esc(device.id)}" ${device.id === selected.id ? 'checked' : ''}><span>${esc(device.name)}</span><small>${esc(device.room)}</small></label>${device.dnd_available ? `<button class="evoice-dnd ${device.dnd ? 'active' : ''}" data-dnd-device="${esc(device.id)}" data-dnd-value="${device.dnd ? 'false' : 'true'}">DND</button>` : ''}</div>`).join('')}</div><label class="evoice-volume"><span>Volume messaggio</span><input type="range" min="0" max="100" value="${ttsVolume}" style="--volume:${ttsVolume}%" data-tts-volume><output>${ttsVolume}%</output></label><textarea id="evoice-tts-message" maxlength="500" rows="3" placeholder="Scrivi il messaggio da pronunciare"></textarea><button class="evoice-send" data-tts-send>INVIA MESSAGGIO</button></section>` : ''
  const sourceGlyph = activeMediaSourceMarkup(selected, 'device-glyph', mainIcon)
  const serviceName = /tunein/i.test(selected.source || '') ? 'tunein' : /amazon music/i.test(selected.source || '') ? 'amazon' : /tidal/i.test(selected.source || '') ? 'tidal' : /stations/i.test(selected.source || '') ? 'stations' : /spotify connect/i.test(selected.source || '') ? 'spotify' : /wireless music bridge/i.test(selected.source || '') ? 'bridge' : ''
  const navigatorIcon = selected.provider === 'control4' && serviceName && recentRoomId ? `<button type="button" class="media-navigator-open" data-msp-open data-msp-service="${serviceName}" data-msp-room="${recentRoomId}" title="Apri ${esc(selected.source)}">${sourceGlyph}</button>` : sourceGlyph
  const navigatorArtwork = navigatorIcon !== sourceGlyph ? mainArtwork.replace('class="media-artwork', `data-msp-open data-msp-service="${serviceName}" data-msp-room="${recentRoomId}" role="button" tabindex="0" class="media-artwork`) : mainArtwork
  const activeOption = (selected.source_options || []).find((source) => Number(source.source_id) === Number(selected.active_source_id))
  const wiimActive = selected.active_experience === 'listen' && (selected.transport_provider === 'wiim' || /wiim/i.test(`${selected.source || ''} ${activeOption?.label || ''}`))
  const timeline = wiimActive ? '<label class="media-timeline" data-wiim-timeline><input type="range" min="0" max="1" step="1" value="0" style="--position:0%" data-wiim-seek aria-label="Avanzamento brano"><span><output data-wiim-elapsed>0:00</output><output data-wiim-remaining>-0:00</output></span></label>' : ''
  const roomName = selected.room && !/^unknown$/i.test(selected.room) ? selected.room : selected.name
  $('#device-list').innerHTML = `<article class="media-session ${wiimActive ? 'has-wiim-timeline' : ''} ${experienceClass} ${deviceVisualClass(selected)}" data-device-id="${esc(selected.id)}">${navigatorArtwork}${navigatorIcon}<div class="media-session-info"><strong>${esc(selected.title || selected.source || selected.name)}</strong><small>${esc(selected.artist || selected.source || roomName)}</small><span class="media-track media-room-name">${esc(roomName)}</span></div>${power}${timeline}${deviceActions(selected, { hidePower: true, wiim: wiimActive })}</article>${voicePanel}${recent}${favorites}<div class="media-library media-room-library"><button class="media-library-toggle" data-media-section-toggle="rooms" aria-expanded="${mediaSections.rooms}"><strong>Stanze</strong><span class="mdi-mask" style="${mdiStyle(mediaSections.rooms ? 'mdi:chevron-up' : 'mdi:chevron-down', 'chevron-down')}"></span></button><div class="media-service-grid" ${mediaSections.rooms ? '' : 'hidden'}>${players}</div></div><div class="media-library media-source-library"><h3>Sorgenti e servizi</h3><div class="media-service-grid">${sources || '<span class="empty-state">Nessuna sorgente disponibile</span>'}</div></div>`
  if (showRecent) {
    const controls = $('#device-list .media-session .media-controls')
    if (controls) controls.insertAdjacentHTML('beforeend', '<button type="button" class="media-now-playing-favorite" data-now-playing-favorite aria-label="Aggiungi ai Preferiti e-Face" aria-pressed="false" title="Aggiungi ai Preferiti e-Face">★</button>')
    updateNowPlayingStar(selected)
  }
  if (recent) loadRecentlyPlayed(selected)
  if (favorites) loadMediaFavorites()
  if (wiimActive) loadWiimTimeline(selected.id)
}

function mediaTime(value) {
  const seconds = Math.max(0, Math.round(Number(value) || 0))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

async function loadWiimTimeline(deviceId) {
  clearTimeout(wiimTimelineTimer)
  const requestId = ++wiimTimelineRequest
  try {
    const response = await fetch(apiUrl('api/wiim/snapshot'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.json()
    const device = payload.device || payload
    const host = document.querySelector(`[data-device-id="${CSS.escape(String(deviceId))}"] [data-wiim-timeline]`)
    if (!host || requestId !== wiimTimelineRequest) return
    const duration = Math.max(0, Number(device.duration) || 0)
    const position = Math.max(0, Math.min(duration || 0, Number(device.position) || 0))
    wiimLoopMode = Number.isFinite(Number(device.loop)) ? Number(device.loop) : 4
    const input = host.querySelector('[data-wiim-seek]')
    input.max = String(Math.max(1, Math.round(duration)))
    if (!wiimTimelineDragging) input.value = String(Math.round(position))
    const shown = Number(input.value) || position
    input.style.setProperty('--position', `${duration ? Math.min(100, shown / duration * 100) : 0}%`)
    host.querySelector('[data-wiim-elapsed]').textContent = mediaTime(shown)
    host.querySelector('[data-wiim-remaining]').textContent = `-${mediaTime(Math.max(0, duration - shown))}`
    const card = host.closest('[data-device-id]')
    card?.querySelector('[data-wiim-action="shuffle"]')?.classList.toggle('active', [2, 3, 5].includes(wiimLoopMode))
    card?.querySelector('[data-wiim-action="repeat"]')?.classList.toggle('active', [0, 1, 2, 5].includes(wiimLoopMode))
  } catch (_) {
    // Il player Control4 resta utilizzabile anche se il WiiM non risponde al polling.
  } finally {
    if (document.querySelector(`[data-device-id="${CSS.escape(String(deviceId))}"] [data-wiim-timeline]`)) wiimTimelineTimer = setTimeout(() => loadWiimTimeline(deviceId), 2000)
  }
}

async function loadRecentlyPlayed(selected) {
  const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
  const scope = (avRoom || activeMediaRoom) && roomId ? `room-${roomId}` : 'global'
  const params = (avRoom || activeMediaRoom) && roomId ? `?room_id=${roomId}` : ''
  const cached = recentCache.get(scope)
  if (cached && Date.now() - cached.updated < 30000) return
  if (recentPending.has(scope)) return recentPending.get(scope)
  const pending = (async () => {
    try {
      const response = await fetch(apiUrl(`api/control4/recently-played${params}`), { cache: 'no-store' })
      if (!response.ok) throw new Error('Ascoltati di recente non disponibili')
      const data = await response.json()
      const host = document.querySelector('[data-recently-played]')
      const items = Array.isArray(data.items) ? data.items : []
      const hiddenItems = Array.isArray(data.hidden_items) ? data.hidden_items : []
      const hiddenCount = Number(data.hidden_count || 0)
      recentCache.set(scope, { items, hiddenItems, hiddenCount, updated: Date.now() })
      if (favoritesCache?.some((favorite) => favorite.kind === 'recent' && !favorite.driver_id && [...items, ...hiddenItems].some((item) => item.key === favorite.key))) await loadMediaFavorites(true)
      if (!host || host.dataset.recentScope !== scope) return
      host.hidden = !items.length && !hiddenCount
      host.querySelector('.media-recent-strip').innerHTML = recentlyPlayedHtml(items, roomId)
      const showHidden = host.querySelector('[data-recent-show-hidden]')
      showHidden.hidden = !hiddenCount
      showHidden.textContent = `Nascosti (${hiddenCount})`
      host.querySelector('.media-recent-hidden').innerHTML = hiddenRecentlyPlayedHtml(hiddenItems)
      updateNowPlayingStar(selected)
      const favoritesPanel = $('[data-media-favorites]')
      if (favoritesPanel && favoritesCache) favoritesPanel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(favoritesPanel.dataset.favoriteRoom))
    } catch (_) {
      const host = document.querySelector('[data-recently-played]')
      if (!cached && host?.dataset.recentScope === scope) host.hidden = true
    } finally { recentPending.delete(scope) }
  })()
  recentPending.set(scope, pending)
  return pending
}

function recentlyPlayedHtml(items, roomId) {
  return items.map((item) => {
    const art = item.content_fingerprint ? apiUrl(`api/media/${encodeURIComponent(item.registry_id)}/artwork?fingerprint=${encodeURIComponent(item.content_fingerprint)}`) : ''
    const pinned = favoritesCache?.some((favorite) => favorite.id === `recent:${item.key}`)
    return `<span class="media-recent-card"><button class="media-recent-item" data-recent-key="${esc(item.key)}" data-recent-room="${roomId}" title="${esc(item.title)}">${art ? `<img src="${esc(art)}" alt="" loading="lazy" draggable="false">` : '<span class="media-recent-art mdi-mask" style="'+mdiStyle('mdi:music-circle','music-circle')+'"></span>'}<b>${esc(item.title || 'Senza titolo')}</b><small>${esc(item.subtitle || '')}</small><em><span class="mdi-mask" style="${mdiStyle(item.driver_id === 1569 ? 'mdi:spotify' : 'mdi:radio', 'music-circle')}"></span>${esc(item.item_type || 'Audio')}</em></button><button type="button" class="media-recent-pin ${pinned ? 'active' : ''}" data-recent-pin="${esc(item.key)}" aria-label="${pinned ? 'Rimuovi dai' : 'Aggiungi ai'} Preferiti" title="${pinned ? 'Rimuovi dai' : 'Aggiungi ai'} Preferiti">★</button><button type="button" class="media-recent-hide" data-recent-hide="${esc(item.key)}" aria-label="Nascondi ${esc(item.title)}" title="Nascondi da Ascoltati di recente">×</button></span>`
  }).join('')
}

function mediaFavoritesHtml(items, roomId) {
  if (!items.length) return '<span class="empty-state">Aggiungi una stazione da Stations o usa ★ negli ascolti recenti.</span>'
  return items.map((item) => {
    const wiimPreset = item.kind === 'wiim_preset'
    const wiimTrack = item.kind === 'wiim_track'
    const art = wiimPreset || wiimTrack ? item.artwork : item.kind === 'station' && item.station_id ? apiUrl(`api/control4/stations/catalog-image/${item.station_id}`) : item.kind === 'msp' && item.image ? item.image : item.kind === 'recent' ? apiUrl(`api/control4/favorites/artwork?identity=${encodeURIComponent(item.id)}`) : ''
    const recent = [...recentCache.values()].flatMap((scope) => [...scope.items, ...scope.hiddenItems]).find((entry) => entry.key === item.key)
    const spotify = item.service === 'spotify' || Number(item.driver_id) === 1569 || Number(recent?.driver_id) === 1569 || (item.kind === 'recent' && !item.driver_id && !recent && ['Playlist', 'Album', 'Artist', 'Track', 'Show'].includes(item.item_type))
    const spotifySource = currentDevices.flatMap((device) => device.source_options || []).find((source) => String(source.label || '').toLocaleLowerCase('it') === 'spotify connect')
    const serviceId = Number(item.kind === 'station' || item.kind === 'msp' ? item.proxy_id : item.driver_id || recent?.driver_id || (spotify ? spotifySource?.source_id : 0))
    const spotifyLogo = 'assets/control4-icons/spotify-connect.png'
    const displayArt = art || (spotify ? spotifyLogo : '')
    const wiimService = String(item.service || '').toLowerCase()
    const fallbackIcon = wiimPreset || wiimTrack ? (wiimService.includes('soundcloud') ? 'mdi:soundcloud' : wiimService.includes('spotify') ? 'mdi:spotify' : wiimService.includes('youtube') ? 'mdi:youtube' : 'mdi:music-circle') : spotify ? 'mdi:spotify' : item.kind === 'station' || item.item_type === 'Station' ? 'mdi:radio' : 'mdi:music-circle'
    const fallback = `<span class="media-recent-art mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')}${displayArt ? ';display:none' : ''}"></span>`
    const imageError = spotify && art ? `if(!this.dataset.fallback){this.dataset.fallback='1';this.src='${spotifyLogo}';return}` : ''
    const originBadge = wiimTrack
      ? '<img class="media-favorite-origin media-favorite-eface" src="assets/brand-icon.png" alt="e-Face" title="Preferito creato da e-Face">'
      : '<span class="mdi-mask media-favorite-origin media-favorite-wiim" style="'+mdiStyle('mdi:speaker-wireless', 'speaker')+'" title="Preset nativo WiiM"></span>'
    const serviceLogo = wiimPreset || wiimTrack ? `<span class="mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')}"></span>${originBadge}` : Number.isSafeInteger(serviceId) && serviceId > 0 ? `<img class="media-favorite-service-icon" src="${apiUrl(`api/control4/source-icon/${serviceId}`)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='block'"><span class="mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')};display:none"></span>` : `<span class="mdi-mask" style="${mdiStyle(fallbackIcon, 'music-circle')}"></span>`
    const remove = wiimPreset ? `<button type="button" class="media-recent-hide" data-wiim-preset-remove="${Number(item.preset_index)}" aria-label="Elimina ${esc(item.title)} da WiiM ed e-Face" title="Elimina da WiiM ed e-Face">×</button>` : `<button type="button" class="media-recent-hide" data-favorite-remove="${esc(item.id)}" aria-label="Rimuovi ${esc(item.title)} dai Preferiti" title="Rimuovi dai Preferiti">×</button>`
    return `<span class="media-recent-card"><button class="media-recent-item" data-favorite-select="${esc(item.id)}" data-favorite-room="${roomId}" title="${esc(item.title)}">${displayArt ? `<img src="${esc(displayArt)}" alt="" loading="lazy" draggable="false" onerror="${imageError}this.style.display='none';this.nextElementSibling.style.display='block'">` : ''}${fallback}<b>${esc(item.title)}</b><small>${esc(item.subtitle || '')}</small><em>${serviceLogo}${esc(wiimPreset || wiimTrack ? item.service || 'WiiM' : item.kind === 'station' ? 'Stations' : spotify ? 'Spotify' : item.item_type || 'Audio')}</em></button>${remove}</span>`
  }).join('')
}

function nowPlayingFavorite(selected) {
  if ((!selected || !['control4','wiim'].includes(selected.provider)) || selected.active_experience !== 'listen') return { recent: null, favorite: null }
  const wiimSource = (selected.source_options || []).find((source) => source.experience === 'listen' && /wiim/i.test(String(source.label || '')))
  if (selected.transport_provider === 'wiim' || (wiimSource && Number(selected.active_source_id) === Number(wiimSource.source_id))) {
    const title = String(selected.title || '').trim().toLocaleLowerCase('it')
    const artist = String(selected.artist || '').trim().toLocaleLowerCase('it')
    const favorite = favoritesCache?.find((item) => item.kind === 'wiim_track' && String(item.title || '').trim().toLocaleLowerCase('it') === title && String(item.subtitle || '').trim().toLocaleLowerCase('it') === artist) || null
    return { recent: null, favorite, wiim: true }
  }
  const stationsSource = (selected.source_options || []).find((source) => source.experience === 'listen' && String(source.label || '').toLocaleLowerCase('it') === 'stations')
  if (Number(selected.station_id) > 0 && stationsSource && String(selected.source || '').toLocaleLowerCase('it') === 'stations') {
    return { recent: null, favorite: favoritesCache?.find((item) => item.id === `station:${stationsSource.source_id}:${selected.station_id}`) || null, stationProxyId: stationsSource.source_id }
  }
  const spotifySource = (selected.source_options || []).find((source) => source.experience === 'listen' && String(source.label || '').toLocaleLowerCase('it') === 'spotify connect')
  if (spotifySource && Number(selected.active_source_id) === Number(spotifySource.source_id) && /spotify connect/i.test(selected.source || '')) {
    const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
    const scope = (avRoom || activeMediaRoom) && roomId ? `room-${roomId}` : 'global'
    const history = recentCache.get(scope)
    const newest = [...(history?.items || []), ...(history?.hiddenItems || [])].sort((left, right) => Number(right.timestamp || 0) - Number(left.timestamp || 0))[0]
    const playlist = Number(newest?.driver_id) === Number(spotifySource.source_id) && String(newest?.item_type || '').toLocaleLowerCase('it') === 'playlist' ? newest : null
    return { recent: playlist, favorite: playlist ? favoritesCache?.find((item) => item.id === `recent:${playlist.key}`) || null : null, spotifyProxyId: spotifySource.source_id }
  }
  const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
  const scope = (avRoom || activeMediaRoom) && roomId ? `room-${roomId}` : 'global'
  const names = [selected.title, selected.artist, selected.album].map((value) => String(value || '').trim().toLocaleLowerCase('it')).filter((value) => value.length > 2)
  const history = recentCache.get(scope)
  const candidates = [...(history?.items || []), ...(history?.hiddenItems || [])]
  const recent = names.map((name) => candidates.find((item) => String(item.title || '').trim().toLocaleLowerCase('it') === name)).find(Boolean) || null
  const favorite = favoritesCache?.find((item) => item.id === `recent:${recent?.key}` || (names.includes(String(item.title || '').trim().toLocaleLowerCase('it')) && (item.kind === 'recent' || item.service === (/spotify/i.test(selected.source || '') ? 'spotify' : /tunein/i.test(selected.source || '') ? 'tunein' : /amazon/i.test(selected.source || '') ? 'amazon' : /tidal/i.test(selected.source || '') ? 'tidal' : undefined)))) || null
  return { recent, favorite }
}

function updateNowPlayingStar(selected) {
  const button = $('#device-list .media-session [data-now-playing-favorite]')
  if (!button || !selected || button.closest('[data-device-id]')?.dataset.deviceId !== String(selected.id)) return
  const context = nowPlayingFavorite(selected)
  const { favorite } = context
  button.classList.toggle('active', Boolean(favorite))
  button.setAttribute('aria-pressed', String(Boolean(favorite)))
  const label = context.wiim ? `${favorite ? 'Rimuovi' : 'Salva'} questo brano WiiM${favorite ? ' dai' : ' nei'} Preferiti e-Face` : context.spotifyProxyId ? `${favorite ? 'Rimuovi' : 'Salva'} playlist Spotify${context.recent?.title ? ` “${context.recent.title}”` : ''}${favorite ? ' dai' : ' nei'} Preferiti e-Face` : favorite ? 'Rimuovi dai Preferiti e-Face' : 'Aggiungi ai Preferiti e-Face'
  button.setAttribute('aria-label', label)
  button.title = label
}

async function loadMediaFavorites(force = false) {
  if (favoritesCache && !force) return
  if (favoritesPending) return favoritesPending
  favoritesPending = (async () => {
    try {
      const response = await fetch(apiUrl('api/control4/favorites'), { cache: 'no-store' })
      if (!response.ok) throw new Error('Preferiti non disponibili')
      favoritesCache = (await response.json()).items || []
      const panel = $('[data-media-favorites]')
      if (panel) panel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(panel.dataset.favoriteRoom))
      const recent = $('[data-recently-played]')
      if (recent) {
        const cached = recentCache.get(recent.dataset.recentScope)
        if (cached) recent.querySelector('.media-recent-strip').innerHTML = recentlyPlayedHtml(cached.items, Number(panel?.dataset.favoriteRoom || 0))
      }
      updateNowPlayingStar(currentDevices.find((item) => item.id === selectedMediaId) || currentDevices.find((item) => item.room === activeMediaRoom))
    } catch (error) { if (force) fail(error) }
    finally { favoritesPending = null }
  })()
  return favoritesPending
}

function hiddenRecentlyPlayedHtml(items) {
  return items.map((item) => `<div class="media-recent-hidden-row"><span>${esc(item.title || 'Senza titolo')}</span><button type="button" data-recent-restore-one="${esc(item.key)}">Ripristina</button></div>`).join('')
}

const tuneInState = { service: 'tunein', name: 'TuneIn', proxyId: 0, roomId: 0, tab: 'Home', stack: [], items: [], total: 0, more: false, search: '', busy: false, maxDevices: 5 }
const navigatorVisibleActions = new Set(['Play', 'SelectStation', 'PresetPlay', 'PlayRecent', 'PinFavorite', 'UnpinFavorite', 'PlayNow', 'PlayShuffle', 'PlayNext', 'AddToQueue', 'ReplaceQueue', 'AddToLibrary', 'RemoveFromLibrary', 'BtConnectDisconnect', 'BtRemoveDevice'])
let bridgePairingTimer = null

async function pollBridgePairing() {
  clearTimeout(bridgePairingTimer)
  if (!$('#music-navigator-dialog').open || tuneInState.service !== 'bridge') return
  try {
    const state = await tuneInRequest({ action: 'BtPairingStatus' })
    const panel = $('#music-navigator-list .music-bridge-confirm')
    if (!panel) return
    if (state.status === 'confirm') panel.innerHTML = `<p>${esc(state.message || 'Conferma il codice sul telefono.')}</p><button type="button" data-bridge-auth>Conferma codice</button><button type="button" data-bridge-cancel>Annulla</button>`
    else if (state.status === 'complete') { panel.innerHTML = '<p>Abbinamento completato.</p>'; setTimeout(() => loadTuneInNavigator(), 900); return }
    else if (state.status === 'expired' || state.status === 'error') { panel.innerHTML = '<p>Abbinamento non completato. Riprova.</p>'; return }
    bridgePairingTimer = setTimeout(pollBridgePairing, 2000)
  } catch (error) { fail(error) }
}

async function tuneInRequest(payload) {
  const response = await fetch(apiUrl(`api/control4/music/${tuneInState.service}/navigate`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, cache: 'no-store', body: JSON.stringify({ proxy_id: tuneInState.proxyId, room_id: tuneInState.roomId, tab: tuneInState.tab, ...payload }) })
  const result = await response.json()
  if (!response.ok) throw new Error(result.detail || `${tuneInState.name} non disponibile`)
  return result
}

function renderTuneInNavigator() {
  $('#music-navigator-tabs').querySelectorAll('[data-msp-tab]').forEach((button) => button.classList.toggle('active', button.dataset.mspTab === tuneInState.tab))
  $('#music-navigator-back').disabled = !tuneInState.stack.length
  const list = $('#music-navigator-list')
  const bridgeToolbar = tuneInState.service === 'bridge' ? `<div class="music-bridge-toolbar"><span>DISPOSITIVI</span><button type="button" data-bridge-refresh title="Aggiorna lista dispositivi" aria-label="Aggiorna lista dispositivi"><span class="mdi-mask" style="${mdiStyle('mdi:refresh', 'refresh')}"></span></button><button type="button" data-bridge-add ${tuneInState.items.length >= tuneInState.maxDevices ? 'disabled' : ''}>Aggiungi dispositivo</button></div>` : ''
  list.innerHTML = bridgeToolbar + (tuneInState.items.map((item) => {
    if (item.header) return `<div class="music-navigator-section">${esc(item.title)}</div>`
    const icon = item.icon || (tuneInState.service === 'spotify' ? 'mdi:spotify' : mediaSourceIcon(tuneInState.service))
    const fallback = `<span class="music-navigator-placeholder"><span class="mdi-mask" style="${mdiStyle(icon, 'music-circle')}"></span></span>`
    const artwork = item.image ? `<img src="${esc(/^(api|assets)\//.test(item.image) ? apiUrl(item.image) : item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.nextElementSibling.hidden=false;this.remove();"><span class="music-navigator-placeholder" hidden><span class="mdi-mask" style="${mdiStyle(icon, 'music-circle')}"></span></span>` : fallback
    return `<div class="music-navigator-row" data-msp-item="${esc(item.id)}"><button type="button" class="music-navigator-main" data-msp-select="${esc(item.id)}">${artwork}<span><strong>${esc(item.title)}</strong>${item.subtitle ? `<small>${esc(item.subtitle)}</small>` : ''}</span><b>${item.link ? '›' : ''}</b></button>${item.actions.some((action) => navigatorVisibleActions.has(action)) ? `<button type="button" class="music-navigator-menu-button" data-msp-menu="${esc(item.id)}" aria-label="Azioni per ${esc(item.title)}">⋮</button>` : ''}</div>`
  }).join('') || `<p class="music-navigator-empty">${tuneInState.service === 'bridge' ? 'Nessun dispositivo Bluetooth abbinato.' : 'Nessun contenuto disponibile.'}</p>`)
  $('#music-navigator-more').hidden = !tuneInState.more
}

async function loadTuneInNavigator(parent = '', append = false) {
  if (tuneInState.busy) return
  tuneInState.busy = true
  if (!append) $('#music-navigator-list').innerHTML = '<p class="music-navigator-empty">Caricamento…</p>'
  try {
    const data = await tuneInRequest({ parent, offset: append ? tuneInState.items.length : 0, search: tuneInState.search })
    if (tuneInState.tab === 'Settings') {
      tuneInState.items = []; tuneInState.more = false
      $('#music-navigator-tabs').querySelectorAll('[data-msp-tab]').forEach((button) => button.classList.toggle('active', button.dataset.mspTab === 'Settings'))
      $('#music-navigator-back').disabled = true
      $('#music-navigator-more').hidden = true
      $('#music-navigator-list').innerHTML = tuneInState.service === 'spotify' ? `<div class="music-navigator-settings"><div><span>Nome dispositivo</span><small>${esc(data.status || 'Spotify Connect')}</small></div><div><span>Utente attuale</span><small>${esc(data.username || 'Nessuno')}</small></div><p>Per avviare nuovi contenuti, usa Spotify Connect dal telefono. I preset salvati possono essere riprodotti qui.</p></div>` : `<div class="music-navigator-settings"><div><span>Stato account</span><small>${esc(data.status || 'Non disponibile')}</small></div><div><span>Nome utente</span><small>${esc(data.username || '—')}</small></div><p>Per collegare nuovamente l'account, apri Strumenti → Account servizi musicali.</p></div>`
      return
    }
    tuneInState.items = append ? [...tuneInState.items, ...data.items] : data.items
    tuneInState.total = data.total
    tuneInState.more = data.more
    if (tuneInState.service === 'bridge') tuneInState.maxDevices = data.max_devices || 5
    renderTuneInNavigator()
  } catch (error) { $('#music-navigator-list').innerHTML = `<p class="music-navigator-empty">${esc(error.message)}</p>` }
  finally { tuneInState.busy = false }
}

async function openTuneInNavigator(roomId, service = 'tunein') {
  const dialog = $('#music-navigator-dialog')
  tuneInState.service = service
  tuneInState.name = ({tunein:'TuneIn',amazon:'Amazon Music',tidal:'TIDAL',stations:'Stations',spotify:'Spotify Connect',bridge:'Wireless Music Bridge'})[service] || 'Musica'
  tuneInState.roomId = roomId
  tuneInState.tab = 'Home'; tuneInState.stack = []; tuneInState.items = []; tuneInState.search = ''
  $('#music-navigator-title').textContent = tuneInState.name
  $('#music-navigator-query').placeholder = `Cerca in ${tuneInState.name}`
  $('#music-navigator-search').hidden = true
  $('#music-navigator-tabs').hidden = false
  dialog.showModal()
  $('#music-navigator-list').innerHTML = `<p class="music-navigator-empty">Connessione a ${esc(tuneInState.name)}…</p>`
  try {
    const response = await fetch(apiUrl('api/control4/music/account-services'), { cache: 'no-store' })
    if (!response.ok) throw new Error('Servizi Control4 non disponibili')
    const data = await response.json()
    const source = (data.services || []).find((item) => item.name?.toLowerCase() === tuneInState.name.toLowerCase())
    if (!source?.proxy_id) throw new Error(`${tuneInState.name} non presente nell’impianto`)
    tuneInState.proxyId = Number(source.proxy_id)
    const tabs = service === 'tunein' ? [{id:'Home',name:'Home'},{id:'Browse',name:'Sfoglia'},{id:'Favorites',name:'Preferiti'},{id:'Settings',name:'Impostazioni'}] : service === 'stations' ? [{id:'Stations',name:'Radio'},{id:'Sources',name:'Sorgenti'},{id:'Genres',name:'Generi'}] : service === 'spotify' ? [{id:'Presets',name:'Preferito'},{id:'Recently Played',name:'Ascoltate di recente'},{id:'Settings',name:'Impostazioni'}] : service === 'bridge' ? [{id:'Devices',name:'Dispositivi'}] : (await tuneInRequest({operation:'tabs'})).tabs
    $('#music-navigator-search-toggle').hidden = service === 'stations' || service === 'spotify' || service === 'bridge'
    if (!tabs.length) throw new Error(`Nessuna sezione ${tuneInState.name} disponibile`)
    $('#music-navigator-tabs').innerHTML = tabs.map((tab) => `<button type="button" data-msp-tab="${esc(tab.id)}">${esc(tab.id === 'Settings' ? 'Impostazioni' : tab.name)}</button>`).join('')
    $('#music-navigator-tabs').setAttribute('aria-label', `Sezioni ${tuneInState.name}`)
    const savedTab = localStorage.getItem(`eface-msp-tab-${service}`)
    tuneInState.tab = tabs.some((tab) => tab.id === savedTab) ? savedTab : tabs[0].id
    if (service === 'tidal') {
      const account = await tuneInRequest({tab:'Settings'})
      if (/logged out/i.test(account.status || '')) tuneInState.tab = 'Settings'
    }
    await loadTuneInNavigator()
  } catch (error) { $('#music-navigator-list').innerHTML = `<p class="music-navigator-empty">${esc(error.message)}</p>` }
}

$('#music-navigator-close').addEventListener('click', () => { clearTimeout(bridgePairingTimer); $('#music-navigator-dialog').close() })
$('#music-navigator-back').addEventListener('click', () => {
  if (!tuneInState.stack.length) return
  tuneInState.stack.pop(); tuneInState.search = ''
  loadTuneInNavigator(tuneInState.stack.at(-1)?.id || '')
})
$('#music-navigator-tabs').addEventListener('click', (event) => {
  const button = event.target.closest('[data-msp-tab]')
  if (!button) return
  tuneInState.tab = button.dataset.mspTab; tuneInState.stack = []; tuneInState.search = ''
  localStorage.setItem(`eface-msp-tab-${tuneInState.service}`, tuneInState.tab)
  loadTuneInNavigator()
})
$('#music-navigator-search-toggle').addEventListener('click', () => {
  const form = $('#music-navigator-search'); form.hidden = !form.hidden
  if (!form.hidden) $('#music-navigator-query').focus()
})
$('#music-navigator-search').addEventListener('submit', (event) => {
  event.preventDefault(); tuneInState.search = $('#music-navigator-query').value.trim(); tuneInState.stack = []
  loadTuneInNavigator()
})
$('#music-navigator-more button').addEventListener('click', () => loadTuneInNavigator(tuneInState.stack.at(-1)?.id || '', true))
$('#music-navigator-list').addEventListener('click', async (event) => {
  if (tuneInState.service !== 'bridge') return
  const refreshButton = event.target.closest('[data-bridge-refresh]')
  const addButton = event.target.closest('[data-bridge-add]')
  const cancelButton = event.target.closest('[data-bridge-cancel]')
  const startButton = event.target.closest('[data-bridge-start]')
  const authButton = event.target.closest('[data-bridge-auth]')
  const removeButton = event.target.closest('[data-bridge-remove-confirm]')
  if (refreshButton) return loadTuneInNavigator()
  if (addButton) {
    document.querySelectorAll('.music-bridge-confirm').forEach((node) => node.remove())
    addButton.closest('.music-bridge-toolbar').insertAdjacentHTML('afterend', '<div class="music-bridge-confirm"><p>Avvia la ricerca Bluetooth, poi abbina il telefono al Wireless Music Bridge dalle impostazioni del telefono.</p><button type="button" data-bridge-start>Avvia abbinamento</button><button type="button" data-bridge-cancel>Annulla</button></div>')
    return
  }
  if (cancelButton) return cancelButton.closest('.music-bridge-confirm').remove()
  if (!startButton && !authButton && !removeButton) return
  const control = startButton || authButton || removeButton
  control.disabled = true
  try {
    await tuneInRequest({ action: startButton ? 'BtAddDevice' : authButton ? 'BtAuthenticate' : 'BtRemoveDevice', item_id: removeButton?.dataset.bridgeRemoveConfirm || '' })
    if (startButton) { control.closest('.music-bridge-confirm').innerHTML = '<p>Bluetooth pronto: avvia l’abbinamento dal telefono.</p>'; pollBridgePairing() }
    else if (authButton) { control.closest('.music-bridge-confirm').innerHTML = '<p>Conferma inviata. Attendo il dispositivo…</p>'; pollBridgePairing() }
    else await loadTuneInNavigator()
  } catch (error) { fail(error); control.disabled = false }
})
$('#music-navigator-list').addEventListener('click', async (event) => {
  const menuButton = event.target.closest('[data-msp-menu]')
  const selected = event.target.closest('[data-msp-select]')
  const id = menuButton?.dataset.mspMenu || selected?.dataset.mspSelect
  if (!id) return
  if (selected && tuneInState.service === 'bridge') return selected.closest('.music-navigator-row').querySelector('[data-msp-menu]')?.click()
  const item = tuneInState.items.find((entry) => entry.id === id)
  if (!item) return
  if (menuButton) {
    const existing = menuButton.parentElement.querySelector('.music-navigator-actions')
    if (existing) return existing.remove()
    document.querySelectorAll('.music-navigator-actions').forEach((node) => node.remove())
    const choices = item.actions.filter((action) => navigatorVisibleActions.has(action))
    menuButton.parentElement.insertAdjacentHTML('beforeend', `<div class="music-navigator-actions">${choices.map((action) => `<button type="button" data-msp-action="${action}" data-msp-action-item="${esc(id)}">${esc(action === 'BtConnectDisconnect' ? item.connected ? 'Disconnetti' : 'Connetti' : ({ Play: 'Play', SelectStation: 'Riproduci', PresetPlay: 'Riproduci preset', PlayRecent: 'Riproduci', PinFavorite: 'Aggiungi come preferito in e-Face', UnpinFavorite: 'Rimuovi dai preferiti in e-Face', PlayNow: 'Riproduci ora', PlayShuffle: 'Riproduci casualmente', PlayNext: 'Riproduci dopo', AddToQueue: 'Aggiungi alla coda', ReplaceQueue: 'Sostituisci coda', AddToLibrary: 'Aggiungi alla libreria', RemoveFromLibrary: 'Rimuovi dalla libreria', BtRemoveDevice: 'Rimuovi dispositivo' })[action] || action)}</button>`).join('')}</div>`)
    return
  }
  if (item.link || item.default_action === 'Browse') {
    tuneInState.stack.push({ id, title: item.title })
    return loadTuneInNavigator(id)
  }
  if (['Play', 'SelectStation', 'PresetPlay', 'PlayRecent'].includes(item.default_action) || item.actions.includes('Play')) {
    const action = ['SelectStation', 'PresetPlay', 'PlayRecent'].includes(item.default_action) ? item.default_action : 'Play'
    try { await tuneInRequest({ action, item_id: id }); $('#music-navigator-dialog').close(); refresh(); setTimeout(refresh, 2500) }
    catch (error) { fail(error) }
  }
})
$('#music-navigator-list').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-msp-action]')
  if (!button) return
  event.stopPropagation()
  if (tuneInState.service === 'bridge' && button.dataset.mspAction === 'BtRemoveDevice') {
    const item = tuneInState.items.find((entry) => entry.id === button.dataset.mspActionItem)
    document.querySelectorAll('.music-bridge-confirm').forEach((node) => node.remove())
    button.closest('.music-navigator-row').insertAdjacentHTML('afterend', `<div class="music-bridge-confirm"><p>Rimuovere “${esc(item?.title || 'questo dispositivo')}” dagli abbinamenti Bluetooth? L’operazione richiederà un nuovo abbinamento per usarlo ancora.</p><button type="button" data-bridge-remove-confirm="${esc(button.dataset.mspActionItem)}">Rimuovi dispositivo</button><button type="button" data-bridge-cancel>Annulla</button></div>`)
    return
  }
  button.disabled = true
  try {
    await tuneInRequest({ action: button.dataset.mspAction, item_id: button.dataset.mspActionItem })
    if (button.dataset.mspAction === 'BtConnectDisconnect') await loadTuneInNavigator()
    else if (['Play', 'SelectStation', 'PresetPlay', 'PlayRecent', 'PlayNow', 'PlayShuffle', 'PlayNext', 'AddToQueue', 'ReplaceQueue'].includes(button.dataset.mspAction)) { $('#music-navigator-dialog').close(); refresh(); setTimeout(refresh, 2500) }
    else { if (['PinFavorite', 'UnpinFavorite'].includes(button.dataset.mspAction)) { favoritesCache = null; await loadMediaFavorites() }; await loadTuneInNavigator(tuneInState.stack.at(-1)?.id || '') }
  } catch (error) { fail(error) }
  finally { button.disabled = false }
})

async function selectRecentlyPlayed(button) {
  button.disabled = true
  try {
    const response = await fetch(apiUrl('api/control4/recently-played/select'), { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({room_id:Number(button.dataset.recentRoom), key:button.dataset.recentKey}) })
    if (!response.ok) throw new Error((await response.json().catch(()=>({}))).detail || 'Avvio non riuscito')
    recentCache.delete(button.closest('[data-recently-played]')?.dataset.recentScope || '')
    await new Promise((resolve) => setTimeout(resolve, 500))
    await refresh()
  } catch (error) { fail(error) } finally { button.disabled = false }
}

function updateGlobalMediaSession() {
  const button = $('#global-media-session')
  const sessions = activeMediaSessions()
  const hasAudio = sessions.some(({ player }) => player.active_experience !== 'watch')
  const hasVideo = sessions.some(({ player }) => player.active_experience === 'watch')
  const mediaState = hasAudio && hasVideo ? 'mixed' : hasVideo ? 'video' : hasAudio ? 'audio' : 'none'
  button.hidden = sessions.length === 0
  button.classList.remove('media-state-audio', 'media-state-video', 'media-state-mixed')
  if (mediaState !== 'none') button.classList.add(`media-state-${mediaState}`)
  $('#mode').dataset.mediaState = mediaState
  button.querySelector('b').textContent = sessions.length
}

function activeMediaSessions() {
  const active = currentDevices.filter((item) => {
    if (item.kind !== 'media_player' || item.availability !== 'available' || item.connection_status === 'offline') return false
    const state = String(item.state).toLowerCase()
    return item.provider === 'control4' ? !['off','unavailable','unknown'].includes(state) && Boolean(item.active_experience) : ['playing','buffering'].includes(state)
  }).sort((left, right) => {
    const echoScore = (item) => item.provider === 'evoice' && (item.device_type === 'echo' || /(?:echo|alexa)/i.test(String(item.entity_id))) ? 1 : 0
    return echoScore(right) - echoScore(left)
  })
  const sessions = []
  const consumed = new Set()
  const consumedPlayback = new Set()
  for (const player of active) {
    if (consumed.has(player.registry_id)) continue
    const playbackIdentity = String(player.title ? `${player.title}|${player.artist || ''}|${player.album || ''}` : player.content_fingerprint || '').trim().toLocaleLowerCase('it')
    const playbackKey = player.provider === 'evoice' && playbackIdentity.replaceAll('|','') ? `${player.provider}|${playbackIdentity}` : ''
    if (playbackKey && consumedPlayback.has(playbackKey)) continue
    const group = mediaGroupFor(player)
    const members = group ? active.filter((item) => item.provider === player.provider && group.member_registry_ids.includes(item.registry_id)) : [player]
    members.forEach((item) => consumed.add(item.registry_id))
    // The Control4-declared owner is the canonical room even if its state is briefly stale.
    const owner = currentDevices.find((item) => item.provider === player.provider && item.registry_id === group?.owner_registry_id) || members.find((item) => String(item.state).toLowerCase() === 'playing') || player
    sessions.push({ player: owner, group, members })
    if (playbackKey) consumedPlayback.add(playbackKey)
  }
  return sessions
}

function openMediaSessions() {
  const sessions = activeMediaSessions()
  $('#media-sessions-list').innerHTML = sessions.map(({ player, members }) => {
    const volumes = members.map((item) => item.volume).filter((level) => level !== null && level !== undefined && Number.isFinite(Number(level))).map(Number)
    const volume = player.provider === 'control4' ? (Number.isFinite(Number(player.volume)) ? Number(player.volume) : 0) : (volumes.length ? Math.round(volumes.reduce((sum, level) => sum + level, 0) / volumes.length) : 0)
    const isVideo = player.active_experience === 'watch'
    const artwork = isVideo && !player.content_fingerprint && player.active_source_id ? `<span class="media-artwork media-video-source"><img src="${apiUrl(`api/control4/source-icon/${player.active_source_id}?v=${encodeURIComponent(appVersion)}`)}" alt="${esc(player.source || '')}" onerror="this.hidden=true"></span>` : mediaArtwork(player)
    return `<div class="media-session-row ${isVideo ? 'media-session-row-watch' : 'media-session-row-listen'}" data-session-device="${esc(player.id)}" role="button" tabindex="0">${artwork}${activeMediaSourceMarkup(player, 'media-session-row-source', isVideo ? 'mdi:video' : mediaSourceIcon(player.source))}<span class="media-session-row-info"><strong>${esc(player.title || player.source || player.name)}</strong><small>${esc(player.artist || player.source || '')}</small></span><button class="media-session-row-power" data-session-power="${esc(player.id)}" aria-label="Spegni intera sessione" title="Spegni intera sessione"><span class="mdi-mask" style="${mdiStyle('mdi:power', 'power')}"></span></button><label class="media-session-row-volume"><span class="mdi-mask" style="${mdiStyle('mdi:volume-high', 'volume-high')}"></span><input type="range" min="0" max="100" value="${volume}" style="--volume:${volume}%" data-session-volume="${esc(player.id)}"><b>${volume}%</b></label><span class="media-session-row-rooms"><span class="mdi-mask" style="${mdiStyle(members.length > 1 ? 'mdi:home-group' : 'mdi:plus-box-outline', 'plus-box-outline')}"></span><b>${esc(members.map((item) => item.room).join(', '))}</b></span><em class="media-session-expand"><span class="mdi-mask" style="${mdiStyle('mdi:chevron-down', 'chevron-down')}"></span></em></div>`
  }).join('') || '<p class="empty-state">Nessuna sessione attiva</p>'
  if (!$('#media-sessions-dialog').open) $('#media-sessions-dialog').showModal()
}

function openMediaRoomControl(player) {
  if (!player) return
  const group = mediaGroupFor(player)
  const master = currentDevices.find((item) => item.provider === player.provider && item.registry_id === group?.owner_registry_id) || player
  const room = master.room || master.name
  const devices = currentDevices.filter((item) => item.kind === 'media_player' && item.provider === master.provider && item.room === master.room)
  openDevices(room, devices.length ? devices : [master], { room, experience: master.active_experience || player.active_experience || '' })
}

function renderHomeMediaSessions() {
  const host = $('#home-live-media')
  const list = $('#home-live-media-list')
  if (!host || !list) return
  const sessions = activeMediaSessions()
  host.hidden = sessions.length === 0
  $('#home-live-media-count').textContent = `${sessions.length} ${sessions.length === 1 ? 'SESSIONE' : 'SESSIONI'}`
  list.innerHTML = sessions.map(({ player, members }) => {
    const video = player.active_experience === 'watch'
    const activeSource = (player.source_options || []).find((source) => Number(source.source_id) === Number(player.active_source_id) || source.label === player.source)
    const sourceId = Number(player.active_source_id || activeSource?.source_id || 0)
    const artwork = !player.content_fingerprint && player.provider === 'control4' && sourceId
      ? `<span class="home-live-art source"><img src="${apiUrl(`api/control4/source-icon/${sourceId}?v=${encodeURIComponent(appVersion)}`)}" alt="" onload="this.parentElement.classList.add('loaded')" onerror="this.hidden=true"><span class="mdi-mask" style="${mdiStyle(video ? 'mdi:television' : mediaSourceIcon(player.source), video ? 'television' : 'music-circle')}"></span></span>`
      : player.content_fingerprint
      ? `<span class="home-live-art"><img src="${mediaArtworkUrl(player)}" alt="" loading="lazy" onerror="this.hidden=true"></span>`
        : `<span class="home-live-art fallback"><span class="mdi-mask" style="${mdiStyle(video ? 'mdi:television' : mediaSourceIcon(player.source), video ? 'television' : 'music-circle')}"></span></span>`
    const rooms = members.map((item) => item.room).filter(Boolean).join(' · ')
    return `<button class="home-live-session ${video ? 'video' : 'audio'}" data-home-session="${esc(player.id)}">${artwork}<span class="home-live-info"><small>${video ? 'VIDEO' : 'AUDIO'} IN RIPRODUZIONE</small><strong>${esc(player.title || player.source || player.name)}</strong><span>${esc([player.artist || player.source, rooms].filter(Boolean).join(' · '))}</span></span><i class="home-live-eq" aria-hidden="true"><b></b><b></b><b></b><b></b><b></b><b></b><b></b><b></b></i></button>`
  }).join('')
}

function mediaArtwork(device) {
  if (device.kind !== 'media_player') return ''
  const sourceId = Number(device.active_source_id || 0)
  const fallback = device.provider === 'control4' && Number.isSafeInteger(sourceId) && sourceId > 0
    ? apiUrl(`api/control4/source-icon/${sourceId}?v=${encodeURIComponent(appVersion)}`) : ''
  if (!device.content_fingerprint) return fallback
    ? `<img class="media-artwork source-fallback" src="${esc(fallback)}" alt="" onerror="this.classList.add('missing');this.removeAttribute('src')">`
    : '<span class="media-artwork missing" aria-hidden="true"></span>'
  const source = mediaArtworkUrl(device)
  return `<img class="media-artwork" src="${esc(source)}" alt="" loading="lazy" onerror="${fallback ? `this.classList.add('source-fallback');this.onerror=()=>{this.classList.add('missing');this.removeAttribute('src')};this.src='${esc(fallback)}'` : `this.classList.add('missing');this.removeAttribute('src')`}">`
}

function mediaArtworkUrl(device) {
  return device.transport_provider === 'wiim'
    ? apiUrl(`api/wiim/artwork?fingerprint=${encodeURIComponent(device.content_fingerprint)}`)
    : apiUrl(`api/media/${encodeURIComponent(device.registry_id)}/artwork?fingerprint=${encodeURIComponent(device.content_fingerprint)}`)
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
    if (lightFilterActive) devices = devices.filter(deviceIsActiveForFilter)
  }
  if (!$('#av-filters').hidden && avRoom) devices = devices.filter((device) => device.room === avRoom)
  const signature = JSON.stringify({devices, selectedMediaId, currentMediaExperience, activeMediaRoom, avRoom, lightFilterRoom, lightFilterActive, sectionFilterMode, securitySections, currentSecurityOrder, mediaSections})
  if (signature === lastDetailSignature && $('#device-list').childElementCount) return
  lastDetailSignature = signature
  renderDeviceList(devices)
}

function deviceIsActiveForFilter(device) {
  if (device.kind === 'light') return lightIsOn(device)
  if (device.kind === 'switch') return stateIsActive(device)
  if (device.kind === 'cover') return stateIsActive(device) || Number(device.position) > 0
  if (device.kind === 'lock') return ['OPEN','OPENING','UNLOCKED'].includes(String(device.state ?? '').trim().toUpperCase())
  if (device.kind === 'climate') return !device.read_only && ['HEATING','COOLING'].includes(String(device.state).toUpperCase())
  return stateIsActive(device)
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
    return `--light-color:rgb(${color.join(',')});--light-glow:${(1 + 11 * mix).toFixed(1)}px;--light-alpha:${(.08 + .72 * mix).toFixed(2)};--card-glow:${(.07 + .44 * mix).toFixed(2)};--card-halo:${(5 + 21 * mix).toFixed(1)}px`
  }
  if (device.kind !== 'cover') return ''
  const hasPosition = device.position !== null && device.position !== undefined && device.position !== '' && Number.isFinite(Number(device.position))
  const percent = Math.max(0, Math.min(100, hasPosition ? Number(device.position) : ['OPEN', 'OPENING'].includes(state) ? 100 : 0))
  const mix = percent / 100
  const from = [170, 181, 184]
  const to = [97, 216, 242]
  const color = from.map((channel, index) => Math.round(channel + (to[index] - channel) * mix))
  return `--cover-color:rgb(${color.join(',')});--cover-glow:${(2 + 5 * mix).toFixed(1)}px;--cover-alpha:${(.12 + .3 * mix).toFixed(2)};--card-glow:${(.09 + .31 * mix).toFixed(2)}`
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
  if (device.kind === 'climate') return device.read_only ? 'device-climate-off' : state === 'HEATING' ? 'device-climate-heat' : state === 'COOLING' ? 'device-climate-cool' : 'device-climate-off'
  if (device.kind === 'media_player') return state === 'PLAYING' ? 'device-media-playing' : ''
  return ''
}

function deviceActions(device, options = {}) {
  if (['light', 'switch'].includes(device.kind)) {
    const active = ['ON','1','TRUE'].includes(String(device.state).trim().toUpperCase())
    const level = active ? brightness255(device) : 0
    const percent = Math.round(level / 255 * 100)
    const dimmer = device.kind === 'light' && device.dimmable ? `<label class="dimmer-control ${active ? 'active' : ''}" style="--level:${percent}%"><input type="range" min="0" max="255" value="${level}" data-brightness><output>${percent}%</output></label>` : ''
    return dimmer
  }
  if (device.kind === 'cover') {
    const garage = /garage|portone/i.test(`${device.icon || ''} ${device.name || ''}`)
    return `<div class="device-actions"><button data-action="open">${garage ? 'APRI' : 'SU'}</button><button data-action="stop">STOP</button><button data-action="close">${garage ? 'CHIUDI' : 'GIÙ'}</button></div>`
  }
  if (device.kind === 'lock') return `<div class="device-actions"><button data-action="unlock" aria-label="Apri ${esc(device.name)}" title="Apri"><span class="mdi-mask" style="${mdiStyle(lockActionIcon(device, true), 'lock-open-outline')}"></span>APRI</button><button data-action="lock" aria-label="Chiudi ${esc(device.name)}" title="Chiudi"><span class="mdi-mask" style="${mdiStyle(lockActionIcon(device, false), 'lock-outline')}"></span>CHIUDI</button></div>`
  if (device.kind === 'climate') {
    const target = Number(device.target_temperature)
    const value = Number.isFinite(target) ? target : 20
    if (device.read_only) return `<div class="climate-summary climate-read-only"><span>UR ${device.humidity ?? '--'}%</span><span>SONDA ESTERNA</span></div>`
    const enabled = !['', 'OFF', 'NONE'].includes(String(device.mode || '').toUpperCase())
    const heat = enabled && String(device.season || '').toUpperCase() === 'WIN'
    const cool = enabled && String(device.season || '').toUpperCase() === 'SUM'
    return `<div class="climate-summary"><span>UR ${device.humidity ?? '--'}%</span><span>${device.season === 'SUM' ? 'ESTATE' : 'INVERNO'}</span><span>PWM ${device.pwm ?? 0}%</span></div><div class="climate-mode-actions"><button class="heat ${heat ? 'active' : ''}" data-climate-season="WIN">HEAT</button><button class="cool ${cool ? 'active' : ''}" data-climate-season="SUM">COOL</button><button class="off ${!heat && !cool ? 'active' : ''}" data-climate-mode="OFF">OFF</button></div><div class="device-actions"><button data-climate-target="${(value - .5).toFixed(1)}">−</button><strong>${value.toFixed(1)}°</strong><button data-climate-target="${(value + .5).toFixed(1)}">＋</button></div>`
  }
  if (device.kind === 'media_player') {
    const caps = device.capabilities || {}
    const disabled = device.connection_status === 'offline' || device.availability !== 'available'
    const button = (operation, icon, label, enabled = false, className = '') => enabled ? `<button class="${className}" data-media-action="${operation}" aria-label="${label}" ${disabled ? 'disabled' : ''}><span class="mdi-mask" style="${mdiStyle(`mdi:${icon}`, icon)}"></span></button>` : ''
    const wiimButton = (action, icon, label) => `<button data-wiim-action="${action}" aria-label="${label}"><span class="mdi-mask" style="${mdiStyle(`mdi:${icon}`, icon)}"></span></button>`
    const controls = [button('video_remote_menu', 'remote-tv', 'Telecomando video', device.active_experience === 'watch' && device.active_source_id), options.wiim ? wiimButton('shuffle', 'shuffle-variant', 'Riproduzione casuale WiiM') : button('media_shuffle', 'shuffle-variant', 'Riproduzione casuale', caps.shuffle), button('media_previous', 'skip-previous', 'Precedente', caps.previous), String(device.state).toLowerCase() === 'playing' ? button('media_pause', 'pause', 'Pausa', caps.pause, 'primary') : button('media_play', 'play', 'Riproduci', caps.play, 'primary'), button('media_next', 'skip-next', 'Successivo', caps.next), options.wiim ? wiimButton('repeat', 'repeat', 'Ripetizione WiiM') : button('media_repeat', 'repeat', 'Ripeti', caps.repeat), button('media_stop', 'stop', 'Stop', caps.stop && currentMediaExperience !== 'listen'), button('turn_off', 'power', 'Spegni stanza', caps.turn_off && !options.hidePower), button('media_zones', 'plus-box-outline', 'Aggiungi stanze', caps.grouping), options.nowPlayingFavorite ? `<button type="button" class="media-now-playing-favorite" data-now-playing-favorite aria-label="Aggiungi ai Preferiti e-Face" aria-pressed="false" title="Aggiungi ai Preferiti e-Face">★</button>` : ''].join('')
    const mute = caps.mute ? button(device.muted ? 'volume_unmute' : 'volume_mute', device.muted ? 'volume-off' : 'volume-high', device.muted ? 'Riattiva audio' : 'Disattiva audio', true, 'media-volume-mute') : '<span></span>'
    const mediaVolume = Number(device.volume) || 0
    const volume = caps.set_volume ? `<label class="media-volume">${mute}<input type="range" min="0" max="100" step="1" value="${mediaVolume}" style="--volume:${mediaVolume}%" data-media-volume ${disabled ? 'disabled' : ''}><output>${mediaVolume}%</output></label>` : ''
    const sourceOptions = device.source_options?.length ? device.source_options.filter((source) => (!currentMediaExperience || source.experience === currentMediaExperience) && !hiddenSourceIds.has(Number(source.source_id))) : (device.source_list || []).map((source) => ({key:source,label:source}))
    const sources = caps.select_source && sourceOptions.length ? `<div class="media-sources">${sourceOptions.map((source) => `<button data-media-source="${esc(source.key)}" class="${source.label === device.source ? 'active' : ''}" ${disabled ? 'disabled' : ''}>${mediaSourceMarkup(source, device.provider)}<b>${esc(source.label)}</b></button>`).join('')}</div>` : ''
    return `<div class="media-controls">${controls}</div>${volume}${sources}`
  }
  return ''
}

async function postDeviceCommand(deviceId, action, value, resourceRevision = null, pin = null) {
  const payload = { action, value, resource_revision: resourceRevision }
  if (pin !== null) payload.pin = pin
  const response = await fetch(apiUrl(`api/devices/${encodeURIComponent(deviceId)}/command`), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
}

let pendingSecurityCommand = null
let activeSecurityArea = null

function openSecurityArea(device) {
  activeSecurityArea = device
  const armed = device.state === 'ARMED' || device.state === 'ALARM'
  const memory = device.alarm_memory || device.tamper_memory
  const icon = device.state === 'ALARM' || device.state === 'TAMPER' ? 'mdi:shield-alert' : armed ? 'mdi:shield-lock' : memory ? 'mdi:history' : 'mdi:shield-check'
  const colorClass = device.state === 'ALARM' || device.state === 'TAMPER' || device.arm_mode === 'instant' ? 'instant' : armed ? 'delayed' : memory ? 'memory' : 'ready'
  $('#security-area-dialog').className = `security-area-dialog ${colorClass}`
  $('#security-area-title').textContent = device.name
  $('#security-area-icon').style.cssText = mdiStyle(icon, 'shield-home')
  $('#security-area-popup-actions').innerHTML = armed
    ? '<button data-area-action="disarm">Disinserisci</button>'
    : '<button data-area-action="arm_instant">Inserisci</button><button data-area-action="arm_delay">Inserisci con ritardo</button>'
  $('#security-area-dialog').showModal()
}

function requestSecurityPin(deviceId, action, button) {
  const device = currentDevices.find((item) => String(item.id) === String(deviceId))
  const operation = action === 'execute' ? 'Esegui scenario' : action === 'disarm' ? 'Disinserisci area' : action.startsWith('arm_') ? 'Inserisci area' : action === 'bypass_on' ? 'Escludi zona' : 'Includi zona'
  pendingSecurityCommand = { deviceId, action, button }
  $('#security-pin-operation').textContent = `${device?.name || 'Sicurezza'} · ${operation}`
  $('#security-pin-error').textContent = ''
  $('#security-pin-input').value = ''
  $('#security-pin-dialog').showModal()
}

function applySecurityCommandState(deviceId, action) {
  const device = currentDevices.find((item) => String(item.id) === String(deviceId))
  if (!device) return
  if (device.kind === 'alarm_partition') {
    if (action === 'disarm') Object.assign(device, { state: 'DISARMED', arm_state: 'D', arm_mode: 'off', alarm: false })
    if (action === 'arm_delay') Object.assign(device, { state: 'ARMED', arm_state: 'A', arm_mode: 'delayed' })
    if (action === 'arm_instant') Object.assign(device, { state: 'ARMED', arm_state: 'IA', arm_mode: 'instant' })
  }
  if (device.kind === 'alarm_zone') {
    if (action === 'bypass_on') Object.assign(device, { state: 'BYPASSED', bypassed: true })
    if (action === 'bypass_off') Object.assign(device, { state: device.active ? 'ACTIVE' : 'CLOSED', bypassed: false })
  }
  renderActiveDeviceList()
}

async function submitSecurityPin(event) {
  event.preventDefault()
  if (!pendingSecurityCommand) return
  const pin = $('#security-pin-input').value.trim()
  const confirmButton = $('#security-pin-confirm')
  if (!pin) { $('#security-pin-error').textContent = 'Inserisci il codice di sicurezza'; return }
  const command = pendingSecurityCommand
  confirmButton.disabled = true
  $('#security-pin-input').value = ''
  $('#security-pin-dialog').close()
  pendingSecurityCommand = null
  try {
    await postDeviceCommand(command.deviceId, command.action, null, null, pin)
    applySecurityCommandState(command.deviceId, command.action)
    await refresh()
    setTimeout(refresh, 700)
    setTimeout(refresh, 1800)
  } catch (error) {
    fail(new Error(`Sicurezza: ${error.message || 'operazione non riuscita'}`))
  } finally { confirmButton.disabled = false }
}

function openMediaZones(device) {
  activeMediaPlayer = device
  renderMediaZones()
  $('#media-zones-dialog').showModal()
}

function mediaGroupFor(device) {
  const groupId = device?.group?.group_id
  return currentMediaGroups.find((group) => group.group_id === groupId && group.member_registry_ids?.includes(device?.registry_id)) || device?.group || null
}

function renderMediaZones() {
  const selected = activeMediaPlayer
  if (!selected) return
  const group = mediaGroupFor(selected)
  const members = new Set(group?.member_registry_ids || [selected.registry_id])
  const allPlayers = currentDevices.filter((item) => item.kind === 'media_player' && item.provider === selected.provider)
  const sourceId = Number(selected.active_source_id)
  const experience = selected.active_experience
  $('#media-zones-dialog').classList.toggle('media-zones-watch', experience === 'watch')
  $('#media-zones-dialog').classList.toggle('media-zones-listen', experience !== 'watch')
  const compatible = (item) => !sourceId || item.provider !== 'control4' || (item.source_options || []).some((source) => Number(source.source_id) === sourceId && (!experience || source.experience === experience))
  const players = allPlayers.filter((item) => members.has(item.registry_id) || compatible(item))
  const playing = players.filter((item) => members.has(item.registry_id) && !['off','unavailable','unknown'].includes(String(item.state).toLowerCase()))
  const owner = players.find((item) => item.registry_id === group?.owner_registry_id) || selected
  const memberVolumes = playing.map((item) => item.volume).filter((level) => level !== null && level !== undefined && Number.isFinite(Number(level))).map(Number)
  const masterVolume = selected.provider === 'control4' ? (Number.isFinite(Number(owner.volume)) ? Number(owner.volume) : 0) : (memberVolumes.length ? Math.round(memberVolumes.reduce((sum, level) => sum + level, 0) / memberVolumes.length) : 0)
  const muteMembers = playing.filter((item) => item.capabilities?.mute)
  const allMuted = muteMembers.length > 0 && muteMembers.every((item) => item.muted)
  const source = `<div class="media-session-source"><span class="mdi-mask" style="${mdiStyle(mediaSourceIcon(selected.source), 'music-circle')}"></span><div><strong>${esc(selected.source || 'Fonte audio')}</strong><b>${esc(selected.title || selected.name)}</b><small>${esc(selected.artist || selected.album || '')}</small></div></div>`
  const master = group?.group_id ? `<div class="media-session-master"><small>VOLUME GENERALE</small><div class="media-session-master-level"><button type="button" class="media-zone-mute" data-group-mute aria-label="${allMuted ? 'Riattiva tutte le stanze' : 'Disattiva audio in tutte le stanze'}" title="${allMuted ? 'Riattiva tutte le stanze' : 'Disattiva audio in tutte le stanze'}" ${muteMembers.length ? '' : 'disabled'}><span class="mdi-mask" style="${mdiStyle(allMuted ? 'mdi:volume-off' : 'mdi:volume-high', 'volume-high')}"></span></button><input type="range" min="0" max="100" value="${masterVolume}" style="--volume:${masterVolume}%" data-group-volume data-base-volume="${masterVolume}" ${group.completeness !== 'complete' ? 'disabled' : ''}><output>${masterVolume}%</output></div></div>` : ''
  const powerAll = `<button class="media-session-power-all" data-session-power-all aria-label="Spegni intera sessione" title="Spegni intera sessione"><span class="mdi-mask" style="${mdiStyle('mdi:power', 'power')}"></span></button>`
  $('#zones-master').innerHTML = source + master + powerAll
  const activeRows = playing.map((player) => {
    const volume = Number.isFinite(Number(player.volume)) ? Number(player.volume) : 0
    const power = player.capabilities?.turn_off ? `<button class="media-zone-power" data-zone-power="${esc(player.id)}" aria-label="Spegni ${esc(player.room)}" title="Spegni ${esc(player.room)}"><span class="mdi-mask" style="${mdiStyle('mdi:power', 'power')}"></span></button>` : ''
    return `<div class="media-zone media-zone-playing"><div class="media-zone-name"><b>${esc(player.room)}</b><small>${esc(player.name)}</small></div>${power}<div class="media-zone-level"><button type="button" class="media-zone-mute" data-zone-mute="${esc(player.id)}" aria-label="${player.muted ? 'Riattiva' : 'Disattiva audio in'} ${esc(player.room)}" title="${player.muted ? 'Riattiva audio' : 'Disattiva audio'}" ${player.capabilities?.mute ? '' : 'disabled'}><span class="mdi-mask" style="${mdiStyle(player.muted ? 'mdi:volume-off' : 'mdi:volume-high', 'volume-high')}"></span></button><input type="range" min="0" max="100" value="${volume}" style="--volume:${volume}%" data-zone-volume data-base-volume="${volume}" data-device-id="${esc(player.id)}" ${!player.capabilities?.set_volume ? 'disabled' : ''}><output>${volume}%</output></div></div>`
  }).join('')
  const choices = players.map((player) => {
    const checked = members.has(player.registry_id)
    const unavailable = player.connection_status === 'offline' || player.availability !== 'available'
    const locked = player.registry_id === selected.registry_id || player.registry_id === group?.owner_registry_id || unavailable
    return `<label class="media-zone-choice ${checked ? 'active' : ''} ${unavailable ? 'unavailable' : ''}"><span><b>${esc(player.room)}</b><small>${checked ? 'In riproduzione' : 'Disponibile'}</small></span><input type="checkbox" value="${esc(player.registry_id)}" ${checked ? 'checked' : ''} ${locked ? 'disabled' : ''}><i></i></label>`
  }).join('')
  $('#media-zones-list').innerHTML = `<button class="media-library-toggle media-zones-toggle" data-media-zones-toggle="playing" aria-expanded="${mediaSections.playing}"><strong>Stanze in riproduzione</strong><span class="mdi-mask" style="${mdiStyle(mediaSections.playing ? 'mdi:chevron-up' : 'mdi:chevron-down', 'chevron-down')}"></span></button><div class="media-playing-list" ${mediaSections.playing ? '' : 'hidden'}>${activeRows}</div><button class="media-zone-add" data-zone-picker-toggle aria-label="Aggiungi o rimuovi stanze" title="Aggiungi o rimuovi stanze"><span class="mdi-mask" style="${mdiStyle('mdi:plus-box-outline', 'plus-box-outline')}"></span></button><div class="media-zone-picker" hidden>${choices}</div>`
}

async function saveMediaZones(button) {
  if (!activeMediaPlayer) return
  button.disabled = true
  const group = mediaGroupFor(activeMediaPlayer)
  const current = new Set(group?.member_registry_ids || [activeMediaPlayer.registry_id])
  const desired = new Set([...document.querySelectorAll('.media-zone-picker input:checked')].map((input) => input.value))
  const additions = [...desired].filter((id) => !current.has(id))
  const removals = [...current].filter((id) => !desired.has(id) && id !== activeMediaPlayer.registry_id)
  try {
    for (const registryId of removals) {
      const player = currentDevices.find((item) => item.registry_id === registryId)
      if (player) await postDeviceCommand(player.id, 'media_unjoin', null, player.resource_revision)
    }
    if (additions.length) await postDeviceCommand(activeMediaPlayer.id, 'media_join', additions, activeMediaPlayer.resource_revision)
    if ($('#media-zones-dialog').open) $('#media-zones-dialog').close()
    if ($('#media-sessions-dialog').open) $('#media-sessions-dialog').close()
    await refresh()
  } catch (error) { fail(error) } finally { button.disabled = false }
}

async function powerOffMediaSession(button, deviceIds) {
  const ids = [...new Set(deviceIds.filter(Boolean))]
  if (!ids.length) return
  button.disabled = true
  try {
    const results = await Promise.allSettled(ids.map((id) => postDeviceCommand(id, 'turn_off')))
    const failed = results.find((result) => result.status === 'rejected')
    if (failed) throw failed.reason
    ids.forEach((id) => {
      setMediaOverride(id, { state: 'off', expires: Date.now() + 5000 })
      const player = currentDevices.find((item) => String(item.id) === String(id))
      if (player) player.state = 'off'
    })
    if ($('#media-sessions-dialog').open) openMediaSessions()
    await new Promise((resolve) => setTimeout(resolve, 450))
    await refresh()
    if ($('#media-sessions-dialog').open) openMediaSessions()
    if ($('#media-zones-dialog').open) {
      activeMediaPlayer = currentDevices.find((item) => String(item.id) === String(activeMediaPlayer?.id)) || activeMediaPlayer
      renderMediaZones()
    }
  } catch (error) { fail(error) } finally { button.disabled = false }
}

function openVideoRemote(device) {
  const source = (device.source_options || []).find((item) => Number(item.source_id) === Number(device.active_source_id) && item.experience === 'watch')
  if (!source) return fail(new Error('Telecomando video non disponibile'))
  activeVideoRemote = { device, source }
  const actions = new Set(source.remote_actions || [])
  const make = (action, label) => actions.has(action) ? `<button data-remote-command="${esc(action)}">${label}</button>` : ''
  const icon = (action, name, label, className = '') => actions.has(action) ? `<button class="remote-icon ${className}" data-remote-command="${esc(action)}" aria-label="${label}" title="${label}"><span class="mdi-mask" style="${mdiStyle(`mdi:${name}`, name)}"></span></button>` : ''
  const quick = [['dvr','DVR'],['guide','GUIDA'],['recall','RICHIAMA'],['menu','MENU'],['cancel','ANNULLA'],['info','INFO'],['input','INGRESSO']].map(([a,l]) => make(a,l)).join('')
  const nav = [['up','▲'],['left','◀'],['enter','SELEZIONA'],['right','▶'],['down','▼']].map(([a,l]) => make(a,l)).join('')
  const digits = ['1','2','3','4','5','6','7','8','9','star','0','pound'].map((key) => make(key.length === 1 ? `digit_${key}` : key, key === 'star' ? '*' : key === 'pound' ? '#' : key)).join('')
  const transport = [icon('scan_rev','rewind','Riavvolgi'),icon('scan_fwd','fast-forward','Avanti veloce'),icon('skip_rev','skip-previous','Precedente'),icon('play','play','Riproduci'),icon('skip_fwd','skip-next','Successivo'),icon('record','record-circle','Registra','remote-record'),icon('pause','pause','Pausa'),icon('stop','stop','Stop')].join('')
  const pages = [make('page_up','▲<small>PG</small>'),make('page_down','<small>PG</small>▼')].join('')
  const channels = `${make('channel_up','⌃')}<span>CH</span>${make('channel_down','⌄')}`
  const volume = device.capabilities?.set_volume ? `<div class="remote-volume-side"><button data-remote-volume-step="2">＋</button><span>VOL</span><button data-remote-volume-step="-2">−</button></div><label class="remote-volume-slider"><span class="mdi-mask" style="${mdiStyle(device.muted ? 'mdi:volume-off' : 'mdi:volume-high','volume-high')}"></span><input type="range" min="0" max="100" value="${Number(device.volume) || 0}" data-remote-volume><output>${Number(device.volume) || 0}</output></label>` : ''
  const custom = [['custom:PROGRAM_A','red','Rosso'],['custom:PROGRAM_B','green','Verde'],['custom:PROGRAM_C','yellow','Giallo'],['custom:PROGRAM_D','blue','Blu']].filter(([action]) => actions.has(action)).map(([action,color,label]) => `<button class="remote-color remote-${color}" data-remote-command="${action}" aria-label="${label}" title="${label}"><span></span></button>`).join('')
  $('#video-remote-title').textContent = `${source.label} · ${device.room}`
  $('#video-remote-body').innerHTML = quick || nav || digits || transport ? `<div class="remote-console"><div class="remote-quick">${quick}</div>${volume}<div class="remote-transport">${transport}${pages}</div><div class="remote-nav">${nav}</div><div class="remote-keypad">${digits}</div><div class="remote-channel-side">${channels}</div>${custom ? `<div class="remote-custom">${custom}</div>` : ''}</div>` : '<p class="remote-empty">Questo apparato non espone comandi telecomando.</p>'
  $('#video-remote-dialog').showModal()
}

async function sendVideoRemote(action, button) {
  if (!activeVideoRemote) return
  button.disabled = true
  try {
    if (action === 'off') await postDeviceCommand(activeVideoRemote.device.id, 'turn_off')
    else await postDeviceCommand(activeVideoRemote.device.id, 'video_remote', { source_id: activeVideoRemote.source.source_id, command: action })
  } catch (error) { fail(error) }
  finally { button.disabled = false }
}

async function setMediaGroupVolume(input) {
  const group = mediaGroupFor(activeMediaPlayer)
  if (!group?.group_id) return
  const targets = [...document.querySelectorAll('#media-zones-list [data-zone-volume]')].map((slider) => ({
    player: currentDevices.find((item) => String(item.id) === String(slider.dataset.deviceId)),
    level: Math.max(0, Math.min(100, Number(slider.value))),
  })).filter((target) => target.player)
  if (!targets.length) return
  input.disabled = true
  try {
    // INVARIANTE: master = delta relativo; ogni volume stanza resta comandato da Control4.
    const results = await Promise.allSettled(targets.map(({ player, level }) => postDeviceCommand(player.id, 'set_volume', level)))
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        targets[index].player.volume = targets[index].level
        setMediaOverride(targets[index].player.id, { volume: targets[index].level })
      }
    })
    const failed = results.find((result) => result.status === 'rejected')
    if (failed) throw failed.reason
    await refresh()
  } catch (error) { fail(error) } finally { input.disabled = false }
}

async function toggleMediaZoneMute(button, all) {
  const group = mediaGroupFor(activeMediaPlayer)
  const members = new Set(group?.member_registry_ids || [activeMediaPlayer?.registry_id])
  const players = currentDevices.filter((item) => item.kind === 'media_player' && item.provider === activeMediaPlayer?.provider && members.has(item.registry_id) && item.capabilities?.mute && !['off','unavailable','unknown'].includes(String(item.state).toLowerCase()))
  const targets = all ? players : players.filter((item) => String(item.id) === String(button.dataset.zoneMute))
  if (!targets.length) return
  const muted = all ? !targets.every((item) => item.muted) : !targets[0].muted
  button.disabled = true
  try {
    const results = await Promise.allSettled(targets.map((item) => postDeviceCommand(item.id, muted ? 'volume_mute' : 'volume_unmute')))
    results.forEach((result, index) => { if (result.status === 'fulfilled') { targets[index].muted = muted; setMediaOverride(targets[index].id, { muted }) } })
    await refresh()
    renderMediaZones()
    const failed = results.find((result) => result.status === 'rejected')
    if (failed) throw failed.reason
  } catch (error) { fail(error) } finally { button.disabled = false }
}

async function setSessionVolume(input) {
  const session = activeMediaSessions().find(({ player }) => String(player.id) === String(input.dataset.sessionVolume))
  if (!session) return
  const value = Number(input.value)
  const levels = session.members.map((player) => player.volume).filter((level) => level !== null && level !== undefined && Number.isFinite(Number(level))).map(Number)
  const reference = session.player.provider === 'control4' ? Number(session.player.volume) : (levels.length ? Math.round(levels.reduce((sum, level) => sum + level, 0) / levels.length) : value)
  const delta = value - (Number.isFinite(reference) ? reference : value)
  input.disabled = true
  try {
    if (session.group?.group_id && session.members.length > 1) {
      // 40/50 + 10 => 50/60. Non inviare mai lo stesso valore assoluto a tutte le stanze.
      const targets = session.members.map((player) => ({ player, level: Number.isFinite(Number(player.volume)) ? Math.max(0, Math.min(100, Number(player.volume) + delta)) : value }))
      const results = await Promise.allSettled(targets.map(({ player, level }) => postDeviceCommand(player.id, 'set_volume', level)))
      const failed = results.find((result) => result.status === 'rejected')
      if (failed) throw failed.reason
    } else {
      await postDeviceCommand(session.player.id, 'set_volume', value)
    }
    session.members.forEach((player) => {
      const level = Number.isFinite(Number(player.volume)) ? Math.max(0, Math.min(100, Number(player.volume) + delta)) : value
      player.volume = level
      setMediaOverride(player.id, { volume: level })
    })
    await refresh()
  } catch (error) { fail(error) } finally { input.disabled = false }
}

async function adjustActiveUiVolume(delta) {
  if ($('#video-remote-dialog').open && activeVideoRemote?.device) {
    const input = $('#video-remote-dialog').querySelector('[data-remote-volume]')
    if (input) { input.value = Math.max(0, Math.min(100, Number(input.value) + delta)); input.dispatchEvent(new Event('change', { bubbles: true })); return true }
  }
  if ($('#media-zones-dialog').open) {
    const input = $('#zones-master').querySelector('[data-group-volume]') || $('#media-zones-list').querySelector('[data-zone-volume]')
    if (input) { input.value = Math.max(0, Math.min(100, Number(input.value) + delta)); input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); return true }
  }
  if ($('#media-sessions-dialog').open) {
    const input = $('#media-sessions-list').querySelector('[data-session-volume]')
    if (input) { input.value = Math.max(0, Math.min(100, Number(input.value) + delta)); input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true })); return true }
  }
  const roomPlayer = currentDevices.find((item) => item.kind === 'media_player' && activeDetailIds?.has(String(item.id)) && stateIsActive(item))
  if (roomPlayer) { await sendDeviceCommand(roomPlayer.id, 'set_volume', null, Math.max(0, Math.min(100, Number(roomPlayer.volume || 0) + delta))); return true }
  return false
}

async function sendDeviceCommand(deviceId, action, button, value) {
  if (button) button.disabled = true
  try {
    await postDeviceCommand(deviceId, action, value)
    const climate = currentDevices.find((item) => String(item.id) === String(deviceId) && item.kind === 'climate')
    if (climate) {
      if (action === 'set_season') {
        climate.season = String(value).toUpperCase()
        if (['', 'OFF', 'NONE'].includes(String(climate.mode || '').toUpperCase())) climate.mode = 'MAN'
      }
      if (action === 'set_mode' && String(value).toUpperCase() === 'OFF') {
        climate.mode = 'OFF'
        climate.state = 'OFF'
      }
      if (action === 'set_target') climate.target_temperature = Number(value)
      renderActiveDeviceList()
      updateNavigationStates()
    }
    const media = currentDevices.find((item) => String(item.id) === String(deviceId) && item.kind === 'media_player')
    if (media) {
      if (action === 'volume_mute') media.muted = true
      if (action === 'volume_unmute') media.muted = false
      if (action === 'set_volume') media.volume = Number(value)
      if (action === 'media_pause') media.state = 'paused'
      if (action === 'media_play') media.state = 'playing'
      if (action === 'media_stop') media.state = 'idle'
      if (action === 'turn_off') media.state = 'off'
      if (action === 'volume_mute') setMediaOverride(deviceId, { muted: true })
      if (action === 'volume_unmute') setMediaOverride(deviceId, { muted: false })
      if (action === 'set_volume') setMediaOverride(deviceId, { volume: Number(value) })
      if (action === 'media_pause') setMediaOverride(deviceId, { state: 'paused', fingerprint: media.content_fingerprint || '', expires: 0 })
      if (action === 'media_stop') setMediaOverride(deviceId, { state: 'idle', fingerprint: media.content_fingerprint || '', expires: 0 })
      if (action === 'media_play') setMediaOverride(deviceId, { state: 'playing', expires: Date.now() + 3000 })
      if (['turn_off','media_next','media_previous','select_source'].includes(action)) mediaTransportOverrides.delete(String(deviceId))
      renderActiveDeviceList()
      updateNavigationStates()
    }
    const refreshDelay = ['set_season', 'set_mode'].includes(action) ? 1200 : ['media_next','media_previous','select_source'].includes(action) ? 900 : 250
    window.setTimeout(refresh, refreshDelay)
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

function closeIntercom() {
  $('#intercom-view').hidden = true
  $('#intercom-frame').contentWindow?.postMessage({type:'eface-intercom-visible',visible:false}, location.origin)
}

function openIntercom() {
  stopEnergyRefresh()
  applyBackground('')
  activeDetailIds = null
  $('#home-view').hidden = true
  $('#detail-view').hidden = true
  $('#energy-view').hidden = true
  $('#intercom-view').hidden = false
  if (!$('#intercom-frame').getAttribute('src')) $('#intercom-frame').src = apiUrl('intercom?embedded=1')
  $('#intercom-frame').contentWindow?.postMessage({type:'eface-intercom-visible',visible:true}, location.origin)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openDevices(title, devices, options = {}) {
  closeIntercom()
  $('#energy-view').hidden = true
  const mediaOnly = devices.length > 0 && devices.every((device) => device.kind === 'media_player')
  activeMediaRoom = options.room && mediaOnly ? options.room : ''
  currentMediaExperience = options.experience || ''
  const backgroundRooms = [...new Set(devices.map((device)=>device.room).filter(Boolean))]
  applyBackground(options.room || (backgroundRooms.length === 1 ? backgroundRooms[0] : ''))
  activeDetailIds = new Set(devices.map((device) => String(device.id)))
  lastDetailSignature = ''
  $('#detail-title').textContent = title
  sectionFilterMode = 'devices'
  sectionFilterDevices = devices
  lightFilterRoom = ''
  lightFilterActive = false
  $('#light-room-toggle').classList.remove('active')
  $('#light-room-toggle').setAttribute('aria-expanded', 'false')
  $('#light-room-menu').hidden = true
  $('#light-all-filter').classList.add('active')
  $('#light-on-filter').classList.remove('active')
  $('#light-on-filter').setAttribute('aria-pressed', 'false')
  $('#light-filters').hidden = !options.filters
  $('#av-filters').hidden = true
  if (options.filters) configureLightFilters(devices)
  renderActiveDeviceList()
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  $('#detail-view').classList.toggle('av-view', Boolean(options.av))
  $('#detail-view').classList.toggle('media-room-view', Boolean(options.room && mediaOnly))
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openScenariosPage() {
  closeIntercom()
  $('#energy-view').hidden = true
  applyBackground('')
  activeDetailIds = null
  $('#detail-title').textContent = 'Scenari'
  sectionFilterMode = 'scenarios'
  sectionFilterDevices = []
  lightFilterRoom = ''
  lightFilterActive = false
  $('#light-room-toggle').classList.remove('active')
  $('#light-all-filter').classList.add('active')
  $('#light-on-filter').classList.remove('active')
  $('#light-on-filter').setAttribute('aria-pressed', 'false')
  $('#light-filters').hidden = false
  $('#av-filters').hidden = true
  $('#device-list').hidden = true
  $('#scenario-panel').hidden = false
  $('#home-view').hidden = true
  $('#detail-view').hidden = false
  $('#detail-view').classList.remove('av-view')
  $('#detail-view').classList.remove('media-room-view')
  loadScenarios()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadScenarios() {
  try {
    const response = await fetch(apiUrl('api/scenarios'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    currentScenarios = (await response.json()).items || []
    configureLightFilters(currentScenarios)
    renderScenarios()
  } catch (error) { fail(error) }
}

function renderScenarios() {
  updateNavigationStates()
  let scenarios = currentScenarios
  if (lightFilterRoom) scenarios = scenarios.filter((scenario) => scenario.room === lightFilterRoom)
  if (lightFilterActive) scenarios = scenarios.filter((scenario) => scenario.running || ['ON','1','TRUE'].includes(String(scenario.state ?? '').toUpperCase()))
  $('#scenario-list').innerHTML = scenarios.map((scenario) => {
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
  closeIntercom()
  stopEnergyRefresh()
  applyBackground('')
  activeDetailIds = null
  $('#detail-view').hidden = true
  $('#energy-view').hidden = true
  $('#detail-view').classList.remove('av-view')
  $('#detail-view').classList.remove('media-room-view')
  $('#home-view').hidden = false
  $('#scenario-panel').hidden = true
  $('#device-list').hidden = false
  $('#light-filters').hidden = true
  $('#av-filters').hidden = true
  document.querySelectorAll('.rail button').forEach((item) => item.classList.remove('active'))
}

function openEnergy() {
  closeIntercom()
  applyBackground('')
  activeDetailIds = null
  $('#home-view').hidden = true
  $('#detail-view').hidden = true
  $('#energy-view').hidden = false
  showEnergyPicker()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function showEnergyPicker() {
  activeEnergyDashboard = null
  $('#energy-title').textContent = 'Dashboard energia'
  $('#energy-picker').hidden = false
  $('#energy-frame-shell').hidden = true
  $('#energy-reload').hidden = true
  startEnergyRefresh()
}

function stopEnergyRefresh() {
  clearInterval(energyRefreshTimer)
  energyRefreshTimer = null
}

function startEnergyRefresh() {
  stopEnergyRefresh()
  loadEnergyDashboards(true)
  energyRefreshTimer = setInterval(() => {
    if ($('#energy-view').hidden || activeEnergyDashboard) return stopEnergyRefresh()
    loadEnergyDashboards(false)
  }, 2000)
}

async function loadEnergyDashboards(showLoading = true) {
  if (energyRefreshRunning) return
  energyRefreshRunning = true
  const picker = $('#energy-dashboard-grid')
  if (showLoading) picker.innerHTML = '<span class="empty-state">Caricamento dashboard…</span>'
  try {
    const response = await fetch(apiUrl('api/sunmind/api/data'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const energy = (await response.json()).energy || {}
    const sites = Array.isArray(energy.sites) && energy.sites.length ? energy.sites : [energy]
    const power = (value) => { const watts = Number(value); return Number.isFinite(watts) ? Math.abs(watts) >= 1000 ? `${(watts / 1000).toFixed(1)} kW` : `${Math.round(watts)} W` : '--' }
    const flowState = (live) => {
      const threshold = 100
      const pv = Number(live.pv_power_w) || 0
      const grid = Number(live.grid_power_w) || 0
      const battery = Number(live.battery_power_w) || 0
      if (grid > threshold) return { key: 'export', icon: 'mdi:transmission-tower-export', label: 'Immissione in rete', watts: grid }
      if (grid < -threshold) return { key: 'grid', icon: 'mdi:transmission-tower-import', label: 'Consumo dalla rete', watts: -grid }
      if (battery > threshold) return { key: 'battery', icon: 'mdi:battery-arrow-up', label: 'Consumo da batteria', watts: battery }
      if (pv > threshold) return { key: 'solar', icon: 'mdi:solar-power-variant', label: 'Produzione fotovoltaica', watts: pv }
      return { key: 'idle', icon: 'mdi:home-outline', label: 'Flusso minimo', watts: Math.max(0, pv, Math.abs(grid), Math.abs(battery)) }
    }
    const masterFlows = []
    picker.innerHTML = sites.map((site, index) => {
      const id = String(site.site_id || site.id || energy.selected_site_id || 'default')
      const name = String(site.site_name || site.name || `Impianto ${index + 1}`)
      const live = site.normalized || (id === energy.site_id ? energy.normalized : {}) || {}
      const battery = Number(live.battery_power_w) || 0
      const batterySoc = Number(live.battery_soc_pct)
      const grid = Number(live.grid_power_w) || 0
      const flow = flowState(live)
      masterFlows.push(flow.key)
      const batteryFlow = Math.abs(battery) < 1
        ? { key: 'idle', icon: 'mdi:battery-outline', label: 'BATTERIA' }
        : battery < 0
        ? { key: 'charge', icon: 'mdi:battery-arrow-down-outline', label: 'CARICA' }
        : { key: 'discharge', icon: 'mdi:battery-arrow-up-outline', label: 'SCARICA' }
      const gridFlow = Math.abs(grid) < 1
        ? { key: 'idle', icon: 'mdi:transmission-tower', label: 'RETE' }
        : grid > 0
        ? { key: 'export', icon: 'mdi:transmission-tower-export', label: 'IMMISSIONE' }
        : { key: 'import', icon: 'mdi:transmission-tower-import', label: 'PRELIEVO' }
      const socLabel = Number.isFinite(batterySoc) ? ` · ${Math.round(batterySoc)}%` : ''
      return `<button class="energy-dashboard-card energy-flow-${flow.key}" data-energy-dashboard="${esc(id)}" data-energy-name="${esc(name)}" title="${esc(flow.label)}"><span class="energy-main-icon mdi-mask" style="${mdiStyle(flow.icon, 'home-outline')}"></span><strong class="energy-dashboard-name">${esc(name)}</strong><span class="energy-flow-metrics"><span class="solar"><i class="mdi-mask" style="${mdiStyle('mdi:solar-power-variant', 'solar-power-variant')}"></i><small>FV</small><b>${power(live.pv_power_w)}</b></span><span class="battery ${batteryFlow.key}"><i class="mdi-mask" style="${mdiStyle(batteryFlow.icon, 'battery-outline')}"></i><small>${batteryFlow.label}</small><b>${power(Math.abs(battery))}${socLabel}</b></span><span class="home"><i class="mdi-mask" style="${mdiStyle('mdi:home-outline', 'home-outline')}"></i><small>CASA</small><b>${power(live.home_power_w)}</b></span><span class="grid ${gridFlow.key}"><i class="mdi-mask" style="${mdiStyle(gridFlow.icon, 'transmission-tower')}"></i><small>${gridFlow.label}</small><b>${power(Math.abs(grid))}</b></span></span></button>`
    }).join('')
    updateEnergyMasterIcon(masterFlows)
  } catch (error) {
    if (showLoading) picker.innerHTML = `<span class="empty-state">e-SunMind non disponibile: ${esc(error.message)}</span>`
  } finally { energyRefreshRunning = false }
}

function updateEnergyMasterIcon(flows) {
  const colors = { solar:'#ffd34e', battery:'#61d8f2', grid:'#ff704f', export:'#62e6a2', idle:'#87979a' }
  const unique = [...new Set((flows || []).map((flow) => colors[flow] || colors.idle))]
  const active = unique.length ? unique : [colors.idle]
  const signature = active.join('|')
  const current = energyMasterColors.join('|')
  if (current && signature !== current) {
    energyMasterPending = energyMasterPending.signature === signature
      ? { signature, confirmations:energyMasterPending.confirmations + 1 }
      : { signature, confirmations:1 }
    if (energyMasterPending.confirmations < 3) return
  }
  energyMasterColors = active
  energyMasterPending = { signature:'', confirmations:0 }
  paintEnergyMasterIcon()
}

function paintEnergyMasterIcon() {
  const icon = document.querySelector('[data-view="energy"] .nav-icon')
  if (!icon || !energyMasterColors.length) return
  const active = energyMasterColors
  icon.classList.add('energy-master-icon')
  icon.style.color = active[0]
  icon.style.setProperty('--energy-master-fill', active.length === 1
    ? active[0]
    : `linear-gradient(90deg,${active.map((color, index) => `${color} ${(index / active.length) * 100}% ${((index + 1) / active.length) * 100}%`).join(',')})`)
}

function openEnergyDashboard(id, name) {
  stopEnergyRefresh()
  activeEnergyDashboard = { id, name }
  $('#energy-title').textContent = name
  $('#energy-picker').hidden = true
  $('#energy-frame-shell').hidden = false
  $('#energy-reload').hidden = false
  $('#energy-frame').src = `${apiUrl('api/sunmind/energy-dashboard/sunsynk-wrapper.html')}?site=${encodeURIComponent(id)}`
}

let energyFrameObserver = null
function syncEnergyFrameHeight() {
  const frame = $('#energy-frame')
  try {
    const doc = frame.contentDocument
    if (!doc?.documentElement || !doc.body) return
    doc.documentElement.style.overflow = 'hidden'
    doc.body.style.overflow = 'hidden'
    const height = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight, 720)
    frame.style.height = `${height}px`
  } catch (_) {}
}

$('#energy-frame').addEventListener('load', () => {
  energyFrameObserver?.disconnect()
  syncEnergyFrameHeight()
  try {
    const doc = $('#energy-frame').contentDocument
    energyFrameObserver = new ResizeObserver(syncEnergyFrameHeight)
    energyFrameObserver.observe(doc.documentElement)
    energyFrameObserver.observe(doc.body)
  } catch (_) {}
  ;[150, 500, 1200, 2500].forEach(delay => setTimeout(syncEnergyFrameHeight, delay))
})

function applyBackground(room = activeBackgroundRoom) {
  activeBackgroundRoom=room
  let selected=room?currentBackgrounds.rooms?.[room]:currentBackgrounds.global
  if(!selected||selected.mode==='inherit'){selected=currentBackgrounds.global||{mode:'preset',preset:'teal'};room=''}
  document.body.dataset.background=selected.mode==='custom'?'custom':selected.preset||'teal'
  const query=room?`?room=${encodeURIComponent(room)}`:''
  document.body.style.setProperty('--custom-background',selected.mode==='custom'?`url("${apiUrl(`api/user/background/image${query}`)}")`:'none')
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
    const [response, hiddenResponse] = await Promise.all([fetch(apiUrl('api/bootstrap'), { cache: 'no-store' }), fetch(apiUrl('api/control4/hidden-sources'), { cache: 'no-store' })])
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    if (hiddenResponse.ok) hiddenSourceIds = new Set((await hiddenResponse.json()).ids || [])
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
  if (event.type === 'ksenia_state') {
    for (const update of data.items || []) {
      const existing = currentDevices.find((item) => String(item.id) === String(update.id))
      if (existing) Object.assign(existing, update)
      else currentDevices.push(update)
    }
    updateNavigationStates()
    renderHomeSecurity()
    if (activeDetailIds && !$('#detail-view').hidden) requestAnimationFrame(renderActiveDeviceList)
    return
  }
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
    renderHomeMediaSessions()
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
  renderHomeStatusCounters()
  renderHomeComfort()
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
  if (button.dataset.view === 'watch') openDevices('Guarda', currentDevices.filter((device) => ['camera', 'doorbell'].includes(device.kind) || (device.kind === 'media_player' && device.experiences?.includes('watch'))), { av: true, experience: 'watch' })
  if (button.dataset.view === 'listen') openDevices('Ascolta', currentDevices.filter((device) => ['media_player', 'media'].includes(device.kind) && (device.experiences?.includes('listen') || device.tts_enabled)), { av: true, experience: 'listen' })
  if (button.dataset.view === 'intercom') openIntercom()
  if (button.dataset.view === 'lights') openDevices('Luci', currentDevices.filter((device) => device.kind === 'light'), { lights: true, filters: true })
  if (button.dataset.view === 'extra') openDevices('Extra', currentDevices.filter((device) => device.kind === 'switch'), { filters: true })
  if (button.dataset.view === 'scenarios') openScenariosPage()
  if (button.dataset.view === 'covers') openDevices('Oscuranti', currentDevices.filter((device) => device.kind === 'cover'), { filters: true })
  if (button.dataset.view === 'comfort') openDevices('Comfort', currentDevices.filter((device) => ['climate', 'temp', 'temperature', 'humidity', 'air', 'air_quality'].includes(device.kind)), { filters: true })
  if (button.dataset.view === 'energy') openEnergy()
  if (button.dataset.view === 'security') openDevices('Sicurezza', currentDevices.filter((device) => ['lock','alarm_partition','alarm_zone','alarm_scenario','alarm_system'].includes(device.kind) || isSecurityGarage(device)))
}))
$('#widgets').addEventListener('click', (event) => {
  const button = event.target.closest('[data-kind]')
  if (!button) return
  const map = { lights: ['light'], extra: ['switch'], covers: ['cover'], security: ['lock','alarm_partition','alarm_zone','alarm_scenario','alarm_system'], comfort: ['climate', 'temp', 'temperature', 'humidity', 'air', 'air_quality'] }
  const kinds = map[button.dataset.kind] || []
  openDevices(button.dataset.label || 'Dispositivi', currentDevices.filter((device) => kinds.includes(device.kind)), { filters: true, lights: button.dataset.kind === 'lights' })
})
$('#home-comfort-summary').addEventListener('click', () => openDevices('Comfort', currentDevices.filter((device) => ['climate', 'temp', 'temperature', 'humidity', 'air', 'air_quality'].includes(device.kind)), { filters: true }))
$('#home-security-summary').addEventListener('click', () => openDevices('Sicurezza', currentDevices.filter((device) => ['lock','alarm_partition','alarm_zone','alarm_scenario','alarm_system'].includes(device.kind) || isSecurityGarage(device))))
$('#detail-view').addEventListener('click', (event) => {
  if ([$('#detail-view'), $('#device-list'), $('#scenario-panel')].includes(event.target)) showHome()
})
$('.horizontal-logo').addEventListener('click', showHome)
$('.horizontal-logo').addEventListener('keydown', (event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); showHome() } })
$('#rooms').addEventListener('click', (event) => {
  const button = event.target.closest('[data-room]')
  if (!button) return
  openDevices(button.dataset.room, currentDevices.filter((device) => device.room.toLocaleLowerCase('it') === button.dataset.room.toLocaleLowerCase('it')), {room:button.dataset.room})
})
$('#home-live-media-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-home-session]')
  if (!button) return
  const player = currentDevices.find((item) => String(item.id) === button.dataset.homeSession)
  if (!player) return
  if (event.target.closest('.home-live-art')) return openMediaRoomControl(player)
  player.active_experience === 'watch' ? openVideoRemote(player) : openMediaZones(player)
})
$('#detail-back').addEventListener('click', showHome)
$('#energy-back').addEventListener('click', () => activeEnergyDashboard ? showEnergyPicker() : showHome())
$('#intercom-back').addEventListener('click', showHome)
$('#intercom-frame').addEventListener('load', () => {
  $('#intercom-frame').contentWindow?.postMessage({type:'eface-intercom-visible',visible:!$('#intercom-view').hidden}, location.origin)
})
$('#intercom-frame').src = apiUrl('intercom?embedded=1')
$('#energy-picker').addEventListener('click', (event) => { const card = event.target.closest('[data-energy-dashboard]'); if (card) openEnergyDashboard(card.dataset.energyDashboard, card.dataset.energyName) })
$('#energy-reload').addEventListener('click', () => { if (!activeEnergyDashboard) return; $('#energy-frame').src = `${apiUrl('api/sunmind/energy-dashboard/sunsynk-wrapper.html')}?site=${encodeURIComponent(activeEnergyDashboard.id)}&refresh=${Date.now()}` })
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
  configureLightFilters(sectionFilterMode === 'scenarios' ? currentScenarios : sectionFilterDevices)
  sectionFilterMode === 'scenarios' ? renderScenarios() : renderActiveDeviceList()
})
$('#light-on-filter').addEventListener('click', (event) => {
  lightFilterActive = !lightFilterActive
  event.currentTarget.setAttribute('aria-pressed', String(lightFilterActive))
  event.currentTarget.classList.toggle('active', lightFilterActive)
  sectionFilterMode === 'scenarios' ? renderScenarios() : renderActiveDeviceList()
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
  sectionFilterMode === 'scenarios' ? renderScenarios() : renderActiveDeviceList()
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
  const wiimButton = event.target.closest('[data-wiim-action]')
  if (wiimButton) {
    const action = wiimButton.dataset.wiimAction
    const shuffled = [2, 3, 5].includes(wiimLoopMode)
    const repeatState = [1, 5].includes(wiimLoopMode) ? 'one' : [0, 2].includes(wiimLoopMode) ? 'all' : 'off'
    let mode = wiimLoopMode
    if (action === 'shuffle') mode = shuffled ? ({ 2: 0, 3: 4, 5: 1 }[wiimLoopMode] ?? 4) : ({ 0: 2, 1: 5, 4: 3 }[wiimLoopMode] ?? 3)
    if (action === 'repeat') {
      const next = repeatState === 'off' ? 'all' : repeatState === 'all' ? 'one' : 'off'
      mode = shuffled ? ({ all: 2, one: 5, off: 3 }[next]) : ({ all: 0, one: 1, off: 4 }[next])
    }
    wiimButton.disabled = true
    fetch(apiUrl('api/wiim/action'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'loop', value: mode }) })
      .then(async (response) => { if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`); wiimLoopMode = mode; loadWiimTimeline(wiimButton.closest('[data-device-id]').dataset.deviceId) })
      .catch((error) => fail(error))
      .finally(() => { wiimButton.disabled = false })
    return
  }
  const nowFavoriteButton = event.target.closest('[data-now-playing-favorite]')
  if (nowFavoriteButton) {
    const selected = currentDevices.find((item) => String(item.id) === nowFavoriteButton.closest('[data-device-id]')?.dataset.deviceId)
    if (!selected || nowFavoriteButton.disabled) return
    nowFavoriteButton.disabled = true
    ;(async () => {
      const station = nowPlayingFavorite(selected)
      if (station.wiim) {
        const response = await fetch(apiUrl('api/control4/favorites/current-wiim-track'), { method: 'POST' })
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Brano WiiM non disponibile')
        favoritesCache = (await response.json()).items || []
        const panel = $('[data-media-favorites]')
        if (panel) panel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(panel.dataset.favoriteRoom))
        updateNowPlayingStar(selected)
        return
      }
      if (station.stationProxyId) {
        const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
        const response = await fetch(apiUrl('api/control4/favorites/current-station'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ room_id: roomId, proxy_id: station.stationProxyId }) })
        if (!response.ok) throw new Error((await response.json()).detail || 'Stazione non disponibile')
        favoritesCache = (await response.json()).items || []
        const panel = $('[data-media-favorites]')
        if (panel) panel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(panel.dataset.favoriteRoom))
        updateNowPlayingStar(selected)
        return
      }
      if (station.spotifyProxyId) {
        const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
        const response = await fetch(apiUrl('api/control4/favorites/current-spotify-playlist'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ room_id: roomId, proxy_id: station.spotifyProxyId }) })
        if (!response.ok) throw new Error((await response.json()).detail || 'Playlist Spotify non disponibile')
        const result = await response.json()
        favoritesCache = result.items || []
        const panel = $('[data-media-favorites]')
        if (panel) panel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(panel.dataset.favoriteRoom))
        updateNowPlayingStar(selected)
        return
      }
      let { recent, favorite } = nowPlayingFavorite(selected)
      if (!recent && !favorite) {
        const roomId = Number(String(selected.registry_id || '').replace('c4room:', ''))
        const scope = (avRoom || activeMediaRoom) && roomId ? `room-${roomId}` : 'global'
        const response = await fetch(apiUrl(`api/control4/recently-played${scope === 'global' ? '' : `?room_id=${roomId}`}`), { cache: 'no-store' })
        if (!response.ok) throw new Error('Cronologia non disponibile')
        const data = await response.json()
        recentCache.set(scope, { items: data.items || [], hiddenItems: data.hidden_items || [], hiddenCount: Number(data.hidden_count || 0), updated: Date.now() })
        ;({ recent, favorite } = nowPlayingFavorite(selected))
      }
      if (!recent && !favorite) throw new Error('Questo contenuto non è ancora disponibile nella cronologia Control4')
      const path = favorite ? 'remove' : 'recent'
      const payload = favorite ? { id: favorite.id } : { key: recent.key, title: recent.title, subtitle: recent.subtitle, item_type: recent.item_type, driver_id: recent.driver_id, registry_id: recent.registry_id, content_fingerprint: recent.content_fingerprint }
      const response = await fetch(apiUrl(`api/control4/favorites/${path}`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!response.ok) throw new Error((await response.json()).detail || 'Preferito non disponibile')
      favoritesCache = (await response.json()).items || []
      const panel = $('[data-media-favorites]')
      if (panel) panel.querySelector('.media-recent-strip').innerHTML = mediaFavoritesHtml(favoritesCache, Number(panel.dataset.favoriteRoom))
      const recents = $('[data-recently-played]')
      if (recents) { const cached = recentCache.get(recents.dataset.recentScope); if (cached) recents.querySelector('.media-recent-strip').innerHTML = recentlyPlayedHtml(cached.items, Number(panel?.dataset.favoriteRoom || 0)) }
      updateNowPlayingStar(selected)
    })().catch(fail).finally(() => { nowFavoriteButton.disabled = false })
    return
  }
  const navigatorButton = event.target.closest('[data-msp-open]')
  if (navigatorButton) return openTuneInNavigator(Number(navigatorButton.dataset.mspRoom), navigatorButton.dataset.mspService || 'tunein')
  const pinRecent = event.target.closest('[data-recent-pin]')
  const removeWiimPreset = event.target.closest('[data-wiim-preset-remove]')
  const removeFavorite = event.target.closest('[data-favorite-remove]')
  const selectFavorite = event.target.closest('[data-favorite-select]')
  if (removeWiimPreset) {
    if (!confirm('Eliminare questo preset dal WiiM e da e-Face?')) return
    removeWiimPreset.disabled = true
    fetch(apiUrl(`api/wiim/presets/${encodeURIComponent(removeWiimPreset.dataset.wiimPresetRemove)}`), { method: 'DELETE' })
      .then(async (response) => { if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Preset WiiM non eliminato'); favoritesCache = null; await loadMediaFavorites(true) })
      .catch(fail).finally(() => { removeWiimPreset.disabled = false })
    return
  }
  if (pinRecent || removeFavorite || selectFavorite) {
    if (Date.now() < recentDragSuppressUntil) { event.preventDefault(); return }
    const control = pinRecent || removeFavorite || selectFavorite
    const roomId = Number($('[data-media-favorites]')?.dataset.favoriteRoom || 0)
    control.disabled = true
    let path, payload
    if (pinRecent) {
      const key = pinRecent.dataset.recentPin
      const existing = favoritesCache?.some((item) => item.id === `recent:${key}`)
      const scope = pinRecent.closest('[data-recently-played]')?.dataset.recentScope
      const item = recentCache.get(scope)?.items.find((entry) => entry.key === key)
      if (!item) { control.disabled = false; return }
      path = existing ? 'remove' : 'recent'
      payload = existing ? {id:`recent:${key}`} : {key, title:item.title, subtitle:item.subtitle, item_type:item.item_type, driver_id:item.driver_id, registry_id:item.registry_id, content_fingerprint:item.content_fingerprint}
    } else if (removeFavorite) { path = 'remove'; payload = {id:removeFavorite.dataset.favoriteRemove} }
    else { path = 'select'; payload = {id:selectFavorite.dataset.favoriteSelect, room_id:roomId} }
    fetch(apiUrl(`api/control4/favorites/${path}`), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
      .then(async (response) => { if (!response.ok) throw new Error((await response.json()).detail || 'Preferito non disponibile'); if (path === 'select') { refresh(); setTimeout(refresh,2500) } else { favoritesCache = null; await loadMediaFavorites() } })
      .catch(fail).finally(() => { control.disabled = false })
    return
  }
  const hideRecent = event.target.closest('[data-recent-hide]')
  const restoreOneRecent = event.target.closest('[data-recent-restore-one]')
  const showHiddenRecents = event.target.closest('[data-recent-show-hidden]')
  if (showHiddenRecents) {
    const panel = showHiddenRecents.closest('[data-recently-played]').querySelector('.media-recent-hidden')
    panel.hidden = !panel.hidden
    return
  }
  if (hideRecent || restoreOneRecent) {
    const control = hideRecent || restoreOneRecent
    control.disabled = true
    const scope = control.closest('[data-recently-played]')?.dataset.recentScope || ''
    const path = hideRecent ? 'hide' : 'restore-one'
    const key = hideRecent?.dataset.recentHide || restoreOneRecent?.dataset.recentRestoreOne
    fetch(apiUrl(`api/control4/recently-played/${path}`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(key ? { key } : {}) })
      .then(async (response) => { if (!response.ok) throw new Error((await response.json()).detail || 'Modifica non riuscita'); if (recentPending.has(scope)) await recentPending.get(scope); recentCache.delete(scope); lastDetailSignature = ''; renderActiveDeviceList() })
      .catch(fail).finally(() => { control.disabled = false })
    return
  }
  if (Date.now() < recentDragSuppressUntil && event.target.closest('[data-recent-key]')) { event.preventDefault(); return }
  if (devicePointerGesture?.moved) { devicePointerGesture = null; return }
  const recentButton = event.target.closest('[data-recent-key]')
  if (recentButton) return selectRecentlyPlayed(recentButton)
  const mediaSectionToggle = event.target.closest('[data-media-section-toggle]')
  if (mediaSectionToggle) {
    const key = mediaSectionToggle.dataset.mediaSectionToggle
    mediaSections[key] = !mediaSections[key]
    return renderActiveDeviceList()
  }
  const ttsSend = event.target.closest('[data-tts-send]')
  if (ttsSend) {
    const message = $('#evoice-tts-message')?.value.trim()
    const targets = [...document.querySelectorAll('[data-tts-target]:checked')].map((input) => input.value)
    const volume = Math.max(0, Math.min(100, Number($('[data-tts-volume]')?.value ?? 50)))
    if (!message || !targets.length) return fail(new Error(!message ? 'Scrivi un messaggio' : 'Seleziona almeno un Echo'))
    localStorage.setItem('eface-tts-volume', String(volume))
    const restoreDelay = 10000
    ttsSend.disabled = true
    return Promise.all(targets.map(async (deviceId) => {
      const device = currentDevices.find((item) => String(item.id) === String(deviceId))
      try {
        if (device?.capabilities?.set_volume && Number.isFinite(Number(device.volume))) {
          const pending = ttsVolumeRestores.get(String(deviceId))
          if (pending?.timer) clearTimeout(pending.timer)
          ttsVolumeRestores.set(String(deviceId), { volume: pending?.volume ?? Number(device.volume), timer: null })
          await postDeviceCommand(deviceId, 'set_volume', volume)
        }
        await postDeviceCommand(deviceId, 'tts', message)
      } finally {
        const pending = ttsVolumeRestores.get(String(deviceId))
        if (pending) pending.timer = setTimeout(async () => {
          try { await postDeviceCommand(deviceId, 'set_volume', pending.volume) } catch (error) { fail(error) }
          finally { ttsVolumeRestores.delete(String(deviceId)) }
        }, restoreDelay)
      }
    })).then(() => {
      $('#evoice-tts-message').value = ''
      const notice = $('#notice'); notice.textContent = 'Messaggio inviato'; notice.hidden = false
      setTimeout(() => { notice.hidden = true }, 2200)
    }).catch(fail).finally(() => { ttsSend.disabled = false })
  }
  const dndButton = event.target.closest('[data-dnd-device]')
  if (dndButton) {
    dndButton.disabled = true
    return postDeviceCommand(dndButton.dataset.dndDevice, 'set_dnd', dndButton.dataset.dndValue === 'true').then(refresh).catch(fail).finally(() => { dndButton.disabled = false })
  }
  const rgbOpen = event.target.closest('[data-rgb-open]')
  if (rgbOpen) return openRgbDialog(rgbOpen.closest('[data-rgb-group]').dataset.rgbGroup)
  const rgbButton = event.target.closest('[data-rgb-action]')
  const rgbCard = event.target.closest('[data-rgb-group]')
  if (rgbButton && rgbCard) return sendRgbCommand(rgbCard.dataset.rgbGroup, rgbButton.dataset.rgbAction, null, rgbButton)
  const climateButton = event.target.closest('[data-climate-target]')
  const climateCard = event.target.closest('[data-device-id]')
  if (climateButton && climateCard) return sendDeviceCommand(climateCard.dataset.deviceId, 'set_target', climateButton, climateButton.dataset.climateTarget)
  const climateSeasonButton = event.target.closest('[data-climate-season]')
  if (climateSeasonButton && climateCard) return sendDeviceCommand(climateCard.dataset.deviceId, 'set_season', climateSeasonButton, climateSeasonButton.dataset.climateSeason)
  const climateModeButton = event.target.closest('[data-climate-mode]')
  if (climateModeButton && climateCard) return sendDeviceCommand(climateCard.dataset.deviceId, 'set_mode', climateModeButton, climateModeButton.dataset.climateMode)
  const mediaButton = event.target.closest('[data-media-action]')
  const mediaCard = event.target.closest('[data-device-id]')
  if (mediaButton?.dataset.mediaAction === 'media_zones' && mediaCard) return openMediaZones(currentDevices.find((item) => String(item.id) === mediaCard.dataset.deviceId))
  if (mediaButton?.dataset.mediaAction === 'video_remote_menu' && mediaCard) return openVideoRemote(currentDevices.find((item) => String(item.id) === mediaCard.dataset.deviceId))
  if (mediaButton && mediaCard) return sendDeviceCommand(mediaCard.dataset.deviceId, mediaButton.dataset.mediaAction, mediaButton)
  const sourceButton = event.target.closest('button[data-media-source]')
  if (sourceButton && mediaCard) {
    const sourceLabel = String(sourceButton.textContent || '').trim().toLowerCase()
    const service = sourceLabel === 'spotify connect' ? 'spotify' : String(sourceButton.dataset.mediaSource || sourceLabel).toLowerCase().includes('stations') || sourceLabel === 'stations' ? 'stations' : ''
    if (service) {
      const room = currentDevices.find((item) => String(item.id) === mediaCard.dataset.deviceId)
      const roomId = Number(String(room?.registry_id || '').replace('c4room:', ''))
      if (roomId) return openTuneInNavigator(roomId, service)
    }
    return sendDeviceCommand(mediaCard.dataset.deviceId, 'select_source', sourceButton, sourceButton.dataset.mediaSource)
  }
  const playerButton = event.target.closest('[data-media-select]')
  if (playerButton) {
    selectedMediaId = playerButton.dataset.mediaSelect
    renderActiveDeviceList()
    return
  }
  const button = event.target.closest('[data-action]')
  const card = event.target.closest('[data-device-id]')
  const sectionToggle = event.target.closest('[data-security-toggle]')
  if (sectionToggle) {
    securitySections[sectionToggle.dataset.securityToggle] = sectionToggle.getAttribute('aria-expanded') !== 'true'
    renderActiveDeviceList()
    return
  }
  if (!button && card?.classList.contains('security-area')) return openSecurityArea(currentDevices.find((item) => String(item.id) === card.dataset.deviceId))
  if (!button && card?.classList.contains('security-zone')) {
    const opening = !card.classList.contains('show-action')
    document.querySelectorAll('.security-zone.show-action').forEach((item) => { item.classList.remove('show-action'); item.setAttribute('aria-expanded', 'false') })
    card.classList.toggle('show-action', opening)
    card.setAttribute('aria-expanded', String(opening))
    return
  }
  if (button && card && card.dataset.deviceId?.startsWith('ksenia-')) return requestSecurityPin(card.dataset.deviceId, button.dataset.action, button)
  if (button && card) sendDeviceCommand(card.dataset.deviceId, button.dataset.action, button)
  if (!button && card?.classList.contains('media-player-card') && !event.target.closest('input,label')) {
    const device = currentDevices.find((item) => String(item.id) === card.dataset.deviceId)
    if (device) {
      selectedMediaId = String(device.id)
      return openDevices(device.room || device.name, currentDevices.filter((item) => item.kind === 'media_player' && item.room === device.room), { room: device.room || device.name, experience: device.active_experience || '' })
    }
  }
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
  const strip = event.target.closest('.media-recent-strip')
  if (strip && event.pointerType === 'mouse' && event.button === 0) {
    recentDrag = { strip, pointerId: event.pointerId, x: event.clientX, left: strip.scrollLeft, moved: false }
    return
  }
  if (!event.target.closest('[data-device-toggle],[data-rgb-toggle]')) return
  devicePointerGesture = { x: event.clientX, y: event.clientY, moved: false }
}, { passive: true })
$('#device-list').addEventListener('pointermove', (event) => {
  if (recentDrag && event.pointerId === recentDrag.pointerId) {
    const delta = event.clientX - recentDrag.x
    if (Math.abs(delta) > 5 && !recentDrag.moved) {
      recentDrag.moved = true
      recentDrag.strip.setPointerCapture(event.pointerId)
    }
    if (recentDrag.moved) recentDrag.strip.scrollLeft = recentDrag.left - delta
    return
  }
  if (!devicePointerGesture) return
  if (Math.hypot(event.clientX - devicePointerGesture.x, event.clientY - devicePointerGesture.y) > 7) devicePointerGesture.moved = true
}, { passive: true })
$('#device-list').addEventListener('pointerup', (event) => {
  if (!recentDrag || event.pointerId !== recentDrag.pointerId) return
  if (recentDrag.moved) recentDragSuppressUntil = Date.now() + 300
  if (recentDrag.strip.hasPointerCapture(event.pointerId)) recentDrag.strip.releasePointerCapture(event.pointerId)
  recentDrag = null
})
$('#device-list').addEventListener('pointercancel', () => { recentDrag = null; devicePointerGesture = { moved: true } }, { passive: true })
$('#device-list').addEventListener('keydown', (event) => {
  const navigator = event.target.closest('[data-msp-open]')
  if (navigator && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault()
    return openTuneInNavigator(Number(navigator.dataset.mspRoom), navigator.dataset.mspService || 'tunein')
  }
  if (!['Enter',' '].includes(event.key) || !event.target.matches('[data-device-toggle],[data-rgb-toggle],.security-zone,.security-area')) return
  event.preventDefault()
  event.target.click()
})
$('#rgb-close').addEventListener('click', () => $('#rgb-dialog').close())
$('#security-pin-form').addEventListener('submit', submitSecurityPin)
function closeSecurityPin() { $('#security-pin-input').value = ''; $('#security-pin-dialog').close(); pendingSecurityCommand = null }
$('#security-pin-close').addEventListener('click', closeSecurityPin)
$('#security-pin-cancel').addEventListener('click', closeSecurityPin)
$('#security-pin-dialog').addEventListener('click', (event) => { if (event.target === $('#security-pin-dialog')) closeSecurityPin() })
$('#security-pin-keys').addEventListener('click', (event) => {
  const key = event.target.closest('[data-pin-key]')?.dataset.pinKey
  if (!key) return
  const input = $('#security-pin-input')
  if (key === 'clear') input.value = ''
  else if (key === 'back') input.value = input.value.slice(0, -1)
  else if (input.value.length < Number(input.maxLength || 16)) input.value += key
  $('#security-pin-error').textContent = ''
})
function closeSecurityArea() { $('#security-area-dialog').close(); activeSecurityArea = null }
$('#security-area-close').addEventListener('click', closeSecurityArea)
$('#security-area-dialog').addEventListener('click', (event) => {
  if (event.target === $('#security-area-dialog')) return closeSecurityArea()
  const button = event.target.closest('[data-area-action]')
  if (!button || !activeSecurityArea) return
  const device = activeSecurityArea
  closeSecurityArea()
  requestSecurityPin(device.id, button.dataset.areaAction, button)
})
$('#rgb-dialog').addEventListener('click', (event) => { if (event.target === $('#rgb-dialog')) $('#rgb-dialog').close() })
$('#media-zones-close').addEventListener('click', () => $('#media-zones-dialog').close())
$('#global-media-session').addEventListener('click', openMediaSessions)
$('#media-sessions-close').addEventListener('click', () => $('#media-sessions-dialog').close())
$('#media-sessions-list').addEventListener('click', (event) => { const row = event.target.closest('[data-session-device]'); if (!row || event.target.closest('[data-session-volume]')) return; const player = currentDevices.find((item) => String(item.id) === row.dataset.sessionDevice); if (!player) return; const power = event.target.closest('[data-session-power]'); if (power) { const session = activeMediaSessions().find(({player:item}) => String(item.id) === power.dataset.sessionPower); return powerOffMediaSession(power, (session?.members || [player]).map((item) => item.id)) } if (event.target.closest('.media-artwork')) { $('#media-sessions-dialog').close(); return openMediaRoomControl(player) } if (event.target.closest('.media-session-row-rooms')) { $('#media-sessions-dialog').close(); return openMediaZones(player) } $('#media-sessions-dialog').close(); player.active_experience === 'watch' ? openVideoRemote(player) : openMediaZones(player) })
$('#media-sessions-list').addEventListener('input', (event) => { if (event.target.matches('[data-session-volume]')) { event.target.style.setProperty('--volume', `${event.target.value}%`); event.target.nextElementSibling.textContent = `${event.target.value}%` } })
$('#media-sessions-list').addEventListener('change', (event) => { if (event.target.matches('[data-session-volume]')) setSessionVolume(event.target) })
$('#media-sessions-list').addEventListener('pointerdown', (event) => {
  const input = event.target.closest('[data-session-volume]')
  if (!input || input.disabled) return
  const rect = input.getBoundingClientRect(); const value = Number(input.value) || 0
  const thumbX = rect.left + value / 100 * rect.width
  if (Math.abs(event.clientX - thumbX) <= 18) return
  event.preventDefault()
  input.value = Math.max(0, Math.min(100, value + (event.clientX < thumbX ? -2 : 2)))
  input.style.setProperty('--volume', `${input.value}%`)
  input.nextElementSibling.textContent = `${input.value}%`
  setSessionVolume(input)
}, { capture: true })
function stepSessionRangeClick(event) {
  const input = event.target.closest('input[type=range]')
  if (!input || input.disabled) return
  const rect = input.getBoundingClientRect()
  const min = Number(input.min) || 0; const max = Number(input.max) || 100; const value = Number(input.value) || 0
  const thumbX = rect.left + ((value - min) / Math.max(1, max - min)) * rect.width
  if (Math.abs(event.clientX - thumbX) <= 18) return
  event.preventDefault()
  input.value = Math.max(min, Math.min(max, value + (event.clientX < thumbX ? -2 : 2)))
  input.style.setProperty('--volume', `${input.value}%`)
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}
$('#zones-master').addEventListener('pointerdown', stepSessionRangeClick, { capture: true })
$('#media-zones-list').addEventListener('pointerdown', stepSessionRangeClick, { capture: true })
$('#media-zones-save').addEventListener('click', (event) => saveMediaZones(event.currentTarget))
$('#media-zones-list').addEventListener('click', (event) => { const button = event.target.closest('[data-zone-picker-toggle]'); if (button) { const picker = $('.media-zone-picker'); picker.hidden = !picker.hidden; button.classList.toggle('active', !picker.hidden) } })
$('#media-zones-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-media-zones-toggle]')
  if (!button) return
  const key = button.dataset.mediaZonesToggle
  mediaSections[key] = !mediaSections[key]
  button.setAttribute('aria-expanded', String(mediaSections[key]))
  button.querySelector('.mdi-mask').setAttribute('style', mdiStyle(mediaSections[key] ? 'mdi:chevron-up' : 'mdi:chevron-down', 'chevron-down'))
  button.nextElementSibling.hidden = !mediaSections[key]
})
$('#media-zones-list').addEventListener('click', (event) => { const button = event.target.closest('[data-zone-power]'); if (button) powerOffMediaSession(button, [button.dataset.zonePower]) })
$('#zones-master').addEventListener('click', (event) => { const button = event.target.closest('[data-session-power-all]'); if (button) { const ids = [...document.querySelectorAll('[data-zone-power]')].map((item) => item.dataset.zonePower); powerOffMediaSession(button, ids) } })
$('#video-remote-close').addEventListener('click', () => $('#video-remote-dialog').close())
$('#video-remote-dialog').addEventListener('click', (event) => {
  if (event.target === $('#video-remote-dialog')) return $('#video-remote-dialog').close()
  const volumeStep = event.target.closest('[data-remote-volume-step]')
  if (volumeStep && activeVideoRemote) {
    const next = Math.max(0, Math.min(100, (Number(activeVideoRemote.device.volume) || 0) + Number(volumeStep.dataset.remoteVolumeStep)))
    activeVideoRemote.device.volume = next
    const slider = $('#video-remote-dialog').querySelector('[data-remote-volume]')
    if (slider) { slider.value = next; slider.nextElementSibling.textContent = next }
    return sendDeviceCommand(activeVideoRemote.device.id, 'set_volume', volumeStep, next)
  }
  const button = event.target.closest('[data-remote-command]')
  if (button) sendVideoRemote(button.dataset.remoteCommand, button)
})
$('#video-remote-dialog').addEventListener('change', (event) => {
  if (!event.target.matches('[data-remote-volume]') || !activeVideoRemote) return
  const value = Number(event.target.value)
  activeVideoRemote.device.volume = value
  event.target.nextElementSibling.textContent = value
  sendDeviceCommand(activeVideoRemote.device.id, 'set_volume', event.target, value)
})
$('#media-zones-list').addEventListener('change', (event) => { if (event.target.matches('.media-zone-picker input[type=checkbox]')) { event.target.closest('.media-zone-choice').classList.toggle('active', event.target.checked) } })
$('#media-zones-list').addEventListener('input', (event) => { if (event.target.matches('[data-zone-volume]')) { event.target.style.setProperty('--volume', `${event.target.value}%`); event.target.closest('.media-zone-level').querySelector('output').textContent = `${event.target.value}%` } })
$('#media-zones-list').addEventListener('change', (event) => { if (event.target.matches('[data-zone-volume]')) sendDeviceCommand(event.target.dataset.deviceId, 'set_volume', event.target, event.target.value) })
$('#zones-master').addEventListener('input', (event) => {
  if (!event.target.matches('[data-group-volume]')) return
  const value = Number(event.target.value)
  event.target.style.setProperty('--volume', `${value}%`)
  event.target.nextElementSibling.textContent = `${value}%`
  const relative = activeMediaPlayer?.provider === 'control4'
  const delta = value - Number(event.target.dataset.baseVolume ?? value)
  document.querySelectorAll('#media-zones-list [data-zone-volume]').forEach((slider) => {
    const next = relative ? Math.max(0, Math.min(100, Number(slider.dataset.baseVolume || 0) + delta)) : value
    slider.value = next
    slider.style.setProperty('--volume', `${next}%`)
    slider.closest('.media-zone-level').querySelector('output').textContent = `${next}%`
  })
})
$('#zones-master').addEventListener('change', (event) => { if (event.target.matches('[data-group-volume]')) setMediaGroupVolume(event.target) })
$('#zones-master').addEventListener('click', (event) => { const button = event.target.closest('[data-group-mute]'); if (button) toggleMediaZoneMute(button, true) })
$('#media-zones-list').addEventListener('click', (event) => { const button = event.target.closest('[data-zone-mute]'); if (button) toggleMediaZoneMute(button, false) })
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
$('#device-list').addEventListener('pointerdown', (event) => {
  if (event.target.matches('[data-wiim-seek]')) { wiimTimelineDragging = true; return }
  const input = event.target.closest('input[data-media-volume]')
  if (!input || input.disabled) return
  const rect = input.getBoundingClientRect()
  const min = Number(input.min) || 0
  const max = Number(input.max) || 100
  const value = Number(input.value) || 0
  const thumbX = rect.left + ((value - min) / Math.max(1, max - min)) * rect.width
  if (Math.abs(event.clientX - thumbX) <= 18) return
  event.preventDefault()
  const next = Math.max(min, Math.min(max, value + (event.clientX < thumbX ? -2 : 2)))
  input.value = String(next)
  input.nextElementSibling.textContent = `${next}%`
  const card = input.closest('[data-device-id]')
  if (card) sendDeviceCommand(card.dataset.deviceId, 'set_volume', input, next)
}, { capture: true })
$('#device-list').addEventListener('input', (event) => {
  if (event.target.matches('[data-wiim-seek]')) {
    const input = event.target
    const duration = Number(input.max) || 0
    const position = Number(input.value) || 0
    input.style.setProperty('--position', `${duration ? position / duration * 100 : 0}%`)
    const host = input.closest('[data-wiim-timeline]')
    host.querySelector('[data-wiim-elapsed]').textContent = mediaTime(position)
    host.querySelector('[data-wiim-remaining]').textContent = `-${mediaTime(Math.max(0, duration - position))}`
  }
  if (event.target.matches('[data-media-volume]')) { event.target.style.setProperty('--volume', `${event.target.value}%`); event.target.nextElementSibling.textContent = `${event.target.value}%` }
  if (event.target.matches('[data-tts-volume]')) { event.target.nextElementSibling.textContent = `${event.target.value}%`; event.target.style.setProperty('--volume', `${event.target.value}%`) }
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
  if (event.target.matches('[data-wiim-seek]')) {
    const input = event.target
    input.disabled = true
    fetch(apiUrl('api/wiim/action'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'seek', value: Number(input.value) || 0 }) })
      .then(async (response) => { if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`) })
      .catch((error) => fail(error))
      .finally(() => { wiimTimelineDragging = false; input.disabled = false })
    return
  }
  if (event.target.matches('[data-tts-select-all]')) {
    document.querySelectorAll('[data-tts-target]').forEach((input) => { input.checked = event.target.checked })
    event.target.indeterminate = false
    return
  }
  if (event.target.matches('[data-tts-target]')) {
    const targets = [...document.querySelectorAll('[data-tts-target]')]
    const selectedCount = targets.filter((input) => input.checked).length
    const selectAll = $('[data-tts-select-all]')
    if (selectAll) { selectAll.checked = selectedCount === targets.length; selectAll.indeterminate = selectedCount > 0 && selectedCount < targets.length }
    return
  }
  const card = event.target.closest('[data-device-id],[data-rgb-group]')
  if (event.target.matches('[data-brightness]')) sendDeviceCommand(card.dataset.deviceId, Number(event.target.value) === 0 ? 'off' : 'brightness', event.target, event.target.value)
  if (event.target.matches('[data-rgb-brightness]')) sendRgbCommand(card.dataset.rgbGroup, 'brightness', event.target.value, event.target)
  if (event.target.matches('[data-rgb-color]')) sendRgbCommand(card.dataset.rgbGroup, 'color', event.target.value, event.target)
  if (event.target.matches('[data-media-volume]')) sendDeviceCommand(card.dataset.deviceId, 'set_volume', event.target, event.target.value)
  if (event.target.matches('select[data-media-source]')) sendDeviceCommand(card.dataset.deviceId, 'select_source', event.target, event.target.value)
})
$('.home-title').addEventListener('click', showHome)
$('#show-all-devices').addEventListener('click', () => openDevices('Tutti i dispositivi', currentDevices))
document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); connectRealtime() } })
navigator.serviceWorker?.addEventListener('message', (event) => {
  if (event.data?.type === 'eface-open-intercom') openIntercom()
})
window.addEventListener('message', (event) => {
  if (event.origin === location.origin && event.source === $('#intercom-frame').contentWindow && event.data?.type === 'eface-intercom-incoming') openIntercom()
})
window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.source !== $('#intercom-frame').contentWindow || event.data?.type !== 'eface-intercom-state') return
  const button=document.querySelector('[data-view="intercom"]')
  button.dataset.intercomState=['idle','available','ringing','active'].includes(event.data.state)?event.data.state:'idle'
  button.title={idle:'Intercom non collegato',available:'Intercom disponibile',ringing:'Chiamata in arrivo',active:'Intercomunicazione attiva'}[button.dataset.intercomState]
})
document.addEventListener('pointerdown', () => {
  try { $('#intercom-frame').contentWindow?.efaceUnlockIntercomAudio?.() } catch (_) {}
}, {once:true, capture:true})
tick()
setInterval(tick, 30000)
window.addEventListener('keydown', (event) => {
  const delta = event.key === 'AudioVolumeUp' ? 2 : event.key === 'AudioVolumeDown' ? -2 : 0
  if (!delta) return
  adjustActiveUiVolume(delta).then((handled) => { if (handled) event.preventDefault() })
})
setInterval(() => {
  if (!realtimeSocket || realtimeSocket.readyState !== WebSocket.OPEN) refresh()
}, 30000)
setInterval(refresh, 60000)
Promise.all([
  fetch(apiUrl('api/auth/status'), {cache:'no-store', credentials:'same-origin'}).then(response => response.ok ? response.json() : {}).catch(() => ({})),
  refresh(),
]).then(([identity]) => {
  loggedUser = identity.name || identity.user || ''
  const mode = $('#mode')
  if (mode && loggedUser && !mode.textContent.includes(loggedUser)) mode.textContent += ` · ${loggedUser}`
  const launch = new URLSearchParams(location.search)
  if (launch.get('view') === 'intercom' || launch.get('push') === '1') {
    openIntercom()
    history.replaceState(null, '', location.pathname)
  }
})
connectRealtime()
{
  const splash = $('#startup-splash')
  const duration = Math.max(0, Number(splash?.dataset.durationMs) || 0)
  if (!splash || !duration) splash?.remove()
  else setTimeout(() => {
    splash.classList.add('closing')
    setTimeout(() => splash.remove(), 650)
  }, duration)
}
