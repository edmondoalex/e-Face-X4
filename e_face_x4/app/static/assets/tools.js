const $ = (selector) => document.querySelector(selector)
const esc = (value) => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML }
const apiUrl = (path) => new URL(path, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()
const brandLink = document.querySelector('.tools-brand')
brandLink.setAttribute('role', 'link')
brandLink.setAttribute('tabindex', '0')
brandLink.setAttribute('aria-label', 'Torna alla Home e-Face')
brandLink.style.cursor = 'pointer'
const openHomeFromBrand = () => { location.href = apiUrl('../') }
brandLink.addEventListener('click', openHomeFromBrand)
brandLink.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openHomeFromBrand() } })
let backgroundData = null

function applyToolsBackground(selected, refreshImage = false) {
  const presets = {
    teal: 'linear-gradient(135deg,#84bfd5,#137073 58%,#0e4a4e)',
    midnight: 'radial-gradient(circle at 70% 20%,#263f61,#08121e 65%)',
    graphite: 'linear-gradient(145deg,#596066,#181c1f 65%)',
    ocean: 'radial-gradient(circle at 25% 20%,#43a8ca,#075079 48%,#03273e)',
    warm: 'radial-gradient(circle at 20% 20%,#b77955,#59372f 52%,#24191b)'
  }
  const image = selected?.mode === 'custom' ? `linear-gradient(rgba(4,22,26,.28),rgba(4,22,26,.48)),url("${apiUrl(`../api/user/background/image${refreshImage ? `?v=${Date.now()}` : ''}`)}")` : (presets[selected?.preset] || presets.teal)
  document.documentElement.style.setProperty('--tools-background', image)
}

async function loadToolsBackground() {
  const response = await fetch(apiUrl('../api/user/background'), {cache:'no-store'})
  if (response.ok) applyToolsBackground((await response.json()).global)
}

function notice(message) { $('#tools-notice').textContent = message; $('#tools-notice').hidden = false; setTimeout(() => { $('#tools-notice').hidden = true }, 3500) }

async function loadBackgrounds(refreshImage = false) {
  const activeRoom=$('#background-room')?.value||''
  const [settingsResponse, bootstrapResponse] = await Promise.all([fetch(apiUrl('../api/user/background'), {cache:'no-store'}), fetch(apiUrl('../api/bootstrap'), {cache:'no-store'})])
  if (!settingsResponse.ok || !bootstrapResponse.ok) throw new Error('Sfondi non disponibili')
  backgroundData = await settingsResponse.json(); const bootstrap = await bootstrapResponse.json(); applyToolsBackground(backgroundData.global, refreshImage)
  const rooms = (bootstrap.dashboard?.rooms || []).map((room) => room.name).filter(Boolean).sort((a,b)=>a.localeCompare(b,'it'))
  $('#background-room').innerHTML = '<option value="">Globale</option>' + rooms.map((room)=>`<option value="${esc(room)}">${esc(room)}</option>`).join('')
  if(rooms.includes(activeRoom))$('#background-room').value=activeRoom
  renderBackgrounds()
}
function renderBackgrounds() {
  const room=$('#background-room').value;const selected=room?(backgroundData.rooms?.[room]||{mode:'inherit'}):backgroundData.global;const names={teal:'E‑Face',midnight:'Notte',graphite:'Grafite',ocean:'Oceano',warm:'Caldo'}
  $('#background-presets').innerHTML=backgroundData.presets.map((preset)=>`<button data-background-preset="${preset}" class="background-preview background-${preset} ${selected.mode==='preset'&&selected.preset===preset?'active':''}"><b>${names[preset]||preset}</b></button>`).join('')+`<button class="background-preview background-custom ${selected.mode==='custom'?'active':''}" data-background-photo><b>Foto personale</b></button>`
  $('#background-inherit').hidden=!room
}
async function saveBackground(payload) {
  const response=await fetch(apiUrl('../api/user/background'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,room:$('#background-room').value})});if(!response.ok)throw new Error((await response.json()).detail);await loadBackgrounds(payload.mode==='custom');notice('Sfondo salvato')
}

