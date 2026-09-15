const $ = (selector) => document.querySelector(selector)
const api = (path) => new URL(`../${path}`, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()

const toolsIntercom = document.createElement('section')
toolsIntercom.id = 'tools-intercom-live'
toolsIntercom.className = 'media-config admin-dashboard-panel tools-intercom-live'
toolsIntercom.hidden = true
toolsIntercom.innerHTML = '<header><button type="button" aria-label="Torna agli Strumenti">‹</button><div><small>CHIAMATA</small><h2>Intercom</h2></div></header><iframe title="Chiamata Intercom" allow="microphone; autoplay"></iframe>'
document.body.append(toolsIntercom)
const toolsIntercomFrame = toolsIntercom.querySelector('iframe')
toolsIntercom.querySelector('header button').addEventListener('click', () => { toolsIntercom.hidden = true; document.body.style.overflow = '' })
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== toolsIntercomFrame.contentWindow || event.data?.type !== 'eface-intercom-incoming') return
  toolsIntercom.hidden = false
  document.body.style.overflow = 'hidden'
  toolsIntercomFrame.contentWindow?.postMessage({type:'eface-intercom-visible', visible:true}, location.origin)
})
toolsIntercomFrame.addEventListener('load', () => toolsIntercomFrame.contentWindow?.postMessage({type:'eface-intercom-visible', visible:false}, location.origin))
toolsIntercomFrame.src = api('intercom?embedded=1')

function message(value) {
  const notice = $('#tools-notice')
  notice.textContent = value
  notice.hidden = false
  clearTimeout(message.timer)
  message.timer = setTimeout(() => { notice.hidden = true }, 5000)
}

async function request(path, options = {}) {
  const response = await fetch(api(path), {cache:'no-store', ...options})
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
  return data
}

function view(name) {
  $('#tools-user-section').hidden = name !== 'user'
  $('#tools-admin-section').hidden = name !== 'admin'
  document.querySelectorAll('[data-tools-view]').forEach((button) => {
    const active = button.dataset.toolsView === name
    button.classList.toggle('active', active)
    if (active) button.setAttribute('aria-current', 'page')
    else button.removeAttribute('aria-current')
  })
  history.replaceState(null, '', name === 'admin' ? '#admin' : location.pathname)
}

function openPanel(id) {
  $(`#${id}`).hidden = false
  document.body.style.overflow = 'hidden'
}

function closePanel(id) {
  $(`#${id}`).hidden = true
  document.body.style.overflow = ''
}

document.querySelectorAll('[data-tools-view]').forEach((button) => button.addEventListener('click', () => view(button.dataset.toolsView)))

async function users() {
  const data = await request('api/admin/users')
  $('#users-count').textContent = `${data.users.length} account`
  const list = $('#users-list')
  list.replaceChildren()
  for (const user of data.users) {
    const row = document.createElement('article')
    row.className = `admin-user-row${user.active ? '' : ' inactive'}`
    const identity = document.createElement('div')
    const name = document.createElement('strong')
    name.textContent = user.name
    const detail = document.createElement('small')
    detail.textContent = `${user.username} · ${user.role === 'admin' ? 'Amministratore' : 'Utente'} · ${user.active ? 'Attivo' : 'Disattivato'} · ${user.origin === 'vps' ? 'VPS' : 'Locale'} · Accesso persistente ${user.trusted_access ? 'Sì' : 'No'}`
    identity.append(name, detail)
    const actions = document.createElement('div')
    actions.className = 'admin-user-actions'
    const reset = document.createElement('button')
    reset.type = 'button'
    reset.className = 'secondary'
    reset.textContent = 'Cambia password'
    reset.addEventListener('click', () => {
      const form = document.createElement('form')
      form.className = 'admin-user-password'
      const input = document.createElement('input')
      input.type = 'password'
      input.minLength = 12
      input.maxLength = 256
      input.required = true
      input.autocomplete = 'new-password'
      input.placeholder = 'Nuova password (min. 12)'
      const save = document.createElement('button')
      save.textContent = 'SALVA'
      form.append(input, save)
      form.addEventListener('submit', async (event) => {
        event.preventDefault()
        try {
          await request(`api/admin/users/${encodeURIComponent(user.username)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:input.value})})
          input.value = ''
          if (user.username === 'admin') { location.href = api('login'); return }
          message('Password aggiornata; le sessioni precedenti sono state chiuse')
          await users()
        } catch (error) { message(error.message) }
      })
      actions.replaceChildren(form)
      input.focus()
    })
    actions.append(reset)
    const trusted = document.createElement('button')
    trusted.type = 'button'
    trusted.className = 'secondary'
    trusted.textContent = user.trusted_access ? 'Persistenza: SÌ' : 'Persistenza: NO'
    trusted.addEventListener('click', async () => {
      if (user.trusted_access && !confirm(`Disattivare l'accesso persistente per ${user.name}? Le sessioni attuali verranno chiuse.`)) return
      try {
        await request(`api/admin/users/${encodeURIComponent(user.username)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({trusted_access:!user.trusted_access})})
        if (user.username === 'admin' && user.trusted_access) { location.href = api('login'); return }
        await users()
        message(user.trusted_access ? 'Accesso persistente disattivato' : 'Accesso persistente attivato')
      } catch(error) { message(error.message) }
    })
    actions.append(trusted)
    if (user.role !== 'admin') {
      const toggle = document.createElement('button')
      toggle.type = 'button'
      toggle.className = 'secondary'
      toggle.textContent = user.active ? 'Disattiva' : 'Riattiva'
      toggle.addEventListener('click', async () => {
        if (user.active && !confirm(`Disattivare ${user.name}? Non potrà più accedere a e-Face.`)) return
        try {
          await request(`api/admin/users/${encodeURIComponent(user.username)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({active:!user.active})})
          await users()
          message(user.active ? 'Utente disattivato' : 'Utente riattivato')
        } catch(error) { message(error.message) }
      })
      actions.append(toggle)
      const remove = document.createElement('button')
      remove.type = 'button'
      remove.className = 'danger'
      remove.textContent = 'Elimina'
      remove.addEventListener('click', async () => {
        if (!confirm(`Eliminare definitivamente ${user.name}? L'account dovrà essere ricreato da zero.`)) return
        try {
          await request(`api/admin/users/${encodeURIComponent(user.username)}`, {method:'DELETE'})
          await users()
          message('Utente eliminato')
        } catch(error) { message(error.message) }
      })
      actions.append(remove)
    }
    row.append(identity, actions)
    list.append(row)
  }
}

$('#users-tool').addEventListener('click', async () => { try { await users(); openPanel('users-config') } catch(error) { message(error.message) } })
$('#users-back').addEventListener('click', () => closePanel('users-config'))
const userOriginLabel = document.createElement('label')
userOriginLabel.textContent = 'Origine account'
userOriginLabel.innerHTML += '<select id="user-origin"><option value="local">Locale · creato dall’amministratore</option><option value="cloud" disabled>Cloud/VPS · e-Voice o e-Manager (da definire)</option></select><small>Il servizio cloud non riceverà la password locale.</small>'
$('#user-create-form .admin-form-grid').append(userOriginLabel)
const trustedAccessLabel = document.createElement('label')
trustedAccessLabel.innerHTML = '<span><input id="user-trusted-access" type="checkbox"> Accesso persistente sui dispositivi</span><small>L’admin può revocarlo in qualsiasi momento.</small>'
$('#user-create-form .admin-form-grid').append(trustedAccessLabel)
$('#user-create-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const form = event.currentTarget
  const button = form.querySelector('button[type=submit]')
  button.disabled = true
  try {
    await request('api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:$('#user-name').value, username:$('#user-username').value, password:$('#user-password').value, origin:$('#user-origin').value, trusted_access:$('#user-trusted-access').checked})})
    form.reset()
    await users()
    message('Utente creato')
  } catch(error) { message(error.message) } finally { button.disabled = false }
})

async function intercom() {
  const {settings, turn} = await request('api/admin/intercom')
  $('#intercom-asterisk-host').value = settings.asterisk_host
  $('#intercom-asterisk-port').value = settings.asterisk_port
  $('#intercom-doorbird-host').value = settings.doorbird_host
  $('#intercom-doorbird-port').value = settings.doorbird_port
  $('#intercom-ring-extension').value = settings.ring_extension
  $('#intercom-turn-url').value = turn.turn_url
  $('#intercom-turn-username').value = turn.turn_username
  $('#intercom-turn-password').value = ''
  $('#intercom-turn-password').placeholder = turn.password_configured ? 'Password gia configurata' : 'Password TURN'
  await personalDevices()
  await provisionerStatus()
  await externalStations()
  await internalStations()
  await voipPhones()
}

const internalAdmin = document.createElement('form')
internalAdmin.className = 'admin-form'
internalAdmin.innerHTML = '<div class="admin-info"><b>Postazioni interne Control4</b><p>Cambia solo il nome mostrato in e-Face. Gli interni SIP e i nomi nei tablet Control4 non vengono modificati.</p></div><div class="admin-form-grid"><label>Interno 8291<input data-internal-name="8291" maxlength="64" required></label><label>Interno 8292<input data-internal-name="8292" maxlength="64" required></label></div><div class="admin-form-actions"><button type="submit">SALVA NOMI</button></div>'
$('#intercom-config').append(internalAdmin)

async function internalStations() {
  const {names} = await request('api/intercom/internal-stations')
  for (const [extension, name] of Object.entries(names)) {
    const field = internalAdmin.querySelector(`[data-internal-name="${extension}"]`)
    if (field) field.value = name
  }
}

internalAdmin.addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = internalAdmin.querySelector('button[type="submit"]')
  button.disabled = true
  try {
    const names = Object.fromEntries([...internalAdmin.querySelectorAll('[data-internal-name]')].map((field) => [field.dataset.internalName, field.value.trim()]))
    await request('api/admin/intercom/internal-stations', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({names})})
    message('Nomi delle postazioni interne salvati in e-Face')
  } catch (error) { message(error.message) }
  finally { button.disabled = false }
})

