const $ = (selector) => document.querySelector(selector)
const esc = (value) => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML }
const apiUrl = (path) => new URL(path, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()

function notice(message) { $('#tools-notice').textContent = message; $('#tools-notice').hidden = false; setTimeout(() => { $('#tools-notice').hidden = true }, 3500) }

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
      $('#control4-result').innerHTML = `<b>Connessione riuscita</b><span>Controller: ${esc(data.controller)}</span><span>OS: ${esc(data.os_version || 'non rilevata')}</span><span>Director locale: ${esc(data.local_host)}</span><span>Stanze rilevate: ${Number(data.rooms) || 0}</span>${data.room_names?.length ? `<span>${data.room_names.map(esc).join(' · ')}</span>` : ''}`
      $('#control4-result').hidden = false
    } else notice('Configurazione Control4 salvata')
  } catch (error) { notice(error.message) } finally { button.disabled = false }
}

$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const response = await fetch(apiUrl('../api/installer/login'), { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('#installer-password').value}) }); if (!response.ok) throw new Error((await response.json()).detail); $('#installer-password').value=''; await loadPlayers() } catch(error){ notice(error.message) } })
$('#media-tool').addEventListener('click', async () => { try { if (await loadPlayers()) $('#media-config').hidden = false } catch(error){ notice(error.message) } })
$('#control4-tool').addEventListener('click', async () => { try { await loadControl4(); $('#control4-config').hidden=false } catch(error){ notice(error.message) } })
$('#control4-back').addEventListener('click', () => { $('#control4-config').hidden=true })
$('#control4-save').addEventListener('click', (event) => sendControl4('', event.currentTarget))
$('#control4-form').addEventListener('submit', (event) => { event.preventDefault(); sendControl4('/test', $('#control4-test')) })
$('#media-back').addEventListener('click', () => { $('#media-config').hidden = true })
$('#logout').addEventListener('click', async () => { await fetch(apiUrl('../api/installer/logout'), {method:'POST'}); $('#admin-tools').hidden=true; $('#admin-locked').hidden=false })
$('#save-players').addEventListener('click', async (event) => { event.currentTarget.disabled=true; try { const players={}; document.querySelectorAll('.player-row').forEach((row, order) => { players[row.dataset.player]={...Object.fromEntries([...row.querySelectorAll('input')].map((input)=>[input.dataset.field,input.checked])),order} }); const response=await fetch(apiUrl('../api/installer/media-players'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({players})}); if(!response.ok) throw new Error((await response.json()).detail); notice('Configurazione salvata'); setTimeout(()=>location.href='./',700) } catch(error){notice(error.message)} finally{event.currentTarget.disabled=false} })
$('#player-list').addEventListener('change',(event)=>{const row=event.target.closest('.player-row');if(!row)return;const visible=row.querySelector('[data-field=visible]');const audio=row.querySelector('[data-field=audio]');const video=row.querySelector('[data-field=video]');if(event.target===visible&&!visible.checked){audio.checked=false;video.checked=false}if((event.target===audio||event.target===video)&&event.target.checked)visible.checked=true})
let draggedRow = null
$('#player-list').addEventListener('pointerdown', (event) => { const handle=event.target.closest('.drag-handle'); if(!handle)return; draggedRow=handle.closest('.player-row'); draggedRow.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
$('#player-list').addEventListener('pointermove', (event) => { if(!draggedRow)return; const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('.player-row'); if(!target||target===draggedRow)return; const rect=target.getBoundingClientRect(); $('#player-list').insertBefore(draggedRow,event.clientY<rect.top+rect.height/2?target:target.nextSibling) })
const finishDrag = () => { if(draggedRow)draggedRow.classList.remove('dragging'); draggedRow=null }
$('#player-list').addEventListener('pointerup', finishDrag)
$('#player-list').addEventListener('pointercancel', finishDrag)
loadPlayers().catch(()=>{})