async function unlockTools() {
  const status = await fetch(apiUrl('../api/installer/status'), {cache:'no-store'})
  if (!status.ok) { $('#admin-locked').hidden = false; $('#admin-tools').hidden = true; return false }
  $('#admin-locked').hidden = true; $('#admin-tools').hidden = false
  const authStatus = await fetch(apiUrl('../api/auth/status'), {cache:'no-store'}).then((res) => res.json())
  let setup = $('#admin-setup')
  if (!setup) {
    setup = document.createElement('div')
    setup.id = 'admin-setup'
    setup.className = 'login-card'
    setup.innerHTML = '<h3>Crea account admin</h3><p>Nuova password per e-Face: almeno 12 caratteri. Prova il login prima di eliminare la vecchia password installatore.</p><form id="admin-setup-form"><input id="admin-new-password" type="password" autocomplete="new-password" minlength="12" placeholder="Nuova password admin" required><button>CREA ADMIN</button></form>'
    $('#admin-tools').prepend(setup)
    setup.querySelector('form').addEventListener('submit', async (event) => {
      event.preventDefault()
      const button = event.currentTarget.querySelector('button')
      button.disabled = true
      try {
        const response = await fetch(apiUrl('../api/auth/setup'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('#admin-new-password').value})})
        if (!response.ok) throw new Error((await response.json()).detail)
        $('#admin-new-password').value = ''
        await unlockTools()
        notice('Admin creato. Prova il login in una finestra privata prima di togliere la vecchia password installatore.')
      } catch(error) { notice(error.message) } finally { button.disabled = false }
    })
  }
  setup.hidden = authStatus.enabled
  return true
}

