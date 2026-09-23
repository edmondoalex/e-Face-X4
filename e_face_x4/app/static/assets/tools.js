const $ = (selector) => document.querySelector(selector)
const esc = (value) => { const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML }
const apiUrl = (path) => new URL(path, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()
const deviceScope = (() => { const key='eface-device-scope-v1'; let value=localStorage.getItem(key); if(!/^[A-Za-z0-9_-]{16,64}$/.test(value||'')){value=(crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`).replaceAll('-','');localStorage.setItem(key,value)} return value })()
const appearanceOptions = (options={}) => ({...options,headers:{...(options.headers||{}),'X-Eface-Device':deviceScope}})
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

const musicAccountsCard = document.createElement('button')
musicAccountsCard.id = 'music-accounts-tool'
musicAccountsCard.type = 'button'
musicAccountsCard.className = 'tool-card'
musicAccountsCard.innerHTML = '<span>♫</span><div><b>Account musicali</b><small>Collega e gestisci le sorgenti</small></div><i>›</i>'
$('#tools-user-section .tools-grid').append(musicAccountsCard)
const musicAccountsPanel = document.createElement('section')
musicAccountsPanel.id = 'music-accounts-config'
musicAccountsPanel.className = 'media-config music-accounts-config'
musicAccountsPanel.hidden = true
musicAccountsPanel.innerHTML = '<header><button type="button" id="music-accounts-back" aria-label="Torna a Strumenti">‹</button><div><small>STRUMENTI</small><h2>Account musicali</h2></div></header><p>Gestisci qui gli accessi alle sorgenti Control4, senza aprire l’app Control4.</p><div id="music-accounts-list" class="music-accounts-list"></div>'
$('.tools-shell').append(musicAccountsPanel)

musicAccountsCard.addEventListener('click', async () => {
  musicAccountsPanel.hidden = false
  $('#music-accounts-list').innerHTML = '<p>Caricamento servizi…</p>'
  try {
    const response = await fetch(apiUrl('../api/control4/music/account-services'), { cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    $('#music-accounts-list').innerHTML = (data.services || []).map((service) => {
      const status = service.status === 'ready' ? 'Collegamento disponibile' : service.status === 'test' ? 'Flusso a link da verificare sul controller' : service.status === 'external' ? 'Accesso gestito dal servizio' : 'Collegamento in preparazione'
      const key = service.name.toLowerCase() === 'amazon music' ? 'amazon' : service.name.toLowerCase() === 'tidal' ? 'tidal' : service.name.toLowerCase() === 'tunein' ? 'tunein' : ''
      const action = key && ['ready', 'test'].includes(service.status) ? `<button type="button" data-music-account="${key}">${service.status === 'test' ? 'Prova collegamento' : 'Ricollega'}</button>` : ''
      return `<div class="music-account-row"><div><strong>${esc(service.name)}</strong><small>${status}</small></div>${action}</div>`
    }).join('') || '<p>Nessun servizio musicale Control4 trovato.</p>'
  } catch (error) { $('#music-accounts-list').innerHTML = `<p>${esc(error.message)}</p>` }
})
$('#music-accounts-back').addEventListener('click', () => { musicAccountsPanel.hidden = true })
musicAccountsPanel.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-music-account]')
  if (!button) return
  const service = ['tidal', 'tunein'].includes(button.dataset.musicAccount) ? button.dataset.musicAccount : 'amazon'
  button.disabled = true
  try {
    const response = await fetch(apiUrl(`../api/control4/music/${service}/auth-link`), { method: 'POST', cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    const url = new URL(data.url)
    if (url.protocol !== 'https:' || url.hostname !== 'link.ctrl4.co') throw new Error('Link musicale non valido')
    window.location.assign(url.href)
  } catch (error) { notice(error.message); button.disabled = false }
})

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
  ensureSkyqPanel()
  const response = await fetch(apiUrl('../api/installer/media-players'), { cache: 'no-store' })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`)
  const data = await response.json()
  const skyq = data.skyq || {}
  $('#skyq-enabled').checked = Boolean(skyq.enabled)
  $('#skyq-host').value = skyq.host || ''
  $('#skyq-name').value = skyq.name || 'Sky Q'
  $('#skyq-control4-room').value = Number(skyq.control4_room_id || 0)
  $('#skyq-control4-source').value = Number(skyq.control4_source_id || 0)
  $('#skyq-command-provider').value = 'native'
  const selectedApps = new Set((skyq.services || []).map(service => String(service).toLocaleLowerCase()))
  const appRanks = new Map((skyq.app_order || []).map((title, index) => [String(title).toLocaleLowerCase(), index]))
  const detectedApps = [...(data.skyq_apps || [])].sort((a, b) => (appRanks.get(String(a.title).toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER) - (appRanks.get(String(b.title).toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER) || String(a.title).localeCompare(String(b.title), 'it'))
  const fallbackIcon = title => /netflix/i.test(title) ? 'netflix' : /spotify/i.test(title) ? 'spotify' : /youtube/i.test(title) ? 'youtube' : /apple/i.test(title) ? 'apple' : /amazon|prime/i.test(title) ? 'amazon' : 'television-play'
  $('#skyq-services').innerHTML = detectedApps.map(app => `<label data-skyq-app="${esc(app.title)}" data-skyq-id="${esc(app.id)}" class="${selectedApps.has(String(app.title).toLocaleLowerCase()) ? 'selected' : ''}"><button type="button" class="skyq-app-drag" aria-label="Trascina ${esc(app.title)}" title="Trascina per riordinare">☰</button><span class="skyq-app-icon"><i class="mdi-mask" style="--icon:url('${apiUrl(`../api/icons/mdi/${fallbackIcon(app.title)}.svg`)}')"></i><img src="${apiUrl(`../api/skyq/apps/${encodeURIComponent(app.id)}/icon?v=${app.custom ? Date.now() : 'auto'}`)}" alt="" loading="lazy" onload="this.parentElement.classList.add('loaded')" onerror="this.hidden=true"></span><strong>${esc(app.title)}</strong><span class="skyq-icon-actions"><button type="button" data-skyq-icon-upload>CAMBIA</button>${app.custom ? '<button type="button" data-skyq-icon-reset>RIPRISTINA</button>' : ''}</span><input type="checkbox" value="${esc(app.title)}" ${selectedApps.has(String(app.title).toLocaleLowerCase()) ? 'checked' : ''}></label>`).join('') || '<p class="skyq-apps-empty">Nessuna app letta. Verifica che Sky Q sia acceso, poi premi SALVA E VERIFICA DIRETTA.</p>'
  $('#player-list').innerHTML = data.items.map((player) => `<div class="player-row ${player.device_type === 'echo' ? 'player-echo' : ''}" data-player="${esc(player.registry_id)}"><button class="drag-handle" type="button" aria-label="Trascina ${esc(player.original_name)}">☰</button><span class="player-identity"><b>${esc(player.original_name)}</b><small>${esc(player.device_type === 'echo' ? 'ECHO' : 'MEDIA PLAYER')} · ${esc(player.entity_id)}</small><span class="player-fields"><label>Nome e-Face<input type="text" maxlength="80" data-field="name" value="${esc(player.name)}" placeholder="${esc(player.original_name)}"></label><label>Stanza<input type="text" maxlength="80" data-field="room" value="${esc(player.room)}" placeholder="${esc(player.original_room)}"></label></span></span><label title="Mostra"><input type="checkbox" data-field="visible" ${player.visible ? 'checked' : ''}></label><label title="Audio"><input type="checkbox" data-field="audio" ${player.audio ? 'checked' : ''}></label><label title="Video"><input type="checkbox" data-field="video" ${player.video ? 'checked' : ''}></label><label title="TTS"><input type="checkbox" data-field="tts" ${player.provider === 'evoice' && player.tts_available && player.tts ? 'checked' : ''} ${player.provider === 'evoice' && player.tts_available ? '' : 'disabled'}></label></div>`).join('') || '<p>Nessun player disponibile</p>'
  return true
}

function ensureSkyqPanel() {
  if ($('#skyq-config')) return
  document.head.insertAdjacentHTML('beforeend', '<style>.skyq-form{margin:18px 0}.skyq-apps-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:18px}.skyq-apps-actions{display:flex;gap:8px}.skyq-apps-actions button{padding:7px 11px;font-size:12px}.skyq-services{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin-top:10px}.skyq-services label{position:relative;display:grid;grid-template-columns:24px 48px minmax(0,1fr);grid-template-rows:auto auto;align-items:center;gap:4px 8px;min-height:76px;padding:8px 11px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.055);cursor:pointer;transition:.15s ease}.skyq-services label:active{transform:scale(.97)}.skyq-services label.dragging{z-index:2;opacity:.58;border-color:var(--cyan);transform:scale(.97)}.skyq-services label.selected{border-color:var(--cyan);background:rgba(75,210,240,.12);box-shadow:0 0 16px rgba(75,210,240,.12)}.skyq-app-drag{grid-row:1/3;width:24px;min-width:24px;height:48px;padding:0;border:0;background:transparent;color:#9ba8ab;cursor:grab;touch-action:none}.skyq-app-drag:active{cursor:grabbing}.skyq-app-icon{position:relative;display:block;grid-row:1/3;width:48px;height:48px;padding:0!important;border-radius:9px;background:#181b1d}.skyq-app-icon i,.skyq-app-icon img{position:absolute;inset:5px;width:38px;height:38px}.skyq-app-icon i{background:#dce6e8}.skyq-app-icon img{object-fit:contain}.skyq-app-icon.loaded i{display:none}.skyq-services strong{align-self:end;padding-right:15px;overflow:hidden}.skyq-icon-actions{display:flex;gap:5px;padding:0!important}.skyq-icon-actions button{min-height:24px;padding:3px 7px;border:1px solid #ffffff28;border-radius:6px;background:#ffffff0b;color:#bfcacc;font-size:9px}.skyq-icon-actions button:active{color:var(--cyan);border-color:var(--cyan)}.skyq-services input{position:absolute;right:8px;top:8px;width:17px;height:17px;accent-color:var(--cyan)}.skyq-apps-empty{grid-column:1/-1;color:var(--muted)}.skyq-inventory{margin-top:22px;padding-top:18px;border-top:1px solid var(--line)}.skyq-inventory-head,.skyq-inventory-tabs{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.skyq-inventory-tabs{justify-content:flex-start;margin:14px 0}.skyq-inventory-tabs button.active{border-color:var(--cyan);color:var(--cyan)}.skyq-inventory-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px;margin:12px 0}.skyq-inventory-summary div{padding:12px;border:1px solid var(--line);border-radius:10px;background:#ffffff09}.skyq-inventory-summary b{display:block;font-size:25px;color:var(--cyan)}.skyq-inventory-tools{display:flex;gap:8px;margin-bottom:10px}.skyq-inventory-tools input{min-width:220px;flex:1}.skyq-inventory-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(245px,1fr));gap:8px;max-height:560px;overflow:auto}.skyq-data-card{display:grid;grid-template-columns:54px minmax(0,1fr);gap:10px;min-height:74px;padding:9px;border:1px solid var(--line);border-radius:10px;background:#ffffff08;text-align:left}.skyq-data-card img{width:54px;height:54px;object-fit:contain;border-radius:7px;background:#111719}.skyq-data-card div{min-width:0}.skyq-data-card b,.skyq-data-card small{display:block;overflow:hidden;text-overflow:ellipsis}.skyq-data-card small{color:var(--muted)}.skyq-data-card p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:4px 0 0;font-size:11px;color:#bac4c6}.skyq-channel-card{cursor:pointer}.skyq-channel-card:hover{border-color:var(--cyan)}@media(max-width:650px){.skyq-inventory-list{grid-template-columns:1fr}.skyq-inventory-tools{flex-direction:column}}</style>')
  document.body.insertAdjacentHTML('beforeend', `<section id="skyq-config" class="media-config" hidden><header><button id="skyq-back">&#8249;</button><div><h2>Configurazione Sky Q</h2></div></header><form id="skyq-form" class="admin-form skyq-form"><div class="admin-info"><b>Collegamento diretto e-Face → Sky Q</b><p>e-Face legge direttamente il decoder in LAN: programma, canale, descrizione, app e copertina. e-Control non viene utilizzato. Per ora i comandi restano affidati alla zona Control4 associata.</p></div><label class="glow-option"><span>Abilita Sky Q nativo</span><input id="skyq-enabled" type="checkbox"></label><div class="admin-form-grid"><label>Indirizzo IPv4 Sky Q<input id="skyq-host" inputmode="decimal" placeholder="192.168.10.64"></label><label>Nome decoder<input id="skyq-name" maxlength="80" placeholder="Sky Q Sala"></label><label>ID stanza Control4<input id="skyq-control4-room" type="number" min="0" placeholder="0 = associazione automatica"></label><label>ID sorgente Control4<input id="skyq-control4-source" type="number" min="0" placeholder="0 = sorgente con nome Sky"></label></div><label>Comandi<select id="skyq-command-provider"><option value="control4">Control4 (attuale)</option><option value="native">Sky Q diretto (futuro)</option></select></label><div class="skyq-apps-head"><b>App Sky Q da mostrare</b><span class="skyq-apps-actions"><button id="skyq-select-all" type="button" class="secondary">TUTTE</button><button id="skyq-select-none" type="button" class="secondary">NESSUNA</button></span></div><div id="skyq-services" class="skyq-services"></div><div class="admin-form-actions"><button type="submit">SALVA SKY Q</button><button id="skyq-test" type="button" class="secondary">SALVA E VERIFICA DIRETTA</button><button id="skyq-players" type="button" class="secondary">PLAYER E ICONE</button></div><div id="skyq-result" class="admin-status" role="status">Sky Q non ancora verificato.</div><section class="skyq-inventory"><div class="skyq-inventory-head"><div><b>Dati disponibili dal decoder</b><small id="skyq-inventory-date"></small></div><button id="skyq-download-all" type="button" class="secondary">SCARICA / AGGIORNA TUTTO</button></div><div id="skyq-inventory-summary" class="skyq-inventory-summary"></div><div class="skyq-inventory-tabs"><button type="button" data-skyq-tab="channels" class="secondary active">CANALI</button><button type="button" data-skyq-tab="recordings" class="secondary">REGISTRAZIONI</button><button type="button" data-skyq-tab="apps" class="secondary">APP</button><button type="button" data-skyq-tab="guide" class="secondary">GUIDA CANALE</button></div><div class="skyq-inventory-tools"><input id="skyq-inventory-search" type="search" placeholder="Cerca nei dati Sky Q"><input id="skyq-guide-day" type="date"></div><div id="skyq-inventory-list" class="skyq-inventory-list"><p>Premi SCARICA / AGGIORNA TUTTO.</p></div></section></form></section>`)
  $('#skyq-back').addEventListener('click', () => { $('#skyq-config').hidden=true })
  $('#skyq-command-provider').closest('label').hidden = true
  const selectApps = checked => $('#skyq-services').querySelectorAll('input').forEach(input => { input.checked = checked; input.closest('label').classList.toggle('selected', checked) })
  $('#skyq-select-all').addEventListener('click', () => selectApps(true))
  $('#skyq-select-none').addEventListener('click', () => selectApps(false))
  $('#skyq-services').addEventListener('change', event => event.target.closest('label')?.classList.toggle('selected', event.target.checked))
  let draggedApp = null
  $('#skyq-services').addEventListener('pointerdown', event => { const handle=event.target.closest('.skyq-app-drag');if(!handle)return;draggedApp=handle.closest('[data-skyq-app]');draggedApp.classList.add('dragging');handle.setPointerCapture(event.pointerId);event.preventDefault() })
  $('#skyq-services').addEventListener('pointermove', event => { if(!draggedApp)return;const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-skyq-app]');if(!target||target===draggedApp||target.parentElement!==$('#skyq-services'))return;const rect=target.getBoundingClientRect();const before=event.clientY<rect.top+rect.height/2||(event.clientY<=rect.bottom&&event.clientX<rect.left+rect.width/2);$('#skyq-services').insertBefore(draggedApp,before?target:target.nextSibling) })
  const finishAppDrag=()=>{if(!draggedApp)return;draggedApp.classList.remove('dragging');draggedApp=null}
  $('#skyq-services').addEventListener('pointerup',finishAppDrag)
  $('#skyq-services').addEventListener('pointercancel',finishAppDrag)
  $('#skyq-services').addEventListener('click', async event => {
    const upload = event.target.closest('[data-skyq-icon-upload]')
    const reset = event.target.closest('[data-skyq-icon-reset]')
    if (!upload && !reset) return
    event.preventDefault(); event.stopPropagation()
    const card = event.target.closest('[data-skyq-id]')
    const appId = card?.dataset.skyqId
    if (!appId) return
    try {
      if (reset) {
        const response = await fetch(apiUrl(`../api/installer/skyq/apps/${encodeURIComponent(appId)}/icon`), {method:'DELETE'})
        if (!response.ok) throw new Error((await response.json().catch(()=>({}))).detail || `HTTP ${response.status}`)
        notice('Icona Sky Q ripristinata'); await loadPlayers(); return
      }
      const input = document.createElement('input'); input.type='file'; input.accept='image/png,image/jpeg,image/webp,image/gif'
      input.addEventListener('change', async () => {
        const file=input.files?.[0]; if(!file)return
        if(file.size>500000)return notice('Icona superiore a 500 KB')
        const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)})
        const response=await fetch(apiUrl(`../api/installer/skyq/apps/${encodeURIComponent(appId)}/icon`),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({mime:file.type,data})})
        if(!response.ok)throw new Error((await response.json().catch(()=>({}))).detail||`HTTP ${response.status}`)
        notice('Icona Sky Q salvata'); await loadPlayers()
      },{once:true}); input.click()
    } catch(error) { notice(error.message) }
  })
  $('#skyq-form .admin-info p').textContent = 'e-Face legge metadati e invia tutti i tasti del telecomando direttamente al decoder in LAN. e-Control e Control4 non sono nel percorso dei comandi Sky Q; il volume della stanza resta su Control4.'
  $('#skyq-players').addEventListener('click', async () => { try { await loadSourceIcons(); $('#media-config').hidden=false } catch(error){notice(error.message)} })
  $('#skyq-form').addEventListener('submit', async (event) => { event.preventDefault(); const button=event.submitter;button.disabled=true;try{await saveSkyq(false)}catch(error){notice(error.message)}finally{button.disabled=false} })
  $('#skyq-test').addEventListener('click', async (event) => { const button=event.currentTarget;button.disabled=true;try{await saveSkyq(true);notice('Sky Q collegato direttamente a e-Face')}catch(error){notice(error.message)}finally{button.disabled=false} })
  $('#skyq-guide-day').value = new Date().toISOString().slice(0,10)
  $('#skyq-download-all').addEventListener('click', event => loadSkyqInventory(true, event.currentTarget))
  $('#skyq-inventory-search').addEventListener('input', renderSkyqInventory)
  document.querySelectorAll('[data-skyq-tab]').forEach(button => button.addEventListener('click', () => { skyqInventoryTab=button.dataset.skyqTab;document.querySelectorAll('[data-skyq-tab]').forEach(item=>item.classList.toggle('active',item===button));renderSkyqInventory() }))
  $('#skyq-guide-day').addEventListener('change', () => { if(skyqGuideSid) loadSkyqGuide(skyqGuideSid) })
}

let skyqInventoryData = null
let skyqInventoryTab = 'channels'
let skyqGuideItems = []
let skyqGuideSid = ''
const skyqImage = fingerprint => fingerprint ? `<img src="${apiUrl(`../api/media/skyq/artwork?fingerprint=${encodeURIComponent(fingerprint)}`)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : '<span></span>'
function renderSkyqInventory() {
  if (!skyqInventoryData) return
  const query=$('#skyq-inventory-search').value.trim().toLocaleLowerCase();let items=skyqInventoryTab==='guide'?skyqGuideItems:(skyqInventoryData[skyqInventoryTab]||[])
  items=items.filter(item=>!query||Object.values(item).some(value=>String(value??'').toLocaleLowerCase().includes(query)))
  if(skyqInventoryTab==='channels') $('#skyq-inventory-list').innerHTML=items.map(item=>`<button type="button" class="skyq-data-card skyq-channel-card" data-guide-sid="${esc(item.sid)}">${skyqImage(item.artwork_fingerprint)}<div><b>${esc(item.number)} · ${esc(item.name)}</b><small>${esc(item.type)} · SID ${esc(item.sid)} · ${esc(item.format)}</small><p>Apri la guida del canale</p></div></button>`).join('')||'<p>Nessun canale trovato.</p>'
  else if(skyqInventoryTab==='recordings') $('#skyq-inventory-list').innerHTML=items.map(item=>`<article class="skyq-data-card">${skyqImage(item.artwork_fingerprint)}<div><b>${esc(item.title)}</b><small>${esc(item.channel)} · ${esc(item.status)} · ${esc(item.source)}</small><p>${esc(item.description)}</p></div></article>`).join('')||'<p>Nessuna registrazione trovata.</p>'
  else if(skyqInventoryTab==='apps') $('#skyq-inventory-list').innerHTML=items.map(item=>`<article class="skyq-data-card"><img src="${apiUrl(`../api/skyq/apps/${encodeURIComponent(item.id)}/icon`)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"><div><b>${esc(item.title)}</b><small>${esc(item.id)}</small></div></article>`).join('')||'<p>Nessuna app trovata.</p>'
  else $('#skyq-inventory-list').innerHTML=items.map(item=>`<article class="skyq-data-card">${skyqImage(item.artwork_fingerprint)}<div><b>${item.start?esc(new Date(item.start).toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'}))+' · ':''}${esc(item.title)}</b><small>${esc(item.channel)}${item.season?` · S${esc(item.season)} E${esc(item.episode)}`:''}</small><p>${esc(item.description)}</p></div></article>`).join('')||'<p>Nessun programma trovato per questa data.</p>'
  $('#skyq-inventory-list').querySelectorAll('[data-guide-sid]').forEach(button=>button.addEventListener('click',()=>loadSkyqGuide(button.dataset.guideSid)))
}
async function loadSkyqInventory(refresh=false, button=null) {
  if(button)button.disabled=true;$('#skyq-inventory-list').innerHTML='<p>Lettura completa dal decoder in corso…</p>'
  try{const response=await fetch(apiUrl(`../api/installer/skyq/inventory${refresh?'?refresh=true':''}`),{cache:'no-store'});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);skyqInventoryData=data;const summary=data.summary||{};$('#skyq-inventory-summary').innerHTML=`<div><b>${Number(summary.channels)||0}</b><span>Canali</span></div><div><b>${Number(summary.recordings)||0}</b><span>Registrazioni</span></div><div><b>${Number(summary.apps)||0}</b><span>App</span></div><div><b>${data.quota?.used??'—'}</b><span>Spazio usato${data.quota?.max!=null?` / ${esc(data.quota.max)}`:''}</span></div>`;$('#skyq-inventory-date').textContent=data.generated_at?`Aggiornato ${new Date(data.generated_at).toLocaleString('it-IT')}`:'';renderSkyqInventory()}catch(error){$('#skyq-inventory-list').innerHTML=`<p>${esc(error.message)}</p>`}finally{if(button)button.disabled=false}
}
async function loadSkyqGuide(sid){skyqGuideSid=sid;skyqInventoryTab='guide';document.querySelectorAll('[data-skyq-tab]').forEach(item=>item.classList.toggle('active',item.dataset.skyqTab==='guide'));$('#skyq-inventory-list').innerHTML='<p>Caricamento guida…</p>';try{const day=$('#skyq-guide-day').value;const response=await fetch(apiUrl(`../api/installer/skyq/guide?sid=${encodeURIComponent(sid)}&day=${encodeURIComponent(day)}`),{cache:'no-store'});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);skyqGuideItems=data.items||[];renderSkyqInventory()}catch(error){$('#skyq-inventory-list').innerHTML=`<p>${esc(error.message)}</p>`}}

function skyqPayload() {
  return { enabled: $('#skyq-enabled').checked, host: $('#skyq-host').value.trim(), name: $('#skyq-name').value.trim(), control4_room_id: Number($('#skyq-control4-room').value || 0), control4_source_id: Number($('#skyq-control4-source').value || 0), command_provider: 'native', services: [...$('#skyq-services').querySelectorAll('input:checked')].map(input => input.value), app_order: [...$('#skyq-services').querySelectorAll('[data-skyq-app]')].map(item => item.dataset.skyqApp) }
}

async function saveSkyq(test = false) {
  const response = await fetch(apiUrl(`../api/installer/skyq${test ? '/test' : ''}`), {method: test ? 'POST' : 'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(skyqPayload())})
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
  if (test) {
    const device = data.device || {}
    $('#skyq-result').innerHTML = `<b>Collegamento diretto riuscito</b><span>${esc(device.hardwareName || device.modelNumber || 'Sky Q')} · ${esc(device.deviceType || '')}</span><span>${esc(data.channel || data.app || data.power || 'Online')}${data.channel_number ? ` · canale ${esc(data.channel_number)}` : ''}</span>${data.title ? `<span>In onda: ${esc(data.title)}</span>` : ''}`
    await loadPlayers()
  } else notice('Configurazione Sky Q salvata')
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
  $('#source-icon-list').innerHTML = data.items.map((source) => `<div class="source-icon-row ${source.hidden ? 'source-icon-hidden' : ''}" data-source-id="${Number(source.source_id)}"><img src="${apiUrl(`../api/control4/source-icon/${Number(source.source_id)}?admin=${Date.now()}`)}" alt="" onerror="this.classList.add('missing')"><b>${esc(source.name)}</b><label>CAMBIA<input type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label><button type="button" data-source-reset ${source.custom ? '' : 'disabled'}>RIPRISTINA ICONA</button><button type="button" data-source-visibility data-hidden="${source.hidden ? 'true' : 'false'}">${source.hidden ? 'MOSTRA' : 'NASCONDI'}</button></div>`).join('') || '<p>Nessuna sorgente disponibile</p>'
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
$('#skyq-tool').addEventListener('click', async () => { try { if (await loadPlayers()) $('#skyq-config').hidden = false } catch(error){ notice(error.message) } })
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
$('#media-back').addEventListener('click', () => { $('#media-config').hidden = true })
$('#logout').addEventListener('click', async () => { await fetch(apiUrl('../api/installer/logout'), {method:'POST'}); const status=await fetch(apiUrl('../api/auth/status')).then((res)=>res.json()); if(status.enabled){await fetch(apiUrl('../api/auth/logout'),{method:'POST'});location.href=apiUrl('../login');return} $('#admin-tools').hidden=true; $('#admin-locked').hidden=false })
$('#save-players').addEventListener('click', async (event) => { event.currentTarget.disabled=true; try { const players={}; document.querySelectorAll('.player-row').forEach((row, order) => { players[row.dataset.player]={...Object.fromEntries([...row.querySelectorAll('input[data-field]')].map((input)=>[input.dataset.field,input.type==='checkbox'?input.checked:input.value.trim()])),order} }); const response=await fetch(apiUrl('../api/installer/media-players'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({players})}); if(!response.ok) throw new Error((await response.json()).detail); notice('Configurazione salvata'); setTimeout(()=>location.href='./',700) } catch(error){notice(error.message)} finally{event.currentTarget.disabled=false} })
$('#player-list').addEventListener('change',(event)=>{const row=event.target.closest('.player-row');if(!row)return;const visible=row.querySelector('[data-field=visible]');const modes=[...row.querySelectorAll('[data-field=audio],[data-field=video],[data-field=tts]')];if(event.target===visible&&!visible.checked)modes.forEach((input)=>{input.checked=false});if(modes.includes(event.target)){if(event.target.checked)visible.checked=true;else if(!modes.some((input)=>input.checked))visible.checked=false}})
$('#source-icon-list').addEventListener('change', async (event) => { const input=event.target.closest('input[type=file]');if(!input?.files[0])return;const file=input.files[0];if(file.size>500000)return notice('Icona superiore a 500 KB');const row=input.closest('[data-source-id]');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',',2)[1]);reader.onerror=reject;reader.readAsDataURL(file)});try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({mime:file.type,data})});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona sostituita');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#source-icon-list').addEventListener('click', async (event) => { const button=event.target.closest('[data-source-reset]');if(!button)return;const row=button.closest('[data-source-id]');try{const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}`),{method:'DELETE'});if(!response.ok)throw new Error((await response.json()).detail);notice('Icona ripristinata');await loadSourceIcons()}catch(error){notice(error.message)} })
$('#source-icon-list').addEventListener('click', async (event) => { const button=event.target.closest('[data-source-visibility]');if(!button)return;const row=button.closest('[data-source-id]');button.disabled=true;try{const hidden=button.dataset.hidden!=='true';const response=await fetch(apiUrl(`../api/installer/media-source-icons/${row.dataset.sourceId}/visibility`),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({hidden})});if(!response.ok)throw new Error((await response.json()).detail);notice(hidden?'Sorgente nascosta in e-Face':'Sorgente visibile in e-Face');await loadSourceIcons()}catch(error){notice(error.message);button.disabled=false} })
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
async function openRoomOrderEditor(){try{await loadRoomOrder();$('#room-order-config').hidden=false}catch(error){notice(error.message)}}
window.efaceOpenRoomOrder=openRoomOrderEditor
$('#room-order-tool').addEventListener('click',openRoomOrderEditor)
$('#room-order-back').addEventListener('click', () => { $('#room-order-config').hidden = true })
let draggedRoom = null
$('#room-order-list').addEventListener('pointerdown', (event) => { const handle = event.target.closest('.room-drag-handle'); if (!handle) return; draggedRoom = handle.closest('.room-order-row'); draggedRoom.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
$('#room-order-list').addEventListener('pointermove', (event) => { if (!draggedRoom) return; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.room-order-row'); if (!target || target === draggedRoom || target.parentElement !== $('#room-order-list')) return; const rect = target.getBoundingClientRect(); $('#room-order-list').insertBefore(draggedRoom, event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling) })
const finishRoomDrag = () => { if (!draggedRoom) return; draggedRoom.classList.remove('dragging'); draggedRoom = null; orderedRooms = [...$('#room-order-list').querySelectorAll('.room-order-row')].map((row) => orderedRooms[Number(row.dataset.index)]); renderRoomOrder() }
$('#room-order-list').addEventListener('pointerup', finishRoomDrag)
$('#room-order-list').addEventListener('pointercancel', finishRoomDrag)
$('#room-order-list').addEventListener('keydown', (event) => { if (!event.target.matches('.room-drag-handle') || !['ArrowUp','ArrowDown'].includes(event.key)) return; event.preventDefault(); const index = Number(event.target.closest('.room-order-row').dataset.index); const other = index + (event.key === 'ArrowUp' ? -1 : 1); if (other < 0 || other >= orderedRooms.length) return; [orderedRooms[index], orderedRooms[other]] = [orderedRooms[other], orderedRooms[index]]; renderRoomOrder(); $('#room-order-list').querySelectorAll('.room-drag-handle')[other]?.focus() })
$('#room-order-save').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({room_order:orderedRooms})}); if (!response.ok) throw new Error((await response.json()).detail); notice('Ordine ambienti salvato'); $('#room-order-config').hidden = true } catch (error) { notice(error.message) } })
const securityLabels = {scenarios:'SCENARI DI INSERIMENTO', areas:'STATO AREE', zones:'ZONE', sensors:'SENSORISTICA', locks:'SERRATURE', cameras:'VIDEOCAMERE'}
let orderedSecurity = Object.keys(securityLabels)
let securityCameras = []
let securitySensors = []
let securityDeviceOrganization = {}
const securityList = $('#security-order-list')
const securitySensorEditor=document.createElement('section');securitySensorEditor.className='security-sensor-order';securitySensorEditor.hidden=true;securityList.after(securitySensorEditor)
function renderSecurityOrder() {
  securityList.innerHTML = orderedSecurity.map((key, index) => `<div class="room-order-row" data-index="${index}"><button type="button" class="drag-handle room-drag-handle" aria-label="Trascina ${securityLabels[key]} per riordinare" title="Trascina per riordinare">☰</button><strong>${securityLabels[key]}</strong>${key==='sensors'?'<button type="button" data-security-sensors-open>APRI ›</button>':''}</div>`).join('')
}
function renderSecuritySensorOrder(){securitySensorEditor.innerHTML=`<header><h3>Ordina Sensoristica</h3><button type="button" data-security-sensors-close>CHIUDI</button></header><p>Trascina i sensori nell’ordine desiderato.</p><div>${securitySensors.map((device,index)=>`<div class="security-sensor-order-row" data-security-sensor-id="${esc(device.id)}" data-sensor-index="${index}"><button type="button" class="sensor-drag-handle" aria-label="Trascina ${esc(device.name)}">☰</button><span><b>${esc(device.name)}</b><small>${esc(device.room||'')}</small></span></div>`).join('')||'<small>Nessun sensore assegnato a Tutta la sicurezza</small>'}</div>`}
function renderSecurityCameras() {
  $('#security-camera-list').innerHTML = securityCameras.map((camera,index)=>{const preview=camera.preview_url||camera.url,entity=/^camera\.[a-z0-9_]+$/.test(preview);return `<div class="security-camera-admin" data-camera-index="${index}"><button type="button" class="drag-handle" data-camera-drag aria-label="Trascina ${esc(camera.name||'videocamera')}">☰</button><div class="security-camera-admin-preview${entity?'':' invalid'}">${entity?`<img src="${apiUrl(`../api/user/security-camera-preview?entity=${encodeURIComponent(preview)}&v=${Date.now()}`)}" alt="Anteprima ${esc(camera.name||'videocamera')}" onerror="this.parentElement.classList.add('invalid');this.parentElement.insertAdjacentText('beforeend','Anteprima non disponibile')">`:'Inserisci entità camera.*'}</div><label>Nome<input data-camera-name maxlength="100" value="${esc(camera.name)}" placeholder="Es. Ingresso"></label><label>Entità anteprima (snapshot)<input data-camera-preview-url maxlength="2000" value="${esc(preview)}" placeholder="camera.nvr_..._ch1"></label><label>Entità video + audio<input data-camera-video-url maxlength="2000" value="${esc(camera.video_url||camera.url)}" placeholder="camera.nvr_..._rtsp_ch1"></label><label>Modalità<select data-camera-mode><option value="snapshot" ${camera.mode==='video'?'':'selected'}>Fotogrammi</option><option value="video" ${camera.mode==='video'?'selected':''}>Video live + audio</option></select></label><button type="button" data-camera-save>SALVA E PROVA</button><button type="button" data-camera-remove aria-label="Elimina videocamera">×</button></div>`}).join('') || '<p>Nessuna videocamera configurata.</p>'
}
const securityStatus=(text,state='')=>{const el=$('#security-save-status');el.textContent=text;el.className=state}
const markSecurityDirty=()=>securityStatus('Modifiche non salvate: premi SALVA E PROVA','dirty')
async function openSecurityOrderEditor(){try{const [response,bootstrapResponse]=await Promise.all([fetch(apiUrl('../api/user/appearance'),{cache:'no-store'}),fetch(apiUrl('../api/bootstrap'),{cache:'no-store'})]);if(!response.ok||!bootstrapResponse.ok)throw new Error('Configurazione sicurezza non disponibile');const [data,bootstrap]=await Promise.all([response.json(),bootstrapResponse.json()]);orderedSecurity=data.security_order||Object.keys(securityLabels);securityCameras=data.security_cameras||[];securityDeviceOrganization=data.device_organization||{};securitySensors=(bootstrap.dashboard?.devices||[]).filter(device=>['sensor','binary_sensor'].includes(device.kind)&&(securityDeviceOrganization[String(device.id)]?.categories||[]).includes('security')).sort((a,b)=>(securityDeviceOrganization[String(a.id)]?.orders?.security??999999)-(securityDeviceOrganization[String(b.id)]?.orders?.security??999999)||String(a.name).localeCompare(String(b.name),'it'));renderSecurityOrder();renderSecuritySensorOrder();renderSecurityCameras();securityStatus('Configurazione caricata');$('#security-order-config').hidden=false}catch(error){notice(error.message)}}
window.efaceOpenSecurityOrder=openSecurityOrderEditor
$('#security-order-tool').addEventListener('click',openSecurityOrderEditor)
$('#security-order-back').addEventListener('click', () => { $('#security-order-config').hidden = true })
let draggedSecurity = null
securityList.addEventListener('pointerdown', (event) => { const handle = event.target.closest('.room-drag-handle'); if (!handle) return; draggedSecurity = handle.closest('.room-order-row'); draggedSecurity.classList.add('dragging'); handle.setPointerCapture(event.pointerId); event.preventDefault() })
securityList.addEventListener('pointermove', (event) => { if (!draggedSecurity) return; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.room-order-row'); if (!target || target === draggedSecurity || target.parentElement !== securityList) return; const rect = target.getBoundingClientRect(); securityList.insertBefore(draggedSecurity, event.clientY < rect.top + rect.height / 2 ? target : target.nextSibling) })
const finishSecurityDrag = () => { if (!draggedSecurity) return; draggedSecurity.classList.remove('dragging'); draggedSecurity = null; orderedSecurity = [...securityList.querySelectorAll('.room-order-row')].map((row) => orderedSecurity[Number(row.dataset.index)]); renderSecurityOrder();markSecurityDirty() }
securityList.addEventListener('pointerup', finishSecurityDrag)
securityList.addEventListener('pointercancel', finishSecurityDrag)
securityList.addEventListener('keydown', (event) => { if (!event.target.matches('.room-drag-handle') || !['ArrowUp','ArrowDown'].includes(event.key)) return; event.preventDefault(); const index = Number(event.target.closest('.room-order-row').dataset.index); const other = index + (event.key === 'ArrowUp' ? -1 : 1); if (other < 0 || other >= orderedSecurity.length) return; [orderedSecurity[index], orderedSecurity[other]] = [orderedSecurity[other], orderedSecurity[index]]; renderSecurityOrder(); securityList.querySelectorAll('.room-drag-handle')[other]?.focus() })
securityList.addEventListener('click',event=>{if(!event.target.closest('[data-security-sensors-open]'))return;securitySensorEditor.hidden=false;renderSecuritySensorOrder();securitySensorEditor.scrollIntoView({behavior:'smooth',block:'start'})})
securitySensorEditor.addEventListener('click',event=>{if(event.target.closest('[data-security-sensors-close]'))securitySensorEditor.hidden=true})
let draggedSecuritySensor=null
securitySensorEditor.addEventListener('pointerdown',event=>{const handle=event.target.closest('.sensor-drag-handle');if(!handle)return;draggedSecuritySensor=handle.closest('[data-security-sensor-id]');draggedSecuritySensor.classList.add('dragging');handle.setPointerCapture(event.pointerId);event.preventDefault()})
securitySensorEditor.addEventListener('pointermove',event=>{if(!draggedSecuritySensor)return;const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-security-sensor-id]');if(!target||target===draggedSecuritySensor||target.parentElement!==draggedSecuritySensor.parentElement)return;const rect=target.getBoundingClientRect();target.parentElement.insertBefore(draggedSecuritySensor,event.clientY<rect.top+rect.height/2?target:target.nextSibling)})
const finishSecuritySensorDrag=()=>{if(!draggedSecuritySensor)return;const previous=[...securitySensors];securitySensors=[...securitySensorEditor.querySelectorAll('[data-security-sensor-id]')].map(row=>previous[Number(row.dataset.sensorIndex)]);securitySensors.forEach((device,index)=>{const saved=securityDeviceOrganization[String(device.id)]||{visible:true,categories:['sensors','security'],orders:{}};saved.orders||={};saved.orders.security=index;securityDeviceOrganization[String(device.id)]=saved});draggedSecuritySensor.classList.remove('dragging');draggedSecuritySensor=null;renderSecuritySensorOrder();markSecurityDirty()}
securitySensorEditor.addEventListener('pointerup',finishSecuritySensorDrag);securitySensorEditor.addEventListener('pointercancel',finishSecuritySensorDrag)
const newCameraId=()=>typeof crypto.randomUUID==='function'?crypto.randomUUID().replaceAll('-',''):`cam${Date.now().toString(36)}${Math.random().toString(36).slice(2,12)}`
$('#security-camera-add').addEventListener('click',()=>{securityCameras.push({id:newCameraId(),name:'',url:''});renderSecurityCameras();markSecurityDirty();const row=$('#security-camera-list').lastElementChild;row?.scrollIntoView({behavior:'smooth',block:'center'});row?.querySelector('[data-camera-name]')?.focus({preventScroll:true})})
$('#security-camera-list').addEventListener('input',event=>{const row=event.target.closest('[data-camera-index]');if(!row)return;const camera=securityCameras[Number(row.dataset.cameraIndex)];if(event.target.matches('[data-camera-name]'))camera.name=event.target.value;if(event.target.matches('[data-camera-preview-url]')){camera.preview_url=event.target.value.trim();camera.url=camera.preview_url}if(event.target.matches('[data-camera-video-url]'))camera.video_url=event.target.value.trim();if(event.target.matches('[data-camera-mode]'))camera.mode=event.target.value;markSecurityDirty()})
async function saveSecurityCameras(message='Salvato ✓'){const response=await fetch(apiUrl('../api/user/appearance'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({security_order:orderedSecurity,device_organization:securityDeviceOrganization,security_cameras:securityCameras.map(camera=>({...camera,id:/^[A-Za-z0-9_-]{8,80}$/.test(camera.id||'')?camera.id:newCameraId(),name:camera.name.trim(),url:camera.url.trim()}))})});const data=await response.json();if(!response.ok)throw new Error(data.detail);securityCameras=data.security_cameras||securityCameras;securityDeviceOrganization=data.device_organization||securityDeviceOrganization;renderSecurityCameras();securityStatus(message,'saved')}
$('#security-camera-list').addEventListener('click',async event=>{const save=event.target.closest('[data-camera-save]');if(save){save.disabled=true;securityStatus('Salvataggio e verifica anteprima…');try{await saveSecurityCameras('Videocamera salvata ✓ — anteprima caricata');notice('Videocamera salvata e disponibile in Sicurezza')}catch(error){securityStatus(`Non salvato: ${error.message}`,'dirty');notice(error.message)}return}const button=event.target.closest('[data-camera-remove]');if(!button)return;securityCameras.splice(Number(button.closest('[data-camera-index]').dataset.cameraIndex),1);renderSecurityCameras();markSecurityDirty()})
let draggedCamera=null
$('#security-camera-list').addEventListener('pointerdown',event=>{const handle=event.target.closest('[data-camera-drag]');if(!handle)return;draggedCamera=handle.closest('[data-camera-index]');draggedCamera.classList.add('dragging');handle.setPointerCapture(event.pointerId);event.preventDefault()})
$('#security-camera-list').addEventListener('pointermove',event=>{if(!draggedCamera)return;const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-camera-index]');if(!target||target===draggedCamera||target.parentElement!==$('#security-camera-list'))return;const rect=target.getBoundingClientRect();$('#security-camera-list').insertBefore(draggedCamera,event.clientY<rect.top+rect.height/2?target:target.nextSibling)})
const finishCameraDrag=()=>{if(!draggedCamera)return;const previous=[...securityCameras];securityCameras=[...$('#security-camera-list').querySelectorAll('[data-camera-index]')].map(row=>previous[Number(row.dataset.cameraIndex)]);draggedCamera.classList.remove('dragging');draggedCamera=null;renderSecurityCameras();markSecurityDirty()}
$('#security-camera-list').addEventListener('pointerup',finishCameraDrag);$('#security-camera-list').addEventListener('pointercancel',finishCameraDrag)
$('#security-order-save').addEventListener('click',async()=>{const button=$('#security-order-save');button.disabled=true;securityStatus('Salvataggio in corso…');try{await saveSecurityCameras('Salvato ✓ — ora è visibile nella pagina Sicurezza');notice('Sicurezza e videocamere salvate')}catch(error){securityStatus(`Non salvato: ${error.message}`,'dirty');notice(error.message)}finally{button.disabled=false}})
$('#card-glow-tool').addEventListener('click', async () => { try { const response = await fetch(apiUrl('../api/user/appearance'), {cache:'no-store'}); if (!response.ok) throw new Error(`HTTP ${response.status}`); $('#card-glow-enabled').checked = (await response.json()).card_glow !== false; $('#card-glow-config').hidden = false } catch (error) { notice(error.message) } })
$('#card-glow-back').addEventListener('click', () => { $('#card-glow-config').hidden = true })
$('#card-glow-enabled').addEventListener('change', async (event) => { const enabled = event.target.checked; try { const response = await fetch(apiUrl('../api/user/appearance'), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({card_glow:enabled})}); if (!response.ok) throw new Error((await response.json()).detail); notice(enabled ? 'Illuminazione schede attivata' : 'Illuminazione schede disattivata') } catch (error) { event.target.checked = !enabled; notice(error.message) } })

const shortcutLabels = {lights:'Luci',switches:'Extra',covers:'Oscuranti',climate:'Comfort',security:'Sicurezza',media:'Audio e video',sensors:'Sensori',other:'Altro'}
const shortcutCategory = (device) => device.kind === 'light' ? 'lights' : device.kind === 'switch' ? 'switches' : device.kind === 'cover' ? 'covers' : ['climate','temp','temperature','humidity','air','air_quality'].includes(device.kind) ? 'climate' : ['lock','alarm_partition','alarm_zone','alarm_scenario','alarm_system'].includes(device.kind) ? 'security' : ['media','media_player','camera','doorbell'].includes(device.kind) ? 'media' : /sensor/.test(device.kind) ? 'sensors' : 'other'
const shortcutsCard = document.createElement('button')
shortcutsCard.id = 'shortcuts-tool'; shortcutsCard.className = 'tool-card'
shortcutsCard.innerHTML = '<span>⌁</span><div><b>Scorciatoie</b><small>Scegli e ordina comandi e categorie</small></div><i>›</i>'
$('#tools-user-section .tools-grid').append(shortcutsCard)
const shortcutsPanel = document.createElement('section')
shortcutsPanel.id = 'shortcuts-config'; shortcutsPanel.className = 'media-config'; shortcutsPanel.hidden = true
shortcutsPanel.innerHTML = '<header><button id="shortcuts-back">‹</button><div><h2>Scorciatoie</h2></div></header><p>Seleziona i dispositivi e trascina la maniglia ☰ per ordinare categorie e dispositivi come appariranno nella pagina Scorciatoie.</p><div id="shortcuts-order-list" class="shortcuts-order-list"></div><footer><button id="shortcuts-save" class="user-save">SALVA SCORCIATOIE</button></footer>'
document.querySelector('.tools-shell').append(shortcutsPanel)
document.head.insertAdjacentHTML('beforeend','<style>.shortcuts-order-list{display:grid;gap:10px}.shortcut-admin-group{padding:10px;border:1px solid #ffffff22;border-radius:12px;background:#ffffff08}.shortcut-admin-group.dragging,.shortcut-admin-device.dragging{opacity:.55;border-color:#55e6ae}.shortcut-admin-head,.shortcut-admin-device{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:9px}.shortcut-admin-head{margin-bottom:8px}.shortcut-admin-head strong{font-size:15px}.shortcut-admin-device{min-height:44px;padding:5px 7px;border-top:1px solid #ffffff12}.shortcut-admin-device small{display:block;color:#9aa9ad}.shortcut-drag-handle{width:38px;min-height:38px;padding:0;touch-action:none;cursor:grab}.shortcut-drag-handle:active{cursor:grabbing}.shortcut-admin-device input{width:20px;height:20px;accent-color:#55e6ae}</style>')
let shortcutGroups = []
let shortcutDevices = []
function renderShortcutAdmin(){
  $('#shortcuts-order-list').innerHTML = shortcutGroups.map((group) => {
    const rank = new Map(group.devices.map((id,index)=>[id,index]))
    const devices = shortcutDevices.filter((item)=>shortcutCategory(item)===group.category).sort((a,b)=>(rank.get(String(a.id))??99999)-(rank.get(String(b.id))??99999)||String(a.name).localeCompare(String(b.name),'it'))
    return `<section class="shortcut-admin-group" data-shortcut-category="${group.category}"><div class="shortcut-admin-head"><button type="button" class="shortcut-drag-handle" data-shortcut-drag="category" aria-label="Trascina categoria ${shortcutLabels[group.category]}">☰</button><strong>${shortcutLabels[group.category]}</strong></div>${devices.map((device)=>`<label class="shortcut-admin-device" data-shortcut-device="${esc(device.id)}"><button type="button" class="shortcut-drag-handle" data-shortcut-drag="device" aria-label="Trascina ${esc(device.name)}">☰</button><span><b>${esc(device.name)}</b><small>${esc(device.room||device.kind)}</small></span><input type="checkbox" ${group.devices.includes(String(device.id))?'checked':''}></label>`).join('')||'<small>Nessun dispositivo</small>'}</section>`
  }).join('')
}
async function loadShortcutAdmin(){
  const [bootstrapResponse,appearanceResponse]=await Promise.all([fetch(apiUrl('../api/bootstrap'),{cache:'no-store'}),fetch(apiUrl('../api/user/appearance'),{cache:'no-store'})])
  if(!bootstrapResponse.ok||!appearanceResponse.ok)throw new Error('Dispositivi non disponibili')
  shortcutDevices=(await bootstrapResponse.json()).dashboard?.devices||[]
  const saved=(await appearanceResponse.json()).shortcuts||[]
  const byCategory=new Map(saved.map((group)=>[group.category,group]))
  shortcutGroups=[...saved.map((group)=>({category:group.category,devices:[...group.devices]})),...Object.keys(shortcutLabels).filter((key)=>!byCategory.has(key)).map((category)=>({category,devices:[]}))]
  renderShortcutAdmin()
}
async function openShortcutEditor(){try{await loadShortcutAdmin();shortcutsPanel.hidden=false}catch(error){notice(error.message)}}
window.efaceOpenShortcutOrder=openShortcutEditor
shortcutsCard.addEventListener('click',openShortcutEditor)
$('#shortcuts-back').addEventListener('click',()=>{shortcutsPanel.hidden=true})
function syncShortcutGroups(){shortcutGroups=[...$('#shortcuts-order-list').querySelectorAll('[data-shortcut-category]')].map((section)=>({category:section.dataset.shortcutCategory,devices:[...section.querySelectorAll('[data-shortcut-device]')].filter((row)=>row.querySelector('input').checked).map((row)=>row.dataset.shortcutDevice)}))}
$('#shortcuts-order-list').addEventListener('change',syncShortcutGroups)
let draggedShortcut=null
$('#shortcuts-order-list').addEventListener('pointerdown',(event)=>{const handle=event.target.closest('[data-shortcut-drag]');if(!handle)return;draggedShortcut=handle.dataset.shortcutDrag==='category'?handle.closest('[data-shortcut-category]'):handle.closest('[data-shortcut-device]');draggedShortcut.classList.add('dragging');handle.setPointerCapture(event.pointerId);event.preventDefault()})
$('#shortcuts-order-list').addEventListener('pointermove',(event)=>{if(!draggedShortcut)return;const category=draggedShortcut.matches('[data-shortcut-category]');const selector=category?'[data-shortcut-category]':'[data-shortcut-device]';const target=document.elementFromPoint(event.clientX,event.clientY)?.closest(selector);if(!target||target===draggedShortcut)return;if(category&&target.parentElement!==$('#shortcuts-order-list'))return;if(!category&&target.parentElement!==draggedShortcut.parentElement)return;const rect=target.getBoundingClientRect();target.parentElement.insertBefore(draggedShortcut,event.clientY<rect.top+rect.height/2?target:target.nextSibling)})
const finishShortcutDrag=()=>{if(!draggedShortcut)return;draggedShortcut.classList.remove('dragging');draggedShortcut=null;syncShortcutGroups();renderShortcutAdmin()}
$('#shortcuts-order-list').addEventListener('pointerup',finishShortcutDrag)
$('#shortcuts-order-list').addEventListener('pointercancel',finishShortcutDrag)
$('#shortcuts-order-list').addEventListener('keydown',(event)=>{const handle=event.target.closest('[data-shortcut-drag]');if(!handle||!['ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const row=handle.dataset.shortcutDrag==='category'?handle.closest('[data-shortcut-category]'):handle.closest('[data-shortcut-device]');const sibling=event.key==='ArrowUp'?row.previousElementSibling:row.nextElementSibling;if(!sibling||sibling.matches('[data-shortcut-device]')!==row.matches('[data-shortcut-device]'))return;row.parentElement.insertBefore(row,event.key==='ArrowUp'?sibling:sibling.nextSibling);syncShortcutGroups();renderShortcutAdmin()})
$('#shortcuts-save').addEventListener('click',async()=>{try{const response=await fetch(apiUrl('../api/user/appearance'),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({shortcuts:shortcutGroups})});if(!response.ok)throw new Error((await response.json()).detail);notice('Scorciatoie salvate');shortcutsPanel.hidden=true}catch(error){notice(error.message)}})

const homeWidgetLabels={overview:['Stato casa','Sicurezza e comfort'],weather:['Meteo','Condizioni rilevate da e-Control'],camera_event:['Videosorveglianza','Ultimo evento NVR esterno'],doorbell:['DoorBird · chiamata','Ultima immagine campanello'],motion:['DoorBird · movimento','Ultimo evento del sensore'],states:['Contatori rapidi','Luci, extra, oscuranti e scorciatoie'],rooms:['Ambienti','Accesso rapido alle stanze'],live:['Sessioni live','Audio e video in riproduzione'],room_pulse:['Casa viva','Stanze, luci, temperatura e media in tempo reale'],lights_now:['Luci accese','Le luci attive in questo momento'],routine_pulse:['Routine in corso','Dispositivi coinvolti in un’automazione'],shopping_list:['Lista della spesa','Apri, aggiungi e completa elementi e-Control'],agenda:['Agenda','Sveglie, timer e promemoria']}
const homeWidgetCard=document.createElement('button');homeWidgetCard.type='button';homeWidgetCard.className='tool-card';homeWidgetCard.innerHTML='<span>▦</span><div><b>Home dinamica</b><small>Scegli, ordina e dimensiona i widget</small></div><i>›</i>';$('#tools-user-section .tools-grid').append(homeWidgetCard)
const homeWidgetPanel=document.createElement('section');homeWidgetPanel.className='media-config';homeWidgetPanel.hidden=true;homeWidgetPanel.innerHTML='<header><button type="button" data-home-widget-back>‹</button><div><h2>Home dinamica</h2></div></header><p>Componi la Home su una griglia a 12 colonne: trascina, dimensiona e guarda subito il risultato nell’anteprima.</p><label>Località meteo<input id="home-weather-location" maxlength="100" placeholder="Es. Torino, Piemonte"></label><label>Entità ultimo evento videosorveglianza<input id="home-camera-entity" placeholder="camera.nvr_32ch_ext_ultimo_evento"></label><fieldset class="home-todo-picker"><legend>Lista della spesa</legend><p>Scegli una delle liste esposte da e-Control.</p><div id="home-todo-options"><small>Caricamento liste…</small></div></fieldset><fieldset class="home-todo-picker"><legend>Agenda</legend><p>Scegli Alexa, l’agenda interna o una delle agende disponibili in e-Control.</p><div id="home-agenda-options"><small>Caricamento agende…</small></div></fieldset><div id="home-widget-preview" class="home-widget-preview" aria-label="Anteprima disposizione Home"></div><div id="home-widget-list" class="shortcuts-order-list"></div><footer><button type="button" id="home-widget-save" class="user-save">SALVA HOME</button></footer>';document.querySelector('.tools-shell').append(homeWidgetPanel)
document.head.insertAdjacentHTML('beforeend','<style>.home-widget-preview{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-auto-flow:dense;align-items:start;gap:7px;margin:16px 0;padding:12px;border-radius:16px;background:#0d1518;box-shadow:inset 0 0 0 1px #ffffff12}.home-widget-preview>div{grid-column:span var(--widget-span);min-width:0;height:var(--preview-height,104px);padding:10px;display:flex;flex-direction:column;justify-content:space-between;border-radius:10px;color:#eff7f6;background:linear-gradient(135deg,#17444a,#20282c);box-shadow:inset 0 0 0 1px #64e8bd33}.home-widget-preview>div[data-preview-height="short"]{--preview-height:72px}.home-widget-preview>div[data-preview-height="standard"],.home-widget-preview>div[data-preview-height="uniform"]{--preview-height:104px}.home-widget-preview>div[data-preview-height="tall"]{--preview-height:148px}.home-widget-preview span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:700}.home-widget-preview small{color:#68e4bb}.home-widget-admin{grid-template-columns:auto minmax(150px,1fr) minmax(112px,auto) minmax(130px,auto) auto!important}.home-widget-dimension{display:grid!important;gap:4px!important}.home-widget-dimension small{color:#9fb0b3;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.home-widget-admin select{min-height:38px}@media(max-width:700px){.home-widget-preview{grid-template-columns:repeat(6,minmax(0,1fr))}.home-widget-preview>div{grid-column:1/-1!important}.home-widget-admin{grid-template-columns:auto minmax(0,1fr) auto!important}.home-widget-dimension{grid-column:2}.home-widget-admin input{grid-column:3;grid-row:1}}</style>')
document.head.insertAdjacentHTML('beforeend','<style>.home-todo-picker{margin:14px 0;padding:14px;border:1px solid #ffffff22;border-radius:13px}.home-todo-picker legend{padding:0 7px;font-weight:800}.home-todo-picker>p{margin:0 0 9px;color:#aebfc1}.home-todo-options{display:grid;gap:7px}.home-todo-option{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;padding:10px;border-radius:10px;background:#ffffff08}.home-todo-option input{width:20px;height:20px;accent-color:#65dfd2}.home-todo-option span b,.home-todo-option span small{display:block}.home-todo-option span small{color:#9caeb0}.home-todo-option>small{color:#65dfd2}</style>')
let homeWidgets=[]
let homeTodoEntity=''
let homeAgendaSource='alexa'
function renderHomeTodoOptions(items){$('#home-todo-options').innerHTML=(items||[]).map(item=>`<label class="home-todo-option"><input type="radio" name="home-todo-entity" value="${esc(item.entity_id)}" ${item.entity_id===homeTodoEntity?'checked':''}><span><b>${esc(item.name)}</b><small>${esc(item.source||'e-Control')}</small></span><small>${Number(item.count)||0} elementi</small></label>`).join('')||'<small>Nessuna lista disponibile in e-Control.</small>'}
function renderHomeAgendaOptions(items){$('#home-agenda-options').innerHTML=(items||[]).map(item=>`<label class="home-todo-option"><input type="radio" name="home-agenda-source" value="${esc(item.id)}" ${item.id===homeAgendaSource?'checked':''}><span><b>${esc(item.name)}</b><small>${item.kind==='alexa'?'Conferma vocale':item.kind==='calendar'?'Agenda e-Control':'Locale e persistente'}</small></span></label>`).join('')}
function renderHomeWidgetPreview(){const spans={quarter:3,compact:4,standard:6,large:8,wide:12},heightLabels={uniform:'Uniforme',short:'Bassa',standard:'Media',tall:'Alta'};$('#home-widget-preview').innerHTML=homeWidgets.filter((item)=>item.visible).map((item)=>{const height=item.height||'standard';return `<div style="--widget-span:${spans[item.size]||6}" data-preview-widget="${item.id}" data-preview-height="${height}"><span>${homeWidgetLabels[item.id]?.[0]||item.id}</span><small>L ${spans[item.size]||6}/12 · H ${heightLabels[height]||'Media'}</small></div>`}).join('')||'<p>Nessun widget visibile</p>'}
function renderHomeWidgetAdmin(){ $('#home-widget-list').innerHTML=homeWidgets.map((item)=>{const label=homeWidgetLabels[item.id]||[item.id,''],height=`<label class="home-widget-dimension"><small>Altezza</small><select data-widget-height aria-label="Altezza ${label[0]}"><option value="uniform" ${item.height==='uniform'?'selected':''}>Uniforme alla riga</option><option value="short" ${item.height==='short'?'selected':''}>Bassa</option><option value="standard" ${!item.height||item.height==='standard'?'selected':''}>Media</option><option value="tall" ${item.height==='tall'?'selected':''}>Alta</option></select></label>`;return `<div class="shortcut-admin-device home-widget-admin" data-home-widget-admin="${item.id}"><button type="button" class="shortcut-drag-handle" data-home-widget-drag aria-label="Trascina ${label[0]}">☰</button><span><b>${label[0]}</b><small>${label[1]}</small></span><label class="home-widget-dimension"><small>Larghezza</small><select data-widget-size aria-label="Larghezza ${label[0]}"><option value="quarter" ${item.size==='quarter'?'selected':''}>25% · 3/12</option><option value="compact" ${item.size==='compact'?'selected':''}>33% · 4/12</option><option value="standard" ${item.size==='standard'?'selected':''}>50% · 6/12</option><option value="large" ${item.size==='large'?'selected':''}>66% · 8/12</option><option value="wide" ${item.size==='wide'?'selected':''}>100% · 12/12</option></select></label>${height}<input type="checkbox" aria-label="Mostra ${label[0]}" ${item.visible?'checked':''}></div>`}).join('');renderHomeWidgetPreview() }
function syncHomeWidgets(){homeWidgets=[...$('#home-widget-list').querySelectorAll('[data-home-widget-admin]')].map((row)=>({id:row.dataset.homeWidgetAdmin,visible:row.querySelector('input').checked,size:row.querySelector('[data-widget-size]').value,height:row.querySelector('[data-widget-height]')?.value||'standard'}));renderHomeWidgetPreview()}
homeWidgetCard.addEventListener('click',async()=>{try{const [response,todoResponse,agendaResponse]=await Promise.all([fetch(apiUrl('../api/user/appearance'),appearanceOptions({cache:'no-store'})),fetch(apiUrl('../api/home/todo/lists'),appearanceOptions({cache:'no-store'})),fetch(apiUrl('../api/home/alexa/agenda'),appearanceOptions({cache:'no-store'}))]);if(!response.ok)throw new Error(`HTTP ${response.status}`);const appearance=await response.json();const todo=todoResponse.ok?await todoResponse.json():{items:[]};const agenda=agendaResponse.ok?await agendaResponse.json():{sources:[]};homeWidgets=appearance.home_widgets||[];homeTodoEntity=appearance.home_todo_entity||todo.selected||'';homeAgendaSource=appearance.home_agenda_source||agenda.selected_source||'alexa';$('#home-camera-entity').value=appearance.home_camera_entity||'camera.nvr_32ch_ext_ultimo_evento';$('#home-weather-location').value=appearance.home_weather_location||'';renderHomeTodoOptions(todo.items);renderHomeAgendaOptions(agenda.sources);renderHomeWidgetAdmin();homeWidgetPanel.hidden=false}catch(error){notice(error.message)}})
homeWidgetPanel.querySelector('[data-home-widget-back]').addEventListener('click',()=>{homeWidgetPanel.hidden=true})
homeWidgetCard.id='home-widget-tool'
homeWidgetPanel.id='home-widget-config'
$('#home-widget-list').addEventListener('change',syncHomeWidgets)
let draggedHomeWidget=null
$('#home-widget-list').addEventListener('pointerdown',(event)=>{const handle=event.target.closest('[data-home-widget-drag]');if(!handle)return;draggedHomeWidget=handle.closest('[data-home-widget-admin]');draggedHomeWidget.classList.add('dragging');handle.setPointerCapture(event.pointerId);event.preventDefault()})
$('#home-widget-list').addEventListener('pointermove',(event)=>{if(!draggedHomeWidget)return;const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-home-widget-admin]');if(!target||target===draggedHomeWidget)return;const rect=target.getBoundingClientRect();target.parentElement.insertBefore(draggedHomeWidget,event.clientY<rect.top+rect.height/2?target:target.nextSibling)})
function finishHomeWidgetDrag(){if(!draggedHomeWidget)return;draggedHomeWidget.classList.remove('dragging');draggedHomeWidget=null;syncHomeWidgets()}
$('#home-widget-list').addEventListener('pointerup',finishHomeWidgetDrag);$('#home-widget-list').addEventListener('pointercancel',finishHomeWidgetDrag)
$('#home-widget-save').addEventListener('click',async()=>{try{syncHomeWidgets();homeTodoEntity=$('input[name="home-todo-entity"]:checked')?.value||'';homeAgendaSource=$('input[name="home-agenda-source"]:checked')?.value||'alexa';if(homeWidgets.find(item=>item.id==='shopping_list')?.visible&&!homeTodoEntity)throw new Error('Scegli la lista da usare per Lista della spesa');const response=await fetch(apiUrl('../api/user/appearance'),appearanceOptions({method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({home_widgets:homeWidgets,home_camera_entity:$('#home-camera-entity').value.trim(),home_weather_location:$('#home-weather-location').value.trim(),home_agenda_source:homeAgendaSource,...(homeTodoEntity?{home_todo_entity:homeTodoEntity}:{})})}));if(!response.ok)throw new Error((await response.json()).detail);notice('Home salvata · Lista e agenda aggiornate');homeWidgetPanel.hidden=true}catch(error){notice(error.message)}})
