const $ = (selector) => document.querySelector(selector)
const esc = (value) => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML }
const apiUrl = (path) => new URL(path, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()
let backgroundData = null

function applyToolsBackground(selected) {
  const presets = {
    teal: 'linear-gradient(135deg,#84bfd5,#137073 58%,#0e4a4e)',
    midnight: 'radial-gradient(circle at 70% 20%,#263f61,#08121e 65%)',
    graphite: 'linear-gradient(145deg,#596066,#181c1f 65%)',
    ocean: 'radial-gradient(circle at 25% 20%,#43a8ca,#075079 48%,#03273e)',
    warm: 'radial-gradient(circle at 20% 20%,#b77955,#59372f 52%,#24191b)'
  }
  const image = selected?.mode === 'custom' ? `linear-gradient(rgba(4,22,26,.28),rgba(4,22,26,.48)),url("${apiUrl(`../api/user/background/image?v=${Date.now()}`)}")` : (presets[selected?.preset] || presets.teal)
  document.documentElement.style.setProperty('--tools-background', image)
}

async function loadToolsBackground() {
  const response = await fetch(apiUrl('../api/user/background'), {cache:'no-store'})
  if (response.ok) applyToolsBackground((await response.json()).global)
}

function notice(message) { $('#tools-notice').textContent = message; $('#tools-notice').hidden = false; setTimeout(() => { $('#tools-notice').hidden = true }, 3500) }

async function loadBackgrounds() {
  const activeRoom=$('#background-room')?.value||''
  const [settingsResponse, bootstrapResponse] = await Promise.all([fetch(apiUrl('../api/user/background'), {cache:'no-store'}), fetch(apiUrl('../api/bootstrap'), {cache:'no-store'})])
  if (!settingsResponse.ok || !bootstrapResponse.ok) throw new Error('Sfondi non disponibili')
  backgroundData = await settingsResponse.json(); const bootstrap = await bootstrapResponse.json(); applyToolsBackground(backgroundData.global)
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
  const response=await fetch(apiUrl('../api/user/background'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,room:$('#background-room').value})});if(!response.ok)throw new Error((await response.json()).detail);await loadBackgrounds();notice('Sfondo salvato')
}

async function loadPlayers() {
  const response = await fetch(apiUrl('../api/installer/media-players'), { cache: 'no-store' })
  if (response.status === 401) { $('#admin-locked').hidden = false; $('#admin-tools').hidden = true; return false }
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#admin-locked').hidden = true; $('#admin-tools').hidden = false
  $('#player-list').innerHTML = data.items.map((player) => `<div class="player-row" data-player="${esc(player.registry_id)}"><button class="drag-handle" type="button" aria-label="Trascina ${esc(player.name)}">☰</button><span><b>${esc(player.name)}</b><small>${esc(player.entity_id)}</small></span><label><input type="checkbox" data-field="visible" ${player.visible ? 'checked' : ''}></label><label><input type="checkbox" data-field="audio" ${player.audio ? 'checked' : ''}></label><label><input type="checkbox" data-field="video" ${player.video ? 'checked' : ''}></label></div>`).join('') || '<p>Nessun player disponibile</p>'
  return true
}