const voipAdmin = document.createElement('section')
voipAdmin.className = 'admin-form'
voipAdmin.innerHTML = '<div class="admin-info"><b>Telefoni VoIP</b><p>Account SIP standard per telefoni di qualsiasi marca: il dispositivo si registra ad Asterisk. Il profilo video abilita H.264/VP8 tra dispositivi SIP compatibili; il client e-Face attuale effettua chiamate audio, quindi non mostra ancora il video del telefono. Verifica sempre il modello reale. Non usare questa sezione per tablet Control4.</p></div><div id="voip-phone-list" class="admin-users-list"></div><form id="voip-phone-form" class="admin-form"><div class="admin-form-grid"><label>Nome telefono<input name="name" maxlength="64" required></label><label>Tipo<select name="profile"><option value="voip_audio">Solo audio</option><option value="voip_video">Audio e video</option></select></label></div><div class="admin-form-actions"><button type="submit">AGGIUNGI TELEFONO</button><button type="button" id="voip-phone-new" class="secondary">NUOVO</button></div></form><div id="voip-phone-credential" class="admin-info" hidden><b>Credenziali SIP del telefono</b><p>Inserisci nel telefono il server Asterisk mostrato nelle impostazioni Intercom, porta SIP 5060, trasporto UDP. Conserva la password in un posto sicuro.</p><label>Interno / utente<input id="voip-phone-user" readonly></label><label>Password SIP<input id="voip-phone-password" type="password" readonly></label><button type="button" id="voip-phone-password-toggle" class="secondary">MOSTRA PASSWORD</button></div>'
$('#intercom-config').append(voipAdmin)
const voipForm = voipAdmin.querySelector('#voip-phone-form')
let voipEditExtension = ''

function voipCredentials(data) {
  $('#voip-phone-user').value = data.username
  $('#voip-phone-password').value = data.password
  $('#voip-phone-password').type = 'password'
  $('#voip-phone-credential').hidden = false
}

async function voipPhones() {
  const {phones} = await request('api/admin/intercom/voip-phones')
  const list = $('#voip-phone-list')
  list.replaceChildren()
  for (const phone of phones) {
    const row = document.createElement('div')
    row.className = 'admin-info'
    const title = document.createElement('b')
    title.textContent = `${phone.name} · ${phone.extension} · ${phone.profile === 'voip_video' ? 'audio + video' : 'audio'} · ${phone.endpoint_present ? 'configurato, registrazione da provare' : 'Asterisk non conferma l’interno'}`
    row.append(title)
    composerAction(row, 'MODIFICA', () => {
      voipEditExtension = phone.extension
      voipForm.elements.name.value = phone.name
      voipForm.elements.profile.value = phone.profile
      voipForm.querySelector('button[type="submit"]').textContent = 'SALVA MODIFICHE'
      $('#voip-phone-credential').hidden = true
    })
    composerAction(row, 'CREDENZIALI', async () => {
      const adminPassword = window.prompt('Password admin e-Face per mostrare la password SIP')
      if (adminPassword === null) return
      try {
        const data = await request(`api/admin/intercom/voip-phones/${phone.extension}/credentials`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({admin_password:adminPassword})})
        voipCredentials(data)
      } catch (error) { message(error.message) }
    })
    composerAction(row, 'RIMUOVI', async () => {
      if (!window.confirm(`Rimuovere il telefono ${phone.name} (${phone.extension}) e revocare il suo account SIP?`)) return
      try {
        await request(`api/admin/intercom/voip-phones/${phone.extension}`, {method:'DELETE'})
        $('#voip-phone-credential').hidden = true
        await voipPhones()
        message('Telefono VoIP rimosso da e-Face e Asterisk')
      } catch (error) { message(error.message) }
    })
    list.append(row)
  }
}

