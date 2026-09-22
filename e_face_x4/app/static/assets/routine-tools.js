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
const professionalCard = document.createElement('button')
professionalCard.type = 'button'
professionalCard.className = 'tool-card'
professionalCard.innerHTML = '<span>{ }</span><div><b>Routine Professional</b><small>Modifica JSON e verifica prima di salvare</small></div><i>›</i>'
document.querySelector('#admin-tools .tools-grid').append(professionalCard)

const panel = document.createElement('section')
panel.className = 'media-config routine-panel'
panel.hidden = true
panel.innerHTML = `<header><button type="button" data-routine-back aria-label="Torna a Strumenti">‹</button><div><small>STRUMENTI UTENTE</small><h2>Routine</h2></div></header>
  <p>Crea automazioni comprensibili. Prima di attivarle, e-Face verifica dispositivi, comandi e possibili interazioni.</p>
  <section class="routine-wizard" aria-label="Creazione guidata routine"><div class="routine-wizard-steps"><b>1 · Descrivi</b><b>2 · Verifica la bozza</b><b>3 · Salva o attiva</b></div><label>Scrivi cosa vuoi che accada<textarea data-routine-description rows="3" maxlength="2000" placeholder="Quando Luce Ufficio Alex si accende, accendi Luce Corridoio poi aspetta 60 secondi poi spegni Luce Corridoio"></textarea></label><p>Usa il nome completo dei dispositivi. La bozza non viene salvata né attivata automaticamente; puoi sempre correggerla nei campi qui sotto.</p><button type="button" class="routine-primary" data-routine-generate>CREA BOZZA DA DESCRIZIONE</button><p data-routine-generate-status role="status" aria-live="polite"></p></section>
  <div class="routine-layout"><aside><button type="button" class="routine-primary" data-routine-new>+ NUOVA ROUTINE</button><div data-routine-list></div></aside>
  <div class="routine-editor" hidden><label>Nome routine<input data-routine-name maxlength="80" placeholder="Es. Luci ingresso la sera"></label><label>Modalità di esecuzione<select data-routine-mode><option value="single">Singola · ignora nuovi eventi mentre è in corso</option><option value="restart">Riavvia · nuovo evento fa ripartire il timer</option><option value="queued">In coda · massimo 5 attese</option><option value="parallel">Parallela · massimo 3 esecuzioni</option></select></label>
  <h3>Quando</h3><p>Una qualsiasi attivazione avvia la routine. Alba e tramonto usano la posizione di e-Control; minuti negativi anticipano, positivi ritardano.</p><div data-routine-triggers></div><button type="button" data-routine-add="trigger">+ Aggiungi attivazione</button>
  <h3>E se <small>(opzionale)</small></h3><p>Tutte queste condizioni devono essere vere all'inizio. Per una fascia oraria, scegli «Intervallo da… a…»: puoi combinare ora fissa, alba e tramonto, anche oltre la mezzanotte.</p><div data-routine-conditions></div><button type="button" data-routine-add="condition">+ Aggiungi condizione</button>
  <h3>Allora</h3><p>I blocchi sono eseguiti nell'ordine mostrato. Dopo un timer puoi ricontrollare uno stato.</p><div data-routine-steps></div>
  <div class="routine-add"><button type="button" data-routine-add="action">+ Azione</button><button type="button" data-routine-add="wait">+ Timer</button><button type="button" data-routine-add="check">+ Verifica</button><button type="button" data-routine-add="choose">+ Scegli ramo</button><button type="button" data-routine-add="protected_cover">+ Cover con bypass protetto</button></div>
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
const professionalPanel = document.createElement('section')
professionalPanel.className = 'media-config routine-panel'
professionalPanel.hidden = true
professionalPanel.innerHTML = `<header><button type="button" data-professional-back aria-label="Torna ad Amministrazione">‹</button><div><small>AMMINISTRAZIONE</small><h2>Routine Professional</h2></div></header>
  <p>Il campo <code>spec</code> delle routine è JSON salvato in SQLite, non un file YAML. Qui modifichi lo stesso schema dell'editor visuale. Nessun comando viene eseguito durante controllo o salvataggio.</p>
  <details class="routine-professional-help"><summary>Schema dei blocchi avanzati</summary><p><code>enabled</code> si imposta con l'interruttore sotto il JSON. Uno qualsiasi dei trigger avvia la routine. Le condizioni supportano <code>and</code>, <code>or</code> e <code>not</code>.</p><pre>"conditions": {"and": [
  {"device_id":"sensor.id","operator":"is","value":"on"},
  {"not":{"device_id":"light.id","operator":"is","value":"on"}}
]},
"steps": [
  {"type":"action","device_id":"light.id","action":"on"},
  {"type":"delay","seconds":10},
  {"type":"wait_until","condition":{"device_id":"sensor.id","value":"off"},"timeout_seconds":300},
  {"type":"if","condition":{"device_id":"light.id","value":"on"},"then":[{"type":"action","device_id":"light.id","action":"off"}],"else":[]},
  {"type":"choose","choices":[{"condition":{"device_id":"sensor.id","value":"on"},"steps":[{"type":"stop","reason":"Occupato"}]}],"default":[]},
  {"type":"repeat","count":2,"steps":[{"type":"action","device_id":"light.id","action":"on"}]},
  {"type":"parallel","branches":[[{"type":"action","device_id":"light.a","action":"on"}],[{"type":"action","device_id":"light.b","action":"on"}]]},
  {"type":"variable","name":"presenza","from_device_id":"sensor.id"},
  {"type":"stop","reason":"Fine"}
]</pre><p>Per cover a percentuale usa <code>{"type":"action","device_id":"cover.buspro_cover_finestra_cucina","action":"set_position","value":8}</code>. Per cover senza percentuale usa <code>open</code>, <code>close</code> o <code>stop</code>.</p><p>Il bypass allarme è consentito solo in <code>protected_cover</code> (admin, modalità single). Esempio: <code>{"type":"protected_cover","bypass_switches":["switch.e_safe_zone_20_bypass_ctrl"],"enable_delay_seconds":3,"move_seconds":40,"steps":[{"type":"action","device_id":"cover.buspro_cover_finestra_cucina","action":"set_position","value":8}]}</code>. Gli switch devono essere spenti prima; il ripristino viene ritentato se non è confermato. Non sostituisce la verifica fisica dell'allarme.</p><p>Sostituisci gli ID con quelli del catalogo. Una variabile può anche avere <code>value</code> fisso; per leggerla usa <code>{"type":"variable","name":"presenza","operator":"is","value":"on"}</code> come condizione.</p></details>
  <div class="routine-professional-actions"><label>Routine<select data-professional-select aria-label="Scegli routine"><option value="">Nuova routine</option></select></label><button type="button" data-professional-new>NUOVA</button><button type="button" data-professional-copy-catalog>COPIA CATALOGO DISPOSITIVI</button></div>
  <details class="routine-professional-help"><summary>Catalogo dispositivi <span data-professional-catalog-count></span></summary><input data-professional-catalog-search type="search" placeholder="Cerca nome, stanza, tipo o ID" aria-label="Cerca nel catalogo dispositivi"><div data-professional-catalog-list class="routine-catalog-list"></div></details>
  <details class="routine-professional-help"><summary>Filtri catalogo routine</summary><p>Queste impostazioni sono globali e persistenti. Non rimuovono il controllo dei tipi di comando realmente supportati.</p><label><input type="checkbox" data-catalog-filter="block_sensitive_names"> Blocca nelle azioni i nomi di accesso (porta, cancello, garage). Le cover e le serrature restano disponibili.</label><label><input type="checkbox" data-catalog-filter="hide_readonly_actions"> Nascondi nelle azioni i dispositivi senza comandi supportati. Restano sempre disponibili come trigger e condizioni.</label><p data-catalog-filter-status></p></details>
  <label class="routine-professional-code">Definizione JSON<textarea data-professional-json spellcheck="false" autocapitalize="off" autocomplete="off" rows="20" aria-label="JSON della routine"></textarea></label>
  <label class="routine-professional-enabled"><input type="checkbox" data-professional-enabled> Mantieni o rendi attiva dopo il salvataggio</label>
  <div class="routine-professional-actions"><button type="button" data-professional-check>CONTROLLA JSON</button><button type="button" data-professional-save>SALVA JSON</button><button type="button" data-professional-open-visual disabled>APRI NELL'EDITOR VISUALE</button></div>
  <div class="routine-review" data-professional-review role="status" aria-live="polite">Seleziona una routine o incolla un JSON. Il controllo usa i dispositivi attuali dell'impianto.</div>`
