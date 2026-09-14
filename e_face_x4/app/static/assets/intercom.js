(() => {
  const $ = (selector) => document.querySelector(selector)
  const adminMode = document.documentElement.classList.contains('admin-intercom')
  const root = new URL('./', location.href)
  const currentVersion = '2.21.24'
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
  let call = null
  let audioContext = null
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
  let intercomVisible = !document.documentElement.classList.contains('embedded')
  let stationsSignature = ''
  async function refreshExternalStations() {
    try {
      const response = await fetch(new URL('api/intercom/external-stations', root), {cache:'no-store', credentials:'same-origin'})
      if (!response.ok) return
      const {stations} = await response.json()
      const signature = JSON.stringify(stations)
      if (signature === stationsSignature) return
      stationsSignature = signature
      const primary = stations.find((station) => station.id === 'ingresso')
      if (primary) {
        $('.doorbird-row .station-copy strong').textContent = primary.name
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
        const open = document.createElement('button')
        open.className = 'station-text-button'
        open.type = 'button'
        open.textContent = 'Apri video'
        const dial = document.createElement('button')
        dial.type = 'button'
        dial.textContent = 'CHIAMA'
        dial.dataset.dialExtension = station.sip_extension
        dial.dataset.externalStation = station.id
        dial.dataset.stationReady = String(station.ready)
        dial.disabled = !station.ready || !phone?.isRegistered() || !!call
        if (!station.ready) dial.title = 'Configura e verifica la rotta SIP in Asterisk'
        copy.append(name, open, dial)
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
        subtitle.textContent = tablet.ready ? 'Tablet Control4 · chiamata da provare' : 'Tablet Control4 · rotta non confermata'
        const dial = document.createElement('button')
        dial.type = 'button'
        dial.textContent = 'CHIAMA'
        dial.dataset.dialExtension = tablet.extension
        dial.dataset.stationReady = String(tablet.ready)
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
    if (intercomVisible) startDoorbirdVideo()
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
  $('#audio-retry').addEventListener('click', playRemoteAudio)

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
  }

  function clearCall(text) {
    call = null
    if (updateAvailable) { location.reload(); return }
    clearInterval(audioStatsTimer)
    audioStatsTimer = null
    $('#intercom-call-panel').hidden = true
    releaseMicrophone()
    $('#remote-audio').srcObject = null
    $('#audio-retry').hidden = true
    $('#audio-status').textContent = 'Audio in ingresso: in attesa'
    $('#call-status').textContent = text
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = true
    setDialButtonsDisabled(!phone || !phone.isRegistered())
  }

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
    micInput = micOutput = micSource = micGain = null
  }

  async function preparedMicrophone() {
    micInput = await microphone()
    if (!audioContext) return micInput
    micSource = audioContext.createMediaStreamSource(micInput)
    micGain = audioContext.createGain()
    micGain.gain.value = Number($('#microphone-gain').value) / 100
    const destination = audioContext.createMediaStreamDestination()
    micSource.connect(micGain)
    micGain.connect(destination)
    micOutput = destination.stream
    return micOutput
  }

  function track(session) {
    call = session
    $('#intercom-call-panel').hidden = false
    $('#audio-status').textContent = 'Connessione audio in preparazione…'
    let iceReadyTimer = null
    let iceReadySent = false
    let boundConnection = null
    let connectionPollTimer = null
    $('#call-status').textContent = session.direction === 'incoming' ? `Chiamata da ${session.remote_identity?.display_name || session.remote_identity?.uri?.user || 'sconosciuto'}` : 'Chiamata in uscita…'
    $('#call-answer').disabled = session.direction !== 'incoming'
    $('#call-hangup').disabled = false
    setDialButtonsDisabled(true)
    function syncRemoteAudio(peerconnection) {
      const receiver = peerconnection.getReceivers?.().find((item) => item.track?.kind === 'audio' && item.track.readyState === 'live')
      if (!receiver || $('#remote-audio').srcObject?.getAudioTracks?.()[0] === receiver.track) return
      $('#remote-audio').srcObject = new MediaStream([receiver.track])
      playRemoteAudio()
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
          syncRemoteAudio(peerconnection)
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
        if (event.track.kind !== 'audio') return
        $('#remote-audio').srcObject = event.streams[0] || new MediaStream([event.track])
        playRemoteAudio()
      })
      syncRemoteAudio(peerconnection)
    }
    session.on('peerconnection', ({peerconnection}) => bindConnection(peerconnection))
    bindConnection(session.connection)
    if (!boundConnection) connectionPollTimer = setInterval(() => bindConnection(session.connection), 250)
    session.on('connecting', () => { $('#call-status').textContent = 'Preparazione rete audio…' })
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
    session.on('sending', () => { $('#call-status').textContent = 'INVITE inviato ad Asterisk…' })
    session.on('progress', () => { $('#call-status').textContent = 'I tablet stanno squillando…' })
    session.on('confirmed', () => { $('#call-status').textContent = 'In conversazione'; bindConnection(session.connection); if (boundConnection) syncRemoteAudio(boundConnection); playRemoteAudio() })
    session.on('ended', () => { clearTimeout(iceReadyTimer); clearInterval(connectionPollTimer); clearCall('Chiamata terminata.') })
    session.on('failed', ({cause}) => { clearTimeout(iceReadyTimer); clearInterval(connectionPollTimer); clearCall(`Chiamata non riuscita: ${cause || 'errore sconosciuto'}`) })
    session.on('getusermediafailed', ({name, message}) => error(`Microfono: ${name || 'errore'} ${message || ''}`))
  }

  async function microphone() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microfono non disponibile: apri e-Face direttamente tramite HTTPS, fuori dalla finestra Home Assistant.')
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

  $('#sip-connect').addEventListener('click', async () => {
    let password = $('#sip-password').value
    if (!window.JsSIP) { error('Il client SIP non è disponibile.'); return }
    error('')
    try {
      const response = await fetch(new URL('api/intercom/sip/credential', root), {cache:'no-store', credentials:'same-origin'})
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Credenziale SIP non disponibile in e-Face')
      const extension = data.username
      if (!/^[0-9]{4}$/.test(extension)) throw new Error('Interno SIP non valido')
      if (!password) password = data.password
      if (!password) throw new Error('Password SIP mancante')
      $('#sip-extension').textContent = `INTERNO ${extension}`
      await loadIce()
      const socket = new JsSIP.WebSocketInterface(socketUrl.toString())
      phone = new JsSIP.UA({sockets:[socket], uri:`sip:${extension}@asterisk`, authorization_user:extension, password, display_name:'e-Face', register:true, session_timers:false})
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
        if (call) { session.terminate(); return }
        track(session)
      })
      phone.start()
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
    if (!button || !phone?.isRegistered() || call || button.dataset.stationReady === 'false' || !/^(82[0-9]{2}|8290|8291|8292)$/.test(button.dataset.dialExtension)) return
    error('')
    setDialButtonsDisabled(true)
    $('#call-status').textContent = 'Richiesta accesso al microfono…'
    try {
      await prepareSpeaker()
      const stream = await preparedMicrophone()
      if (button.dataset.externalStation) {
        $('#call-status').textContent = 'Preparo la postazione esterna…'
        const response = await fetch(new URL(`api/intercom/external-stations/${encodeURIComponent(button.dataset.externalStation)}/prepare-call`, root),
          {method:'POST', cache:'no-store', credentials:'same-origin'})
        const result = await response.json().catch(() => ({}))
        if (!response.ok || result.extension !== button.dataset.dialExtension) throw new Error(result.detail || 'Postazione esterna non pronta')
      }
      if (!phone?.isRegistered() || call) { releaseMicrophone(); return }
      phone.call(`sip:${button.dataset.dialExtension}@asterisk`, {mediaStream:stream, mediaConstraints:{audio:true, video:false}, pcConfig:peerConfig()})
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
    try {
      await prepareSpeaker()
      const stream = await preparedMicrophone()
      if (call !== incoming) { releaseMicrophone(); return }
      incoming.answer({mediaStream:stream, mediaConstraints:{audio:true, video:false}, pcConfig:peerConfig()})
      $('#call-answer').disabled = true
    }
    catch (exception) { releaseMicrophone(); error(exception.message) }
  })

  $('#call-hangup').addEventListener('click', () => {
    if (!call) return
    $('#call-status').textContent = 'Chiusura chiamata…'
    $('#call-hangup').disabled = true
    call.terminate()
  })
  if (!adminMode) $('#sip-connect').click()
  window.addEventListener('pagehide', () => { if (phone) phone.stop() })
})()