$('#voip-phone-new').addEventListener('click', () => {
  voipEditExtension = ''
  voipForm.reset()
  voipForm.querySelector('button[type="submit"]').textContent = 'AGGIUNGI TELEFONO'
  $('#voip-phone-credential').hidden = true
})
$('#voip-phone-password-toggle').addEventListener('click', () => {
  const field = $('#voip-phone-password')
  field.type = field.type === 'password' ? 'text' : 'password'
})
voipForm.addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = voipForm.querySelector('button[type="submit"]')
  button.disabled = true
  const payload = {name:voipForm.elements.name.value.trim(), profile:voipForm.elements.profile.value}
  try {
    if (voipEditExtension) {
      await request(`api/admin/intercom/voip-phones/${voipEditExtension}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
      message('Telefono VoIP aggiornato; verifica registrazione, audio e video')
    } else {
      const data = await request('api/admin/intercom/voip-phones', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
      voipCredentials(data)
      message('Account SIP creato; inserisci le credenziali nel telefono')
    }
    await voipPhones()
  } catch (error) { message(error.message) }
  finally { button.disabled = false }
})

const provisionerAdmin = document.createElement('form')
provisionerAdmin.className = 'admin-form'
provisionerAdmin.innerHTML = '<div class="admin-info"><b>Associazione Asterisk e-Face</b><p>Una sola volta: indirizzo, token e impronta TLS del servizio Asterisk e-Face. Dopo l’associazione, aggiungere postazioni esterne richiede solo questa pagina.</p></div><div class="admin-form-grid"><label>IP Asterisk<input id="external-provisioner-host" inputmode="decimal" required></label><label>Porta servizio<input id="external-provisioner-port" type="number" min="1" max="65535" required></label><label>Token associazione<input id="external-provisioner-token" type="password" autocomplete="new-password"></label><label>Impronta TLS SHA-256<input id="external-provisioner-fingerprint" required></label></div><div class="admin-form-actions"><button type="submit">ASSOCIA ASTERISK</button></div><div id="external-provisioner-state" class="admin-status" role="status"></div>'
$('#intercom-config').append(provisionerAdmin)

async function provisionerStatus() {
  const data = await request('api/admin/intercom/provisioner')
  $('#external-provisioner-host').value = data.host || $('#intercom-asterisk-host').value
  $('#external-provisioner-port').value = data.port || 9443
  $('#external-provisioner-fingerprint').value = data.fingerprint || ''
  $('#external-provisioner-token').value = ''
  $('#external-provisioner-token').placeholder = data.configured ? 'Token già salvato' : 'Token Asterisk richiesto'
  $('#external-provisioner-state').textContent = data.configured ? 'Asterisk associato: configurazione postazioni automatica.' : 'Asterisk non ancora associato.'
}

provisionerAdmin.addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = provisionerAdmin.querySelector('button[type=submit]')
  button.disabled = true
  try {
    await request('api/admin/intercom/provisioner', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
      host:$('#external-provisioner-host').value.trim(), port:Number($('#external-provisioner-port').value),
      token:$('#external-provisioner-token').value.trim(), fingerprint:$('#external-provisioner-fingerprint').value.trim()})})
    await provisionerStatus()
    message('Asterisk associato a e-Face')
  } catch (error) { message(error.message) }
  finally { button.disabled = false }
})

const externalAdmin = document.createElement('div')
externalAdmin.className = 'admin-form'
externalAdmin.innerHTML = '<div class="admin-info"><b>Postazioni esterne</b><p>Aggiungi un DoorBird qui: e-Face salva le credenziali, configura automaticamente la rotta SIP persistente in Asterisk e abilita CHIAMA dopo la verifica. Non serve modificare il dialplan a mano.</p></div><div id="external-stations-list"></div><div class="admin-form-actions"><button id="external-add" type="button" class="secondary">AGGIUNGI POSTAZIONE</button><button id="external-save" type="button">SALVA E CONFIGURA</button></div>'
$('#intercom-config').append(externalAdmin)
let externalStationRows = []

function externalRow(station) {
  const card = document.createElement('div')
  card.className = 'admin-info external-station-card'
  card.innerHTML = '<div class="admin-form-grid"><label>Nome<input data-field="name" required></label><label>IP DoorBird<input data-field="host" inputmode="decimal" required></label><label>Porta HTTP<input data-field="http_port" type="number" min="1" max="65535" required></label><label>Interno SIP<input data-field="sip_extension" inputmode="numeric" pattern="82[0-9]{2}" required></label><label>Utente API<input data-field="username" autocomplete="off"></label><label>Password API<input data-field="password" type="password" autocomplete="new-password"></label></div><div data-sip-status></div><div class="admin-form-actions"><button type="button" class="secondary" data-remove>RIMUOVI</button></div>'
  card.dataset.stationId = station.id
  for (const field of ['name', 'host', 'http_port', 'sip_extension', 'username']) {
    card.querySelector(`[data-field="${field}"]`).value = station[field] ?? ''
  }
  card.dataset.ready = String(station.ready)
  card.querySelector('[data-sip-status]').textContent = station.ready ? 'SIP attivo' : 'SIP da configurare automaticamente al salvataggio'
  card.querySelector('[data-field="password"]').placeholder = station.credential_configured ? 'Password salvata' : 'Password richiesta per il video'
  if (station.id === 'ingresso') {
    for (const field of ['host', 'http_port', 'sip_extension']) card.querySelector(`[data-field="${field}"]`).readOnly = true
    card.querySelector('[data-remove]').hidden = true
  }
  card.querySelector('[data-remove]').addEventListener('click', () => {
    externalStationRows = externalStationRows.filter((row) => row !== card)
    card.remove()
  })
  externalStationRows.push(card)
  $('#external-stations-list').append(card)
}

async function externalStations() {
  const {stations} = await request('api/admin/intercom/external-stations')
  externalStationRows = []
  $('#external-stations-list').replaceChildren()
  stations.forEach(externalRow)
}

$('#external-add').addEventListener('click', () => {
  if (externalStationRows.length >= 8) return message('Massimo 8 postazioni esterne')
  const ids = new Set(externalStationRows.map((row) => row.dataset.stationId))
  const extensions = new Set(externalStationRows.map((row) => row.querySelector('[data-field="sip_extension"]').value))
  let number = 2
  while (ids.has(`esterno-${number}`) || extensions.has(String(8200 + number))) number++
  externalRow({id:`esterno-${number}`, name:`Postazione esterna ${number}`, host:'', http_port:80, sip_extension:String(8200 + number), username:'', ready:false, credential_configured:false})
})

$('#external-save').addEventListener('click', async () => {
  const button = $('#external-save')
  button.disabled = true
  try {
    const stations = externalStationRows.map((row) => {
      const value = (field) => row.querySelector(`[data-field="${field}"]`).value.trim()
      return {id:row.dataset.stationId, name:value('name'), host:value('host'), http_port:Number(value('http_port')),
        sip_extension:value('sip_extension'), username:value('username'), password:row.querySelector('[data-field="password"]').value,
        ready:row.dataset.ready === 'true'}
    })
    await request('api/admin/intercom/external-stations', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({stations})})
    await externalStations()
    message('Postazioni salvate e rotte SIP configurate in Asterisk.')
  } catch (error) { message(error.message) }
  finally { button.disabled = false }
})

const intercomClientPanel = document.createElement('div')
intercomClientPanel.className = 'admin-form intercom-client-admin'
intercomClientPanel.innerHTML = '<h3>Postazione SIP e impostazioni Intercom</h3><p>Collega manualmente questa pagina per fare una prova. Nell’Intercom normale la postazione si collega automaticamente quando apri la schermata.</p><iframe title="Postazione SIP e impostazioni Intercom" loading="lazy"></iframe>'
$('#intercom-config').append(intercomClientPanel)
const intercomAdminFrame = intercomClientPanel.querySelector('iframe')
$('#intercom-tool').addEventListener('click', async () => { try { await intercom(); openPanel('intercom-config'); intercomAdminFrame.src = api('intercom?embedded=1&admin=1') } catch(error) { message(error.message) } })
$('#intercom-back').addEventListener('click', () => { $('#voip-phone-password').value = ''; $('#voip-phone-credential').hidden = true; intercomAdminFrame.removeAttribute('src'); closePanel('intercom-config') })
const amiTestForm = document.createElement('form')
amiTestForm.className = 'admin-form'
amiTestForm.innerHTML = '<div class="admin-info"><b>Accesso Asterisk dedicato</b><p>Verifica l’utente AMI eface e la configurazione dell’interno 8301. Questo test non cambia password né chiamate. Usa la password AMI dedicata, non quella SIP o admin e-Face.</p></div><label>Password AMI eface<input id="intercom-ami-secret" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" data-lpignore="true" required></label><div class="admin-form-actions"><button type="submit">VERIFICA ACCESSO AMI</button></div><div id="intercom-ami-result" class="admin-status" role="status" hidden></div>'
$('#intercom-config').append(amiTestForm)
const doorbirdCheck = document.createElement('div')
doorbirdCheck.className = 'admin-form'
doorbirdCheck.innerHTML = '<div class="admin-info"><b>DoorBird</b><p>Verifica la credenziale salvata in e-Face leggendo le informazioni del dispositivo. Non modifica SIP, pulsante o relè.</p></div><div class="admin-form-actions"><button type="button">VERIFICA CREDENZIALE DOORBIRD</button></div><div class="admin-status" role="status" hidden></div>'
$('#intercom-config').append(doorbirdCheck)
doorbirdCheck.querySelector('button').addEventListener('click', async () => {
  const button = doorbirdCheck.querySelector('button')
  const status = doorbirdCheck.querySelector('[role=status]')
  button.disabled = true
  try {
    const data = await request('api/admin/intercom/doorbird/check', {method:'POST'})
    status.textContent = data.authenticated ? 'Credenziale DoorBird valida.'
      : data.reason === 'authentication' ? 'DoorBird raggiungibile, ma credenziale rifiutata.'
      : data.reason === 'network' ? 'DoorBird non raggiungibile.'
      : 'DoorBird raggiungibile, risposta non verificata.'
  } catch(error) { status.textContent = error.message }
  finally { status.hidden = false; button.disabled = false }
})
amiTestForm.addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = amiTestForm.querySelector('button[type=submit]')
  const secret = $('#intercom-ami-secret').value.trim()
  $('#intercom-ami-secret').value = ''
  button.disabled = true
  try {
    const data = await request('api/admin/intercom/ami/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({secret})})
    const source = data.source_ip ? ` IP e-Face: ${data.source_ip}.` : ''
    const status = data.issue === 'network' ? 'Asterisk AMI non raggiungibile.'
      : data.issue === 'authentication' ? 'Login AMI rifiutato: verifica ACL IP e password.'
      : data.issue === 'config_read' && data.reason === 'permission' ? 'Login AMI riuscito; Asterisk nega il permesso di lettura.'
      : data.issue === 'config_read' && data.reason === 'category' ? 'Login AMI riuscito; categoria 8301 non trovata dalla richiesta.'
      : data.issue === 'config_read' && data.reason === 'file' ? 'Login AMI riuscito; file pjsip_custom.conf non accessibile dalla richiesta.'
      : data.issue === 'config_read' ? 'Login AMI riuscito; Asterisk rifiuta la richiesta GetConfig per un altro motivo.'
      : data.issue === 'protocol' ? 'Errore di protocollo AMI.'
      : data.auth_8301_found ? 'Accesso AMI riuscito; auth 8301 trovata.' : 'Accesso AMI riuscito; auth 8301 non trovata.'
    $('#intercom-ami-result').textContent = status + source
    $('#intercom-ami-result').hidden = false
  } catch(error) { $('#intercom-ami-result').textContent = error.message; $('#intercom-ami-result').hidden = false }
  finally { button.disabled = false }
})
$('#intercom-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const payload = {
    asterisk_host:$('#intercom-asterisk-host').value.trim(),
    asterisk_port:Number($('#intercom-asterisk-port').value),
    doorbird_host:$('#intercom-doorbird-host').value.trim(),
    doorbird_port:Number($('#intercom-doorbird-port').value),
    ring_extension:$('#intercom-ring-extension').value.trim(),
  }
  try {
    await request('api/admin/intercom', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)})
    message('Impostazioni e-Face salvate; Asterisk non è stato modificato')
  } catch(error) { message(error.message) }
})
$('#intercom-turn-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  try {
    await request('api/admin/intercom/turn', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({turn_url:$('#intercom-turn-url').value.trim(), turn_username:$('#intercom-turn-username').value.trim(), turn_password:$('#intercom-turn-password').value})})
    $('#intercom-turn-password').value = ''
    message('Relay TURN salvato; non modifica il dialplan Asterisk')
  } catch(error) { message(error.message) }
})
$('#intercom-test').addEventListener('click', async () => {
  const button = $('#intercom-test')
  button.disabled = true
  try {
    const data = await request('api/admin/intercom/test', {method:'POST'})
    $('#intercom-status').textContent = `Asterisk: ${data.asterisk_reachable ? 'raggiungibile' : 'non raggiungibile'} · DoorBird: ${data.doorbird_reachable ? 'raggiungibile' : 'non raggiungibile'} · Telefonia e-Face: non ancora attiva`
  } catch(error) { message(error.message) } finally { button.disabled = false }
})

function renderInstallation(data) {
  const target = $('#installation-results')
  target.replaceChildren()
  const checks = [
    [data.asterisk_tcp ? '✓' : '!', 'Asterisk', data.asterisk_tcp ? 'WebSocket raggiungibile dalla rete e-Face' : 'Non raggiungibile: controlla IP, porta e add-on'],
    [data.doorbird_tcp ? '✓' : '!', 'DoorBird', data.doorbird_tcp ? 'Dispositivo raggiungibile dalla rete e-Face' : 'Non raggiungibile: controlla IP e rete'],
    [data.turn_configured ? '✓' : '!', 'TURN', data.turn_configured ? 'Credenziali salvate in e-Face' : 'Configura server e credenziali nel pannello Videocitofono'],
    [data.turn_udp ? '✓' : data.turn_udp_tested ? '!' : '–', 'Rete audio remota', data.turn_udp ? 'STUN risponde via UDP; autenticazione e audio da verificare con una chiamata' : data.turn_udp_tested ? 'UDP non risponde: controlla VPS e firewall' : 'Test UDP non disponibile per questa configurazione TURN'],
    ['–', 'Attivazione VPS', 'Codice impianto e provisioning automatico: da sviluppare'],
    ['–', 'Chiamata', 'Esegui il test audio reale da LAN e rete mobile'],
  ]
  for (const [symbol, title, detail] of checks) {
    const row = document.createElement('p')
    const heading = document.createElement('strong')
    heading.textContent = `${symbol} ${title}: `
    row.append(heading, document.createTextNode(detail))
    target.append(row)
  }
}

let composerGuide = null
let composerStep = Math.max(0, Math.min(3, Number(localStorage.getItem('eface-composer-wizard-step')) || 0))

function composerValue(label, value) {
  const row = document.createElement('p')
  const title = document.createElement('strong')
  title.textContent = `${label}: `
  row.append(title, document.createTextNode(value))
  return row
}

const personalAdmin = document.createElement('section')
personalAdmin.className = 'admin-form'
personalAdmin.innerHTML = '<div class="admin-info"><b>Dispositivi personali e-Face</b><p>Ogni cellulare, tablet o PC ottiene automaticamente un interno proprio al primo accesso Intercom. Qui puoi cambiare il nome visibile o revocare il dispositivo. Se è perso o rubato, cambia anche la password dell’utente e-Face oppure disattiva l’account.</p></div><div id="personal-device-list" class="admin-users-list"></div>'
const legacySipSection = $('#sip-accounts-list')?.closest('.admin-form')
legacySipSection?.before(personalAdmin)
legacySipSection?.remove()

async function personalDevices() {
  const {devices} = await request('api/admin/intercom/personal-devices')
  const list = $('#personal-device-list')
  list.replaceChildren()
  if (!devices.length) {
    const empty = document.createElement('p')
    empty.textContent = 'Nessun dispositivo personale ancora registrato. Apri Intercom sul cellulare, tablet o PC con un utente e-Face non amministratore.'
    list.append(empty)
  }
  for (const device of devices) {
    const row = document.createElement('div')
    row.className = 'admin-info'
    const title = document.createElement('b')
    title.textContent = `${device.name} · ${device.owner} · interno ${device.extension}`
    row.append(title)
    composerAction(row, 'RINOMINA', async () => {
      const name = window.prompt('Nuovo nome del dispositivo', device.name)
      if (name === null) return
      try {
        await request(`api/admin/intercom/personal-devices/${device.device_id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name.trim()})})
        await personalDevices()
        message('Nome dispositivo aggiornato')
      } catch (error) { message(error.message) }
    })
    composerAction(row, 'REVOCA', async () => {
      if (!window.confirm(`Revocare ${device.name} (${device.extension})? L’app su quel dispositivo non potrà più usare questa credenziale.`)) return
      try {
        await request(`api/admin/intercom/personal-devices/${device.device_id}`, {method:'DELETE'})
        await personalDevices()
        message('Dispositivo personale revocato')
      } catch (error) { message(error.message) }
    })
    list.append(row)
  }
  return new Set(devices.map((device) => device.owner))
}

