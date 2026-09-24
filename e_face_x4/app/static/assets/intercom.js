(() => {
  const $ = (selector) => document.querySelector(selector)
  const adminMode = document.documentElement.classList.contains('admin-intercom')
  const root = new URL('./', location.href)
const currentVersion = '2.21.265'
  function newDeviceId() {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
    const bytes = new Uint8Array(16)
    if (typeof crypto.getRandomValues === 'function') crypto.getRandomValues(bytes)
    else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256)
    bytes[6] = (bytes[6] & 15) | 64
    bytes[8] = (bytes[8] & 63) | 128
    const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
  }
  let updateAvailable = false
  async function checkForUpdate() {
    if (document.hidden || !intercomVisible) return
    try {
      const response = await fetch(new URL('intercom', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const html = await response.text()
      const version = html.match(/assets\/intercom\.js\?v=([0-9.]+)/)?.[1]
      if (version && version !== currentVersion) updateAvailable = true
      if (updateAvailable && !call) location.reload()
    } catch (_) { /* A temporary network error must not interrupt Intercom. */ }
  }
  setInterval(checkForUpdate, 30000)
  const socketUrl = new URL('api/intercom/sip', root)
  socketUrl.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  let phone = null
  let ownExtension = ''
  let call = null
  let audioContext = null
  let ringtoneTimer = null
  let ringtoneUrl = null
  let ringtoneKind = ''
  let ringtoneActive = false
  let ringPreferences = {ringtone:'doorbell', ring_volume:80, vibration:true, silent:false}
  let deviceDnd = false
  let videoCapable = false
  let videoEnabled = false
  let cameraFacing = 'user'
  let localVideoStream = null
  let activeVideoSender = null
  let currentDeviceId = ''
  let rejectIncomingUntil = 0
  let audioStatsTimer = null
  let micInput = null
  let micOutput = null
  let micSource = null
  let micGain = null
  let iceServers = []
  let doorbirdTimer = null
  let doorbirdImageUrl = null
  let doorbirdAbort = null
  let doorbirdStopped = false
  let doorbirdVideoActive = false
  let doorbirdRetryTimer = null
  let doorbirdAlertTimer = null
  let doorbirdAlertActive = false
  let callDoorbirdTimer = null
  let intercomVisible = !document.documentElement.classList.contains('embedded')
  let stationsSignature = ''
  const externalVideoByExtension = new Map()
  const pushedCaller = new URLSearchParams(location.search).get('from')
  const pushedDoorbird = new URLSearchParams(location.search).get('doorbird')
  $('.intercom-station-list').prepend($('.doorbird-row'))
  function publishIntercomState(state) {
    if (window.parent !== window) window.parent.postMessage({type:'eface-intercom-state', state}, location.origin)
  }
  if (pushedCaller) {
    $('#call-title').textContent = `Chiamata da ${pushedCaller}`
    $('#call-status').textContent = 'Collegamento in corso…'
    $('#call-status').hidden = false
    $('#intercom-call-panel').hidden = false
    $('#call-hangup').disabled = false
  }
  async function refreshExternalStations() {
    try {
      const response = await fetch(new URL('api/intercom/external-stations', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const {stations} = await response.json()
      const signature = JSON.stringify(stations)
      if (signature === stationsSignature) return
      stationsSignature = signature
      externalVideoByExtension.clear()
      stations.forEach(station => externalVideoByExtension.set(station.sip_extension, station.id))
      const primary = stations.find((station) => station.id === 'ingresso')
      if (primary) {
        $('.doorbird-row .station-copy strong').textContent = primary.name
        $('#doorbird-extension').textContent = `Postazione esterna · interno ${primary.sip_extension}`
        $('#call-doorbird').disabled = !primary.ready || !phone?.isRegistered() || !!call
        $('#call-doorbird').dataset.dialExtension = primary.sip_extension
        $('#call-doorbird').dataset.stationReady = String(primary.ready)
      }
      document.querySelectorAll('.external-extra-row').forEach((row) => row.remove())
      let anchor = $('.doorbird-row')
      for (const station of stations.filter((item) => item.id !== 'ingresso')) {
        const row = document.createElement('div')
        row.className = 'intercom-station-row doorbird-row external-extra-row'
        const icon = document.createElement('span')
        icon.className = 'station-icon'
        icon.textContent = '▣'
        const copy = document.createElement('div')
        copy.className = 'station-copy'
        const name = document.createElement('strong')
        name.textContent = station.name
        const subtitle = document.createElement('small')
        subtitle.textContent = `Postazione esterna · interno ${station.sip_extension}`
        const open = document.createElement('button')
        open.className = 'station-text-button'
        open.type = 'button'
        open.textContent = 'Apri video'
        const dial = document.createElement('button')
        dial.type = 'button'
        dial.textContent = 'CHIAMA'
        dial.dataset.dialExtension = station.sip_extension
        dial.dataset.externalStation = station.id
        // Le postazioni esterne hanno video HTTP e devono aprire il pannello.
        dial.dataset.videoCapable = 'true'
        dial.dataset.stationReady = String(station.ready)
        dial.disabled = !station.ready || !phone?.isRegistered() || !!call
        if (!station.ready) dial.title = 'Configura e verifica la rotta SIP in Asterisk'
        copy.append(name, subtitle, open, dial)
        const frame = document.createElement('div')
        frame.className = 'doorbird-frame'
        const image = document.createElement('img')
        image.alt = `Video ${station.name}`
        const status = document.createElement('span')
        status.textContent = 'Apri video per visualizzare'
        frame.append(image, status)
        open.addEventListener('click', () => {
          const expanded = row.classList.toggle('expanded')
          open.textContent = expanded ? 'Riduci video' : 'Apri video'
          if (expanded) {
            image.src = new URL(`api/intercom/external-stations/${encodeURIComponent(station.id)}/video`, root).toString()
            status.hidden = true
          } else {
            image.removeAttribute('src')
            status.hidden = false
          }
        })
        row.append(icon, copy, frame)
        anchor.after(row)
        anchor = row
      }
    } catch (_) { /* Keep the current station list if the server is temporarily unreachable. */ }
  }
  refreshExternalStations()
  setInterval(refreshExternalStations, 30000)
  async function refreshInternalStations() {
    try {
      const response = await fetch(new URL('api/intercom/internal-stations', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const {names, tablets = []} = await response.json()
      for (const [extension, name] of Object.entries(names)) {
        const label = document.querySelector(`[data-dial-extension="${extension}"]`)?.closest('.intercom-station-row')?.querySelector('.station-copy strong')
        if (label) label.textContent = name
      }
      document.querySelectorAll('.control4-extra-row').forEach(row => row.remove())
      let anchor = $('#call-tavolo').closest('.intercom-station-row')
      for (const tablet of tablets) {
        const row = document.createElement('div')
        row.className = 'intercom-station-row control4-extra-row'
        const icon = document.createElement('span')
        icon.className = 'station-icon'
        icon.textContent = '▣'
        const copy = document.createElement('div')
        copy.className = 'station-copy'
        const title = document.createElement('strong')
        title.textContent = tablet.name
        const subtitle = document.createElement('small')
        subtitle.textContent = `Tablet Control4 · interno ${tablet.extension} · ${tablet.ready ? 'chiamata da provare' : 'rotta non confermata'}`
        const dial = document.createElement('button')
        dial.type = 'button'
        dial.textContent = 'CHIAMA'
        dial.dataset.dialExtension = tablet.extension
        dial.dataset.stationReady = String(tablet.ready)
        dial.dataset.videoCapable = 'true'
        dial.disabled = !tablet.ready || !phone?.isRegistered() || !!call
        copy.append(title, subtitle)
        row.append(icon, copy, dial)
        anchor.after(row)
        anchor = row
      }
    } catch (_) { /* Keep the last labels while offline. */ }
  }
  refreshInternalStations()
  setInterval(refreshInternalStations, 30000)
  async function refreshVoipPhones() {
    try {
      const response = await fetch(new URL('api/intercom/voip-phones', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const {phones} = await response.json()
      document.querySelectorAll('.voip-phone-row').forEach(row => row.remove())
      const control4Rows = [...document.querySelectorAll('.control4-extra-row')]
      let anchor = control4Rows.at(-1) || $('#call-tavolo').closest('.intercom-station-row')
      for (const device of phones) {
        const row = document.createElement('div')
        row.className = 'intercom-station-row voip-phone-row'
        const icon = document.createElement('span')
        icon.className = 'station-icon'
        icon.textContent = '☎'
        const copy = document.createElement('div')
        copy.className = 'station-copy'
        const title = document.createElement('strong')
        title.textContent = device.name
        const subtitle = document.createElement('small')
        subtitle.textContent = `${device.extension} · ${device.profile === 'voip_video' ? 'VoIP video' : 'VoIP audio'} · ${device.endpoint_present ? 'registrazione da verificare' : 'non configurato'}`
        const dial = document.createElement('button')
        dial.type = 'button'
        dial.textContent = 'CHIAMA'
        dial.dataset.dialExtension = device.extension
        dial.dataset.stationReady = String(device.endpoint_present)
        dial.dataset.videoCapable = String(device.profile === 'voip_video')
        dial.disabled = !device.endpoint_present || !phone?.isRegistered() || !!call
        copy.append(title, subtitle)
        row.append(icon, copy, dial)
        anchor.after(row)
        anchor = row
      }
    } catch (_) { /* Keep last known list while offline. */ }
  }
  refreshVoipPhones()
  setInterval(refreshVoipPhones, 30000)
  let personalDevicesSignature = ''
  let personalDevicesRequest = 0
  async function refreshPersonalDevices() {
    const requestId = ++personalDevicesRequest
    try {
      const response = await fetch(new URL('api/intercom/personal-devices', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const {devices} = await response.json()
      if (requestId !== personalDevicesRequest) return
      const signature = JSON.stringify({ownExtension, devices:devices.map(device => ({
        id:device.id, name:device.name, owner:device.owner, extension:device.extension,
        device_type:device.device_type, video_capable:device.video_capable, video_enabled:device.video_enabled,
      }))})
      if (signature === personalDevicesSignature) return
      personalDevicesSignature = signature
      document.querySelectorAll('.personal-device-row').forEach(row => row.remove())
      const voipRows = [...document.querySelectorAll('.voip-phone-row')]
      const control4Rows = [...document.querySelectorAll('.control4-extra-row')]
      let anchor = voipRows.at(-1) || control4Rows.at(-1) || $('#call-tavolo').closest('.intercom-station-row')
      for (const device of devices) {
        const row = document.createElement('div')
        row.className = 'intercom-station-row personal-device-row'
        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
        icon.setAttribute('class', 'station-icon')
        icon.setAttribute('viewBox', '0 0 24 24')
        icon.innerHTML = device.device_type === 'phone'
          ? '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M10 18h4"/>'
          : device.device_type === 'tablet'
            ? '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M11 18h2"/>'
            : '<path d="M3 4h18v13H3zM8 21h8M12 17v4"/>'
        const copy = document.createElement('div')
        copy.className = 'station-copy'
        const title = document.createElement('strong')
        title.textContent = device.name
        const subtitle = document.createElement('small')
        subtitle.textContent = `${device.owner} · interno ${device.extension} · ${device.video_capable && device.video_enabled ? 'video' : 'audio'}${device.extension === ownExtension ? ' · questo dispositivo' : ''}`
        copy.append(title, subtitle)
        if (device.extension === ownExtension) {
          row.classList.add('current-device-row')
          const controls = document.createElement('div'); controls.className = 'current-device-controls'
          const levelControl=(label,source)=>{const wrap=document.createElement('label'),output=document.createElement('output'),slider=source.cloneNode();slider.removeAttribute('id');output.textContent=`${source.value}%`;wrap.append(document.createTextNode(label),output,slider);slider.addEventListener('input',()=>{source.value=slider.value;source.dispatchEvent(new Event('input'));output.textContent=`${slider.value}%`});return wrap}
          controls.append(levelControl('Volume altoparlante',$('#speaker-gain')),levelControl('Livello microfono',$('#microphone-gain')))
          const dnd = document.createElement('button'); dnd.type='button'; dnd.className='dnd-switch'
          const renderDnd=()=>{ dnd.classList.toggle('active',deviceDnd); dnd.innerHTML=`<span class="mdi-switch"></span><b>DND ${deviceDnd?'ATTIVO':'DISATTIVO'}</b>` }
          renderDnd(); dnd.addEventListener('click', async()=>{
            const next=!deviceDnd
            const response=await fetch(new URL(`api/intercom/personal-device/${encodeURIComponent(currentDeviceId)}/preferences`,root),{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:device.name,ringtone:ringPreferences.ringtone,ring_volume:ringPreferences.ring_volume,vibration:ringPreferences.vibration,silent:ringPreferences.silent,dnd:next})})
            if(!response.ok){const data=await response.json().catch(()=>({}));error(data.detail||'DND non aggiornato');return}
            deviceDnd=next; renderDnd()
          }); controls.append(dnd); row.append(icon,copy,controls); $('.doorbird-row').after(row)
        } else {
          const dial = document.createElement('button'); dial.type='button'; dial.textContent='CHIAMA'; dial.dataset.dialExtension=device.extension; dial.dataset.stationReady='true'; dial.dataset.videoCapable='true'; dial.disabled=!phone?.isRegistered()||!!call
          row.append(icon,copy,dial); anchor.after(row); anchor=row
        }
      }
    } catch (_) { /* Keep last known list while offline. */ }
  }
  refreshPersonalDevices()
  setInterval(refreshPersonalDevices, 30000)
  async function refreshGroups() {
    try {
      const response=await fetch(new URL('api/intercom/groups',root),{cache:'no-store',credentials:'same-origin'})
      if(!response.ok)return
      const {groups}=await response.json()
      document.querySelectorAll('.custom-group-row').forEach(row=>row.remove())
      const all=groups.find(group=>group.extension==='8290')
      if(all) $('#call-control4').previousElementSibling.querySelector('strong').textContent=all.name
      let anchor=$('#call-control4').closest('.intercom-station-row')
      for(const group of groups.filter(group=>group.extension!=='8290')){
        const row=document.createElement('div');row.className='intercom-station-row custom-group-row'
        row.innerHTML='<svg class="station-icon" viewBox="0 0 24 24"><path d="M4 8h4l4-3v14l-4-3H4zM16 9c2 2 2 4 0 6M19 6c4 4 4 8 0 12"/></svg><div class="station-copy"><strong></strong><small></small></div><button>CHIAMA</button>'
        row.querySelector('strong').textContent=group.name;row.querySelector('small').textContent=`Gruppo ${group.extension} · ${group.members.length} interni`
        const button=row.querySelector('button');button.dataset.dialExtension=group.extension;button.dataset.videoCapable='true';button.disabled=!phone?.isRegistered()||!!call
        anchor.after(row);anchor=row
      }
    }catch(_){}
  }
  refreshGroups();setInterval(refreshGroups,30000)
  $('#doorbird-expand').addEventListener('click', () => {
    const expanded = $('.doorbird-row').classList.toggle('expanded')
    $('#doorbird-expand').setAttribute('aria-expanded', String(expanded))
    $('#doorbird-expand').textContent = expanded ? 'Riduci video' : 'Apri video'
  })

  function startDoorbirdVideo() {
    if (doorbirdStopped || document.hidden || !intercomVisible) return
    clearTimeout(doorbirdTimer)
    clearTimeout(doorbirdRetryTimer)
    doorbirdAbort?.abort()
    doorbirdVideoActive = true
    const image = $('#doorbird-image')
    image.onerror = () => {
      if (!doorbirdVideoActive || doorbirdStopped || document.hidden || !intercomVisible) return
      doorbirdVideoActive = false
      image.onerror = null
      image.removeAttribute('src')
      $('#doorbird-image-status').textContent = 'Video interrotto. Caricamento immagini...'
      $('#doorbird-image-status').hidden = false
      refreshDoorbird()
      doorbirdRetryTimer = setTimeout(startDoorbirdVideo, 30000)
    }
    image.onload = () => {
      if (!doorbirdVideoActive) return
      image.hidden = false
      $('#doorbird-image-status').hidden = true
    }
    image.src = new URL('api/intercom/doorbird/video', root).toString()
  }

  async function refreshDoorbird() {
    if (doorbirdStopped || document.hidden || !intercomVisible) return
    doorbirdAbort = new AbortController()
    try {
      const response = await fetch(new URL('api/intercom/doorbird/image', root), {
        cache:'no-store', credentials:'same-origin', signal:doorbirdAbort.signal
      })
      if (response.status === 204) throw new Error('Immagine non autorizzata da DoorBird in questo momento.')
      if (!response.ok) throw new Error('Immagine DoorBird non disponibile.')
      const blob = await response.blob()
      if (doorbirdStopped || document.hidden || !intercomVisible) return
      const nextUrl = URL.createObjectURL(blob)
      const previousUrl = doorbirdImageUrl
      doorbirdImageUrl = nextUrl
      const image = $('#doorbird-image')
      image.src = nextUrl
      image.hidden = false
      $('#doorbird-image-status').hidden = true
      if (previousUrl) URL.revokeObjectURL(previousUrl)
    } catch (exception) {
      if (exception.name !== 'AbortError') {
        $('#doorbird-image-status').textContent = exception.message
        $('#doorbird-image-status').hidden = false
        $('#doorbird-image').hidden = true
      }
    } finally {
      doorbirdAbort = null
      if (!doorbirdStopped && !document.hidden && intercomVisible && !doorbirdVideoActive) doorbirdTimer = setTimeout(refreshDoorbird, 2000)
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden || !intercomVisible) {
      clearTimeout(doorbirdTimer)
      clearTimeout(doorbirdRetryTimer)
      doorbirdAbort?.abort()
      doorbirdVideoActive = false
      $('#doorbird-image').removeAttribute('src')
    } else {
      startDoorbirdVideo()
    }
  })
  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'eface-intercom-visible') return
    intercomVisible = !!event.data.visible
    if (intercomVisible) {
      startDoorbirdVideo()
      if (call?.direction === 'incoming' && ringtoneActive) {
        prepareRingtoneAudio().play().catch(() => {
          audioContext?.resume().then(() => {
            ringBurst()
            if (!ringtoneTimer) ringtoneTimer = setInterval(ringBurst, 2200)
          }).catch(() => {})
        })
      }
    }
    else {
      clearTimeout(doorbirdTimer)
      clearTimeout(doorbirdRetryTimer)
      doorbirdAbort?.abort()
      doorbirdVideoActive = false
      $('#doorbird-image').removeAttribute('src')
    }
  })
  window.addEventListener('pagehide', () => {
    doorbirdStopped = true
    clearTimeout(doorbirdTimer)
    clearTimeout(doorbirdRetryTimer)
    doorbirdAbort?.abort()
    doorbirdVideoActive = false
    $('#doorbird-image').removeAttribute('src')
    if (doorbirdImageUrl) URL.revokeObjectURL(doorbirdImageUrl)
  })
  if (!adminMode) startDoorbirdVideo()
  const icePreferenceKey = 'eface-intercom-fast-ice-v1'
  let icePreference = null
  try { icePreference = localStorage.getItem(icePreferenceKey) } catch (_) { /* storage unavailable */ }
  if (icePreference === '1' || icePreference === '0') $('#fast-ice').checked = icePreference === '1'
  $('#fast-ice').addEventListener('change', () => {
    icePreference = $('#fast-ice').checked ? '1' : '0'
    try { localStorage.setItem(icePreferenceKey, icePreference) } catch (_) { /* storage unavailable */ }
  })
  const iceHint = document.createElement('small')
  iceHint.textContent = 'In rete locale: attiva per far squillare subito. Da remoto: disattiva per usare TURN. La scelta resta su questo dispositivo.'
  $('#fast-ice').closest('label').after(iceHint)
  $('#sip-password').parentElement.firstChild.textContent = 'Password SIP alternativa (facoltativa)'
  $('#sip-password').placeholder = 'Vuoto = usa la credenziale salvata in e-Face'
  if (adminMode) $('.intercom-settings').open = true
  for (const [id, fallback] of [['speaker-gain', 100], ['microphone-gain', 100]]) {
    try {
      const stored = Number(localStorage.getItem(`eface-intercom-${id}-${id === 'speaker-gain' ? 'v2' : 'v1'}`))
      if (stored >= Number($(`#${id}`).min) && stored <= Number($(`#${id}`).max)) $(`#${id}`).value = stored
    } catch (_) { /* storage unavailable */ }
    $(`#${id}-value`).textContent = `${$(`#${id}`).value || fallback}%`
  }

  async function loadIce() {
    const response = await fetch(new URL('api/intercom/ice', root), {cache:'no-store'})
    if (!response.ok) throw new Error('Configurazione audio remoto non disponibile')
    iceServers = (await response.json()).iceServers || []
    if (icePreference === null) $('#fast-ice').checked = iceServers.length === 0
  }

  function peerConfig() {
    return $('#fast-ice').checked || !iceServers.length
      ? {iceServers: []}
      : {iceServers, iceTransportPolicy: 'relay'}
  }

  function setDialButtonsDisabled(disabled) {
    document.querySelectorAll('[data-dial-extension]').forEach((button) => {
      button.disabled = disabled || button.dataset.stationReady === 'false'
    })
  }

  async function prepareSpeaker() {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) return
      audioContext = new AudioContextClass()
    }
    if (audioContext.state !== 'running') await audioContext.resume()
    $('#remote-audio').volume = Number($('#speaker-gain').value) / 100
  }

  async function playRemoteAudio() {
    if (!$('#remote-audio').srcObject) return
    try {
      await $('#remote-audio').play()
      $('#audio-retry').hidden = true
    } catch (_) {
      $('#audio-retry').hidden = false
      $('#audio-status').textContent = 'Audio bloccato dal browser: premi ATTIVA AUDIO'
    }
  }

  function ringBurst() {
    if (!ringtoneActive || ringPreferences.silent || !audioContext || audioContext.state !== 'running') return
    const now = audioContext.currentTime
    const patterns = {classic:[[880,0],[660,.24]], double:[[760,0],[760,.18],[940,.48]], soft:[[520,0],[650,.3]]}
    for (const [frequency, delay] of patterns[ringPreferences.ringtone] || patterns.classic) {
      const oscillator = audioContext.createOscillator()
      const gain = audioContext.createGain()
      oscillator.frequency.value = frequency
      oscillator.type = ringPreferences.ringtone === 'soft' ? 'sine' : 'square'
      gain.gain.setValueAtTime(0.0001, now + delay)
      const peak = ringPreferences.ringtone === 'soft' ? .75 : 1
      gain.gain.exponentialRampToValueAtTime(Math.max(.001, peak * ringPreferences.ring_volume / 100), now + delay + .025)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + delay + .2)
      oscillator.connect(gain)
      gain.connect(audioContext.destination)
      oscillator.start(now + delay)
      oscillator.stop(now + delay + .22)
    }
  }

  function makeRingtoneWav(kind) {
    const sampleRate = 16000, count = Math.floor(sampleRate * 2.2)
    const buffer = new ArrayBuffer(44 + count * 2), view = new DataView(buffer)
    const text = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)))
    text(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); text(8, 'WAVE'); text(12, 'fmt ')
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
    text(36, 'data'); view.setUint32(40, count * 2, true)
    const notes = {
      doorbell:[[0,.58,784],[.66,.62,523],[1.38,.38,784]], dingdong:[[0,.72,659],[.78,.82,440]],
      double:[[0,.42,740],[.52,.42,740],[1.12,.48,932]], bell:[[0,1.45,587],[1.5,.55,784]],
      soft:[[0,.65,523],[.72,.75,659]], classic:[[0,.42,880],[.5,.48,660]]
    }[kind] || [[0,.58,784],[.66,.62,523],[1.38,.38,784]]
    for (let index = 0; index < count; index += 1) {
      const time = index / sampleRate
      let sample = 0
      for (const [start, length, frequency] of notes) {
        const age = time - start
        if (age < 0 || age >= length) continue
        const envelope = Math.min(1, age / .012) * Math.exp(-3.2 * age / length)
        sample += envelope * (Math.sin(2*Math.PI*frequency*age) + .48*Math.sin(2*Math.PI*frequency*2.01*age) + .2*Math.sin(2*Math.PI*frequency*3.98*age))
      }
      view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample * .5)) * 32767, true)
    }
    return URL.createObjectURL(new Blob([buffer], {type:'audio/wav'}))
  }

  function prepareRingtoneAudio() {
    const player = $('#ringtone-audio')
    if (!ringtoneUrl || ringtoneKind !== ringPreferences.ringtone) {
      if (ringtoneUrl) URL.revokeObjectURL(ringtoneUrl)
      ringtoneKind = ringPreferences.ringtone
      ringtoneUrl = makeRingtoneWav(ringtoneKind)
      player.src = ringtoneUrl
    }
    player.volume = Number(ringPreferences.ring_volume) / 100
    player.currentTime = 0
    return player
  }

  async function unlockRingtoneAudio() {
    const player = prepareRingtoneAudio()
    const savedVolume = player.volume
    player.volume = 0
    try {
      await player.play()
      player.pause()
      player.currentTime = 0
      player.volume = savedVolume
      document.documentElement.dataset.ringtoneUnlocked = 'true'
      return true
    } catch (_) {
      player.volume = savedVolume
      return false
    }
  }
  window.efaceUnlockIntercomAudio = unlockRingtoneAudio
  document.addEventListener('pointerdown', unlockRingtoneAudio, {once:true, capture:true})

  async function startRingtone() {
    if (ringtoneActive) return
    ringtoneActive = true
    if (ringPreferences.vibration) navigator.vibrate?.([500, 250, 500, 900, 500, 250, 500])
    if (ringPreferences.silent) return
    try {
      await prepareRingtoneAudio().play()
    } catch (_) {
      try {
        await prepareSpeaker()
        ringBurst()
        ringtoneTimer = setInterval(ringBurst, 2200)
      } catch (_) {
        $('#audio-retry').textContent = 'ATTIVA SUONERIA'
        $('#audio-retry').hidden = false
      }
    }
  }

  function stopRingtone() {
    ringtoneActive = false
    clearInterval(ringtoneTimer)
    ringtoneTimer = null
    $('#ringtone-audio').pause()
    $('#ringtone-audio').currentTime = 0
    navigator.vibrate?.(0)
    $('#audio-retry').textContent = 'ATTIVA AUDIO'
  }

  $('#audio-retry').addEventListener('click', async () => {
    if (call?.direction === 'incoming' && !call.isEstablished?.()) {
      ringtoneActive = false
      await startRingtone()
      return
    }
    await playRemoteAudio()
  })

  function error(message) {
    $('#intercom-error').textContent = message
    $('#intercom-error').hidden = !message
  }

  function connection(connected, text) {
    $('#intercom-state').textContent = text
    $('#intercom-dot').classList.toggle('online', connected)
    $('#sip-connect').disabled = connected
    $('#sip-disconnect').disabled = !phone
    setDialButtonsDisabled(!connected || !!call)
    publishIntercomState(connected ? 'available' : 'idle')
  }

  function clearCall(text) {
    stopRingtone()
    clearTimeout(doorbirdAlertTimer)
    doorbirdAlertActive = false
    clearInterval(callDoorbirdTimer)
    call = null
    if (updateAvailable) { location.reload(); return }
    clearInterval(audioStatsTimer)
    audioStatsTimer = null
    $('#intercom-call-panel').hidden = true
    releaseMicrophone()
    $('#remote-audio').srcObject = null
    $('#remote-video').srcObject = null
    $('#call-doorbird-preview').removeAttribute('src')
    $('#call-doorbird-preview').hidden = true
    $('#local-video').srcObject = null
    $('.local-video-wrap').hidden = true
    $('#intercom-video-panel').classList.remove('has-local')
    $('#intercom-video-panel').hidden = true
    document.body.classList.remove('video-call-active')
    $('#remote-video-placeholder').hidden = false
    $('#video-status').textContent = 'Video: in attesa'
    activeVideoSender = null
    $('#audio-retry').hidden = true
    $('#audio-status').textContent = 'Audio in ingresso: in attesa'
    $('#call-status').textContent = text
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = true
    setDialButtonsDisabled(!phone || !phone.isRegistered())
    publishIntercomState(phone?.isRegistered() ? 'available' : 'idle')
  }

  function closeDoorbirdAlert() {
    clearTimeout(doorbirdAlertTimer)
    doorbirdAlertActive = false
    clearInterval(callDoorbirdTimer)
    if (call) return
    stopRingtone()
    $('#intercom-call-panel').hidden = true
    $('#intercom-video-panel').hidden = true
    $('#call-doorbird-preview').removeAttribute('src')
    $('#call-doorbird-preview').hidden = true
    $('#remote-video-placeholder').hidden = false
    $('#call-status').textContent = 'Nessuna chiamata in corso.'
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = true
  }

  function showCallDoorbirdVideo(stationId = 'ingresso') {
    clearInterval(callDoorbirdTimer)
    const preview = $('#call-doorbird-preview')
    const refresh = () => {
      preview.src = new URL(`api/intercom/external-stations/${encodeURIComponent(stationId)}/image?t=${Date.now()}`, root).toString()
      preview.hidden = false
    }
    refresh()
    callDoorbirdTimer = setInterval(refresh, 1200)
    $('#remote-video-placeholder').hidden = true
    $('#intercom-video-panel').hidden = false
    $('#video-status').textContent = 'Video live DoorBird attivo'
  }

  function showDoorbirdIncoming(stationId = 'ingresso') {
    clearTimeout(doorbirdAlertTimer)
    doorbirdAlertActive = true
    showCallDoorbirdVideo(stationId)
    $('#intercom-call-panel').hidden = false
    $('#call-title').textContent = 'Chiamata da DoorBird'
    $('#call-status').textContent = 'DoorBird sta chiamando · attendo la sessione audio SIPâ€¦'
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = false
    $('#video-status').textContent = 'Video live DoorBird attivo'
    requestAnimationFrame(() => $('#intercom-video-panel').scrollIntoView({behavior:'smooth', block:'start'}))
    if (!call) startRingtone()
    doorbirdAlertTimer = setTimeout(closeDoorbirdAlert, 45000)
  }

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'eface-doorbird-incoming') return
    showDoorbirdIncoming(event.data.station_id)
  })
  if (pushedDoorbird) setTimeout(() => showDoorbirdIncoming(pushedDoorbird), 250)

  $('#speaker-gain').addEventListener('input', () => {
    const percent = Number($('#speaker-gain').value)
    $('#speaker-gain-value').textContent = `${percent}%`
    try { localStorage.setItem('eface-intercom-speaker-gain-v2', String(percent)) } catch (_) { /* storage unavailable */ }
    $('#remote-audio').volume = percent / 100
  })

  $('#microphone-gain').addEventListener('input', () => {
    const percent = Number($('#microphone-gain').value)
    $('#microphone-gain-value').textContent = `${percent}%`
    try { localStorage.setItem('eface-intercom-microphone-gain-v1', String(percent)) } catch (_) { /* storage unavailable */ }
    if (micGain) micGain.gain.value = percent / 100
  })

  function releaseMicrophone() {
    if (micSource) micSource.disconnect()
    if (micGain) micGain.disconnect()
    if (micOutput) micOutput.getTracks().forEach((track) => track.stop())
    if (micInput) micInput.getTracks().forEach((track) => track.stop())
    if (localVideoStream) localVideoStream.getTracks().forEach((track) => track.stop())
    micInput = micOutput = micSource = micGain = null
    localVideoStream = null
  }

  async function prepareCameraPreview() {
    const existing = localVideoStream?.getVideoTracks?.().find(track => track.readyState === 'live')
    if (existing) return existing
    if (!videoCapable || !videoEnabled) return null
      $('#intercom-video-panel').hidden = false
      $('#video-status').textContent = 'Richiesta accesso alla camera…'
    try {
        try {
          localVideoStream = await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:cameraFacing},width:{ideal:1280},height:{ideal:720}}})
        } catch (firstError) {
          if (firstError?.name === 'NotAllowedError' || firstError?.name === 'SecurityError') throw firstError
          localVideoStream = await navigator.mediaDevices.getUserMedia({audio:false,video:true})
        }
        const track = localVideoStream.getVideoTracks()[0]
        if (!track) throw new Error('Nessuna camera disponibile')
        $('#local-video').srcObject = localVideoStream
        $('.local-video-wrap').hidden = false
        $('#intercom-video-panel').classList.add('has-local')
        $('.local-video-wrap').classList.toggle('environment', cameraFacing === 'environment')
        $('#intercom-video-panel').hidden = false
        $('#video-status').textContent = 'Video locale pronto'
        requestAnimationFrame(() => $('#intercom-video-panel').scrollIntoView({behavior:'smooth', block:'start'}))
        return track
    } catch (exception) {
        const denied = exception?.name === 'NotAllowedError' || exception?.name === 'SecurityError'
        $('#video-status').textContent = denied ? 'Permesso camera negato · abilitalo nelle impostazioni del dispositivo' : `Camera non disponibile · ${exception?.message || 'chiamata solo audio'}`
        return null
    }
  }

  async function preparedMicrophone(includeVideo = false) {
    micInput = await microphone()
    if (!audioContext) micOutput = micInput
    else {
      micSource = audioContext.createMediaStreamSource(micInput)
      micGain = audioContext.createGain()
      micGain.gain.value = Number($('#microphone-gain').value) / 100
      const destination = audioContext.createMediaStreamDestination()
      micSource.connect(micGain)
      micGain.connect(destination)
      micOutput = destination.stream
    }
    if (includeVideo) {
      const track = await prepareCameraPreview()
      if (track) micOutput.addTrack(track)
    }
    return micOutput
  }

  function sessionOffersVideo(session) {
    const bodies = [session?.request?.body, session?._request?.body, session?._remote_sdp]
    if (bodies.some((body) => /(?:^|\r?\n)m=video\s/i.test(body || ''))) return true
    return !!session?.connection?.getTransceivers?.().some((item) => item.receiver?.track?.kind === 'video')
  }

  function track(session) {
    if (session.direction === 'incoming' && deviceDnd) {
      rejectIncomingUntil = Date.now() + 1500
      session.terminate({status_code:486, reason_phrase:'DND'})
      publishIntercomState(phone?.isRegistered() ? 'available' : 'idle')
      return
    }
    call = session
    clearTimeout(doorbirdAlertTimer)
    doorbirdAlertActive = false
    $('#intercom-call-panel').hidden = false
    $('#audio-status').textContent = 'Connessione audio in preparazione…'
    const remoteOffersVideo = session.direction === 'incoming' && sessionOffersVideo(session)
    const remoteExtension = String(session.remote_identity?.uri?.user || '')
    const remoteName = String(session.remote_identity?.display_name || '').toLowerCase()
    const targetName = String(session.data?.efaceTargetName || session.remote_identity?.display_name || session.remote_identity?.uri?.user || 'interno')
    $('#call-title').textContent = session.direction === 'incoming' ? `Chiamata da ${targetName}` : `Chiamata a ${targetName}`
    const doorbirdCaller = ['8000','8201','8290'].includes(remoteExtension) || ['doorbird','ingresso','cancello'].some(name => remoteName.includes(name))
    const externalStation = externalVideoByExtension.get(remoteExtension) || (doorbirdCaller ? externalVideoByExtension.values().next().value : '')
    if (session.direction === 'incoming' && externalStation) {
      showCallDoorbirdVideo(externalStation)
    }
    const personalIncoming = session.direction === 'incoming' && /^83[0-9]{2}$/.test(remoteExtension)
    if (remoteOffersVideo || personalIncoming) {
      document.body.classList.add('video-call-active')
      $('#intercom-video-panel').hidden = false
      $('#video-status').textContent = 'Preparo il video prima della risposta…'
      requestAnimationFrame(() => $('#intercom-video-panel').scrollIntoView({behavior:'smooth', block:'start'}))
      if (session.direction === 'incoming') prepareCameraPreview()
    }
    let iceReadyTimer = null
    let iceReadySent = false
    let boundConnection = null
    let connectionPollTimer = null
    $('#call-status').textContent = session.direction === 'incoming' ? `Chiamata da ${targetName}` : `Chiamata a ${targetName}…`
    $('#call-answer').disabled = session.direction !== 'incoming'
    $('#call-hangup').disabled = false
    setDialButtonsDisabled(true)
    if (session.direction === 'incoming') {
      publishIntercomState('ringing')
      if (window.parent !== window) {
        window.parent.postMessage({type:'eface-intercom-incoming'}, location.origin)
        setTimeout(startRingtone, 120)
      } else startRingtone()
    }
    function syncRemoteAudio(peerconnection) {
      const receiver = peerconnection.getReceivers?.().find((item) => item.track?.kind === 'audio' && item.track.readyState === 'live')
      if (!receiver || $('#remote-audio').srcObject?.getAudioTracks?.()[0] === receiver.track) return
      $('#remote-audio').srcObject = new MediaStream([receiver.track])
      playRemoteAudio()
    }
    function syncRemoteVideo(peerconnection) {
      const receiver = peerconnection.getReceivers?.().find((item) => item.track?.kind === 'video' && item.track.readyState === 'live')
      if (!receiver || $('#remote-video').srcObject?.getVideoTracks?.()[0] === receiver.track) return
      $('#remote-video').srcObject = new MediaStream([receiver.track])
      $('#remote-video-placeholder').hidden = true
      $('#intercom-video-panel').hidden = false
      $('#video-status').textContent = 'Video remoto attivo'
      $('#remote-video').play().catch(() => {})
    }
    function bindConnection(peerconnection) {
      if (!peerconnection || boundConnection === peerconnection) return
      boundConnection = peerconnection
      clearInterval(connectionPollTimer)
      connectionPollTimer = null
      $('#audio-status').textContent = 'Connessione audio rilevata, attendo i pacchetti…'
      clearInterval(audioStatsTimer)
      audioStatsTimer = setInterval(async () => {
        try {
          if (session.isEnded?.() || ['closed', 'failed'].includes(peerconnection.connectionState)) {
            clearCall('Chiamata terminata.')
            return
          }
          syncRemoteAudio(peerconnection)
          syncRemoteVideo(peerconnection)
          const stats = await peerconnection.getStats()
          let packets = 0
          stats.forEach((item) => { if (item.type === 'inbound-rtp' && (item.kind === 'audio' || item.mediaType === 'audio')) packets += item.packetsReceived || 0 })
          if (call !== session) return
          const player = $('#remote-audio').paused ? 'riproduzione sospesa' : 'riproduzione attiva'
          $('#audio-status').textContent = `Audio ricevuto: ${packets} pacchetti · ${player}`
          if (packets > 0 && $('#remote-audio').paused) $('#audio-retry').hidden = false
        } catch (_) { if (call === session) $('#audio-status').textContent = 'Statistiche audio non disponibili nel browser' }
      }, 2000)
      peerconnection.addEventListener('track', (event) => {
        if (event.track.kind === 'audio') {
          $('#remote-audio').srcObject = event.streams[0] || new MediaStream([event.track])
          playRemoteAudio()
        } else if (event.track.kind === 'video') syncRemoteVideo(peerconnection)
      })
      peerconnection.addEventListener('connectionstatechange', () => {
        if (call !== session || !['closed', 'failed'].includes(peerconnection.connectionState)) return
        clearCall('Chiamata terminata.')
      })
      syncRemoteAudio(peerconnection)
      syncRemoteVideo(peerconnection)
    }
    session.on('peerconnection', ({peerconnection}) => bindConnection(peerconnection))
    bindConnection(session.connection)
    if (!boundConnection) connectionPollTimer = setInterval(() => bindConnection(session.connection), 250)
    session.on('connecting', () => { $('#call-title').textContent = session.direction === 'incoming' ? `Chiamata da ${targetName}` : `Chiamata a ${targetName}` })
    session.on('icecandidate', ({candidate, ready}) => {
      const fastLocal = $('#fast-ice').checked || !iceServers.length
      const usable = fastLocal
        ? candidate?.type === 'host' && candidate?.protocol?.toLowerCase() === 'udp'
        : candidate?.type === 'relay'
      if (iceReadyTimer || iceReadySent || !usable) return
      iceReadyTimer = setTimeout(() => {
        iceReadyTimer = null
        iceReadySent = true
        ready()
      }, fastLocal ? 1500 : 250)
    })
    session.on('sdp', ({originator}) => { if (originator === 'local') clearTimeout(iceReadyTimer) })
    session.on('sending', () => { $('#call-title').textContent = `Chiamata a ${targetName}` })
    session.on('progress', () => { $('#call-status').textContent = `Chiamata a ${targetName} · squilla…` })
    session.on('confirmed', () => { stopRingtone(); publishIntercomState('active'); $('#call-status').textContent = `In conversazione con ${targetName}`; bindConnection(session.connection); if (boundConnection) { syncRemoteAudio(boundConnection); syncRemoteVideo(boundConnection); activeVideoSender=boundConnection.getSenders?.().find(sender=>sender.track?.kind==='video') || null } playRemoteAudio() })
    session.on('ended', () => { clearTimeout(iceReadyTimer); clearInterval(connectionPollTimer); clearCall('Chiamata terminata.') })
    session.on('failed', ({cause}) => {
      clearTimeout(iceReadyTimer);clearInterval(connectionPollTimer)
      const retryAudio=session.direction==='outgoing'&&session._efaceHadVideo&&!session._efaceRetried&&/488|not acceptable|unsupported|media/i.test(String(cause||''))
      const target=session._efaceTarget
      clearCall(retryAudio?'Video non compatibile · riprovo solo audio…':`Chiamata non riuscita: ${cause || 'errore sconosciuto'}`)
      if(retryAudio&&target&&phone?.isRegistered())setTimeout(async()=>{try{const stream=await preparedMicrophone(false);const retry=phone.call(`sip:${target}@asterisk`,{mediaStream:stream,mediaConstraints:{audio:true,video:false},pcConfig:peerConfig(),data:{efaceTarget:target,efaceTargetName:targetName}});retry._efaceTarget=target;retry._efaceRetried=true}catch(exception){releaseMicrophone();error(exception.message)}},180)
    })
    session.on('getusermediafailed', ({name, message}) => error(`Microfono: ${name || 'errore'} ${message || ''}`))
  }

  async function microphone() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microfono non disponibile: apri e-Face direttamente tramite HTTPS, fuori dalla finestra e-Control.')
    }
    try {
      return await navigator.mediaDevices.getUserMedia({audio:true, video:false})
    } catch (exception) {
      if (exception.name === 'NotAllowedError' || exception.name === 'PermissionDeniedError') {
        throw new Error('Permesso microfono negato. Abilitalo nelle impostazioni del sito e-Face in Chrome.')
      }
      throw new Error(`Microfono non disponibile: ${exception.name || exception.message}`)
    }
  }

  function pushKeyBytes(value) {
    const padding = '='.repeat((4 - value.length % 4) % 4)
    return Uint8Array.from(atob((value + padding).replace(/-/g, '+').replace(/_/g, '/')), character => character.charCodeAt(0))
  }

  $('#repair-push').addEventListener('click', async event => {
    const button = event.currentTarget
    const statusLine = $('#push-repair-status')
    button.disabled = true
    statusLine.textContent = 'Rigenero la registrazione notifiche…'
    try {
      if (!currentDeviceId || !/^83\d{2}$/.test(ownExtension)) throw new Error('Prima premi COLLEGA per registrare questo dispositivo')
      if (!('serviceWorker' in navigator) || !('PushManager' in window) || !window.isSecureContext) throw new Error('Apri e-Face installata tramite HTTPS')
      if (Notification.permission === 'denied') throw new Error('Abilita le notifiche nelle impostazioni Android di Chrome/e-Face')
      if (Notification.permission !== 'granted' && await Notification.requestPermission() !== 'granted') throw new Error('Autorizzazione notifiche non concessa')
      const registration = await navigator.serviceWorker.register(new URL('service-worker.js', root), {scope:new URL('./', root).pathname})
      await navigator.serviceWorker.ready
      const previous = await registration.pushManager.getSubscription()
      await fetch(new URL(`api/intercom/push/subscription/${encodeURIComponent(currentDeviceId)}`, root), {method:'DELETE', credentials:'same-origin'}).catch(() => null)
      if (previous) await previous.unsubscribe()
      const keyResponse = await fetch(new URL('api/intercom/push/key', root), {cache:'no-store', credentials:'same-origin'})
      const keyData = await keyResponse.json().catch(() => ({}))
      if (!keyResponse.ok || !keyData.public_key) throw new Error(keyData.detail || 'Chiave notifiche non disponibile')
      const subscription = await registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:pushKeyBytes(keyData.public_key)})
      const saveResponse = await fetch(new URL(`api/intercom/push/subscription/${encodeURIComponent(currentDeviceId)}`, root), {method:'PUT', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify(subscription.toJSON())})
      if (!saveResponse.ok) throw new Error((await saveResponse.json().catch(() => ({}))).detail || 'Registrazione notifiche non salvata')
      const testResponse = await fetch(new URL(`api/intercom/push/call/${encodeURIComponent(ownExtension)}`, root), {method:'POST', credentials:'same-origin'})
      const test = await testResponse.json().catch(() => ({}))
      if (!testResponse.ok || !test.sent) throw new Error(test.detail || 'Il servizio push non ha accettato la prova')
      statusLine.textContent = '✓ Registrazione nuova: notifica di prova inviata.'
    } catch (exception) {
      statusLine.textContent = `Errore: ${exception.message}`
    } finally { button.disabled = false }
  })

  $('#sip-connect').addEventListener('click', async () => {
    let password = $('#sip-password').value
    if (!window.JsSIP) { error('Il client SIP non è disponibile.'); return }
    error('')
    try {
      const statusResponse = await fetch(new URL('api/auth/status', root), {cache:'no-store', credentials:'same-origin'})
      const status = await statusResponse.json()
      if (!statusResponse.ok || !status.user) throw new Error('Accedi a e-Face per usare Intercom')
      let response
      if (status.user === 'admin') {
        response = await fetch(new URL('api/intercom/sip/credential', root), {cache:'no-store', credentials:'same-origin'})
      } else {
        const key = `eface-personal-device-id-${status.user}`
        let deviceId = localStorage.getItem(key)
        if (!deviceId) {
          deviceId = newDeviceId()
          localStorage.setItem(key, deviceId)
        }
        currentDeviceId = deviceId
        const kind = /iPad|Tablet/i.test(navigator.userAgent) || (/Android/i.test(navigator.userAgent) && !/Mobile/i.test(navigator.userAgent)) ? 'tablet' : /iPhone|Android|Mobile/i.test(navigator.userAgent) ? 'phone' : 'desktop'
        const deviceType = {phone:'Cellulare', tablet:'Tablet', desktop:'PC'}[kind]
        let detectedVideo = Boolean(navigator.mediaDevices?.getUserMedia && kind !== 'desktop')
        try { detectedVideo = detectedVideo || (await navigator.mediaDevices?.enumerateDevices?.() || []).some(device => device.kind === 'videoinput') } catch (_) {}
        response = await fetch(new URL('api/intercom/sip/personal-device', root), {
          method:'POST', cache:'no-store', credentials:'same-origin', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({device_id:deviceId, name:`${deviceType} ${status.user}`, device_type:kind, video_capable:detectedVideo}),
        })
      }
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Credenziale SIP non disponibile in e-Face')
      ringPreferences = {ringtone:data.ringtone || 'doorbell', ring_volume:Number.isInteger(data.ring_volume) ? data.ring_volume : 80, vibration:data.vibration !== false, silent:data.silent === true}
      deviceDnd = data.dnd === true
      videoCapable = data.video_capable === true
      videoEnabled = data.video_enabled === true
      cameraFacing = data.camera_facing === 'environment' ? 'environment' : 'user'
      const extension = data.username
      if (!/^[0-9]{4}$/.test(extension)) throw new Error('Interno SIP non valido')
      if (!password) password = data.password
      if (!password) throw new Error('Password SIP mancante')
      ownExtension = extension
      $('#sip-extension').textContent = `INTERNO ${extension}`
      await loadIce()
      const socket = new JsSIP.WebSocketInterface(socketUrl.toString())
      phone = new JsSIP.UA({sockets:[socket], uri:`sip:${extension}@asterisk`, authorization_user:extension, password, display_name:data.name || 'e-Face', register:true, session_timers:false})
      $('#sip-password').value = ''
      connection(false, 'Connessione in corso…')
      $('#sip-connect').disabled = true
      phone.on('registered', () => connection(true, 'Registrato su Asterisk'))
      phone.on('registrationFailed', ({cause}) => {
        const failed = phone
        phone = null
        failed.stop()
        connection(false, 'Registrazione fallita')
        error(`Asterisk: ${cause || 'credenziali o rete non valide'}`)
      })
      phone.on('disconnected', () => connection(false, 'Connessione interrotta'))
      phone.on('newRTCSession', ({session}) => {
        if (session.direction === 'incoming' && Date.now() < rejectIncomingUntil) {
          session.terminate({status_code:486, reason_phrase:'Declined'})
          return
        }
        if (call) { session.terminate(); return }
        track(session)
      })
      phone.start()
      refreshPersonalDevices()
    } catch (exception) {
      phone = null
      connection(false, 'Non collegato')
      error(exception.message)
    }
  })

  $('#sip-disconnect').addEventListener('click', () => {
    if (call) call.terminate()
    if (phone) phone.stop()
    phone = null
    clearCall('Nessuna chiamata in corso.')
    connection(false, 'Non collegato')
  })

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-dial-extension]')
    if (!button || !phone?.isRegistered() || call || button.dataset.stationReady === 'false' || !/^(82[0-9]{2}|8290|8291|8292|83[0-9]{2})$/.test(button.dataset.dialExtension)) return
    error('')
    setDialButtonsDisabled(true)
    $('#call-status').textContent = 'Richiesta accesso al microfono…'
    try {
      const externalStation = button.dataset.externalStation || ''
      const videoDestination = button.dataset.videoCapable === 'true' || !!externalStation
      const targetName = button.closest('.intercom-station-row')?.querySelector('.station-copy strong')?.textContent?.trim() || button.dataset.dialExtension
      if (videoDestination) {
        document.body.classList.add('video-call-active')
        $('#call-title').textContent = `Chiamata a ${targetName}`
        $('#intercom-call-panel').hidden = false
        $('#intercom-video-panel').hidden = false
        $('#video-status').textContent = videoEnabled ? 'Preparazione video…' : 'Camera locale disattivata · attendo il video remoto'
        if (externalStation) showCallDoorbirdVideo(externalStation)
        requestAnimationFrame(() => $('#intercom-video-panel').scrollIntoView({behavior:'smooth', block:'start'}))
      }
      const pushPromise = fetch(new URL(`api/intercom/push/call/${encodeURIComponent(button.dataset.dialExtension)}`, root), {method:'POST', cache:'no-store', credentials:'same-origin'})
        .then(async response => ({response, result:await response.json().catch(() => ({}))}))
        .catch(() => null)
      await prepareSpeaker()
      const includeVideo = videoDestination && !externalStation && videoEnabled
      const stream = await preparedMicrophone(includeVideo)
      if (externalStation) {
        $('#call-status').textContent = 'Preparo la postazione esterna…'
        const response = await fetch(new URL(`api/intercom/external-stations/${encodeURIComponent(externalStation)}/prepare-call`, root),
          {method:'POST', cache:'no-store', credentials:'same-origin'})
        const result = await response.json().catch(() => ({}))
        if (!response.ok || result.extension !== button.dataset.dialExtension) throw new Error(result.detail || 'Postazione esterna non pronta')
      }
      if (!phone?.isRegistered() || call) { releaseMicrophone(); return }
      const push = await pushPromise
      if (push?.response.ok && push.result.sent > 0) {
        $('#call-status').textContent = 'Notifica inviata, attendo il collegamento del dispositivo…'
        await new Promise(resolve => setTimeout(resolve, 4500))
      }
      const session=phone.call(`sip:${button.dataset.dialExtension}@asterisk`, {mediaStream:stream, mediaConstraints:{audio:true, video:stream.getVideoTracks().length > 0}, pcConfig:peerConfig(), data:{efaceTarget:button.dataset.dialExtension, efaceTargetName:targetName}})
      session._efaceTarget=button.dataset.dialExtension;session._efaceHadVideo=stream.getVideoTracks().length>0
    } catch (exception) {
      releaseMicrophone()
      $('#call-status').textContent = 'Chiamata non avviata.'
      setDialButtonsDisabled(!phone?.isRegistered())
      error(exception.message)
    }
  })

  $('#call-answer').addEventListener('click', async () => {
    if (!call || call.direction !== 'incoming') return
    error('')
    const incoming = call
    stopRingtone()
    try {
      await prepareSpeaker()
      const stream = await preparedMicrophone(sessionOffersVideo(incoming) && videoEnabled)
      if (call !== incoming) { releaseMicrophone(); return }
      incoming.answer({mediaStream:stream, mediaConstraints:{audio:true, video:stream.getVideoTracks().length > 0}, pcConfig:peerConfig()})
      $('#call-answer').disabled = true
    }
    catch (exception) { releaseMicrophone(); error(exception.message) }
  })

  $('#call-hangup').addEventListener('click', () => {
    if (!call) {
      if (doorbirdAlertActive) closeDoorbirdAlert()
      return
    }
    const incoming = call.direction === 'incoming'
    $('#call-status').textContent = 'Chiusura chiamata…'
    $('#call-hangup').disabled = true
    stopRingtone()
    if (incoming) rejectIncomingUntil = Date.now() + 1500
    call.terminate(incoming ? {status_code:486, reason_phrase:'Declined'} : undefined)
  })
  $('#video-toggle').addEventListener('click', () => {
    const track=localVideoStream?.getVideoTracks?.()[0]
    if(!track)return
    track.enabled=!track.enabled
    $('#video-toggle').textContent=track.enabled?'DISATTIVA VIDEO':'ATTIVA VIDEO'
    $('#video-toggle').classList.toggle('off',!track.enabled)
    $('#video-status').textContent=track.enabled?'Video locale attivo':'Video locale disattivato'
  })
  $('#camera-switch').addEventListener('click', async()=>{
    if(!call?.isEstablished?.() || !videoCapable)return
    const next=cameraFacing==='user'?'environment':'user'
    try{
      const replacement=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:next},width:{ideal:1280},height:{ideal:720}}})
      const nextTrack=replacement.getVideoTracks()[0]
      const sender=call.connection?.getSenders?.().find(item=>item.track?.kind==='video') || activeVideoSender
      if(!sender||!nextTrack)throw new Error('Cambio camera non supportato durante questa chiamata')
      await sender.replaceTrack(nextTrack)
      localVideoStream?.getTracks().forEach(track=>track.stop());localVideoStream=replacement;activeVideoSender=sender;cameraFacing=next
      $('#local-video').srcObject=replacement;$('.local-video-wrap').classList.toggle('environment',cameraFacing==='environment')
      $('#video-status').textContent=cameraFacing==='environment'?'Camera posteriore attiva':'Camera frontale attiva'
    }catch(exception){error(exception.message||'Cambio camera non disponibile')}
  })
  if (!adminMode) $('#sip-connect').click()
  window.addEventListener('pagehide', () => { if (phone) phone.stop() })
})()
