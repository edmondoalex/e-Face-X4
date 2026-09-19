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
  <section class="routine-wizard" aria-label="Creazione guidata routine"><div class="routine-wizard-steps"><b>1 · Descrivi</b><b>2 · Verifica la bozza</b><b>3 · Salva o attiva</b></div><label>Scrivi cosa vuoi che accada<textarea data-routine-description rows="3" maxlength="2000" placeholder="Quando Luce Ufficio Alex si accende, accendi Luce Corridoio poi aspetta 60 secondi poi spegni Luce Corridoio"></textarea></label><p>Usa il nome completo dei dispositivi. La bozza non viene salvata né attivata automaticamente; puoi sempre correggerla nei campi qui sotto.</p><button type="button" class="routine-primary" data-routine-generate>CREA BOZZA DA DESCRIZIONE</button><p data-routine-generate-status role="status" aria-live="polite"></p></section>
  <div class="routine-layout"><aside><button type="button" class="routine-primary" data-routine-new>+ NUOVA ROUTINE</button><div data-routine-list></div></aside>
  <div class="routine-editor" hidden><label>Nome routine<input data-routine-name maxlength="80" placeholder="Es. Luci ingresso la sera"></label>
  <h3>Quando</h3><p>Una qualsiasi attivazione avvia la routine. Alba e tramonto usano la posizione di Home Assistant; minuti negativi anticipano, positivi ritardano.</p><div data-routine-triggers></div><button type="button" data-routine-add="trigger">+ Aggiungi attivazione</button>
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
  <div class="routine-filters"><label>Dispositivo<input data-routine-filter-device placeholder="Nome dispositivo"></label><label>Routine<input data-routine-filter-routine type="search" list="routine-log-names" placeholder="Nome routine"><datalist id="routine-log-names"></datalist></label><button type="button" data-routine-filter>FILTRA</button></div>
  <div data-routine-log-list></div>`
root.append(logPanel)
const $ = selector => panel.querySelector(selector)
let routines = []
let devices = []
let current = null
let draft = null
const actions = {
  light_scenario: [['on', 'Attiva'], ['off', 'Disattiva'], ['run', 'Esegui'], ['stop', 'Ferma']],
  light: [['on', 'Accendi'], ['off', 'Spegni'], ['brightness', 'Luminosità %']],
  switch: [['on', 'Accendi'], ['off', 'Spegni']],
  cover: [['open', 'Apri'], ['close', 'Chiudi'], ['stop', 'Ferma']],
  media_player: [['media_play', 'Riproduci'], ['media_pause', 'Pausa'], ['media_stop', 'Stop'], ['media_next', 'Successivo'], ['media_previous', 'Precedente'], ['turn_off', 'Spegni stanza'], ['set_volume', 'Volume %'], ['volume_mute', 'Mute'], ['volume_unmute', 'Riattiva audio'], ['select_source', 'Seleziona sorgente'], ['remote_command', 'Tasto telecomando sorgente'], ['dnd_on', 'Attiva Non disturbare'], ['dnd_off', 'Disattiva Non disturbare'], ['tts', 'Messaggio vocale (TTS)']],
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
const deviceField = (selected, scope = 'all') => `<div class="routine-device-field"><input data-device-search type="search" autocomplete="off" placeholder="Cerca stanza o dispositivo, es. ufficio" aria-label="Cerca dispositivo"><select data-field="device" data-device-scope="${scope}">${deviceOptions(selected, scope === 'safe' ? safeDevices() : scope === 'media' ? devices.filter(item => item.kind === 'media_player') : devices)}</select></div>`
const mediaRemoteCapabilities = {media_play:'play',media_pause:'pause',media_stop:'stop',media_next:'next',media_previous:'previous',turn_off:'turn_off',volume_mute:'mute',volume_unmute:'mute'}
const remoteLabels = {play:'Play',pause:'Pausa',stop:'Stop',skip_fwd:'Successivo',skip_rev:'Precedente',scan_fwd:'Avanti veloce',scan_rev:'Riavvolgi',channel_up:'Canale +',channel_down:'Canale −',up:'Su',down:'Giù',left:'Sinistra',right:'Destra',enter:'OK / Seleziona',menu:'Menu',guide:'Guida',info:'Info',cancel:'Indietro',dvr:'DVR',record:'Registra',input:'Ingresso',recall:'Richiama',page_up:'Pagina +',page_down:'Pagina −'}
function remoteFields(deviceId, sourceId = 0, command = '', trigger = true) {
  const device = devices.find(item => item.id === deviceId)
  const sources = (device?.source_options || []).filter(item => item.experience === 'watch' && item.remote_actions?.length)
  const options = trigger ? [{source_id:0,label:'Comandi player audio / video'}, ...sources] : sources
  const selected = options.find(item => Number(item.source_id) === Number(sourceId)) || options[0]
  const commands = selected?.source_id === 0 ? actions.media_player.filter(([key]) => mediaRemoteCapabilities[key] && device?.capabilities?.[mediaRemoteCapabilities[key]]) : (selected?.remote_actions || []).map(key => [key,remoteLabels[key] || key.replaceAll('_',' ')])
  return `<select data-field="remote-source" aria-label="Sorgente telecomando"><option value="">Scegli sorgente</option>${options.map(item => `<option value="${Number(item.source_id)}" ${Number(item.source_id) === Number(selected?.source_id) ? 'selected' : ''}>${escapeHtml(item.label)}</option>`).join('')}</select><select data-field="remote-command" aria-label="Tasto telecomando"><option value="">Scegli tasto</option>${commands.map(([key,label]) => `<option value="${escapeHtml(key)}" ${key === command ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select>`
}
const valuesFor = deviceId => {
  const device = devices.find(item => item.id === deviceId)
  const byKind = {light:['on','off'], light_scenario: [...(device?.capabilities?.onoff ? ['on','off'] : []),'command_on','command_off','running','idle'], switch:['on','off'], binary_sensor:['on','off'], cover:['open','closed','opening','closing'], media_player:['playing','paused','idle','off','standby','buffering','unavailable'], lock:['locked','unlocked'], climate:['heat','cool','auto','off'], alarm_zone:['closed','active','tamper','masked','bypassed'], alarm_partition:['disarmed','armed','alarm','tamper']}
  return [...new Set([...(byKind[device?.kind] || []), String(device?.state ?? '').toLowerCase()].filter(Boolean))]
}
const stateLabels = {closed:'Chiuso', active:'Attivo / rilevato', running:'Avvio scenario', command_on:'Accendi scenario (comando)', command_off:'Spegni scenario (comando)', tamper:'Sabotaggio', masked:'Mascherato', bypassed:'Escluso', disarmed:'Disinserito', armed:'Inserito', alarm:'Allarme'}
const stateSelect = (deviceId, selected) => {
  const values = valuesFor(deviceId)
  if (!values.length || !['light','light_scenario','switch','binary_sensor','cover','media_player','lock','climate','alarm_zone','alarm_partition'].includes(devices.find(item => item.id === deviceId)?.kind)) {
    return `<input data-field="value" value="${escapeHtml(selected || '')}" placeholder="${values.length ? `Stato attuale: ${escapeHtml(values[0])}` : 'Stato del dispositivo'}" aria-label="Stato del dispositivo">`
  }
  if (selected && !values.includes(selected)) values.push(selected)
  const scenario = devices.find(item => item.id === deviceId)?.kind === 'light_scenario'
  return `<select data-field="value" aria-label="Stato possibile"><option value="">Scegli stato</option>${values.map(value => `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(scenario && ['on','off'].includes(value) ? `Stato ${value.toUpperCase()} (dispositivi conformi)` : stateLabels[value] ? `${stateLabels[value]} (${value})` : value)}</option>`).join('')}</select>`
}
function collect() {
  if (!draft) return
  draft.name = $('[data-routine-name]').value.trim()
  draft.triggers = [...$('[data-routine-triggers]').children].map(row => {
    const type = row.querySelector('[data-field="type"]').value
    return type === 'time' ? {type, at: row.querySelector('[data-field="at"]')?.value || ''}
      : type === 'doorbird' ? {type, event: row.querySelector('[data-field="event"]')?.value || ''}
      : type === 'sun' ? {type, event: row.querySelector('[data-field="sun-event"]')?.value || 'sunrise', offset_minutes: Number(row.querySelector('[data-field="sun-offset"]')?.value ?? 0)}
      : type === 'remote' ? {type, device_id:row.querySelector('[data-field="device"]')?.value || '', source_id:Number(row.querySelector('[data-field="remote-source"]')?.value || 0), command:row.querySelector('[data-field="remote-command"]')?.value || ''}
      : {type: 'state', device_id: row.querySelector('[data-field="device"]')?.value || '', to: row.querySelector('[data-field="value"]')?.value || ''}
  })
  draft.conditions = [...$('[data-routine-conditions]').children].map(row => row.querySelector('[data-field="condition-type"]')?.value === 'sun'
    ? {type:'sun', event:row.querySelector('[data-field="sun-event"]')?.value || 'sunset', offset_minutes:Number(row.querySelector('[data-field="sun-offset"]')?.value ?? 0), relation:row.querySelector('[data-field="sun-relation"]')?.value || 'after'}
    : {device_id: row.querySelector('[data-field="device"]')?.value || '', operator: row.querySelector('[data-field="operator"]')?.value || 'is', value: row.querySelector('[data-field="value"]')?.value || ''})
  draft.steps = [...$('[data-routine-steps]').children].map(row => {
    const type = row.dataset.type
    if (type === 'wait') return {type, seconds: Number(row.querySelector('[data-field="seconds"]').value)}
    if (type === 'check') return {type, device_id: row.querySelector('[data-field="device"]').value, operator: row.querySelector('[data-field="operator"]').value, value: row.querySelector('[data-field="value"]').value}
    const action = row.querySelector('[data-field="action"]').value
    const value = row.querySelector('[data-field="action-value"]')?.value
    return {type, device_id: row.querySelector('[data-field="device"]').value, action, value: action === 'remote_command' ? {source_id:Number(row.querySelector('[data-field="remote-source"]')?.value || 0),command:row.querySelector('[data-field="remote-command"]')?.value || ''} : value === undefined || value === '' ? null : ['tts','select_source'].includes(action) ? value : Number(value)}
  })
}
function renderList() {
  $('[data-routine-list]').innerHTML = routines.map(item => `<div class="routine-list-row"><button type="button" class="routine-list-item${current?.id === item.id ? ' selected' : ''}" data-routine-open="${escapeHtml(item.id)}"><b>${escapeHtml(item.name)}</b><small>${item.enabled ? 'ATTIVA' : 'DISATTIVATA'} · versione ${item.revision} · creata da ${escapeHtml(item.owner || 'utente')}</small></button><button type="button" class="routine-duplicate" data-routine-duplicate="${escapeHtml(item.id)}" aria-label="Duplica ${escapeHtml(item.name)}" title="Duplica (copia disattivata)">⧉</button><label class="routine-enable" title="${item.enabled ? 'Sospendi' : 'Attiva'} routine"><input type="checkbox" data-routine-enabled="${escapeHtml(item.id)}" ${item.enabled ? 'checked' : ''} aria-label="${item.enabled ? 'Sospendi' : 'Attiva'} ${escapeHtml(item.name)}"><span></span></label></div>`).join('') || '<p>Nessuna routine creata.</p>'
}
function renderEditor() {
  $('.routine-editor').hidden = !draft
  if (!draft) return
  $('[data-routine-name]').value = draft.name || ''
  $('[data-routine-triggers]').innerHTML = draft.triggers.map((item, index) => `<div class="routine-block" data-index="${index}"><select data-field="type"><option value="state" ${item.type === 'state' ? 'selected' : ''}>Quando cambia un dispositivo</option><option value="time" ${item.type === 'time' ? 'selected' : ''}>A un orario</option><option value="sun" ${item.type === 'sun' ? 'selected' : ''}>Alba / Tramonto</option><option value="remote" ${item.type === 'remote' ? 'selected' : ''}>Tasto telecomando e-Face</option><option value="doorbird" ${item.type === 'doorbird' ? 'selected' : ''}>Evento DoorBird</option></select>${item.type === 'time' ? `<input data-field="at" type="time" value="${escapeHtml(item.at || '')}">` : item.type === 'doorbird' ? `<select data-field="event"><option value="doorbell" ${item.event === 'doorbell' ? 'selected' : ''}>Chiamata</option><option value="motionsensor" ${item.event === 'motionsensor' ? 'selected' : ''}>Movimento</option></select>` : item.type === 'sun' ? solarFields(item) : item.type === 'remote' ? `${deviceField(item.device_id,'media')}${remoteFields(item.device_id,item.source_id,item.command)}` : `${deviceField(item.device_id)}${stateSelect(item.device_id, item.to)}`}<button type="button" data-routine-remove="trigger" aria-label="Rimuovi">×</button></div>`).join('')
  $('[data-routine-conditions]').innerHTML = draft.conditions.map((item, index) => conditionRow(item, index, 'condition')).join('')
  $('[data-routine-steps]').innerHTML = draft.steps.map((item, index) => {
    if (item.type === 'wait') return `<div class="routine-block" data-index="${index}" data-type="wait"><b>Timer</b><label>Secondi<input data-field="seconds" type="number" min="1" max="3600" value="${Number(item.seconds) || 60}"></label>${stepButtons(index)}</div>`
    if (item.type === 'check') return conditionRow(item, index, 'check')
    const device = devices.find(entry => entry.id === item.device_id)
    const choices = actions[device?.kind] || []
    const capabilityFor = device?.kind === 'light_scenario' ? {on:'onoff',off:'onoff',run:'run',stop:'run'} : {media_play:'play',media_pause:'pause',media_stop:'stop',media_next:'next',media_previous:'previous',turn_off:'turn_off',set_volume:'set_volume',volume_mute:'mute',volume_unmute:'mute'}
    const actionChoices = choices.filter(([key]) => key === 'tts' ? device?.tts_enabled : key.startsWith('dnd_') ? device?.dnd_available : key === 'remote_command' ? device?.source_options?.some(source => source.experience === 'watch' && source.remote_actions?.length) : key === 'select_source' ? device?.capabilities?.select_source && (device?.source_list?.length || device?.source_options?.length) : !capabilityFor[key] || device?.capabilities?.[capabilityFor[key]])
    const sourceChoices = device?.provider === 'control4' ? (device.source_options || []).map(source => [source.key,source.label]) : (device?.source_list || []).map(source => [source,source])
    const value = item.action === 'tts' ? `<label class="routine-tts">Testo da pronunciare<textarea data-field="action-value" maxlength="500" rows="3">${escapeHtml(item.value || '')}</textarea></label>` : item.action === 'remote_command' ? remoteFields(item.device_id,item.value?.source_id,item.value?.command,false) : item.action === 'select_source' ? `<label class="routine-tts">Sorgente<select data-field="action-value"><option value="">Scegli sorgente</option>${sourceChoices.map(([key,label]) => `<option value="${escapeHtml(key)}" ${key === item.value || label === item.value ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select></label>` : ['brightness', 'set_volume', 'set_target'].includes(item.action) ? `<label>Valore<input data-field="action-value" type="number" min="${item.action === 'set_target' ? 5 : 0}" max="${item.action === 'set_target' ? 35 : 100}" value="${item.value ?? ''}"></label>` : ''
    return `<div class="routine-block" data-index="${index}" data-type="action"><b>Azione</b>${deviceField(item.device_id, 'safe')}<select data-field="action"><option value="">Comando...</option>${actionChoices.map(([key, label]) => `<option value="${key}" ${key === item.action ? 'selected' : ''}>${label}</option>`).join('')}</select>${value}${stepButtons(index)}</div>`
  }).join('')
  $('[data-routine-delete]').hidden = !current
  $('[data-routine-review]').textContent = 'Premi «Controlla» per leggere gli effetti della routine.'
  renderList()
}
function conditionRow(item, index, type) {
  if (type === 'condition') return `<div class="routine-block" data-index="${index}"><select data-field="condition-type"><option value="state" ${item.type === 'sun' ? '' : 'selected'}>Stato dispositivo</option><option value="sun" ${item.type === 'sun' ? 'selected' : ''}>Alba / Tramonto</option></select>${item.type === 'sun' ? solarFields(item, true) : `${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator === 'is' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id, item.value)}`}<button type="button" data-routine-remove="condition" aria-label="Rimuovi">×</button></div>`
  return `<div class="routine-block" data-index="${index}" ${type === 'check' ? 'data-type="check"' : ''}><b>${type === 'check' ? 'Verifica e interrompi se falsa' : 'Condizione iniziale'}</b>${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator === 'is' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id, item.value)}${type === 'check' ? stepButtons(index) : '<button type="button" data-routine-remove="condition" aria-label="Rimuovi">×</button>'}</div>`
}
function solarFields(item, condition = false) { return `<select data-field="sun-event" aria-label="Evento solare"><option value="sunrise" ${item.event === 'sunrise' ? 'selected' : ''}>Alba</option><option value="sunset" ${item.event === 'sunset' ? 'selected' : ''}>Tramonto</option></select><label class="routine-sun-offset">Minuti prima (−) / dopo (+)<input data-field="sun-offset" type="number" min="-180" max="180" step="1" value="${Number(item.offset_minutes) || 0}"></label>${condition ? `<select data-field="sun-relation" aria-label="Confronto con alba o tramonto"><option value="after" ${item.relation === 'after' ? 'selected' : ''}>Dopo questo orario</option><option value="before" ${item.relation === 'before' ? 'selected' : ''}>Prima di questo orario</option></select>` : ''}` }
function stepButtons() { return '<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per cambiare ordine; usa freccia su e giù da tastiera" title="Trascina per riordinare">☰</button><button type="button" data-routine-remove="step" aria-label="Rimuovi">×</button></div>' }
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
  sessionStorage.setItem('eface-tools-panel', 'routine')
  document.body.style.overflow = 'hidden'
  load().then(() => {
    const id = sessionStorage.getItem('eface-routine-id')
    if (id) $('[data-routine-list]').querySelectorAll('[data-routine-open]').forEach(button => { if (button.dataset.routineOpen === id) button.click() })
  }).catch(error => $('[data-routine-list]').textContent = error.message)
}
function close() { panel.hidden = true; sessionStorage.removeItem('eface-tools-panel'); document.body.style.overflow = '' }
userCard.addEventListener('click', open)
$('[data-routine-back]').addEventListener('click', close)
$('[data-routine-new]').addEventListener('click', () => { sessionStorage.removeItem('eface-routine-id'); current = null; draft = {name: '', triggers: [{type: 'state', device_id: '', to: ''}], conditions: [], steps: [{type: 'action', device_id: '', action: ''}]}; renderEditor() })
$('[data-routine-generate]').addEventListener('click', async event => {
  const button = event.currentTarget
  const status = $('[data-routine-generate-status]')
  button.disabled = true
  status.textContent = 'Verifico la descrizione con i dispositivi dell’impianto…'
  try {
    const result = await request('api/user/routines/from-text', jsonOptions('POST', {text:$('[data-routine-description]').value}))
    sessionStorage.removeItem('eface-routine-id')
    current = null
    draft = result.spec
    renderEditor()
    showReview(result.review)
    status.textContent = 'Bozza pronta e disattivata. Controlla ogni campo, poi salva o attiva.'
    $('.routine-editor').scrollIntoView({behavior:'smooth',block:'start'})
  } catch(error) { status.textContent = error.message }
  finally { button.disabled = false }
})
$('[data-routine-list]').addEventListener('click', event => {
  const duplicate = event.target.closest('[data-routine-duplicate]')
  if (duplicate) {
    const source = routines.find(item => item.id === duplicate.dataset.routineDuplicate)
    if (!source) return
    duplicate.disabled = true
    const spec = structuredClone(source.spec)
    spec.name = `${source.name.slice(0, 72)} (copia)`
    request('api/user/routines', jsonOptions('POST', {spec, enabled:false})).then(async result => {
      current = result.item
      draft = structuredClone(current.spec)
      await load()
      renderEditor()
      $('[data-routine-review]').textContent = 'Copia creata e disattivata. Modificala, controllala e attivala quando vuoi.'
    }).catch(error => window.alert(error.message)).finally(() => {duplicate.disabled = false})
    return
  }
  const button = event.target.closest('[data-routine-open]')
  if (!button) return
  current = routines.find(item => item.id === button.dataset.routineOpen)
  sessionStorage.setItem('eface-routine-id', current.id)
  draft = structuredClone(current.spec)
  renderEditor()
})
$('[data-routine-list]').addEventListener('change', async event => {
  const toggle = event.target.closest('[data-routine-enabled]')
  if (!toggle) return
  const item = routines.find(entry => entry.id === toggle.dataset.routineEnabled)
  if (!item) return
  toggle.disabled = true
  try {
    let confirm_warnings = false
    if (toggle.checked) {
      const review = await request('api/user/routines/validate', jsonOptions('POST', {spec:item.spec, id:item.id}))
      if (review.errors.length) throw new Error(review.errors.join(' · '))
      if (review.warnings.length) {
        confirm_warnings = window.confirm(`Verifica prima di attivare:\n\n${review.warnings.join('\n')}\n\nConfermi?`)
        if (!confirm_warnings) { toggle.checked = false; return }
      }
    }
    const result = await request(`api/user/routines/${encodeURIComponent(item.id)}/enabled`, jsonOptions('POST', {enabled:toggle.checked, confirm_warnings}))
    routines = routines.map(entry => entry.id === item.id ? result.item : entry)
    if (current?.id === item.id) current = result.item
    renderList()
  } catch (error) {
    toggle.checked = item.enabled
    window.alert(error.message)
  } finally { toggle.disabled = false }
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
})
let draggedStep = null
panel.addEventListener('pointerdown', event => {
  const handle = event.target.closest('[data-routine-drag]')
  if (!handle || event.button !== 0) return
  const block = handle.closest('[data-routine-steps] > .routine-block')
  if (!block) return
  collect()
  draggedStep = {pointerId: event.pointerId, handle, block}
  handle.setPointerCapture(event.pointerId)
  block.classList.add('dragging')
  event.preventDefault()
})
panel.addEventListener('pointermove', event => {
  if (!draggedStep || event.pointerId !== draggedStep.pointerId) return
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-routine-steps] > .routine-block')
  if (!target || target === draggedStep.block) return
  const middle = target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2
  $('[data-routine-steps]').insertBefore(draggedStep.block, event.clientY < middle ? target : target.nextSibling)
})
const finishDrag = event => {
  if (!draggedStep || event.pointerId !== draggedStep.pointerId) return
  const {block} = draggedStep
  draggedStep = null
  block.classList.remove('dragging')
  if (event.type !== 'pointercancel') draft.steps = [...$('[data-routine-steps]').children].map(row => draft.steps[Number(row.dataset.index)])
  renderEditor()
}
panel.addEventListener('pointerup', finishDrag)
panel.addEventListener('pointercancel', finishDrag)
panel.addEventListener('keydown', event => {
  if (!event.target.matches('[data-routine-drag]') || !['ArrowUp', 'ArrowDown'].includes(event.key)) return
  event.preventDefault()
  collect()
  const index = Number(event.target.closest('[data-index]').dataset.index)
  const next = index + (event.key === 'ArrowUp' ? -1 : 1)
  if (next < 0 || next >= draft.steps.length) return
  ;[draft.steps[index], draft.steps[next]] = [draft.steps[next], draft.steps[index]]
  renderEditor()
  $('[data-routine-steps]').querySelectorAll('[data-routine-drag]')[next]?.focus()
})
panel.addEventListener('input', event => {
  if (!event.target.matches('[data-device-search]')) return
  const select = event.target.parentElement.querySelector('[data-field="device"]')
  const allowed = select.dataset.deviceScope === 'safe' ? safeDevices() : select.dataset.deviceScope === 'media' ? devices.filter(item => item.kind === 'media_player') : devices
  select.innerHTML = deviceOptions(select.value, allowed, event.target.value)
})
panel.addEventListener('change', event => {
  const field = event.target
  if (!field.matches('[data-field="device"],[data-field="type"],[data-field="condition-type"],[data-field="action"],[data-field="remote-source"]')) return
  collect()
  const row = field.closest('[data-index]')
  const index = Number(row?.dataset.index)
  if (row?.parentElement.matches('[data-routine-triggers]')) {
    if (field.dataset.field === 'type') draft.triggers[index] = field.value === 'time' ? {type:'time',at:'18:00'} : field.value === 'sun' ? {type:'sun',event:'sunrise',offset_minutes:0} : field.value === 'remote' ? {type:'remote',device_id:'',source_id:0,command:''} : field.value === 'doorbird' ? {type:'doorbird',event:'doorbell'} : {type:'state',device_id:'',to:''}
    else if (field.dataset.field === 'device' && draft.triggers[index].type === 'remote') { draft.triggers[index].source_id = 0; draft.triggers[index].command = '' }
    else if (field.dataset.field === 'device') draft.triggers[index].to = ''
    else if (field.dataset.field === 'remote-source') draft.triggers[index].command = ''
  } else if (row?.parentElement.matches('[data-routine-conditions]')) {
    if (field.dataset.field === 'condition-type') draft.conditions[index] = field.value === 'sun' ? {type:'sun',event:'sunset',offset_minutes:0,relation:'after'} : {device_id:'',operator:'is',value:''}
    else draft.conditions[index].value = ''
  }
  else if (row?.dataset.type === 'check') draft.steps[index].value = ''
  else if (row?.dataset.type === 'action') {
    if (field.dataset.field === 'device') { draft.steps[index].action = ''; draft.steps[index].value = null }
    if (field.dataset.field === 'action') draft.steps[index].value = null
    if (field.dataset.field === 'remote-source') draft.steps[index].value.command = ''
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
adminCard.addEventListener('click', () => { logPanel.hidden = false; sessionStorage.setItem('eface-tools-panel', 'routine-log'); document.body.style.overflow = 'hidden'; loadLogs(); loadRoutineNames() })
logPanel.querySelector('[data-routine-log-back]').addEventListener('click', () => { logPanel.hidden = true; sessionStorage.removeItem('eface-tools-panel'); document.body.style.overflow = '' })
logPanel.querySelector('[data-routine-filter]').addEventListener('click', () => loadLogs())
setTimeout(() => {
  const saved = sessionStorage.getItem('eface-tools-panel')
  if (saved === 'routine') userCard.click()
  if (saved === 'routine-log') {
    document.querySelector('[data-tools-view="admin"]:not([hidden])')?.click()
    adminCard.click()
  }
}, 900)
setInterval(() => { if (!logPanel.hidden && !document.hidden) loadLogs(true) }, 3000)
let logsLoading = false
let lastLogSignature = ''
async function loadRoutineNames() {
  try {
    const data = await request('api/user/routines')
    logPanel.querySelector('#routine-log-names').innerHTML = [...new Set((data.items || []).map(item => item.name).filter(Boolean))].sort((a,b) => a.localeCompare(b, 'it')).map(name => `<option value="${escapeHtml(name)}"></option>`).join('')
  } catch { /* Il filtro per nome funziona anche senza suggerimenti. */ }
}
async function loadLogs(background = false) {
  if (logsLoading) return
  logsLoading = true
  const target = logPanel.querySelector('[data-routine-log-list]')
  const scrollTop = logPanel.scrollTop
  const opened = new Set([...target.querySelectorAll('.routine-log-run[open] p')].map(item => item.textContent.match(/esecuzione\s+([\w-]+)/)?.[1]).filter(Boolean))
  if (!background) target.textContent = 'Caricamento…'
  try {
    const params = new URLSearchParams({device_id:logPanel.querySelector('[data-routine-filter-device]').value.trim(), routine_name:logPanel.querySelector('[data-routine-filter-routine]').value.trim(), limit:'100'})
    const data = await request(`api/admin/routines/log?${params}`)
    const signature = JSON.stringify({filter:params.toString(),items:data.items || []})
    if (background && signature === lastLogSignature) return
    lastLogSignature = signature
    target.innerHTML = (data.items || []).map(run => `<details class="routine-log-run"><summary><b>${escapeHtml(run.name)}</b><span>${escapeHtml(new Date(run.started_at).toLocaleString('it-IT'))} · ${escapeHtml(run.status)}</span><small>${escapeHtml(run.trigger_detail)}</small></summary><p>Versione ${run.revision} · modificata da ${escapeHtml(run.modified_by || 'sconosciuto')} · esecuzione ${escapeHtml(run.id)}</p>${run.events.map(entry => `<div class="routine-log-event"><time>${escapeHtml(new Date(entry.at).toLocaleTimeString('it-IT'))}</time><b>${escapeHtml(entry.stage)}</b><span>${escapeHtml([entry.device_name, entry.detail].filter(Boolean).join(' · '))}</span><small>${escapeHtml([entry.action, entry.stage === 'condition' ? {pass:'Condizione soddisfatta',skip:'Condizione NON soddisfatta'}[entry.result] || entry.result : entry.result, entry.stage !== 'condition' && entry.before_state && `prima: ${entry.before_state}`, entry.after_state && `dopo: ${entry.after_state}`].filter(Boolean).join(' · '))}</small></div>`).join('')}</details>`).join('') || '<p>Nessuna esecuzione nel periodo conservato.</p>'
    target.querySelectorAll('.routine-log-run').forEach(item => { if (opened.has(item.querySelector('p')?.textContent.match(/esecuzione\s+([\w-]+)/)?.[1])) item.open = true })
    if (background) logPanel.scrollTop = scrollTop
  } catch(error) { if (!background) target.textContent = error.message }
  finally { logsLoading = false }
}