async function loadPlayers() {
  if (!await unlockTools()) return false
  const response = await fetch(apiUrl('../api/installer/media-players'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#player-list').innerHTML = data.items.map((player) => `<div class="player-row ${player.device_type === 'echo' ? 'player-echo' : ''}" data-player="${esc(player.registry_id)}"><button class="drag-handle" type="button" aria-label="Trascina ${esc(player.original_name)}">☰</button><span class="player-identity"><b>${esc(player.original_name)}</b><small>${esc(player.device_type === 'echo' ? 'ECHO' : 'MEDIA PLAYER')} · ${esc(player.entity_id)}</small><span class="player-fields"><label>Nome e-Face<input type="text" maxlength="80" data-field="name" value="${esc(player.name)}" placeholder="${esc(player.original_name)}"></label><label>Stanza<input type="text" maxlength="80" data-field="room" value="${esc(player.room)}" placeholder="${esc(player.original_room)}"></label></span></span><label title="Mostra"><input type="checkbox" data-field="visible" ${player.visible ? 'checked' : ''}></label><label title="Audio"><input type="checkbox" data-field="audio" ${player.audio ? 'checked' : ''}></label><label title="Video"><input type="checkbox" data-field="video" ${player.video ? 'checked' : ''}></label><label title="TTS"><input type="checkbox" data-field="tts" ${player.provider === 'evoice' && player.tts_available && player.tts ? 'checked' : ''} ${player.provider === 'evoice' && player.tts_available ? '' : 'disabled'}></label></div>`).join('') || '<p>Nessun player disponibile</p>'
  return true
}

async function loadControl4() {
  const response = await fetch(apiUrl('../api/installer/control4'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#control4-host').value = data.host || '192.168.3.10'
  $('#control4-artwork-hosts').value = data.artwork_hosts || ''
  $('#control4-username').value = data.username || ''
  $('#control4-password').placeholder = data.password_configured ? 'Password già salvata' : 'Password Control4'
}

async function loadSourceIcons() {
  const response = await fetch(apiUrl('../api/installer/media-source-icons'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#source-icon-list').innerHTML = data.items.map((source) => `<div class="source-icon-row" data-source-id="${Number(source.source_id)}"><img src="${apiUrl(`../api/control4/source-icon/${Number(source.source_id)}?admin=${Date.now()}`)}" alt="" onerror="this.classList.add('missing')"><b>${esc(source.name)}</b><label>CAMBIA<input type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label><button type="button" data-source-reset ${source.custom ? '' : 'disabled'}>RIPRISTINA</button></div>`).join('') || '<p>Nessuna sorgente disponibile</p>'
}

function control4Payload() { return { host: $('#control4-host').value.trim(), username: $('#control4-username').value.trim(), password: $('#control4-password').value, artwork_hosts: $('#control4-artwork-hosts').value.trim() } }

async function sendControl4(path, button) {
  button.disabled = true
  $('#control4-result').hidden = true
  try {
    const response = await fetch(apiUrl(`../api/installer/control4${path}`), { method: path ? 'POST' : 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(control4Payload()) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    $('#control4-password').value = ''
    if (path) {
      $('#control4-result').innerHTML = `<b>Connessione riuscita</b><span>Controller: ${esc(data.controller)}</span><span>OS: ${esc(data.os_version || 'non rilevata')}</span><span>Director locale: ${esc(data.local_host)}</span><span>Stanze rilevate: ${Number(data.rooms) || 0}</span><span>Sorgenti rilevate: ${Number(data.sources) || 0}</span><span>Esperienze: ${(data.experiences || []).map(esc).join(' · ') || '—'}</span>${data.room_names?.length ? `<span>${data.room_names.map(esc).join(' · ')}</span>` : ''}`
      $('#control4-result').hidden = false
    } else notice('Configurazione Control4 salvata')
  } catch (error) { notice(error.message) } finally { button.disabled = false }
}

$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const response = await fetch(apiUrl('../api/installer/login'), { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('#installer-password').value}) }); if (!response.ok) throw new Error((await response.json()).detail); $('#installer-password').value=''; await unlockTools() } catch(error){ notice(error.message) } })
$('#media-tool').addEventListener('click', async () => { try { if (await loadPlayers()) { await loadSourceIcons(); $('#media-config').hidden = false } } catch(error){ notice(error.message) } })
$('#control4-tool').addEventListener('click', async () => { try { await loadControl4(); $('#control4-config').hidden=false } catch(error){ notice(error.message) } })
$('#control4-back').addEventListener('click', () => { $('#control4-config').hidden=true })
$('#control4-save').addEventListener('click', (event) => sendControl4('', event.currentTarget))
$('#control4-form').addEventListener('submit', (event) => { event.preventDefault(); sendControl4('/test', $('#control4-test')) })
$('#control4-artwork-diagnostic').addEventListener('click', async (event) => {
  const button = event.currentTarget
  button.disabled = true
  try {
    const response = await fetch(apiUrl('../api/admin/control4/artwork-diagnostic'), { cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    const players = data.players || []
    $('#control4-result').innerHTML = `<b>Diagnosi cover</b>${players.length ? players.map(player => `<span>${esc(player.room || 'Stanza')} · ${esc(player.title || player.source || 'Sorgente')}: ${esc(player.artwork_origin?.scheme || '')}://${esc(player.artwork_host || 'nessun URL')}${player.artwork_origin?.port ? `:${Number(player.artwork_origin.port)}` : ''} · ${esc(player.artwork_status)}${player.content_type ? ` · ${esc(player.content_type)}` : ''}${player.bytes != null ? ` · ${Number(player.bytes)} byte` : ''}</span>`).join('') : '<span>Nessuna riproduzione Control4 attiva, oppure Control4 non raggiungibile.</span>'}`
    $('#control4-result').hidden = false
  } catch (error) { notice(error.message) } finally { button.disabled = false }
})
$('#control4-support-link').addEventListener('click', async (event) => {
  const button = event.currentTarget
  button.disabled = true
  try {
    const response = await fetch(apiUrl('../api/admin/control4/artwork-support-link'), { method: 'POST' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    const url = new URL(data.path, location.origin).href
    $('#control4-result').innerHTML = `<b>Link diagnostico valido 10 minuti, una sola lettura</b><span style="overflow-wrap:anywhere">${esc(url)}</span>`
    $('#control4-result').hidden = false
    try { await navigator.clipboard.writeText(url); notice('Link copiato negli appunti') } catch (_) { notice('Copia il link visualizzato') }
  } catch (error) { notice(error.message) } finally { button.disabled = false }
})
$('#control4-service-discovery').addEventListener('click', async (event) => {
  const button = event.currentTarget
  button.disabled = true
  try {
    const response = await fetch(apiUrl('../api/admin/control4/service-discovery'), { cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    const candidates = data.driver_candidates || []
    $('#control4-result').innerHTML = `<b>Driver candidati per login — solo nomi, nessun valore</b>${candidates.map(item => `<span>${esc(item.name)} · ID ${Number(item.source_id)} · tipo ${esc(item.source_type || '?')} · variabili: ${esc((item.variable_names || []).join(', ') || 'nessuna')} · comandi: ${esc((item.command_names || []).join(', ') || 'nessuno')} · campi scheda: ${esc((item.item_fields || []).join(', ') || 'nessuno')}</span>`).join('') || '<span>Nessun driver musicale riconosciuto: serve verificare come il Director li denomina.</span>'}<b>Sorgenti Ascolta: ${(data.services || []).length}</b>`
    $('#control4-result').hidden = false
  } catch (error) { notice(error.message) } finally { button.disabled = false }
})
$('#control4-service-link').addEventListener('click', async (event) => {
  const button = event.currentTarget
  button.disabled = true
  try {
    const response = await fetch(apiUrl('../api/admin/control4/artwork-support-link'), { method: 'POST' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    const url = new URL(data.path, location.origin)
    url.searchParams.set('services', 'true')
    $('#control4-result').innerHTML = `<b>Link ricognizione servizi valido 10 minuti, una sola lettura</b><span style="overflow-wrap:anywhere">${esc(url.href)}</span>`
    $('#control4-result').hidden = false
    try { await navigator.clipboard.writeText(url.href); notice('Link copiato negli appunti') } catch (_) { notice('Copia il link visualizzato') }
  } catch (error) { notice(error.message) } finally { button.disabled = false }
})
const pairingControls = document.createElement('div')
pairingControls.className = 'control4-actions'
pairingControls.innerHTML = '<button type="button" data-music-pairing-probe="tunein">VERIFICA ASSOCIAZIONE TUNEIN</button><button type="button" data-music-pairing-probe="amazon">VERIFICA ASSOCIAZIONE AMAZON</button>'
$('#control4-result').before(pairingControls)
pairingControls.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-music-pairing-probe]')
  if (!button) return
  button.disabled = true
  try {
    const service = button.dataset.musicPairingProbe
    const response = await fetch(apiUrl(`../api/admin/control4/music-pairing-probe?service=${encodeURIComponent(service)}`), { method: 'POST', cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    $('#control4-result').innerHTML = `<b>${esc(data.service)} · driver ${Number(data.driver_id)} · soli nomi dei campi</b><span>${esc((data.field_names || []).join(', ') || 'Nessun campo esposto dal driver')}</span>`
    $('#control4-result').hidden = false
  } catch (error) { notice(error.message) } finally { button.disabled = false }
})
$('#media-back').addEventListener('click', () => { $('#media-config').hidden = true })
$('#logout').addEventListener('click', async () => { await fetch(apiUrl('../api/installer/logout'), {method:'POST'}); const status=await fetch(apiUrl('../api/auth/status')).then((res)=>res.json()); if(status.enabled){await fetch(apiUrl('../api/auth/logout'),{method:'POST'});location.href=apiUrl('../login');return} $('#admin-tools').hidden=true; $('#admin-locked').hidden=false })
$('#save-players').addEventListener('click', async (event) => { event.currentTarget.disabled=true; try { const players={}; document.querySelectorAll('.player-row').forEach((row, order) => { players[row.dataset.player]={...Object.fromEntries([...row.querySelectorAll('input[data-field]')].map((input)=>[input.dataset.field,input.type==='checkbox'?input.checked:input.value.trim()])),order} }); const response=await fetch(apiUrl('../api/installer/media-players'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({players})}); if(!response.ok) throw new Error((await response.json()).detail); notice('Configurazione salvata'); setTimeout(()=>location.href='./',700) } catch(error){notice(error.message)} finally{event.currentTarget.disabled=false} })
$('#player-list').addEventListener('change',(event)=>{const row=event.target.closest('.player-row');if(!row)return;const visible=row.querySelector('[data-field=visible]');const modes=[...row.querySelectorAll('[data-field=audio],[data-field=video],[data-field=tts]')];if(event.target===visible&&!visible.checked)modes.forEach((input)=>{input.checked=false});if(modes.includes(event.target)){if(event.target.checked)visible.checked=true;else if(!modes.some((input)=>input.checked))visible.checked=false}})
$('#source-icon-list').addEventListener('change', async (event) => { const input=event.target.closest('input[type=file]');if(!input?.files[0])return;const file=input.files[0];if(file.size>500000)return notice('Icona superiore a 500 KB');const row=input.closest('[data-source-id]');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)});try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({mime:file.type,data})});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona sostituita');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#source-icon-list').addEventListener('click', async (event) => { const button=event.target.closest('[data-source-reset]');if(!button)return;const row=button.closest('[data-source-id]');try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'DELETE'});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona ripristinata');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#background-tool').addEventListener('click',async()=>{try{await loadBackgrounds();$('#background-config').hidden=false}catch(error){notice(error.message)}})
$('#background-back').addEventListener('click',()=>{$('#background-config').hidden=true})
$('#background-room').addEventListener('change',renderBackgrounds)
$('#background-presets').addEventListener('click',async(event)=>{const preset=event.target.closest('[data-background-preset]')?.dataset.backgroundPreset;if(preset)try{await saveBackground({mode:'preset',preset})}catch(error){notice(error.message)};if(event.target.closest('[data-background-photo]'))$('#background-file').click()})
$('#background-inherit').addEventListener('click',async()=>{try{await saveBackground({mode:'inherit'})}catch(error){notice(error.message)}})
$('#background-file').addEventListener('change',async(event)=>{const file=event.target.files[0];if(!file)return;if(file.size>4000000)return notice('Foto superiore a 4 MB');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)});try{await saveBackground({mode:'custom',mime:file.type,data})}catch(error){notice(error.message)}finally{event.target.value=''}})

const cardThemeNames={graphite:'Grafite',petrol:'Petrolio',midnight:'Notte',slate:'Ardesia',warm:'Calda'}
async function loadCardThemes(){const response=await fetch(apiUrl('../api/user/card-theme'),{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();document.body.dataset.cardTheme=data.theme;$('#card-theme-presets').innerHTML=data.themes.map(theme=>`<button class="card-theme-preview card-theme-${theme} ${theme===data.theme?'active':''}" data-card-theme="${theme}"><i></i><span><b>${cardThemeNames[theme]||theme}</b><small>Anteprima schede</small></span></button>`).join('')}
$('#card-theme-tool').addEventListener('click',async()=>{try{await loadCardThemes();$('#card-theme-config').hidden=false}catch(error){notice(error.message)}})
$('#card-theme-back').addEventListener('click',()=>{$('#card-theme-config').hidden=true})
$('#card-theme-presets').addEventListener('click',async(event)=>{const theme=event.target.closest('[data-card-theme]')?.dataset.cardTheme;if(!theme)return;try{const response=await fetch(apiUrl('../api/user/card-theme'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme})});if(!response.ok)throw new Error((await response.json()).detail);await loadCardThemes();notice('Colore card salvato')}catch(error){notice(error.message)}})
let draggedRow = null
$('#player-list').addEventListener('pointerdown', (event) => { const handle=event.target.closest('.drag-handle'); if(!handle)return; draggedRow=handle.closest('.player-row'); draggedRow.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
$('#player-list').addEventListener('pointermove', (event) => { if(!draggedRow)return; const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('.player-row'); if(!target||target===draggedRow)return; const rect=target.getBoundingClientRect(); $('#player-list').insertBefore(draggedRow,event.clientY<rect.top+rect.height/2?target:target.nextSibling) })
const finishDrag = () => { if(draggedRow)draggedRow.classList.remove('dragging'); draggedRow=null }
$('#player-list').addEventListener('pointerup', finishDrag)
$('#player-list').addEventListener('pointercancel', finishDrag)
unlockTools().catch(()=>{})
loadToolsBackground().catch(()=>{})
loadCardThemes().catch(()=>{})

let orderedRooms = []
function renderRoomOrder() {
  $('#room-order-list').innerHTML = orderedRooms.map((name, index) => `<div class="room-order-row" data-index="${index}"><button type="button" class="drag-handle room-drag-handle" aria-label="Trascina ${esc(name)} per riordinare" title="Trascina per riordinare">☰</button><strong>${esc(name.toLocaleUpperCase('it'))}</strong></div>`).join('') || '<p>Nessun ambiente disponibile</p>'
}
async function loadRoomOrder() {
  const [bootstrapResponse, appearanceResponse] = await Promise.all([fetch(apiUrl('../api/bootstrap'), {cache:'no-store'}), fetch(apiUrl('../api/user/appearance'), {cache:'no-store'})])
  if (!bootstrapResponse.ok || !appearanceResponse.ok) throw new Error('Ambienti non disponibili')
  const bootstrap = await bootstrapResponse.json(); const appearance = await appearanceResponse.json()
  const names = [...new Map((bootstrap.dashboard?.rooms || []).map((room) => String(room.name || '').trim()).filter(Boolean).map((name) => [name.toLocaleLowerCase('it'), name])).values()]
  const ranks = new Map((appearance.room_order || []).map((name, index) => [String(name).toLocaleLowerCase('it'), index]))
  orderedRooms = names.sort((a, b) => (ranks.get(a.toLocaleLowerCase('it')) ?? Number.MAX_SAFE_INTEGER) - (ranks.get(b.toLocaleLowerCase('it')) ?? Number.MAX_SAFE_INTEGER) || a.localeCompare(b, 'it'))
  renderRoomOrder()
}
$('#room-order-tool').addEventListener('click', async () => { try { await loadRoomOrder(); $('#room-order-config').hidden = false } catch (error) { notice(error.message) } })
$('#room-order-back').addEventListener('click', () => { $('#room-order-config').hidden = true })
let draggedRoom = null
$('#room-order-list').addEventListener('pointerdown', (event) => { const handle = event.target.closest('.room-drag-handle'); if (!handle) return; draggedRoom = handle.closest('.room-order-row'); draggedRoom.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
$('#room-order-list').addEventListener('pointermove', (event) => { if (!draggedRoom) return; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.room-order-row'); if (!target || target === draggedRoom || target.parentElement !== $('#room-order-list')) return; const rect = target.getBoundingClientRect(); $('#room-order-list').insertBefore(draggedRoom, event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling) })
const finishRoomDrag = () => { if (!draggedRoom) return; draggedRoom.classList.remove('dragging'); draggedRoom = null; orderedRooms = [...$('#room-order-list').querySelectorAll('.room-order-row')].map((row) => orderedRooms[Number(row.dataset.index)]); renderRoomOrder() }
$('#room-order-list').addEventListener('pointerup', finishRoomDrag)
$('#room-order-list').addEventListener('pointercancel', finishRoomDrag)
$('#room-order-list').addEventListener('keydown', (event) => { if (!event.target.matches('.room-drag-handle') || !['ArrowUp','ArrowDown'].includes(event.key)) return; event.preventDefault(); const index = Number(event.target.closest('.room-order-row').dataset.index); const other = index + (event.key === 'ArrowUp' ? -1 : 1); if (other < 0 || other >= orderedRooms.length) return; [orderedRooms[index], orderedRooms[other]] = [orderedRooms[other], orderedRooms[index]]; renderRoomOrder(); $('#room-order-list').querySelectorAll('.room-drag-handle')[other]?.focus() })
$('#room-order-save').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({room_order:orderedRooms})}); if (!response.ok) throw new Error((await response.json()).detail); notice('Ordine ambienti salvato'); $('#room-order-config').hidden = true } catch (error) { notice(error.message) } })
const securityLabels = {scenarios:'SCENARI DI INSERIMENTO', areas:'STATO AREE', zones:'ZONE', locks:'SERRATURE'}
let orderedSecurity = Object.keys(securityLabels)
const securityList = $('#security-order-list')
function renderSecurityOrder() {
  securityList.innerHTML = orderedSecurity.map((key, index) => `<div class="room-order-row" data-index="${index}"><button type="button" class="drag-handle room-drag-handle" aria-label="Trascina ${securityLabels[key]} per riordinare" title="Trascina per riordinare">☰</button><strong>${securityLabels[key]}</strong></div>`).join('')
}
$('#security-order-tool').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {cache:'no-store'}); if (!response.ok) throw new Error(`HTTP ${response.status}`); orderedSecurity = (await response.json()).security_order || Object.keys(securityLabels); renderSecurityOrder(); $('#security-order-config').hidden = false } catch (error) { notice(error.message) } })
$('#security-order-back').addEventListener('click', () => { $('#security-order-config').hidden = true })
let draggedSecurity = null
securityList.addEventListener('pointerdown', (event) => { const handle = event.target.closest('.room-drag-handle'); if (!handle) return; draggedSecurity = handle.closest('.room-order-row'); draggedSecurity.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
securityList.addEventListener('pointermove', (event) => { if (!draggedSecurity) return; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.room-order-row'); if (!target || target === draggedSecurity || target.parentElement !== securityList) return; const rect = target.getBoundingClientRect(); securityList.insertBefore(draggedSecurity, event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling) })
const finishSecurityDrag = () => { if (!draggedSecurity) return; draggedSecurity.classList.remove('dragging'); draggedSecurity = null; orderedSecurity = [...securityList.querySelectorAll('.room-order-row')].map((row) => orderedSecurity[Number(row.dataset.index)]); renderSecurityOrder() }
securityList.addEventListener('pointerup', finishSecurityDrag)
securityList.addEventListener('pointercancel', finishSecurityDrag)
securityList.addEventListener('keydown', (event) => { if (!event.target.matches('.room-drag-handle') || !['ArrowUp','ArrowDown'].includes(event.key)) return; event.preventDefault(); const index = Number(event.target.closest('.room-order-row').dataset.index); const other = index + (event.key === 'ArrowUp' ? -1 : 1); if (other < 0 || other >= orderedSecurity.length) return; [orderedSecurity[index], orderedSecurity[other]] = [orderedSecurity[other], orderedSecurity[index]]; renderSecurityOrder(); securityList.querySelectorAll('.room-drag-handle')[other]?.focus() })
$('#security-order-save').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({security_order:orderedSecurity})}); if (!response.ok) throw new Error((await response.json()).detail); notice('Ordine sicurezza salvato'); $('#security-order-config').hidden = true } catch (error) { notice(error.message) } })
$('#card-glow-tool').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {cache:'no-store'}); if (!response.ok) throw new Error(`HTTP ${response.status}`); $('#card-glow-enabled').checked = (await response.json()).card_glow !== false; $('#card-glow-config').hidden = false } catch (error) { notice(error.message) } })
$('#card-glow-back').addEventListener('click', () => { $('#card-glow-config').hidden = true })
$('#card-glow-enabled').addEventListener('change', async (event) => { const enabled = event.target.checked; try { const response = await fetch(apiUrl('../api/user/appearance'), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({card_glow:enabled})}); if (!response.ok) throw new Error((await response.json()).detail); notice(enabled ? 'Illuminazione schede attivata' : 'Illuminazione schede disattivata') } catch (error) { event.target.checked = !enabled; notice(error.message) } })
