const $ = (selector) => document.querySelector(selector)
const api = (path) => new URL(`../${path}`, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()

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
    detail.textContent = `${user.username} · ${user.role === 'admin' ? 'Amministratore' : 'Utente'} · ${user.active ? 'Attivo' : 'Disattivato'}`
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
    }
    row.append(identity, actions)
    list.append(row)
  }
}

$('#users-tool').addEventListener('click', async () => { try { await users(); openPanel('users-config') } catch(error) { message(error.message) } })
$('#users-back').addEventListener('click', () => closePanel('users-config'))
$('#user-create-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const form = event.currentTarget
  const button = form.querySelector('button[type=submit]')
  button.disabled = true
  try {
    await request('api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:$('#user-name').value, username:$('#user-username').value, password:$('#user-password').value})})
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
}

$('#intercom-tool').addEventListener('click', async () => { try { await intercom(); openPanel('intercom-config') } catch(error) { message(error.message) } })
$('#intercom-back').addEventListener('click', () => closePanel('intercom-config'))
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

async function initialize() {
  const status = await request('api/auth/status')
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
    setup.innerHTML = '<span>◇</span><div><b>Preparazione impianto</b><small>Controlli per la futura attivazione guidata</small></div><i>›</i>'
    setup.addEventListener('click', () => openPanel('installation-config'))
    $('#admin-tools .tools-grid').prepend(setup)
    const link = document.createElement('a')
    link.href = api('intercom')
    link.className = 'tool-card'
    const icon = document.createElement('span')
    icon.textContent = '☎'
    const description = document.createElement('div')
    const title = document.createElement('b')
    title.textContent = 'Postazione SIP di prova'
    const detail = document.createElement('small')
    detail.textContent = 'Audio e-Face in rete locale'
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
