const root = document.querySelector('.tools-shell')
const escapeHtml = value => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML.replaceAll('"', '&quot;').replaceAll("'", '&#39;') }
const endpoint = path => new URL(`../${path}`, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()
async function request(path, options = {}) {
  const response = await fetch(endpoint(path), {cache: 'no-store', ...options})
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.join(' · ') : detail?.message || `HTTP ${response.status}`)
  }
  return data
}
const jsonOptions = (method, body) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
const userCard = document.createElement('button')
userCard.type = 'button'
userCard.className = 'tool-card'
userCard.innerHTML = '<span>⏱</span><div><b>Routine</b><small>Personalizza le azioni della casa</small></div><i>›</i>'
document.querySelector('#tools-user-section .tools-grid').append(userCard)
const adminCard = document.createElement('button')
adminCard.type = 'button'
adminCard.className = 'tool-card'
adminCard.innerHTML = '<span>☷</span><div><b>Registro routine</b><small>Eventi, comandi e dispositivi coinvolti</small></div><i>›</i>'
document.querySelector('#admin-tools .tools-grid').append(adminCard)

const panel = document.createElement('section')
panel.className = 'media-config routine-panel'
panel.hidden = true
panel.innerHTML = `<header><button type="button" data-routine-back aria-label="Torna a Strumenti">‹</button><div><small>STRUMENTI UTENTE</small><h2>Routine</h2></div></header>
  <p>Crea automazioni comprensibili. Prima di attivarle, e-Face verifica dispositivi, comandi e possibili interazioni.</p>
  <div class="routine-layout"><aside><button type="button" class="routine-primary" data-routine-new>+ NUOVA ROUTINE</button><div data-routine-list></div></aside>
  <div class="routine-editor" hidden><label>Nome routine<input data-routine-name maxlength="80" placeholder="Es. Luci ingresso la sera"></label>
  <h3>Quando</h3><p>Una qualsiasi attivazione avvia la routine.</p><div data-routine-triggers></div><button type="button" data-routine-add="trigger">+ Aggiungi attivazione</button>
  <h3>E se <small>(opzionale)</small></h3><p>Tutte queste condizioni devono essere vere all'inizio.</p><div data-routine-conditions></div><button type="button" data-routine-add="condition">+ Aggiungi condizione</button>
  <h3>Allora</h3><p>I blocchi sono eseguiti nell'ordine mostrato. Dopo un timer puoi ricontrollare uno stato.</p><div data-routine-steps></div>
  <div class="routine-add"><button type="button" data-routine-add="action">+ Azione</button><button type="button" data-routine-add="wait">+ Timer</button><button type="button" data-routine-add="check">+ Verifica</button></div>
  <div class="routine-review" data-routine-review aria-live="polite">Premi «Controlla» per leggere gli effetti della routine.</div>
  <div class="routine-actions"><button type="button" data-routine-validate>CONTROLLA</button><button type="button" data-routine-save="draft">SALVA DISATTIVATA</button><button type="button" class="routine-primary" data-routine-save="active">SALVA E ATTIVA</button><button type="button" data-routine-delete hidden>ELIMINA</button></div></div></div>`
root.append(panel)
const logPanel = document.createElement('section')
logPanel.className = 'media-config routine-panel'
logPanel.hidden = true
logPanel.innerHTML = `<header><button type="button" data-routine-log-back aria-label="Torna ad Amministrazione">‹</button><div><small>AMMINISTRAZIONE</small><h2>Registro routine</h2></div></header>
  <p>Comando richiesto, risposta del connettore e stato osservato sono registrati separatamente. Conservazione massima: 15 giorni e 50 MB.</p>
  <div class="routine-filters"><label>Dispositivo<input data-routine-filter-device placeholder="Nome o ID dispositivo"></label><label>Routine<input data-routine-filter-routine placeholder="ID routine"></label><button type="button" data-routine-filter>FILTRA</button></div>
  <div data-routine-log-list></div>`