function composerParagraph(parent, value) {
  const paragraph = document.createElement('p')
  paragraph.textContent = value
  parent.append(paragraph)
}

function composerAction(parent, label, action) {
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'secondary'
  button.textContent = label
  button.addEventListener('click', action)
  parent.append(button)
}

async function saveComposerTablets(tablets) {
  const data = await request('api/admin/intercom/control4-tablets', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tablets})})
  composerGuide.additional_tablets = data.tablets
  renderComposerWizard()
  message('Tablet e rotta SIP salvati. Prova una chiamata reale prima di considerarlo operativo.')
}

function composerTabletEditor(parent) {
  const tablets = composerGuide.additional_tablets || []
  for (const tablet of tablets) {
    const row = document.createElement('div')
    row.className = 'admin-form-actions'
    row.append(composerValue(`Interno ${tablet.extension}`, `${tablet.name} · SIP ${tablet.sip_user} · ${tablet.status === 'route_present' ? 'rotta presente, chiamata da provare' : 'rotta non confermata'}`))
    composerAction(row, 'MODIFICA', () => {
      form.elements.extension.value = tablet.extension
      form.elements.name.value = tablet.name
      form.elements.sip_user.value = tablet.sip_user
    })
    composerAction(row, 'RIMUOVI', async () => {
      if (!confirm(`Rimuovere ${tablet.name} e la sua rotta SIP gestita da e-Face?`)) return
      try { await saveComposerTablets(tablets.filter(item => item.extension !== tablet.extension)) } catch (error) { message(error.message) }
    })
    parent.append(row)
  }
  const form = document.createElement('form')
  form.className = 'admin-form'
  form.innerHTML = '<div class="admin-form-grid"><label>Interno (8293–8299)<select name="extension" required></select></label><label>Nome tablet<input name="name" maxlength="64" required></label><label>SIP User Name da Composer<input name="sip_user" maxlength="64" pattern="[A-Za-z0-9_.-]{3,64}" required></label></div><div class="admin-form-actions"><button type="submit">SALVA TABLET</button></div>'
  for (let extension = 8293; extension <= 8299; extension++) {
    const option = document.createElement('option')
    option.value = String(extension)
    option.textContent = String(extension)
    form.elements.extension.append(option)
  }
  form.addEventListener('submit', async event => {
    event.preventDefault()
    const button = form.querySelector('button[type="submit"]')
    button.disabled = true
    try {
      const tablet = {extension:form.elements.extension.value, name:form.elements.name.value.trim(), sip_user:form.elements.sip_user.value.trim()}
      await saveComposerTablets([...tablets.filter(item => item.extension !== tablet.extension).map(({extension, name, sip_user}) => ({extension, name, sip_user})), tablet])
    } catch (error) { message(error.message); button.disabled = false }
  })
  parent.append(form)
}