root.append(professionalPanel)
const $ = selector => panel.querySelector(selector)
let routines = []
let devices = []
let catalogFilters = {block_sensitive_names:true, hide_readonly_actions:true}
let current = null
let draft = null
const actions = {
  light_scenario: [['on', 'Attiva'], ['off', 'Disattiva'], ['run', 'Esegui'], ['stop', 'Ferma']],
  light: [['on', 'Accendi'], ['off', 'Spegni'], ['brightness', 'Luminosità %']],
  switch: [['on', 'Accendi'], ['off', 'Spegni']],
  cover: [['open', 'Apri'], ['close', 'Chiudi'], ['stop', 'Ferma'], ['set_position', 'Posizione %']],
  lock: [['lock', 'Blocca'], ['unlock', 'Sblocca']],
  media_player: [['media_play', 'Riproduci'], ['media_pause', 'Pausa'], ['media_stop', 'Stop'], ['media_next', 'Successivo'], ['media_previous', 'Precedente'], ['turn_off', 'Spegni stanza'], ['set_volume', 'Volume %'], ['volume_mute', 'Mute'], ['volume_unmute', 'Riattiva audio'], ['select_source', 'Seleziona sorgente'], ['remote_command', 'Tasto telecomando sorgente'], ['dnd_on', 'Attiva Non disturbare'], ['dnd_off', 'Disattiva Non disturbare'], ['tts', 'Messaggio vocale (TTS)']],
  climate: [['set_target', 'Temperatura °C']]
}
const sensitive = /portone|cancello|garage|serratura|allarme|alarm|gate|door|lock/i
const safeDevices = () => devices.filter(item => { const identity = [item.id, item.entity_id, item.name, item.room].join(' '); return (!catalogFilters.hide_readonly_actions || actions[item.kind]) && (item.kind === 'lock' || item.kind === 'cover' || !catalogFilters.block_sensitive_names || (!sensitive.test(identity) && !/porta/i.test(identity))) })
const deviceOptions = (selected, allowed = devices, query = '') => {
  const words = query.trim().toLocaleLowerCase('it-IT').split(/\s+/).filter(Boolean)
  const matches = allowed.filter(item => words.every(word => [item.room, item.name, item.id, item.entity_id].some(part => String(part || '').toLocaleLowerCase('it-IT').includes(word))))
  const shown = matches
  const selectedItem = allowed.find(item => item.id === selected)
  if (selectedItem && !shown.some(item => item.id === selected)) shown.unshift(selectedItem)
  return `<option value="">${matches.length ? `Scegli dispositivo (${matches.length})` : 'Nessun dispositivo trovato'}</option>${shown.map(item => `<option value="${escapeHtml(item.id)}" ${item.id === selected ? 'selected' : ''}>${escapeHtml([item.room, item.name, item.id].filter(Boolean).join(' · '))}</option>`).join('')}`
}
const deviceField = (selected, scope = 'all') => `<div class="routine-device-field"><input data-device-search type="search" autocomplete="off" placeholder="Cerca stanza o dispositivo, es. ufficio" aria-label="Cerca dispositivo"><select data-field="device" data-device-scope="${scope}">${deviceOptions(selected, scope === 'safe' ? safeDevices() : scope === 'media' ? devices.filter(item => item.kind === 'media_player') : scope === 'cover_light' ? devices.filter(item => ['cover','light'].includes(item.kind)) : devices)}</select></div>`
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
const visualCondition = condition => Boolean(condition && !condition.and && !condition.or && !condition.not && [undefined, 'state', 'sun', 'time_window'].includes(condition.type))
const visualSteps = (steps, depth = 0) => Array.isArray(steps) && depth <= 5 && steps.every(step => {
  if (['action', 'wait', 'delay', 'check'].includes(step?.type)) return true
  if (step?.type === 'protected_cover') return Array.isArray(step.bypass_switches) && Array.isArray(step.steps) && step.steps.every(child => child?.type === 'action')
  return depth === 0 && step?.type === 'choose' && Array.isArray(step.choices) && step.choices.every(choice => visualCondition(choice.condition) && visualSteps(choice.steps, depth + 1)) && visualSteps(step.default || [], depth + 1)
})
const canOpenVisual = spec => Boolean(spec && Array.isArray(spec.conditions) && spec.conditions.every(visualCondition) && visualSteps(spec.steps))
const newChoose = () => ({type:'choose', choices:[{condition:{type:'time_window',start:{kind:'sunrise',offset_minutes:0},end:{kind:'sunset',offset_minutes:0}},steps:[{type:'action',device_id:'',action:''}]}],default:[]})
const newCondition = type => type === 'sun' ? {type,event:'sunset',offset_minutes:0,relation:'after'} : type === 'time_window' ? {type,start:{kind:'sunrise',offset_minutes:0},end:{kind:'sunset',offset_minutes:0}} : {device_id:'',operator:'is',value:''}
function collectCondition(row) {
  const type = row.querySelector('[data-field="condition-type"]')?.value || 'state'
  if (type === 'sun') return {type, event:row.querySelector('[data-field="sun-event"]')?.value || 'sunset', offset_minutes:Number(row.querySelector('[data-field="sun-offset"]')?.value ?? 0), relation:row.querySelector('[data-field="sun-relation"]')?.value || 'after'}
  if (type === 'time_window') {
    const boundary = edge => {
      const kind = row.querySelector(`[data-field="window-${edge}-kind"]`)?.value || 'time'
      return kind === 'time' ? {kind,at:row.querySelector(`[data-field="window-${edge}-at"]`)?.value || ''} : {kind,offset_minutes:Number(row.querySelector(`[data-field="window-${edge}-offset"]`)?.value ?? 0)}
    }
    return {type,start:boundary('start'),end:boundary('end')}
  }
  return {device_id:row.querySelector('[data-field="device"]')?.value || '',operator:row.querySelector('[data-field="operator"]')?.value || 'is',value:row.querySelector('[data-field="value"]')?.value || ''}
}
function collectStepRow(row) {
  const type = row.dataset.type
  if (type === 'protected_cover') return {type,bypass_switches:[...row.querySelectorAll('[data-protected-bypass]:checked')].map(input => input.value),enable_delay_seconds:Number(row.querySelector('[data-field="enable-delay"]').value),move_seconds:Number(row.querySelector('[data-field="move-seconds"]').value),steps:[...row.querySelector(':scope > [data-protected-steps]').children].map(collectStepRow)}
  if (type === 'choose') {
    const branches = [...row.querySelectorAll(':scope > .routine-choose-branches > [data-choose-branch]')]
    const readSteps = branch => [...branch.querySelector('[data-choose-steps]').children].map(collectStepRow)
    return {type,choices:branches.filter(branch => branch.dataset.chooseBranch !== 'default').map(branch => ({condition:collectCondition(branch.querySelector('[data-choose-condition]')),steps:readSteps(branch)})),default:readSteps(branches.find(branch => branch.dataset.chooseBranch === 'default'))}
  }
  if (type === 'wait' || type === 'delay') return {type,seconds:Number(row.querySelector('[data-field="seconds"]').value)}
  if (type === 'check') return {type,device_id:row.querySelector('[data-field="device"]').value,operator:row.querySelector('[data-field="operator"]').value,value:row.querySelector('[data-field="value"]').value}
  const action = row.querySelector('[data-field="action"]').value
  const value = row.querySelector('[data-field="action-value"]')?.value
  return {type:'action',device_id:row.querySelector('[data-field="device"]').value,action,value:action === 'remote_command' ? {source_id:Number(row.querySelector('[data-field="remote-source"]')?.value || 0),command:row.querySelector('[data-field="remote-command"]')?.value || ''} : value === undefined || value === '' ? null : ['tts','select_source'].includes(action) ? value : Number(value)}
}
function collect() {
  if (!draft) return
  draft.name = $('[data-routine-name]').value.trim()
  draft.mode = $('[data-routine-mode]').value
  draft.triggers = [...$('[data-routine-triggers]').children].map(row => {
    const type = row.querySelector('[data-field="type"]').value
    return type === 'time' ? {type, at: row.querySelector('[data-field="at"]')?.value || ''}
      : type === 'doorbird' ? {type, event: row.querySelector('[data-field="event"]')?.value || ''}
      : type === 'sun' ? {type, event: row.querySelector('[data-field="sun-event"]')?.value || 'sunrise', offset_minutes: Number(row.querySelector('[data-field="sun-offset"]')?.value ?? 0)}
      : type === 'remote' ? {type, device_id:row.querySelector('[data-field="device"]')?.value || '', source_id:Number(row.querySelector('[data-field="remote-source"]')?.value || 0), command:row.querySelector('[data-field="remote-command"]')?.value || ''}
      : {type: 'state', device_id: row.querySelector('[data-field="device"]')?.value || '', to: row.querySelector('[data-field="value"]')?.value || ''}
  })
  draft.conditions = [...$('[data-routine-conditions]').children].map(collectCondition)
  draft.steps = [...$('[data-routine-steps]').children].map(collectStepRow)
}
function renderList() {
  $('[data-routine-list]').innerHTML = routines.map(item => `<div class="routine-list-row"><button type="button" class="routine-list-item${current?.id === item.id ? ' selected' : ''}" data-routine-open="${escapeHtml(item.id)}"><b>${escapeHtml(item.name)}</b><small>${item.enabled ? 'ATTIVA' : 'DISATTIVATA'} · versione ${item.revision} · creata da ${escapeHtml(item.owner || 'utente')}</small></button><button type="button" class="routine-duplicate" data-routine-duplicate="${escapeHtml(item.id)}" aria-label="Duplica ${escapeHtml(item.name)}" title="Duplica (copia disattivata)">⧉</button><label class="routine-enable" title="${item.enabled ? 'Sospendi' : 'Attiva'} routine"><input type="checkbox" data-routine-enabled="${escapeHtml(item.id)}" ${item.enabled ? 'checked' : ''} aria-label="${item.enabled ? 'Sospendi' : 'Attiva'} ${escapeHtml(item.name)}"><span></span></label></div>`).join('') || '<p>Nessuna routine creata.</p>'
}
function renderEditor() {
  $('.routine-editor').hidden = !draft
  if (!draft) return
  if (!canOpenVisual(draft)) {
    $('.routine-editor').hidden = true
    window.alert('Questa routine contiene blocchi avanzati. Modificala in Amministrazione → Routine Professional; l’editor lineare non può rappresentarli senza perdita di dati.')
    return
  }
  $('[data-routine-name]').value = draft.name || ''
  $('[data-routine-mode]').value = draft.mode || 'single'
  $('[data-routine-triggers]').innerHTML = draft.triggers.map((item, index) => `<div class="routine-block" data-index="${index}"><select data-field="type"><option value="state" ${item.type === 'state' ? 'selected' : ''}>Quando cambia un dispositivo</option><option value="time" ${item.type === 'time' ? 'selected' : ''}>A un orario</option><option value="sun" ${item.type === 'sun' ? 'selected' : ''}>Alba / Tramonto</option><option value="remote" ${item.type === 'remote' ? 'selected' : ''}>Tasto telecomando e-Face</option><option value="doorbird" ${item.type === 'doorbird' ? 'selected' : ''}>Evento DoorBird</option></select>${item.type === 'time' ? `<input data-field="at" type="time" value="${escapeHtml(item.at || '')}">` : item.type === 'doorbird' ? `<select data-field="event"><option value="doorbell" ${item.event === 'doorbell' ? 'selected' : ''}>Chiamata</option><option value="motionsensor" ${item.event === 'motionsensor' ? 'selected' : ''}>Movimento</option></select>` : item.type === 'sun' ? solarFields(item) : item.type === 'remote' ? `${deviceField(item.device_id,'media')}${remoteFields(item.device_id,item.source_id,item.command)}` : `${deviceField(item.device_id)}${stateSelect(item.device_id, item.to)}`}<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per riordinare l'attivazione" title="Trascina per riordinare">☰</button><button type="button" data-routine-duplicate-row="trigger" aria-label="Duplica attivazione" title="Duplica">⧉</button><button type="button" data-routine-remove="trigger" aria-label="Rimuovi">×</button></div></div>`).join('')
  $('[data-routine-conditions]').innerHTML = draft.conditions.map((item, index) => conditionRow(item, index, 'condition')).join('')
  $('[data-routine-steps]').innerHTML = draft.steps.map((item, index) => renderStepRow(item, index)).join('')
  if (document.querySelector('#tools-admin-nav')?.hidden) panel.querySelectorAll('[data-routine-add="protected_cover"],[data-choose-add-step="protected_cover"]').forEach(button => { button.hidden = true })
  $('[data-routine-delete]').hidden = !current
  $('[data-routine-review]').textContent = 'Premi «Controlla» per leggere gli effetti della routine.'
  renderList()
}
function conditionRow(item, index, type) {
  if (type === 'condition') return `<div class="routine-block" data-index="${index}"><select data-field="condition-type"><option value="state" ${!['sun','time_window'].includes(item.type) ? 'selected' : ''}>Stato dispositivo</option><option value="sun" ${item.type === 'sun' ? 'selected' : ''}>Alba / Tramonto</option><option value="time_window" ${item.type === 'time_window' ? 'selected' : ''}>Intervallo da… a…</option></select>${item.type === 'sun' ? solarFields(item, true) : item.type === 'time_window' ? windowFields(item) : `${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator === 'is' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id, item.value)}`}<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per riordinare la condizione" title="Trascina per riordinare">☰</button><button type="button" data-routine-duplicate-row="condition" aria-label="Duplica condizione" title="Duplica">⧉</button><button type="button" data-routine-remove="condition" aria-label="Rimuovi">×</button></div></div>`
  return `<div class="routine-block" data-index="${index}" ${type === 'check' ? 'data-type="check"' : ''}><b>${type === 'check' ? 'Verifica e interrompi se falsa' : 'Condizione iniziale'}</b>${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator === 'is' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id, item.value)}${type === 'check' ? stepButtons(index) : '<button type="button" data-routine-remove="condition" aria-label="Rimuovi">×</button>'}</div>`
}
function chooseConditionFields(item) {
  const kind = item.type || 'state'
  return `<select data-field="condition-type" aria-label="Tipo condizione del ramo"><option value="state" ${kind === 'state' ? 'selected' : ''}>Stato dispositivo</option><option value="sun" ${kind === 'sun' ? 'selected' : ''}>Alba / Tramonto</option><option value="time_window" ${kind === 'time_window' ? 'selected' : ''}>Intervallo da… a…</option></select>${kind === 'sun' ? solarFields(item, true) : kind === 'time_window' ? windowFields(item) : `${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator !== 'is_not' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id,item.value)}`}`
}
function renderChooseBranch(choice, index) {
  const isDefault = index === 'default'
  const steps = isDefault ? choice : choice.steps
  return `<section class="routine-choose-branch" data-choose-branch="${index}"><div class="routine-choose-title">${isDefault ? '' : '<button type="button" class="routine-choice-drag" data-routine-drag aria-label="Trascina per riordinare la scelta" title="Trascina per riordinare">☰</button>'}<b>${isDefault ? 'Altrimenti' : `Scelta ${Number(index) + 1}`}</b>${isDefault ? '' : '<span><button type="button" data-choose-duplicate-choice aria-label="Duplica scelta" title="Duplica">⧉</button><button type="button" data-choose-remove-choice aria-label="Rimuovi scelta">×</button></span>'}</div>${isDefault ? '' : `<div class="routine-choose-condition" data-choose-condition>${chooseConditionFields(choice.condition)}</div>`}<div class="routine-choose-steps" data-choose-steps>${steps.map((step, stepIndex) => renderStepRow(step, stepIndex, true)).join('')}</div><div class="routine-choose-add"><button type="button" data-choose-add-step="action">+ Azione</button><button type="button" data-choose-add-step="wait">+ Timer</button><button type="button" data-choose-add-step="check">+ Verifica</button><button type="button" data-choose-add-step="protected_cover">+ Cover con bypass protetto</button></div></section>`
}
function renderStepRow(item, index, nested = false) {
  const marker = nested === 'protected' ? `data-protected-step="${index}"` : nested ? `data-branch-step="${index}"` : `data-index="${index}"`
  const controls = nested === 'protected' ? '<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per riordinare il blocco" title="Trascina per riordinare">☰</button><button type="button" data-protected-duplicate-step aria-label="Duplica azione" title="Duplica">⧉</button><button type="button" data-protected-remove-step aria-label="Rimuovi azione">×</button></div>' : nested ? '<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per riordinare il blocco" title="Trascina per riordinare">☰</button><button type="button" data-branch-duplicate-step aria-label="Duplica blocco" title="Duplica">⧉</button><button type="button" data-branch-remove-step aria-label="Rimuovi blocco">×</button></div>' : stepButtons()
  if (item.type === 'protected_cover') return `<div class="routine-block routine-protected" ${marker} data-type="protected_cover"><b>Cover con bypass protetto</b><p>Le zone e-Safe devono essere spente. e-Face registra il ripristino e lo ritenta dopo un errore o riavvio.</p><div class="routine-protected-switches">${devices.filter(device => device.kind === 'safety_bypass').map(device => `<label><input type="checkbox" data-protected-bypass value="${escapeHtml(device.id)}" ${item.bypass_switches?.includes(device.id) ? 'checked' : ''}>${escapeHtml(device.name)}</label>`).join('') || '<span>Nessun bypass e-Safe disponibile</span>'}</div><label>Attesa dopo bypass (s)<input data-field="enable-delay" type="number" min="0" max="30" value="${Number(item.enable_delay_seconds ?? 3)}"></label><label>Tempo movimento prima del ripristino (s)<input data-field="move-seconds" type="number" min="1" max="180" value="${Number(item.move_seconds ?? 40)}"></label><div data-protected-steps>${(item.steps || []).map((step,i) => renderStepRow(step,i,'protected')).join('')}</div><button type="button" data-protected-add-step>+ Aggiungi cover o luce</button>${controls}</div>`
  if (item.type === 'choose') return `<div class="routine-block routine-choose" ${marker} data-type="choose"><b>Scegli un ramo · il primo che risulta vero</b><div class="routine-choose-branches">${item.choices.map((choice, choiceIndex) => renderChooseBranch(choice, choiceIndex)).join('')}${renderChooseBranch(item.default || [], 'default')}</div><button type="button" data-choose-add-choice>+ Aggiungi scelta</button>${controls}</div>`
  if (item.type === 'wait' || item.type === 'delay') return `<div class="routine-block" ${marker} data-type="${item.type}"><b>Timer</b><label>Secondi<input data-field="seconds" type="number" min="1" max="3600" value="${Number(item.seconds) || 60}"></label>${controls}</div>`
  if (item.type === 'check') return `<div class="routine-block" ${marker} data-type="check"><b>Verifica e interrompi se falsa</b>${deviceField(item.device_id)}<select data-field="operator"><option value="is" ${item.operator !== 'is_not' ? 'selected' : ''}>è</option><option value="is_not" ${item.operator === 'is_not' ? 'selected' : ''}>non è</option></select>${stateSelect(item.device_id,item.value)}${controls}</div>`
  const device = devices.find(entry => entry.id === item.device_id)
  const choices = actions[device?.kind] || []
  const capabilityFor = device?.kind === 'light_scenario' ? {on:'onoff',off:'onoff',run:'run',stop:'run'} : {media_play:'play',media_pause:'pause',media_stop:'stop',media_next:'next',media_previous:'previous',turn_off:'turn_off',set_volume:'set_volume',volume_mute:'mute',volume_unmute:'mute'}
  const actionChoices = choices.filter(([key]) => key === 'set_position' ? device?.position_supported : key === 'tts' ? device?.tts_enabled : key.startsWith('dnd_') ? device?.dnd_available : key === 'remote_command' ? device?.source_options?.some(source => source.experience === 'watch' && source.remote_actions?.length) : key === 'select_source' ? device?.capabilities?.select_source && (device?.source_list?.length || device?.source_options?.length) : !capabilityFor[key] || device?.capabilities?.[capabilityFor[key]])
  const sourceChoices = device?.provider === 'control4' ? (device.source_options || []).map(source => [source.key,source.label]) : (device?.source_list || []).map(source => [source,source])
  const value = item.action === 'tts' ? `<label class="routine-tts">Testo da pronunciare<textarea data-field="action-value" maxlength="500" rows="3">${escapeHtml(item.value || '')}</textarea></label>` : item.action === 'remote_command' ? remoteFields(item.device_id,item.value?.source_id,item.value?.command,false) : item.action === 'select_source' ? `<label class="routine-tts">Sorgente<select data-field="action-value"><option value="">Scegli sorgente</option>${sourceChoices.map(([key,label]) => `<option value="${escapeHtml(key)}" ${key === item.value || label === item.value ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select></label>` : ['brightness', 'set_volume', 'set_target', 'set_position'].includes(item.action) ? `<label>Valore<input data-field="action-value" type="number" min="${item.action === 'set_target' ? 5 : 0}" max="${item.action === 'set_target' ? 35 : 100}" value="${item.value ?? ''}"></label>` : ''
  return `<div class="routine-block" ${marker} data-type="action"><b>Azione</b>${deviceField(item.device_id,nested === 'protected' ? 'cover_light' : 'safe')}<select data-field="action"><option value="">Comando...</option>${actionChoices.map(([key,label]) => `<option value="${key}" ${key === item.action ? 'selected' : ''}>${label}</option>`).join('')}</select>${value}${controls}</div>`
}
function windowFields(item) {
  const edge = (label,key,defaultTime) => {
    const boundary = item[key] || {kind:'time',at:defaultTime}
    const kind = boundary.kind || 'time'
    return `<label class="routine-window-edge">${label}<select data-field="window-${key}-kind"><option value="time" ${kind==='time'?'selected':''}>Orario</option><option value="sunrise" ${kind==='sunrise'?'selected':''}>Alba</option><option value="sunset" ${kind==='sunset'?'selected':''}>Tramonto</option></select>${kind==='time'?`<input data-field="window-${key}-at" type="time" value="${escapeHtml(boundary.at||defaultTime)}">`:`<span>Minuti prima (−) / dopo (+)<input data-field="window-${key}-offset" type="number" min="-180" max="180" step="1" value="${Number(boundary.offset_minutes)||0}"></span>`}</label>`
  }
  return `<div class="routine-window">${edge('Da','start','18:00')}${edge('A','end','23:00')}<small>Da incluso, A escluso. Se «A» precede «Da», l'intervallo continua oltre mezzanotte.</small></div>`
}
function solarFields(item, condition = false) { return `<select data-field="sun-event" aria-label="Evento solare"><option value="sunrise" ${item.event === 'sunrise' ? 'selected' : ''}>Alba</option><option value="sunset" ${item.event === 'sunset' ? 'selected' : ''}>Tramonto</option></select><label class="routine-sun-offset">Minuti prima (−) / dopo (+)<input data-field="sun-offset" type="number" min="-180" max="180" step="1" value="${Number(item.offset_minutes) || 0}"></label>${condition ? `<select data-field="sun-relation" aria-label="Confronto con alba o tramonto"><option value="after" ${item.relation === 'after' ? 'selected' : ''}>Dopo questo orario</option><option value="before" ${item.relation === 'before' ? 'selected' : ''}>Prima di questo orario</option></select>` : ''}` }
function stepButtons() { return '<div class="routine-move"><button type="button" class="drag-handle routine-drag" data-routine-drag aria-label="Trascina per cambiare ordine; usa freccia su e giù da tastiera" title="Trascina per riordinare">☰</button><button type="button" data-routine-duplicate-row="step" aria-label="Duplica blocco" title="Duplica">⧉</button><button type="button" data-routine-remove="step" aria-label="Rimuovi">×</button></div>' }
function showReview(review) {
  $('[data-routine-review]').innerHTML = `<b>Effetti previsti in casa</b><p>${escapeHtml(review.description)}</p>${review.errors.length ? `<div class="routine-errors"><b>Da correggere</b>${review.errors.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : '<p class="routine-ok">Controlli bloccanti superati.</p>'}${review.warnings.length ? `<div class="routine-warnings"><b>Da valutare</b>${review.warnings.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : ''}`
  if (review.risks?.length) $('[data-routine-review]').insertAdjacentHTML('beforeend', `<div class="routine-warnings"><b>Possibili conseguenze sull'impianto</b>${review.risks.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>`)
}
async function load() {
  const [list, catalog] = await Promise.all([request('api/user/routines'), request('api/user/routines/catalog')])
  routines = list.items || []
  devices = catalog.devices || []
  catalogFilters = catalog.filters || catalogFilters
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
function protectedStepAt(element) {
  const block = element.closest('[data-type="protected_cover"]')
  if (!block) return null
  const branch = block.closest('[data-choose-branch]')
  if (!branch) return draft.steps[Number(block.dataset.index)]
  const outer = branch.closest('[data-routine-steps] > .routine-block')
  const choose = draft.steps[Number(outer.dataset.index)]
  const steps = branch.dataset.chooseBranch === 'default' ? choose.default : choose.choices[Number(branch.dataset.chooseBranch)].steps
  return steps[Number(block.dataset.branchStep)]
}
panel.addEventListener('click', event => {
  const protectedControl = event.target.closest('[data-protected-add-step],[data-protected-remove-step],[data-protected-duplicate-step]')
  if (protectedControl) {
    collect()
    const block = protectedStepAt(protectedControl)
    if (!block) return
    if (protectedControl.hasAttribute('data-protected-add-step')) { if (block.steps.length >= 20) return window.alert('Massimo 20 azioni.'); block.steps.push({type:'action',device_id:'',action:''}) }
    else { const index = Number(protectedControl.closest('[data-protected-step]').dataset.protectedStep); if (protectedControl.hasAttribute('data-protected-duplicate-step')) { if (block.steps.length >= 20) return window.alert('Massimo 20 azioni.'); block.steps.splice(index + 1,0,structuredClone(block.steps[index])) } else block.steps.splice(index,1) }
    renderEditor()
    return
  }
  const choiceControl = event.target.closest('[data-choose-add-choice],[data-choose-remove-choice],[data-choose-duplicate-choice],[data-choose-add-step],[data-branch-remove-step],[data-branch-duplicate-step]')
  if (choiceControl) {
    collect()
    const outer = choiceControl.closest('[data-routine-steps] > .routine-block')
    const choose = draft.steps[Number(outer.dataset.index)]
    const branch = choiceControl.closest('[data-choose-branch]')
    const branchIndex = branch?.dataset.chooseBranch
    const steps = branchIndex === 'default' ? choose.default : choose.choices[Number(branchIndex)]?.steps
    if (choiceControl.hasAttribute('data-choose-add-choice')) { if (choose.choices.length >= 8) return window.alert('Massimo 8 scelte.'); choose.choices.push({condition:newCondition('time_window'),steps:[{type:'action',device_id:'',action:''}]}) }
    else if (choiceControl.hasAttribute('data-choose-duplicate-choice')) { if (choose.choices.length >= 8) return window.alert('Massimo 8 scelte.'); choose.choices.splice(Number(branchIndex) + 1, 0, structuredClone(choose.choices[Number(branchIndex)])) }
    else if (choiceControl.hasAttribute('data-choose-remove-choice')) choose.choices.splice(Number(branchIndex), 1)
    else if (choiceControl.hasAttribute('data-choose-add-step')) { if (steps.length >= 20) return window.alert('Massimo 20 blocchi per ramo.'); steps.push(choiceControl.dataset.chooseAddStep === 'protected_cover' ? {type:'protected_cover',bypass_switches:[],enable_delay_seconds:3,move_seconds:40,steps:[{type:'action',device_id:'',action:''}]} : choiceControl.dataset.chooseAddStep === 'wait' ? {type:'wait',seconds:60} : choiceControl.dataset.chooseAddStep === 'check' ? {type:'check',device_id:'',operator:'is',value:''} : {type:'action',device_id:'',action:''}) }
    else {
      const stepIndex = Number(choiceControl.closest('[data-branch-step]').dataset.branchStep)
      if (choiceControl.hasAttribute('data-branch-duplicate-step')) { if (steps.length >= 20) return window.alert('Massimo 20 blocchi per ramo.'); steps.splice(stepIndex + 1, 0, structuredClone(steps[stepIndex])) }
      else if (choiceControl.hasAttribute('data-branch-remove-step')) steps.splice(stepIndex, 1)
    }
    renderEditor()
    return
  }
  const duplicate = event.target.closest('[data-routine-duplicate-row]')
  if (duplicate) {
    collect()
    const index = Number(duplicate.closest('[data-index]').dataset.index)
    const collection = duplicate.dataset.routineDuplicateRow === 'trigger' ? draft.triggers : duplicate.dataset.routineDuplicateRow === 'condition' ? draft.conditions : draft.steps
    const limit = duplicate.dataset.routineDuplicateRow === 'trigger' ? 12 : duplicate.dataset.routineDuplicateRow === 'condition' ? 8 : 20
    if (collection.length >= limit) return window.alert(`Massimo ${limit} voci in questa sezione.`)
    collection.splice(index + 1, 0, structuredClone(collection[index]))
    renderEditor()
    return
  }
  const add = event.target.closest('[data-routine-add]')
  if (add) {
    collect()
    const kind = add.dataset.routineAdd
    if (kind === 'trigger') draft.triggers.push({type: 'state', device_id: '', to: ''})
    else if (kind === 'condition') draft.conditions.push({device_id: '', operator: 'is', value: ''})
    else draft.steps.push(kind === 'protected_cover' ? {type:'protected_cover',bypass_switches:[],enable_delay_seconds:3,move_seconds:40,steps:[{type:'action',device_id:'',action:''}]} : kind === 'choose' ? newChoose() : kind === 'wait' ? {type: 'wait', seconds: 60} : kind === 'check' ? {type: 'check', device_id: '', operator: 'is', value: ''} : {type: 'action', device_id: '', action: ''})
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
function dragCollection(container) {
  if (container.matches('[data-routine-triggers]')) return {items:draft.triggers,key:'index',kind:'trigger'}
  if (container.matches('[data-routine-conditions]')) return {items:draft.conditions,key:'index',kind:'condition'}
  if (container.matches('[data-routine-steps]')) return {items:draft.steps,key:'index',kind:'step'}
  if (container.matches('[data-protected-steps]')) {
    const block = container.closest('[data-type="protected_cover"]')
    const outer = block.closest('[data-routine-steps] > .routine-block')
    const branch = block.closest('[data-choose-branch]')
    return {items:protectedStepAt(container)?.steps,key:'protectedStep',kind:'protectedStep',topIndex:Number(outer.dataset.index),branch:branch?.dataset.chooseBranch,protectedIndex:block.dataset.branchStep}
  }
  const outer = container.closest('[data-routine-steps] > .routine-block')
  if (!outer || outer.dataset.type !== 'choose') return null
  const topIndex = Number(outer.dataset.index)
  const choose = draft.steps[topIndex]
  if (container.matches('.routine-choose-branches')) return {items:choose.choices,key:'chooseBranch',kind:'choice',topIndex}
  const branch = container.closest('[data-choose-branch]')?.dataset.chooseBranch
  if (container.matches('[data-choose-steps]') && branch !== undefined) return {items:branch === 'default' ? choose.default : choose.choices[Number(branch)]?.steps,key:'branchStep',kind:'branchStep',topIndex,branch}
  return null
}
function dragItems(container, info) {
  return [...container.children].filter(item => info.kind !== 'choice' || item.dataset.chooseBranch !== 'default')
}
function dragContainer(info) {
  if (info.kind === 'trigger') return $('[data-routine-triggers]')
  if (info.kind === 'condition') return $('[data-routine-conditions]')
  if (info.kind === 'step') return $('[data-routine-steps]')
  if (info.kind === 'protectedStep') {
    const outer = $('[data-routine-steps]').children[info.topIndex]
    const block = info.branch === undefined ? outer : outer?.querySelector(`[data-choose-branch="${info.branch}"] > [data-choose-steps] > [data-branch-step="${info.protectedIndex}"]`)
    return block?.querySelector(':scope > [data-protected-steps]')
  }
  const outer = $('[data-routine-steps]').children[info.topIndex]
  if (info.kind === 'choice') return outer?.querySelector(':scope > .routine-choose-branches')
  return outer?.querySelector(`:scope > .routine-choose-branches > [data-choose-branch="${info.branch}"] > [data-choose-steps]`)
}
let draggedStep = null
panel.addEventListener('pointerdown', event => {
  const handle = event.target.closest('[data-routine-drag]')
  if (!handle || event.button !== 0) return
  const block = handle.closest('.routine-choose-branch, .routine-block')
  if (!block) return
  collect()
  const container = block.parentElement
  const info = dragCollection(container)
  if (!info?.items) return
  draggedStep = {pointerId:event.pointerId,handle,block,container,info}
  handle.setPointerCapture(event.pointerId)
  block.classList.add('dragging')
  event.preventDefault()
})
panel.addEventListener('pointermove', event => {
  if (!draggedStep || event.pointerId !== draggedStep.pointerId) return
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.routine-choose-branch, .routine-block')
  if (!target || target === draggedStep.block || target.parentElement !== draggedStep.container || target.dataset.chooseBranch === 'default') return
  const middle = target.getBoundingClientRect().top + target.getBoundingClientRect().height / 2
  draggedStep.container.insertBefore(draggedStep.block, event.clientY < middle ? target : target.nextSibling)
})
const finishDrag = event => {
  if (!draggedStep || event.pointerId !== draggedStep.pointerId) return
  const {block,container,info} = draggedStep
  draggedStep = null
  block.classList.remove('dragging')
  if (event.type !== 'pointercancel') {
    const ordered = dragItems(container,info).map(row => info.items[Number(row.dataset[info.key])])
    info.items.splice(0,info.items.length,...ordered)
  }
  renderEditor()
}
panel.addEventListener('pointerup', finishDrag)
panel.addEventListener('pointercancel', finishDrag)
panel.addEventListener('keydown', event => {
  if (!event.target.matches('[data-routine-drag]') || !['ArrowUp', 'ArrowDown'].includes(event.key)) return
  event.preventDefault()
  collect()
  const block = event.target.closest('.routine-choose-branch, .routine-block')
  const info = dragCollection(block.parentElement)
  if (!info?.items) return
  const index = Number(block.dataset[info.key])
  const next = index + (event.key === 'ArrowUp' ? -1 : 1)
  if (next < 0 || next >= info.items.length) return
  ;[info.items[index], info.items[next]] = [info.items[next], info.items[index]]
  renderEditor()
  const moved = dragContainer(info)?.children[next]
  moved?.querySelector(info.kind === 'choice' ? ':scope > .routine-choose-title [data-routine-drag]' : ':scope > .routine-move [data-routine-drag]')?.focus()
})
panel.addEventListener('input', event => {
  if (!event.target.matches('[data-device-search]')) return
  const select = event.target.parentElement.querySelector('[data-field="device"]')
  const allowed = select.dataset.deviceScope === 'safe' ? safeDevices() : select.dataset.deviceScope === 'media' ? devices.filter(item => item.kind === 'media_player') : select.dataset.deviceScope === 'cover_light' ? devices.filter(item => ['cover','light'].includes(item.kind)) : devices
  select.innerHTML = deviceOptions(select.value, allowed, event.target.value)
})
panel.addEventListener('change', event => {
  const field = event.target
  if (!field.matches('[data-field="device"],[data-field="type"],[data-field="condition-type"],[data-field="window-start-kind"],[data-field="window-end-kind"],[data-field="action"],[data-field="remote-source"]')) return
  collect()
  const protectedChild = field.closest('[data-protected-step]')
  if (protectedChild) {
    const block = protectedStepAt(field)
    const child = block.steps[Number(protectedChild.dataset.protectedStep)]
    if (field.dataset.field === 'device') { child.action = ''; child.value = null }
    if (field.dataset.field === 'action') child.value = null
    renderEditor()
    return
  }
  const branch = field.closest('[data-choose-branch]')
  if (branch) {
    const outer = branch.closest('[data-routine-steps] > .routine-block')
    const choose = draft.steps[Number(outer.dataset.index)]
    const branchIndex = branch.dataset.chooseBranch
    const choice = branchIndex === 'default' ? null : choose.choices[Number(branchIndex)]
    const stepRow = field.closest('[data-branch-step]')
    if (stepRow) {
      const step = (choice?.steps || choose.default)[Number(stepRow.dataset.branchStep)]
      if (field.dataset.field === 'device') { if (step.type === 'action') { step.action = ''; step.value = null } else step.value = '' }
      if (field.dataset.field === 'action') step.value = null
      if (field.dataset.field === 'remote-source' && step.type === 'action') step.value = {source_id:Number(field.value || 0),command:''}
    } else if (choice) {
      if (field.dataset.field === 'condition-type') choice.condition = newCondition(field.value)
      else if (field.dataset.field === 'window-start-kind' || field.dataset.field === 'window-end-kind') {
        const edge = field.dataset.field === 'window-start-kind' ? 'start' : 'end'
        choice.condition[edge] = field.value === 'time' ? {kind:'time',at:edge === 'start' ? '18:00' : '23:00'} : {kind:field.value,offset_minutes:0}
      } else if (field.dataset.field === 'device') choice.condition.value = ''
    }
    renderEditor()
    return
  }
  const row = field.closest('[data-index]')
  const index = Number(row?.dataset.index)
  if (row?.parentElement.matches('[data-routine-triggers]')) {
    if (field.dataset.field === 'type') draft.triggers[index] = field.value === 'time' ? {type:'time',at:'18:00'} : field.value === 'sun' ? {type:'sun',event:'sunrise',offset_minutes:0} : field.value === 'remote' ? {type:'remote',device_id:'',source_id:0,command:''} : field.value === 'doorbird' ? {type:'doorbird',event:'doorbell'} : {type:'state',device_id:'',to:''}
    else if (field.dataset.field === 'device' && draft.triggers[index].type === 'remote') { draft.triggers[index].source_id = 0; draft.triggers[index].command = '' }
    else if (field.dataset.field === 'device') draft.triggers[index].to = ''
    else if (field.dataset.field === 'remote-source') draft.triggers[index].command = ''
  } else if (row?.parentElement.matches('[data-routine-conditions]')) {
    if (field.dataset.field === 'condition-type') draft.conditions[index] = field.value === 'sun' ? {type:'sun',event:'sunset',offset_minutes:0,relation:'after'} : field.value === 'time_window' ? {type:'time_window',start:{kind:'sunset',offset_minutes:0},end:{kind:'time',at:'23:00'}} : {device_id:'',operator:'is',value:''}
    else if (field.dataset.field === 'window-start-kind' || field.dataset.field === 'window-end-kind') {
      const key = field.dataset.field === 'window-start-kind' ? 'start' : 'end'
      draft.conditions[index][key] = field.value === 'time' ? {kind:'time',at:key==='start'?'18:00':'23:00'} : {kind:field.value,offset_minutes:0}
    } else draft.conditions[index].value = ''
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
const professional = selector => professionalPanel.querySelector(selector)
let professionalItems = []
let professionalCurrent = null
const professionalTemplate = () => ({name:'Nuova routine',mode:'single',triggers:[{type:'state',device_id:'',to:'on'}],conditions:[],steps:[{type:'action',device_id:'',action:'on'}]})
const hasAdvancedFlow = spec => !canOpenVisual(spec)
function renderProfessionalChoice() {
  professional('[data-professional-select]').innerHTML = `<option value="">Nuova routine</option>${professionalItems.map(item => `<option value="${escapeHtml(item.id)}" ${professionalCurrent?.id === item.id ? 'selected' : ''}>${escapeHtml(item.name)} · v${item.revision}</option>`).join('')}`
}
function selectProfessional(item) {
  professionalCurrent = item || null
  professional('[data-professional-json]').value = JSON.stringify(item?.spec || professionalTemplate(), null, 2)
  professional('[data-professional-enabled]').checked = Boolean(item?.enabled)
  professional('[data-professional-open-visual]').disabled = !item || hasAdvancedFlow(item.spec)
  professional('[data-professional-review]').textContent = item ? `Versione ${item.revision} · creata da ${item.owner} · ${item.enabled ? 'attiva' : 'disattivata'}. Modifica il JSON e premi CONTROLLA JSON.` : 'Nuova routine: sostituisci gli ID vuoti con quelli del catalogo. Non sarà attivata automaticamente.'
  renderProfessionalChoice()
}
async function loadProfessional() {
  const [data, catalog] = await Promise.all([request('api/admin/routines/professional'), request('api/user/routines/catalog')])
  professionalItems = data.items || []
  devices = catalog.devices || []
  catalogFilters = catalog.filters || catalogFilters
  professionalPanel.querySelectorAll('[data-catalog-filter]').forEach(input => { input.checked = Boolean(catalogFilters[input.dataset.catalogFilter]) })
  renderProfessionalCatalog()
  selectProfessional(professionalItems.find(item => item.id === professionalCurrent?.id) || null)
}
function renderProfessionalCatalog() {
  const query = professional('[data-professional-catalog-search]').value.trim().toLocaleLowerCase('it-IT')
  const matching = devices.filter(item => [item.name, item.room, item.kind, item.id].some(value => String(value || '').toLocaleLowerCase('it-IT').includes(query)))
  professional('[data-professional-catalog-count]').textContent = `(${devices.length})`
  professional('[data-professional-catalog-list]').innerHTML = matching.map(item => {
    const commands = actions[item.kind]?.filter(([action]) => item.kind !== 'light_scenario' || item.capabilities?.[action === 'on' || action === 'off' ? 'onoff' : 'run']).map(([action]) => action) || []
    return `<div class="routine-catalog-item"><b>${escapeHtml(item.name || item.id)}</b><small>${escapeHtml([item.room, item.kind, item.id].filter(Boolean).join(' · '))}</small><small>Trigger: stato · Condizione: stato · Azioni: ${escapeHtml(commands.join(', ') || 'sola lettura')}</small></div>`
  }).join('') || '<p>Nessun dispositivo trovato.</p>'
}
professional('[data-professional-catalog-search]').addEventListener('input', renderProfessionalCatalog)
professionalPanel.addEventListener('change', async event => {
  const input = event.target.closest('[data-catalog-filter]')
  if (!input) return
  const next = {...catalogFilters, [input.dataset.catalogFilter]:input.checked}
  input.disabled = true
  try {
    const result = await request('api/admin/routines/catalog-filters', jsonOptions('PUT', next))
    catalogFilters = result.filters
    professional('[data-catalog-filter-status]').textContent = 'Filtri salvati per tutti gli utenti.'
    renderProfessionalCatalog()
  } catch (error) {
    input.checked = Boolean(catalogFilters[input.dataset.catalogFilter])
    professional('[data-catalog-filter-status]').textContent = error.message
  } finally { input.disabled = false }
})
function professionalSpec() {
  let spec
  try { spec = JSON.parse(professional('[data-professional-json]').value) } catch(error) { throw new Error(`JSON non valido: ${error.message}`) }
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) throw new Error('La definizione deve essere un oggetto JSON.')
  return spec
}
function showProfessionalReview(review) {
  professional('[data-professional-review]').innerHTML = `<b>Effetti previsti in casa</b><p>${escapeHtml(review.description)}</p>${review.errors.length ? `<div class="routine-errors"><b>Da correggere</b>${review.errors.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : '<p class="routine-ok">Controlli bloccanti superati.</p>'}${review.warnings.length ? `<div class="routine-warnings"><b>Da valutare</b>${review.warnings.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>` : ''}`
  if (review.risks?.length) professional('[data-professional-review]').insertAdjacentHTML('beforeend', `<div class="routine-warnings"><b>Possibili conseguenze sull'impianto</b>${review.risks.map(item => `<p>${escapeHtml(item)}</p>`).join('')}</div>`)
}
professionalCard.addEventListener('click', () => { professionalPanel.hidden = false; sessionStorage.setItem('eface-tools-panel', 'routine-professional'); document.body.style.overflow = 'hidden'; loadProfessional().catch(error => professional('[data-professional-review]').textContent = error.message) })
professional('[data-professional-back]').addEventListener('click', () => { professionalPanel.hidden = true; sessionStorage.removeItem('eface-tools-panel'); document.body.style.overflow = '' })
professional('[data-professional-select]').addEventListener('change', event => selectProfessional(professionalItems.find(item => item.id === event.target.value)))
professional('[data-professional-new]').addEventListener('click', () => selectProfessional(null))
professional('[data-professional-copy-catalog]').addEventListener('click', async () => {
  try {
    const data = await request('api/user/routines/catalog')
    await navigator.clipboard.writeText(JSON.stringify(data.devices || [], null, 2))
    professional('[data-professional-review]').textContent = 'Catalogo copiato: nomi, ID, tipi e comandi disponibili. Non contiene password.'
  } catch(error) { professional('[data-professional-review]').textContent = `Copia non riuscita: ${error.message}` }
})
professional('[data-professional-check]').addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true
  try { showProfessionalReview(await request('api/admin/routines/professional/validate', jsonOptions('POST', {spec:professionalSpec(),id:professionalCurrent?.id || null}))) }
  catch(error) { professional('[data-professional-review]').textContent = error.message }
  finally { button.disabled = false }
})
professional('[data-professional-save]').addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true
  try {
    const spec = professionalSpec()
    const review = await request('api/admin/routines/professional/validate', jsonOptions('POST', {spec,id:professionalCurrent?.id || null}))
    showProfessionalReview(review)
    if (review.errors.length) return
    const enabled = professional('[data-professional-enabled]').checked
    const confirm_warnings = enabled && review.warnings.length ? window.confirm(`Controlla prima di attivare:\n\n${review.warnings.join('\n')}\n\nConfermi?`) : false
    if (enabled && review.warnings.length && !confirm_warnings) return
    const id = professionalCurrent?.id
    const result = await request(id ? `api/admin/routines/professional/${encodeURIComponent(id)}` : 'api/admin/routines/professional', jsonOptions(id ? 'PUT' : 'POST', {spec,enabled,confirm_warnings,expected_revision:professionalCurrent?.revision ?? null}))
    professionalCurrent = result.item
    await loadProfessional()
    showProfessionalReview(result.review)
    professional('[data-professional-review]').insertAdjacentHTML('afterbegin', `<p class="routine-ok">${escapeHtml(result.item.name)} salvata · versione ${result.item.revision} · ${result.item.enabled ? 'attiva' : 'disattivata'}.</p>`)
  } catch(error) { professional('[data-professional-review]').textContent = error.message }
  finally { button.disabled = false }
})
professional('[data-professional-open-visual]').addEventListener('click', () => {
  if (!professionalCurrent) return
  if (hasAdvancedFlow(professionalCurrent.spec)) {
    professional('[data-professional-review]').textContent = 'Questa routine contiene blocchi avanzati: modificala qui nel JSON. L’editor visuale lineare non può rappresentarli senza perdita di dati.'
    return
  }
  sessionStorage.setItem('eface-routine-id', professionalCurrent.id)
  professionalPanel.hidden = true
  userCard.click()
})
setTimeout(() => {
  const saved = sessionStorage.getItem('eface-tools-panel')
  if (saved === 'routine') userCard.click()
  if (saved === 'routine-log') {
    document.querySelector('[data-tools-view="admin"]:not([hidden])')?.click()
    adminCard.click()
  }
  if (saved === 'routine-professional') {
    document.querySelector('[data-tools-view="admin"]:not([hidden])')?.click()
    professionalCard.click()
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