async function loadControl4() {
  const response = await fetch(apiUrl('../api/installer/control4'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#control4-host').value = data.host || '192.168.3.10'
  $('#control4-username').value = data.username || ''
  $('#control4-password').placeholder = data.password_configured ? 'Password già salvata' : 'Password Control4'
}

async function loadSourceIcons() {
  const response = await fetch(apiUrl('../api/installer/media-source-icons'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  $('#source-icon-list').innerHTML = data.items.map((source) => `<div class="source-icon-row" data-source-id="${Number(source.source_id)}"><img src="${apiUrl(`../api/control4/source-icon/${Number(source.source_id)}?admin=${Date.now()}`)}" alt="" onerror="this.classList.add('missing')"><b>${esc(source.name)}</b><label>CAMBIA<input type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label><button type="button" data-source-reset ${source.custom ? '' : 'disabled'}>RIPRISTINA</button></div>`).join('') || '<p>Nessuna sorgente disponibile</p>'
}

function control4Payload() { return { host: $('#control4-host').value.trim(), username: $('#control4-username').value.trim(), password: $('#control4-password').value } }

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

$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const response = await fetch(apiUrl('../api/installer/login'), { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('#installer-password').value}) }); if (!response.ok) throw new Error((await response.json()).detail); $('#installer-password').value=''; await loadPlayers() } catch(error){ notice(error.message) } })
$('#media-tool').addEventListener('click', async () => { try { if (await loadPlayers()) { await loadSourceIcons(); $('#media-config').hidden = false } } catch(error){ notice(error.message) } })
$('#control4-tool').addEventListener('click', async () => { try { await loadControl4(); $('#control4-config').hidden=false } catch(error){ notice(error.message) } })
$('#control4-back').addEventListener('click', () => { $('#control4-config').hidden=true })
$('#control4-save').addEventListener('click', (event) => sendControl4('', event.currentTarget))
$('#control4-form').addEventListener('submit', (event) => { event.preventDefault(); sendControl4('/test', $('#control4-test')) })
$('#media-back').addEventListener('click', () => { $('#media-config').hidden = true })
$('#logout').addEventListener('click', async () => { await fetch(apiUrl('../api/installer/logout'), {method:'POST'}); $('#admin-tools').hidden=true; $('#admin-locked').hidden=false })
$('#save-players').addEventListener('click', async (event) => { event.currentTarget.disabled=true; try { const players={}; document.querySelectorAll('.player-row').forEach((row, order) => { players[row.dataset.player]={...Object.fromEntries([...row.querySelectorAll('input')].map((input)=>[input.dataset.field,input.checked])),order} }); const response=await fetch(apiUrl('../api/installer/media-players'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({players})}); if(!response.ok) throw new Error((await response.json()).detail); notice('Configurazione salvata'); setTimeout(()=>location.href='./',700) } catch(error){notice(error.message)} finally{event.currentTarget.disabled=false} })
$('#player-list').addEventListener('change',(event)=>{const row=event.target.closest('.player-row');if(!row)return;const visible=row.querySelector('[data-field=visible]');const audio=row.querySelector('[data-field=audio]');const video=row.querySelector('[data-field=video]');if(event.target===visible&&!visible.checked){audio.checked=false;video.checked=false}if((event.target===audio||event.target===video)&&event.target.checked)visible.checked=true})
$('#source-icon-list').addEventListener('change', async (event) => { const input=event.target.closest('input[type=file]');if(!input?.files[0])return;const file=input.files[0];if(file.size>500000)return notice('Icona superiore a 500 KB');const row=input.closest('[data-source-id]');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)});try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({mime:file.type,data})});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona sostituita');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#source-icon-list').addEventListener('click', async (event) => { const button=event.target.closest('[data-source-reset]');if(!button)return;const row=button.closest('[data-source-id]');try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'DELETE'});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona ripristinata');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#background-tool').addEventListener('click',async()=>{try{await loadBackgrounds();$('#background-config').hidden=false}catch(error){notice(error.message)}})
$('#background-back').addEventListener('click',()=>{$('#background-config').hidden=true})
$('#background-room').addEventListener('change',renderBackgrounds)
$('#background-presets').addEventListener('click',async(event)=>{const preset=event.target.closest('[data-background-preset]')?.dataset.backgroundPreset;if(preset)try{await saveBackground({mode:'preset',preset})}catch(error){notice(error.message)};if(event.target.closest('[data-background-photo]'))$('#background-file').click()})
$('#background-inherit').addEventListener('click',async()=>{try{await saveBackground({mode:'inherit'})}catch(error){notice(error.message)}})
$('#background-file').addEventListener('change',async(event)=>{const file=event.target.files[0];if(!file)return;if(file.size>4000000)return notice('Foto superiore a 4 MB');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)});try{await saveBackground({mode:'custom',mime:file.type,data})}catch(error){notice(error.message)}finally{event.target.value=''}})
let draggedRow = null
$('#player-list').addEventListener('pointerdown', (event) => { const handle=event.target.closest('.drag-handle'); if(!handle)return; draggedRow=handle.closest('.player-row'); draggedRow.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
$('#player-list').addEventListener('pointermove', (event) => { if(!draggedRow)return; const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('.player-row'); if(!target||target===draggedRow)return; const rect=target.getBoundingClientRect(); $('#player-list').insertBefore(draggedRow,event.clientY<rect.top+rect.height/2?target:target.nextSibling) })
const finishDrag = () => { if(draggedRow)draggedRow.classList.remove('dragging'); draggedRow=null }
$('#player-list').addEventListener('pointerup', finishDrag)
$('#player-list').addEventListener('pointercancel', finishDrag)
loadPlayers().catch(()=>{})
loadToolsBackground().catch(()=>{})