function renderComposerWizard() {
  if (!composerGuide) return
  const titles = ['Collegamenti di base', 'Aggiungi e-Face in Composer', 'Rileva i tablet Control4', 'Verifica e stato']
  $('#composer-wizard-progress').textContent = `PASSO ${composerStep + 1} DI 4`
  $('#composer-wizard-title').textContent = titles[composerStep]
  const content = $('#composer-wizard-content')
  content.replaceChildren()
  if (composerStep === 0) {
    content.append(composerValue('Controller Control4', composerGuide.control4.host || 'non configurato'))
    content.append(composerValue('Account Director', composerGuide.control4.password_configured ? composerGuide.control4.username : 'credenziali mancanti'))
    content.append(composerValue('Asterisk e-Face', composerGuide.asterisk_host))
    content.append(composerValue('Associazione Asterisk', composerGuide.asterisk_paired ? 'presente' : 'da completare in Videocitofono'))
    composerParagraph(content, 'Puoi configurare o modificare il Director in qualsiasi momento. Dopo il salvataggio torna qui: il wizard rilegge i dati aggiornati. Il SIP dei tablet è separato dalle credenziali dell’account Director.')
    composerAction(content, 'CONFIGURA / MODIFICA CONTROL4', () => { closePanel('installation-config'); $('#control4-tool').click() })
    composerAction(content, 'CONFIGURA / MODIFICA ASTERISK', () => { closePanel('installation-config'); $('#intercom-tool').click() })
  } else if (composerStep === 1) {
    composerParagraph(content, 'In Composer Pro: Agents → Communication → External Devices → Add Device. Imposta Caller ID su “e-Face X4”; nel campo SIP AOR inserisci il valore qui sotto. Il campo Password riguarda il dispositivo esterno Control4: non usare la password del Director né quella del client e-Face 8301. Salva e applica le modifiche.')
    const aor = `${composerGuide.eface_extension}@${composerGuide.asterisk_host}`
    content.append(composerValue('SIP AOR e-Face', aor))
    composerAction(content, 'COPIA SIP AOR', async () => { try { await navigator.clipboard.writeText(aor); message('SIP AOR copiato') } catch (_) { message('Copia non disponibile: seleziona il valore mostrato') } })
    content.append(composerValue('Utente SIP Control4', composerGuide.control4_sip_user || 'non presente in e-Face'))
    content.append(composerValue('Password External Device', composerGuide.control4_sip_copy_present ? 'copia presente in Credenziali impianto: confronta con Composer' : 'non disponibile in e-Face: non completare questo passo'))
    composerParagraph(content, 'La credenziale SIP Control4 salvata oggi in e-Face è una copia di riferimento; questo tutorial non la genera né la modifica nel controller.')
    composerAction(content, 'GESTISCI CREDENZIALI', async () => { try { await credentials(); closePanel('installation-config'); openPanel('credentials-config') } catch (error) { message(error.message) } })
  } else if (composerStep === 2) {
    composerParagraph(content, 'Per ogni tablet: Composer Pro → System Design → apri il tablet → Intercom → SIP Information. Prendi il valore “User Name”: è l’identificativo SIP con cui il proxy Control4 raggiunge quel tablet. Non usare il nome della stanza al suo posto.')
    for (const [extension, name] of Object.entries(composerGuide.tablet_aliases)) content.append(composerValue(`Tablet beta ${extension}`, name))
    composerParagraph(content, 'Puoi modificare le etichette 8291/8292 in Videocitofono. Per un nuovo tablet inserisci il SIP User Name letto in Composer: e-Face crea la rotta 8293–8299 tramite il proxy SIP Control4 già presente in Asterisk. Per ora il nuovo tablet è chiamabile singolarmente, non è incluso nel gruppo Tutti (8290). La rotta confermata non garantisce squillo o audio: prova una chiamata reale.')
    composerAction(content, 'MODIFICA NOMI TABLET', () => { closePanel('installation-config'); $('#intercom-tool').click() })
    composerAction(content, 'GESTISCI TELEFONI VOIP', () => { closePanel('installation-config'); $('#intercom-tool').click(); setTimeout(() => voipAdmin.scrollIntoView({behavior:'smooth', block:'start'}), 150) })
    composerTabletEditor(content)
  } else {
    composerParagraph(content, 'Esegui Verifica impianto qui sotto per rete Asterisk, DoorBird e TURN. Poi apri Intercom e verifica una chiamata vera in entrambi i sensi: la sola risposta TCP o la presenza di una rotta non dimostra audio e squillo.')
    content.append(composerValue('Director', composerGuide.control4.password_configured ? 'credenziali presenti' : 'da configurare'))
    content.append(composerValue('SIP e-Face 8301', composerGuide.eface_password_present ? 'copia presente, da confrontare con Asterisk' : 'mancante'))
    content.append(composerValue('SIP Control4', composerGuide.control4_sip_copy_present ? 'copia presente, da confrontare con Composer' : 'mancante'))
    content.append(composerValue('Provisioner Asterisk', composerGuide.asterisk_paired ? 'associato' : 'non associato'))
  }
  $('#composer-wizard-prev').disabled = composerStep === 0
  $('#composer-wizard-next').textContent = composerStep === 3 ? 'RICOMINCIA' : 'AVANTI'
}