root.append(logPanel)
const $ = selector => panel.querySelector(selector)
let routines = []
let devices = []
let current = null
let draft = null
const actions = {
  light: [['on', 'Accendi'], ['off', 'Spegni'], ['brightness', 'Luminosità %']],
  switch: [['on', 'Accendi'], ['off', 'Spegni']],
  cover: [['open', 'Apri'], ['close', 'Chiudi'], ['stop', 'Ferma']],
  media_player: [['media_play', 'Riproduci'], ['media_pause', 'Pausa'], ['media_stop', 'Stop'], ['turn_off', 'Spegni stanza'], ['set_volume', 'Volume %'], ['volume_mute', 'Mute'], ['volume_unmute', 'Riattiva audio']],
  climate: [['set_target', 'Temperatura °C']]
}
const sensitive = /porta|portone|cancello|garage|serratura|allarme|alarm|gate|door|lock/i
const safeDevices = () => devices.filter(item => actions[item.kind] && !sensitive.test([item.id, item.entity_id, item.name, item.room].join(' ')))
const deviceOptions = (selected, allowed = devices, query = '') => {
  const words = query.trim().toLocaleLowerCase('it-IT').split(/\s+/).filter(Boolean)
  const matches = allowed.filter(item => words.every(word => [item.room, item.name, item.id, item.entity_id].some(part => String(part || '').toLocaleLowerCase('it-IT').includes(word))))
  const shown = matches.slice(0, 80)
  const selectedItem = allowed.find(item => item.id === selected)
  if (selectedItem && !shown.some(item => item.id === selected)) shown.unshift(selectedItem)
  return `<option value="">${matches.length > 80 ? `${matches.length} risultati: affina la ricerca` : matches.length ? `Scegli dispositivo (${matches.length})` : 'Nessun dispositivo trovato'}</option>${shown.map(item => `<option value="${escapeHtml(item.id)}" ${item.id === selected ? 'selected' : ''}>${escapeHtml([item.room, item.name, item.id].filter(Boolean).join(' · '))}</option>`).join('')}`
}
const deviceField = (selected, scope = 'all') => `<div class="routine-device-field"><input data-device-search type="search" autocomplete="off" placeholder="Cerca stanza o dispositivo, es. ufficio" aria-label="Cerca dispositivo"><select data-field="device" data-device-scope="${scope}">${deviceOptions(selected, scope === 'safe' ? safeDevices() : devices)}</select></div>`
const valuesFor = deviceId => {
  const device = devices.find(item => item.id === deviceId)
  const byKind = {light:['on','off'], switch:['on','off'], binary_sensor:['on','off'], cover:['open','closed','opening','closing'], media_player:['playing','paused','idle','off'], lock:['locked','unlocked'], climate:['heat','cool','auto','off'], alarm_system:['armed','disarmed']}
  return [...new Set([...(byKind[device?.kind] || []), String(device?.state ?? '').toLowerCase()].filter(Boolean))]
}
const stateSelect = (deviceId, selected) => {
  const values = valuesFor(deviceId)
  if (!values.length || !['light','switch','binary_sensor','cover','media_player','lock','climate','alarm_system'].includes(devices.find(item => item.id === deviceId)?.kind)) {
    return `<input data-field="value" value="${escapeHtml(selected || '')}" placeholder="${values.length ? `Stato attuale: ${escapeHtml(values[0])}` : 'Stato del dispositivo'}" aria-label="Stato del dispositivo">`
  }
  if (selected && !values.includes(selected)) values.push(selected)
  return `<select data-field="value" aria-label="Stato possibile"><option value="">Scegli stato</option>${values.map(value => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('')}</select>`
}
function collect() {
  if (!draft) return
  draft.name = $('[data-routine-name]').value.trim()
  draft.triggers = [...$('[data-routine-triggers]').children].map(row => {
    const type = row.querySelector('[data-field="type"]').value
    return type === 'time' ? {type, at: row.querySelector('[data-field="at"]')?.value || ''}
      : type === 'doorbird' ? {type, event: row.querySelector('[data-field="event"]')?.value || ''}
      : {type: 'state', device_id: row.querySelector('[data-field="device"]')?.value || '', to: row.querySelector('[data-field="value"]')?.value || ''}
  })
  draft.conditions = [...$('[data-routine-conditions]').children].map(row => ({device_id: row.querySelector('[data-field="device"]').value, operator: row.querySelector('[data-field="operator"]').value, value: row.querySelector('[data-field="value"]').value}))
  draft.steps = [...$('[data-routine-steps]').children].map(row => {
    const type = row.dataset.type
    if (type === 'wait') return {type, seconds: Number(row.querySelector('[data-field="seconds"]').value)}
    if (type === 'check') return {type, device_id: row.querySelector('[data-field="device"]').value, operator: row.querySelector('[data-field="operator"]').value, value: row.querySelector('[data-field="value"]').value}
    const action = row.querySelector('[data-field="action"]').value
    const value = row.querySelector('[data-field="action-value"]')?.value
    return {type, device_id: row.querySelector('[data-field="device"]').value, action, value: value === undefined || value === '' ? null : Number(value)}
  })
}
function renderList() {
  $('[data-routine-list]').innerHTML = routines.map(item => `<button type="button" class="routine-list-item${current?.id === item.id ? ' selected' : ''}" data-routine-open="${escapeHtml(item.id)}"><b>${escapeHtml(item.name)}</b><small>${item.enabled ? 'ATTIVA' : 'DISATTIVATA'} · versione ${item.revision}</small></button>`).join('') || '<p>Nessuna routine creata.</p>'
}
function renderEditor() {
  $('.routine-editor').hidden = !draft
  if (!draft) return
  $('[data-routine-name]').value = draft.name || ''
  $('[data-routine-triggers]').innerHTML = draft.triggers.map((item, index) => `<div class="routine-block" data-index="${index}"><select data-field="type"><option value="state" ${item.type === 'state' ? 'selected' : ''}>Quando cambia un dispositivo</option><option value="time" ${item.type === 'time' ? 'selected' : ''}>A un orario</option><option value="doorbird" ${item.type === 'doorbird' ? 'selected' : ''}>Evento DoorBird</option></select>${item.type === 'time' ? `<input data-field="at" type="time" value="${escapeHtml(item.at || '')}">` : item.type === 'doorbird' ? `<select data-field="event"><option value="doorbell" ${item.event === 'doorbell' ? 'selected' : ''}>Chiamata</option><option value="motionsensor" ${item.event === 'motionsensor' ? 'selected' : ''}>Movimento</option></select>` : `${deviceField(item.device_id)}${stateSelect(item.device_id, item.to)}`}<button type="button" data-routine-remove="trigger" aria-label="Rimuovi">×</button></div>`).join('')
  $('[data-routine-conditions]').innerHTML = draft.conditions.map((item, index) => conditionRow(item, index, 'condition')).join('')
  $('[data-routine-steps]').innerHTML = draft.steps.map((item, index) => {
    if (item.type === 'wait') return `<div class="routine-block" data-index="${index}" data-type="wait"><b>Timer</b><label>Secondi<input data-field="seconds" type="number" min="1" max="3600" value="${Number(item.seconds) || 60}"></label>${stepButtons(index)}</div>`
    if (item.type === 'check') return conditionRow(item, index, 'check')
    const device = devices.find(entry => entry.id === item.device_id)
    const choices = actions[device?.kind] || []
    const actionChoices = choices.filter(([key]) => !device?.capabilities || !({media_play:'play',media_pause:'pause',media_stop:'stop',turn_off:'turn_off',set_volume:'set_volume',volume_mute:'mute',volume_unmute:'mute'}[key]) || device.capabilities[{media_play:'play',media_pause:'pause',media_stop:'stop',turn_off:'turn_off',set_volume:'set_volume',volume_mute:'mute',volume_unmute:'mute'}[key]])
    const value = ['brightness', 'set_volume', 'set_target'].includes(item.action) ? `<label>Valore<input data-field="action-value" type="number" min="${item.action === 'set_target' ? 5 : 0}" max="${item.action === 'set_target' ? 35 : 100}" value="${item.value ?? ''}"></label>` : ''
    return `<div class="routine-block" data-index="${index}" data-type="action"><b>Azione</b>${deviceField(item.device_id, 'safe')}<select data-field="action"><option value="">Comando...</option>${actionChoices.map(([key, label]) => `<option value="${key}" ${key === item.action ? 'selected' : ''}>${label}</option>`).join('')}</select>${value}${stepButtons(index)}</div>`
  }).join('')
  $('[data-routine-delete]').hidden = !current
  $('[data-routine-review]').textContent = 'Premi «Controlla» per leggere gli effetti della routine.'
  renderList()
}
function conditionRow(item, index, type) {
  return `<div class="routine-block" data-index="${index}" ${type === 'check' ? 'data-type="check"' : ''}><b>${type === 'check' ? 'Verifica e interrompi se falsa' : 'Condizione iniziale'}</b>${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator === 'is' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id, item.value)}${type === 'check' ? stepButtons(index) : '<button type="button" data-routine-remove="condition" aria-label="Rimuovi">×</button>'}</div>`
}
function stepButtons() { return '<div class="routine-move"><button type="button" data-routine-up aria-label="Sposta su">↑</button><button type="button" data-routine-down aria-label="Sposta giù">↓</button><button type="button" data-routine-remove="step" aria-label="Rimuovi">×</button></div>' }
function showReview(review) {
  $('[data-routine-review]').innerHTML = `<b>Effetti previsti in casa</b><p>${escapeHtml(review.description)}</p>${review.errors.length ? `<div class="routine-errors"><b>Da correggere</b>${review.errors.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : '<p class="routine-ok">Controlli bloccanti superati.</p>'}${review.warnings.length ? `<div class="routine-warnings"><b>Da valutare</b>${review.warnings.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : ''}`
}
async function load() {
  const [list, catalog] = await Promise.all([request('api/user/routines'), request('api/user/routines/catalog')])
  routines = list.items || []
  devices = catalog.devices || []
  renderList()
  if (catalog.demo) $('[data-routine-review]').textContent = 'Modalità demo: le routine non possono essere attivate.'
}
function open() {
  panel.hidden = false
  document.body.style.overflow = 'hidden'
  load().catch(error => $('[data-routine-list]').textContent = error.message)
}
function close() { panel.hidden = true; document.body.style.overflow = '' }
userCard.addEventListener('click', open)
$('[data-routine-back]').addEventListener('click', close)
$('[data-routine-new]').addEventListener('click', () => { current = null; draft = {name: '', triggers: [{type: 'state', device_id: '', to: ''}], conditions: [], steps: [{type: 'action', device_id: '', action: ''}]}; renderEditor() })
$('[data-routine-list]').addEventListener('click', event => {
  const button = event.target.closest('[data-routine-open]')
  if (!button) return
  current = routines.find(item => item.id === button.dataset.routineOpen)
  draft = structuredClone(current.spec)
  renderEditor()
})
panel.addEventListener('click', event => {
  const add = event.target.closest('[data-routine-add]')
  if (add) {
    collect()
    const kind = add.dataset.routineAdd
    if (kind === 'trigger') draft.triggers.push({type: 'state', device_id: '', to: ''})
    else if (kind === 'condition') draft.conditions.push({device_id: '', operator: 'is', value: ''})
    else draft.steps.push(kind === 'wait' ? {type: 'wait', seconds: 60} : kind === 'check' ? {type: 'check', device_id: '', operator: 'is', value: ''} : {type: 'action', device_id: '', action: ''})
    renderEditor()
    return
  }
  const remove = event.target.closest('[data-routine-remove]')
  if (remove) {
    collect()
    const index = Number(remove.closest('[data-index]').dataset.index)
    const collection = remove.dataset.routineRemove === 'trigger' ? draft.triggers : remove.dataset.routineRemove === 'condition' ? draft.conditions : draft.steps
    collection.splice(index, 1)
    renderEditor()
    return
  }
  const move = event.target.closest('[data-routine-up],[data-routine-down]')
  if (move) {
    collect()
    const index = Number(move.closest('[data-index]').dataset.index)
    const next = index + (move.hasAttribute('data-routine-up') ? -1 : 1)
    if (next < 0 || next >= draft.steps.length) return
    ;[draft.steps[index], draft.steps[next]] = [draft.steps[next], draft.steps[index]]
    renderEditor()
  }
})
panel.addEventListener('input', event => {
  if (!event.target.matches('[data-device-search]')) return
  const select = event.target.parentElement.querySelector('[data-field="device"]')
  const allowed = select.dataset.deviceScope === 'safe' ? safeDevices() : devices
  select.innerHTML = deviceOptions(select.value, allowed, event.target.value)
})
panel.addEventListener('change', event => {
  const field = event.target
  if (!field.matches('[data-field="device"],[data-field="type"],[data-field="action"]')) return
  collect()
  const row = field.closest('[data-index]')
  const index = Number(row?.dataset.index)
  if (row?.parentElement.matches('[data-routine-triggers]')) {
    if (field.dataset.field === 'type') draft.triggers[index] = field.value === 'time' ? {type:'time',at:'18:00'} : field.value === 'doorbird' ? {type:'doorbird',event:'doorbell'} : {type:'state',device_id:'',to:''}
    else if (field.dataset.field === 'device') draft.triggers[index].to = ''
  } else if (row?.parentElement.matches('[data-routine-conditions]')) draft.conditions[index].value = ''
  else if (row?.dataset.type === 'check') draft.steps[index].value = ''
  else if (row?.dataset.type === 'action') {
    if (field.dataset.field === 'device') { draft.steps[index].action = ''; draft.steps[index].value = null }
    if (field.dataset.field === 'action') draft.steps[index].value = null
  }
  renderEditor()
})
$('[data-routine-validate]').addEventListener('click', async () => { collect(); try { showReview(await request('api/user/routines/validate', jsonOptions('POST', {spec:draft, id:current?.id}))) } catch(error) { $('[data-routine-review]').textContent = error.message } })
panel.querySelectorAll('[data-routine-save]').forEach(button => button.addEventListener('click', async () => {
  collect()
  button.disabled = true
  try {
    const review = await request('api/user/routines/validate', jsonOptions('POST', {spec:draft, id:current?.id}))
    showReview(review)
    if (review.errors.length) return
    const enabled = button.dataset.routineSave === 'active'
    const confirm_warnings = enabled && review.warnings.length ? window.confirm(`Verifica prima di attivare:\n\n${review.warnings.join('\n')}\n\nConfermi?`) : false
    if (enabled && review.warnings.length && !confirm_warnings) return
    const path = current ? `api/user/routines/${encodeURIComponent(current.id)}` : 'api/user/routines'
    const result = await request(path, jsonOptions(current ? 'PUT' : 'POST', {spec:draft, enabled, confirm_warnings, expected_revision:current?.revision ?? null}))
    current = result.item
    draft = structuredClone(current.spec)
    await load()
    renderEditor()
    $('[data-routine-review]').textContent = enabled ? 'Routine attiva. Il registro Admin seguirà ogni esecuzione.' : 'Routine salvata e disattivata.'
  } catch(error) { $('[data-routine-review]').textContent = error.message } finally { button.disabled = false }
}))
$('[data-routine-delete]').addEventListener('click', async () => {
  if (!current || !window.confirm(`Eliminare «${current.name}»? Il registro Admin rimane disponibile per 15 giorni.`)) return
  try {
    await request(`api/user/routines/${encodeURIComponent(current.id)}`, {method:'DELETE'})
    current = null; draft = null; renderEditor(); await load()
  } catch(error) { $('[data-routine-review]').textContent = error.message }
})
adminCard.addEventListener('click', () => { logPanel.hidden = false; document.body.style.overflow = 'hidden'; loadLogs() })
logPanel.querySelector('[data-routine-log-back]').addEventListener('click', () => { logPanel.hidden = true; document.body.style.overflow = '' })
logPanel.querySelector('[data-routine-filter]').addEventListener('click', loadLogs)
async function loadLogs() {
  const target = logPanel.querySelector('[data-routine-log-list]')
  target.textContent = 'Caricamento…'
  try {
    const params = new URLSearchParams({device_id:logPanel.querySelector('[data-routine-filter-device]').value.trim(), routine_id:logPanel.querySelector('[data-routine-filter-routine]').value.trim(), limit:'100'})
    const data = await request(`api/admin/routines/log?${params}`)
    target.innerHTML = (data.items || []).map(run => `<details class="routine-log-run"><summary><b>${escapeHtml(run.name)}</b><span>${escapeHtml(new Date(run.started_at).toLocaleString('it-IT'))} · ${escapeHtml(run.status)}</span><small>${escapeHtml(run.trigger_detail)}</small></summary><p>Versione ${run.revision} · modificata da ${escapeHtml(run.modified_by || 'sconosciuto')} · esecuzione ${escapeHtml(run.id)}</p>${run.events.map(entry => `<div class="routine-log-event"><time>${escapeHtml(new Date(entry.at).toLocaleTimeString('it-IT'))}</time><b>${escapeHtml(entry.stage)}</b><span>${escapeHtml(entry.device_name || entry.detail || '')}</span><small>${escapeHtml([entry.action, entry.result, entry.before_state && `prima: ${entry.before_state}`, entry.after_state && `dopo: ${entry.after_state}`].filter(Boolean).join(' · '))}</small></div>`).join('')}</details>`).join('') || '<p>Nessuna esecuzione nel periodo conservato.</p>'
  } catch(error) { target.textContent = error.message }
}
