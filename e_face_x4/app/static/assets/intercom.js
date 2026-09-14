(() => {
  const $ = (selector) => document.querySelector(selector)
  const root = new URL('./', location.href)
  const socketUrl = new URL('api/intercom/sip', root)
  socketUrl.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  let phone = null
  let call = null
  let audioContext = null
  let speakerGain = null
  let micInput = null
  let micOutput = null
  let micSource = null
  let micGain = null
  let iceServers = []
  let doorbirdTimer = null
  let doorbirdImageUrl = null
  let doorbirdAbort = null
  let doorbirdStopped = false

  async function refreshDoorbird() {
    if (doorbirdStopped || document.hidden) return
    doorbirdAbort = new AbortController()
    try {
      const response = await fetch(new URL('api/intercom/doorbird/image', root), {
        cache:'no-store', credentials:'same-origin', signal:doorbirdAbort.signal
      })
      if (response.status === 204) throw new Error('Immagine non autorizzata da DoorBird in questo momento.')
      if (!response.ok) throw new Error('Immagine DoorBird non disponibile.')
      const blob = await response.blob()
      if (doorbirdStopped || document.hidden) return
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
      if (!doorbirdStopped && !document.hidden) doorbirdTimer = setTimeout(refreshDoorbird, 2000)
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearTimeout(doorbirdTimer)
      doorbirdAbort?.abort()
    } else {
      clearTimeout(doorbirdTimer)
      refreshDoorbird()
    }
  })
  window.addEventListener('pagehide', () => {
    doorbirdStopped = true
    clearTimeout(doorbirdTimer)
    doorbirdAbort?.abort()
    if (doorbirdImageUrl) URL.revokeObjectURL(doorbirdImageUrl)
  })
  refreshDoorbird()
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

  async function loadIce() {
    const response = await fetch(new URL('api/intercom/ice', root), {cache:'no-store'})
    if (!response.ok) throw new Error('Configurazione audio remoto non disponibile')
    iceServers = (await response.json()).iceServers || []
    if (icePreference === null) $('#fast-ice').checked = iceServers.length === 0
  }

  function peerConfig() {
    return {iceServers: $('#fast-ice').checked ? [] : iceServers}
  }

  async function prepareSpeaker() {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) return
      audioContext = new AudioContextClass()
      const source = audioContext.createMediaElementSource($('#remote-audio'))
      speakerGain = audioContext.createGain()
      source.connect(speakerGain)
      speakerGain.connect(audioContext.destination)
      speakerGain.gain.value = Number($('#speaker-gain').value) / 100
    }
    if (audioContext.state !== 'running') await audioContext.resume()
  }

  function error(message) {
    $('#intercom-error').textContent = message
    $('#intercom-error').hidden = !message
  }

  function connection(connected, text) {
    $('#intercom-state').textContent = text
    $('#intercom-dot').classList.toggle('online', connected)
    $('#sip-connect').disabled = connected
    $('#sip-disconnect').disabled = !phone
    $('#call-control4').disabled = !connected || !!call
  }

  function clearCall(text) {
    call = null
    releaseMicrophone()
    $('#remote-audio').srcObject = null
    $('#call-status').textContent = text
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = true
    $('#call-control4').disabled = !phone || !phone.isRegistered()
  }

  $('#speaker-gain').addEventListener('input', () => {
    const percent = Number($('#speaker-gain').value)
    $('#speaker-gain-value').textContent = `${percent}%`
    if (speakerGain) speakerGain.gain.value = percent / 100
    else $('#remote-audio').volume = Math.min(percent / 100, 1)
  })

  $('#microphone-gain').addEventListener('input', () => {
    const percent = Number($('#microphone-gain').value)
    $('#microphone-gain-value').textContent = `${percent}%`
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
    let iceReadyTimer = null
    $('#call-status').textContent = session.direction === 'incoming' ? `Chiamata da ${session.remote_identity?.display_name || session.remote_identity?.uri?.user || 'sconosciuto'}` : 'Chiamata in uscita…'
    $('#call-answer').disabled = session.direction !== 'incoming'
    $('#call-hangup').disabled = false
    $('#call-control4').disabled = true
    session.on('peerconnection', ({peerconnection}) => {
      peerconnection.addEventListener('track', (event) => {
        if (event.track.kind !== 'audio') return
        $('#remote-audio').srcObject = event.streams[0] || new MediaStream([event.track])
        $('#remote-audio').play().catch(() => error('Tocca lo schermo per abilitare la riproduzione audio.'))
      })
    })
    session.on('connecting', () => { $('#call-status').textContent = 'Preparazione rete audio…' })
    session.on('icecandidate', ({candidate, ready}) => {
      if (!$('#fast-ice').checked || iceReadyTimer || candidate?.type !== 'host' || candidate?.protocol?.toLowerCase() !== 'udp') return
      iceReadyTimer = setTimeout(() => {
        iceReadyTimer = null
        ready()
      }, 1500)
    })
    session.on('sdp', ({originator}) => { if (originator === 'local') clearTimeout(iceReadyTimer) })
    session.on('sending', () => { $('#call-status').textContent = 'INVITE inviato ad Asterisk…' })
    session.on('progress', () => { $('#call-status').textContent = 'I tablet stanno squillando…' })
    session.on('confirmed', () => { $('#call-status').textContent = 'In conversazione' })
    session.on('ended', () => { clearTimeout(iceReadyTimer); clearCall('Chiamata terminata.') })
    session.on('failed', ({cause}) => { clearTimeout(iceReadyTimer); clearCall(`Chiamata non riuscita: ${cause || 'errore sconosciuto'}`) })
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

  $('#call-control4').addEventListener('click', async () => {
    if (!phone?.isRegistered() || call) return
    error('')
    $('#call-control4').disabled = true
    $('#call-status').textContent = 'Richiesta accesso al microfono…'
    try {
      await prepareSpeaker()
      const stream = await preparedMicrophone()
      if (!phone?.isRegistered() || call) { releaseMicrophone(); return }
      phone.call('sip:8290@asterisk', {mediaStream:stream, mediaConstraints:{audio:true, video:false}, pcConfig:peerConfig()})
    } catch (exception) {
      releaseMicrophone()
      $('#call-status').textContent = 'Chiamata non avviata.'
      $('#call-control4').disabled = !phone?.isRegistered()
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

  $('#call-hangup').addEventListener('click', () => { if (call) call.terminate() })
  window.addEventListener('pagehide', () => { if (phone) phone.stop() })
})()