async function loadComposerWizard() {
  composerGuide = await request('api/admin/intercom/composer-guide')
  renderComposerWizard()
}

async function resumeComposerWizard(panel) {
  try {
    await loadComposerWizard()
    if (panel === 'intercom-config') { $('#voip-phone-password').value = ''; $('#voip-phone-credential').hidden = true; intercomAdminFrame.removeAttribute('src') }
    closePanel(panel)
    openPanel('installation-config')
  } catch (error) { message(error.message) }
}

for (const [panel, label] of [['control4-config', 'TORNA AL WIZARD'], ['intercom-config', 'TORNA AL WIZARD'], ['credentials-config', 'TORNA AL WIZARD']]) {
  const bar = document.createElement('div')
  bar.className = 'admin-form-actions composer-return'
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'secondary'
  button.textContent = label
  button.addEventListener('click', () => resumeComposerWizard(panel))
  bar.append(button)
  $(`#${panel} > header`).after(bar)
}

$('#composer-wizard-prev').addEventListener('click', () => { composerStep--; localStorage.setItem('eface-composer-wizard-step', composerStep); renderComposerWizard() })
$('#composer-wizard-next').addEventListener('click', () => { composerStep = (composerStep + 1) % 4; localStorage.setItem('eface-composer-wizard-step', composerStep); renderComposerWizard() })
$('#installation-back').addEventListener('click', () => closePanel('installation-config'))
$('#installation-check').addEventListener('click', async (event) => {
  const button = event.currentTarget
  button.disabled = true
  $('#installation-results').textContent = 'Verifica in corso…'
  try { renderInstallation(await request('api/admin/installation/preflight')) }
  catch(error) { $('#installation-results').textContent = error.message }
  finally { button.disabled = false }
})

let credentialKind = null
let credentialRevealTimer = null

function hideCredentialReveal() {
  clearTimeout(credentialRevealTimer)
  $('#credential-revealed-password').value = ''
  $('#credential-admin-password').value = ''
  $('#credential-revealed').hidden = true
}

