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
  $('#player-list').innerHTML = data.items.map((player) => `<div class="player-row" data-player="${esc(player.registry_id)}"><span><b>${esc(player.name)}</b><small>${esc(player.entity_id)}</small></span><label><input type="checkbox" data-field="visible" ${player.visible ? 'checked' : ''}></label><label><input type="checkbox" data-field="audio" ${player.audio ? 'checked' : ''}></label><label><input type="checkbox" data-field="video" ${player.video ? 'checked' : ''}></label></div>`).join('') || '<p>Nessun player disponibile</p>'
  return true
}

$('#login-form').addEventListener('submit', async (event) => { event.preventDefault(); try { const response = await fetch(apiUrl('../api/installer/login'), { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('#installer-password').value}) }); if (!response.ok) throw new Error((await response.json()).detail); $('#installer-password').value=''; await loadPlayers() } catch(error){ notice(error.message) } })
$('#media-tool').addEventListener('click', async () => { try { if (await loadPlayers()) $('#media-config').hidden = false } catch(error){ notice(error.message) } })
$('#media-back').addEventListener('click', () => { $('#media-config').hidden = true })
$('#logout').addEventListener('click', async () => { await fetch(apiUrl('../api/installer/logout'), {method:'POST'}); $('#admin-tools').hidden=true; $('#admin-locked').hidden=false })
$('#save-players').addEventListener('click', async (event) => { event.currentTarget.disabled=true; try { const players={}; document.querySelectorAll('.player-row').forEach((row) => { players[row.dataset.player]=Object.fromEntries([...row.querySelectorAll('input')].map((input)=>[input.dataset.field,input.checked])) }); const response=await fetch(apiUrl('../api/installer/media-players'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({players})}); if(!response.ok) throw new Error((await response.json()).detail); notice('Configurazione salvata'); setTimeout(()=>location.href='./',700) } catch(error){notice(error.message)} finally{event.currentTarget.disabled=false} })
$('#player-list').addEventListener('change',(event)=>{const row=event.target.closest('.player-row');if(!row)return;const visible=row.querySelector('[data-field=visible]');const audio=row.querySelector('[data-field=audio]');const video=row.querySelector('[data-field=video]');if(event.target===visible&&!visible.checked){audio.checked=false;video.checked=false}if((event.target===audio||event.target===video)&&event.target.checked)visible.checked=true})
loadPlayers().catch(()=>{})
