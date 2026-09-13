(() => {
  const $ = (selector) => document.querySelector(selector)
  const root = new URL('./', location.href)
  const socketUrl = new URL('api/intercom/sip', root)
  socketUrl.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  let phone = null
  let call = null
  let activeStream = null

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
    if (activeStream) activeStream.getTracks().forEach((track) => track.stop())
    activeStream = null
    $('#remote-audio').srcObject = null
    $('#call-status').textContent = text
    $('#call-answer').disabled = true
    $('#call-hangup').disabled = true
    $('#call-control4').disabled = !phone || !phone.isRegistered()
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

  $('#sip-connect').addEventListener('click', () => {
    const password = $('#sip-password').value
    if (!password) { error('Inserisci la password SIP dell’interno 8301.'); return }
    if (!window.JsSIP) { error('Il client SIP non è disponibile.'); return }
    error('')
    try {
      const socket = new JsSIP.WebSocketInterface(socketUrl.toString())
      phone = new JsSIP.UA({sockets:[socket], uri:'sip:8301@asterisk', authorization_user:'8301', password, display_name:'e-Face Test', register:true, session_timers:false})
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
    let stream = null
    try {
      stream = await microphone()
      if (!phone?.isRegistered() || call) { stream.getTracks().forEach((track) => track.stop()); return }
      phone.call('sip:8290@asterisk', {mediaStream:stream, mediaConstraints:{audio:true, video:false}, pcConfig:{iceServers:[]}})
      activeStream = stream
    } catch (exception) {
      if (stream) stream.getTracks().forEach((track) => track.stop())
      $('#call-status').textContent = 'Chiamata non avviata.'
      $('#call-control4').disabled = !phone?.isRegistered()
      error(exception.message)
    }
  })

  $('#call-answer').addEventListener('click', () => {
    if (!call || call.direction !== 'incoming') return
    error('')
    try { call.answer({mediaConstraints:{audio:true, video:false}, pcConfig:{iceServers:[]}}) }
    catch (exception) { error(exception.message) }
    $('#call-answer').disabled = true
  })

  $('#call-hangup').addEventListener('click', () => { if (call) call.terminate() })
  window.addEventListener('pagehide', () => { if (phone) phone.stop() })
})()