async function credentials() {
  const {credentials: entries} = await request('api/admin/credentials')
  const list = $('#credentials-list')
  list.replaceChildren()
  for (const entry of entries) {
    const row = document.createElement('article')
    row.className = 'admin-user-row'
    const identity = document.createElement('div')
    const name = document.createElement('strong')
    name.textContent = entry.label
    const detail = document.createElement('small')
    detail.textContent = `${entry.username || 'Utente non indicato'} · ${entry.managed ? entry.configured ? 'Configurata' : 'Da configurare' : entry.configured ? 'Copia presente, NON verificata' : 'Nessuna copia'} · ${entry.managed ? 'Gestita da e-Face' : 'Non sincronizzata con il dispositivo'}`
    identity.append(name, detail)
    const actions = document.createElement('div')
    actions.className = 'admin-user-actions'
    if (entry.revealable) {
      const reveal = document.createElement('button')
      reveal.type = 'button'
      reveal.className = 'secondary'
      reveal.textContent = 'Mostra'
      reveal.addEventListener('click', () => {
        hideCredentialReveal()
        $('#credential-import-form').hidden = true
        credentialKind = entry.kind
        $('#credential-reveal-title').textContent = `Mostra password · ${entry.label}`
        $('#credential-reveal-form').hidden = false
        $('#credential-admin-password').focus()
      })
      actions.append(reveal)
    }
    const edit = document.createElement('button')
    edit.type = 'button'
    edit.className = 'secondary'
    edit.textContent = entry.managed ? 'Gestisci' : entry.configured ? 'Aggiorna copia' : 'Importa copia'
    edit.addEventListener('click', async () => {
      hideCredentialReveal()
      $('#credential-reveal-form').hidden = true
      credentialKind = entry.kind
      if (!entry.managed) {
        $('#credential-import-title').textContent = `${entry.configured ? 'Aggiorna' : 'Importa'} · ${entry.label}`
        $('#credential-import-username').value = entry.username || ''
        $('#credential-import-password').value = ''
        $('#credential-import-confirm').checked = false
        $('#credential-import-password').required = !entry.configured
        $('#credential-import-form').hidden = false
        $('#credential-import-username').focus()
        return
      }
      closePanel('credentials-config')
      if (entry.kind === 'turn') $('#intercom-tool').click()
      else if (entry.kind === 'control4') $('#control4-tool').click()
      else if (entry.kind === 'eface_admin') { await users(); openPanel('users-config') }
    })
    actions.append(edit)
    if (!entry.managed && entry.configured) {
      const remove = document.createElement('button')
      remove.type = 'button'
      remove.className = 'secondary'
      remove.textContent = 'Rimuovi copia'
      remove.addEventListener('click', async () => {
        if (!confirm(`Rimuovere solo la copia ${entry.label} da e-Face? Asterisk e DoorBird non cambiano.`)) return
        try {
          hideCredentialReveal()
          $('#credential-import-form').hidden = true
          $('#credential-reveal-form').hidden = true
          await request(`api/admin/credentials/${entry.kind}`, {method:'DELETE'})
          await credentials()
          message('Copia rimossa da e-Face; dispositivo invariato')
        } catch(error) { message(error.message) }
      })
      actions.append(remove)
    }
    row.append(identity, actions)
    list.append(row)
  }
}

$('#credentials-back').addEventListener('click', () => {
  hideCredentialReveal()
  $('#credential-reveal-form').hidden = true
  $('#credential-import-form').hidden = true
  closePanel('credentials-config')
})
$('#credential-hide').addEventListener('click', hideCredentialReveal)
$('#credential-reveal-cancel').addEventListener('click', () => { $('#credential-reveal-form').hidden = true; $('#credential-admin-password').value = '' })
$('#credential-import-cancel').addEventListener('click', () => { $('#credential-import-form').hidden = true; $('#credential-import-password').value = ''; $('#credential-import-confirm').checked = false })
$('#credential-import-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = event.currentTarget.querySelector('button[type=submit]')
  button.disabled = true
  try {
    await request(`api/admin/credentials/${credentialKind}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:$('#credential-import-username').value, password:$('#credential-import-password').value, confirmed:$('#credential-import-confirm').checked})})
    $('#credential-import-password').value = ''
    $('#credential-import-confirm').checked = false
    $('#credential-import-form').hidden = true
    await credentials()
    message('Copia salvata in e-Face; il dispositivo non è stato modificato')
  } catch(error) { message(error.message) }
  finally { button.disabled = false }
})
$('#credential-reveal-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const button = event.currentTarget.querySelector('button[type=submit]')
  button.disabled = true
  try {
    const data = await request(`api/admin/credentials/${credentialKind}/reveal`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({admin_password:$('#credential-admin-password').value})})
    $('#credential-admin-password').value = ''
    $('#credential-reveal-form').hidden = true
    $('#credential-revealed-password').value = data.password
    $('#credential-revealed').hidden = false
    credentialRevealTimer = setTimeout(hideCredentialReveal, 30000)
  } catch(error) { $('#credential-admin-password').value = ''; message(error.message) }
  finally { button.disabled = false }
})
window.addEventListener('pagehide', hideCredentialReveal)

const deviceSoundPanel = document.createElement('section')
deviceSoundPanel.id = 'personal-device-sound-config'
deviceSoundPanel.className = 'media-config admin-dashboard-panel'
deviceSoundPanel.hidden = true
deviceSoundPanel.innerHTML = '<header><button type="button" aria-label="Torna a Utente">‹</button><div><small>UTENTE</small><h2>Questo dispositivo</h2></div></header><form class="admin-form"><div class="admin-info"><b>Identità e suoneria Intercom</b><p>Queste preferenze valgono soltanto sul cellulare, tablet o PC in uso.</p></div><div class="admin-form-grid"><label>Nome dispositivo<input name="name" maxlength="64" required></label><label>Suoneria<select name="ringtone"><option value="classic">Classica</option><option value="double">Doppio tono</option><option value="soft">Delicata</option></select></label><label>Volume suoneria <output name="volume_output">80%</output><input name="ring_volume" type="range" min="0" max="100" step="5"></label><label><span><input name="vibration" type="checkbox"> Vibrazione</span></label><label><span><input name="silent" type="checkbox"> Modalità silenziosa</span></label><label><span><input name="push_enabled" type="checkbox"> Ricevi chiamate con e-Face chiusa</span><small>Richiede HTTPS, installazione PWA e autorizzazione notifiche.</small></label></div><div class="admin-form-actions"><button type="button" data-preview>PROVA SUONERIA</button><button type="submit">SALVA</button></div></form>'
document.body.append(deviceSoundPanel)
const deviceSoundForm = deviceSoundPanel.querySelector('form')
deviceSoundForm.elements.ringtone.innerHTML = '<option value="doorbell">Videocitofono</option><option value="dingdong">Din-don</option><option value="double">Campanello doppio</option><option value="bell">Campana</option><option value="soft">Delicata</option>'
let currentPersonalDeviceId = ''
function previewDeviceSound() {
  if (deviceSoundForm.elements.silent.checked) return message('Modalità silenziosa attiva')
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) return message('Audio non disponibile in questo browser')
  const context = new AudioContextClass()
  const volume = Number(deviceSoundForm.elements.ring_volume.value) / 100
  const patterns = {doorbell:[[784,0],[523,.38],[784,.82]], dingdong:[[659,0],[440,.46]], double:[[740,0],[740,.24],[932,.58]], bell:[[587,0],[784,.62]], soft:[[523,0],[659,.34]], classic:[[880,0],[660,.24]]}
  const now = context.currentTime
  for (const [frequency, delay] of patterns[deviceSoundForm.elements.ringtone.value]) {
    const oscillator=context.createOscillator(), gain=context.createGain()
    oscillator.frequency.value=frequency; gain.gain.setValueAtTime(.0001,now+delay); gain.gain.exponentialRampToValueAtTime(Math.max(.001,.25*volume),now+delay+.02); gain.gain.exponentialRampToValueAtTime(.0001,now+delay+.16); oscillator.connect(gain); gain.connect(context.destination); oscillator.start(now+delay); oscillator.stop(now+delay+.18)
  }
  setTimeout(() => context.close(), 1200)
}
async function openDeviceSound(status) {
  currentPersonalDeviceId = localStorage.getItem(`eface-personal-device-id-${status.user}`) || ''
  if (!currentPersonalDeviceId) return message('Apri prima Intercom su questo dispositivo per registrarlo')
  const data = await request(`api/intercom/personal-device/${encodeURIComponent(currentPersonalDeviceId)}/preferences`)
  for (const key of ['name','ringtone','ring_volume']) deviceSoundForm.elements[key].value = data[key]
  deviceSoundForm.elements.vibration.checked = data.vibration
  deviceSoundForm.elements.silent.checked = data.silent
  if ('serviceWorker' in navigator && 'PushManager' in window) {
    const registration = await navigator.serviceWorker.register(api('service-worker.js'), {scope:new URL('./', api('service-worker.js')).pathname})
    deviceSoundForm.elements.push_enabled.checked = Boolean(await registration.pushManager.getSubscription())
  } else deviceSoundForm.elements.push_enabled.disabled = true
  deviceSoundForm.elements.volume_output.value = `${data.ring_volume}%`
  openPanel(deviceSoundPanel.id)
}
deviceSoundPanel.querySelector('header button').addEventListener('click', () => closePanel(deviceSoundPanel.id))
deviceSoundForm.elements.ring_volume.addEventListener('input', event => { deviceSoundForm.elements.volume_output.value = `${event.target.value}%` })
deviceSoundForm.querySelector('[data-preview]').addEventListener('click', previewDeviceSound)
function pushKeyBytes(value) {
  const padding = '='.repeat((4 - value.length % 4) % 4)
  return Uint8Array.from(atob((value + padding).replace(/-/g, '+').replace(/_/g, '/')), char => char.charCodeAt(0))
}
async function savePushPreference(enabled) {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !window.isSecureContext) {
    if (enabled) throw new Error('Le notifiche richiedono e-Face aperta tramite HTTPS')
    return
  }
  const registration = await navigator.serviceWorker.ready
  let subscription = await registration.pushManager.getSubscription()
  if (enabled) {
    if (Notification.permission === 'denied') throw new Error('Notifiche bloccate nelle impostazioni di Chrome')
    if (!subscription) {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') throw new Error('Autorizzazione notifiche non concessa')
      const {public_key:publicKey} = await request('api/intercom/push/key')
      subscription = await registration.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:pushKeyBytes(publicKey)})
    }
    await request(`api/intercom/push/subscription/${encodeURIComponent(currentPersonalDeviceId)}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(subscription.toJSON())})
  } else if (subscription) {
    await request(`api/intercom/push/subscription/${encodeURIComponent(currentPersonalDeviceId)}`, {method:'DELETE'}).catch(() => null)
    await subscription.unsubscribe()
  }
}
deviceSoundForm.addEventListener('submit', async event => {
  event.preventDefault()
  try {
    await request(`api/intercom/personal-device/${encodeURIComponent(currentPersonalDeviceId)}/preferences`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:deviceSoundForm.elements.name.value.trim(), ringtone:deviceSoundForm.elements.ringtone.value, ring_volume:Number(deviceSoundForm.elements.ring_volume.value), vibration:deviceSoundForm.elements.vibration.checked, silent:deviceSoundForm.elements.silent.checked})})
    await savePushPreference(deviceSoundForm.elements.push_enabled.checked)
    message('Impostazioni del dispositivo salvate')
    closePanel(deviceSoundPanel.id)
  } catch(error) { message(error.message) }
})

