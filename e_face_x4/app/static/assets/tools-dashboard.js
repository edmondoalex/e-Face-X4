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
  const {settings} = await request('api/admin/intercom')
  $('#intercom-asterisk-host').value = settings.asterisk_host
  $('#intercom-asterisk-port').value = settings.asterisk_port
  $('#intercom-doorbird-host').value = settings.doorbird_host
  $('#intercom-doorbird-port').value = settings.doorbird_port
  $('#intercom-ring-extension').value = settings.ring_extension
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
$('#intercom-test').addEventListener('click', async () => {
  const button = $('#intercom-test')
  button.disabled = true
  try {
    const data = await request('api/admin/intercom/test', {method:'POST'})
    $('#intercom-status').textContent = `Asterisk: ${data.asterisk_reachable ? 'raggiungibile' : 'non raggiungibile'} · DoorBird: ${data.doorbird_reachable ? 'raggiungibile' : 'non raggiungibile'} · Telefonia e-Face: non ancora attiva`
  } catch(error) { message(error.message) } finally { button.disabled = false }
})

async function initialize() {
  const status = await request('api/auth/status')
  $('#tools-admin-nav').hidden = status.enabled && status.role !== 'admin'
  if (status.enabled && status.role === 'admin') {
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