async function initialize() {
  const status = await request('api/auth/status')
  if (status.enabled) {
    const phoneLink = document.createElement('button')
    phoneLink.type = 'button'
    phoneLink.className = 'tool-card'
    phoneLink.innerHTML = '<span><svg viewBox="0 0 24 24" aria-hidden="true" style="width:30px;height:30px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round"><path d="M5 7v5M9 5v9M13 4v11M17 5v9M21 7v5M5 18c4.5 3 9.5 3 14 0"/></svg></span><div><b>Videocitofono</b><small>Nome e suoneria di questo dispositivo</small></div><i>›</i>'
    phoneLink.addEventListener('click', () => openDeviceSound(status).catch(error => message(error.message)))
    $('#tools-user-section .tools-grid').append(phoneLink)
  }
  $('#tools-admin-nav').hidden = status.enabled && status.role !== 'admin'
  if (status.enabled && status.role === 'admin') {
    const vault = document.createElement('button')
    vault.type = 'button'
    vault.id = 'credentials-tool'
    vault.className = 'tool-card'
    vault.innerHTML = '<span>⌑</span><div><b>Credenziali impianto</b><small>Account e password in un unico punto</small></div><i>›</i>'
    vault.addEventListener('click', async () => { try { await credentials(); openPanel('credentials-config') } catch(error) { message(error.message) } })
    $('#admin-tools .tools-grid').prepend(vault)
    const setup = document.createElement('button')
    setup.type = 'button'
    setup.id = 'installation-tool'
    setup.className = 'tool-card'
    setup.innerHTML = '<span>◇</span><div><b>Configurazione guidata Intercom</b><small>Tutorial Composer e verifiche impianto</small></div><i>›</i>'
    setup.addEventListener('click', async () => { try { await loadComposerWizard(); openPanel('installation-config') } catch (error) { message(error.message) } })
    $('#admin-tools .tools-grid').prepend(setup)
    const link = document.createElement('a')
    link.href = api('intercom')
    link.className = 'tool-card'
    const icon = document.createElement('span')
    icon.textContent = '☎'
    const description = document.createElement('div')
    const title = document.createElement('b')
    title.textContent = 'Postazione citofono'
    const detail = document.createElement('small')
    detail.textContent = 'Audio e-Face in rete locale e da remoto'
    description.append(title, detail)
    const arrow = document.createElement('i')
    arrow.textContent = '›'
    link.append(icon, description, arrow)
    $('#admin-tools .tools-grid').append(link)
  }
  $('#tools-admin-section').querySelector('#admin-locked p').textContent = status.enabled ? 'Solo l’account admin può gestire impianto e accessi.' : 'Inserisci la password installatore configurata nelle opzioni dell’add-on.'
  if (location.hash === '#admin' && !$('#tools-admin-nav').hidden) view('admin')
  try { const health = await request('health'); $('#tools-version').textContent = health.version } catch { /* Versione opzionale */ }
}
initialize().catch((error) => message(error.message))
