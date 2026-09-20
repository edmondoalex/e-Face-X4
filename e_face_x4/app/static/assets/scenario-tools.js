const shell = document.querySelector('.tools-shell')
const card = document.createElement('button')
card.id = 'scenarios-tool'
card.type = 'button'
card.className = 'tool-card'
card.innerHTML = '<span>✦</span><div><b>Scenari</b><small>Crea e modifica gli scenari luce e tapparelle HDL</small></div><i>›</i>'
document.querySelector('#tools-user-section .tools-grid').append(card)

const panel = document.createElement('section')
panel.id = 'scenarios-config'
panel.className = 'media-config scenario-studio'
panel.hidden = true
panel.innerHTML = `<header><button type="button" data-scene-back aria-label="Torna a Strumenti">‹</button><div><small>STRUMENTI UTENTE · e-HDL</small><h2>Scenari</h2></div><button type="button" data-scene-reload title="Rileggi da HDL">↻</button></header>
<div class="scene-hero"><div><small>SCENE STUDIO</small><h3>La tua casa, in un gesto.</h3><p>Combina luci, dimmer e tapparelle. Le modifiche vengono salvate direttamente in e-HDL e compaiono nella pagina Scenari.</p></div><div data-scene-stats></div></div>
<div class="scene-layout"><aside class="scene-library"><div class="scene-library-head"><b>I TUOI SCENARI</b><button type="button" data-scene-new>+ Nuovo</button></div><input type="search" data-scene-filter placeholder="Cerca scenario" aria-label="Cerca scenario"><div data-scene-list></div></aside>
<div class="scene-workspace"><div data-scene-editor><p>Caricamento scenari…</p></div></div></div><p data-scene-message class="scene-message" role="status" aria-live="polite"></p>`
shell.append(panel)

const $ = selector => panel.querySelector(selector)
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))
const endpoint = path => new URL(`../${path}`, location.href.endsWith('/') ? location.href : `${location.href}/`).toString()
async function request(path, options={}) { const response=await fetch(endpoint(path),{cache:'no-store',...options});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);return data }
const json = (method,body) => ({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
let catalog={items:[],devices:[],groups:[],ha_triggers:[]}, currentId='', draft=null, revision='', dirty=false, filter='', targetFilter='all', admin=false, busy=false
function targetKey(item,kind='light') { if(item.group_id)return `group:${item.group_id}`;if(item.entity_id)return `${kind==='cover'?'cover':'light'}:${String(item.entity_id).toLowerCase()}`;return `${kind}:${item.subnet_id}.${item.device_id}.${item.channel}` }
function targets() {
  const devices=(catalog.devices||[]).filter(device=>['light','cover'].includes(String(device.type||'light'))).map(device=>{
    const kind=String(device.type||'light')
    const item=device.entity_id?{entity_id:String(device.entity_id).toLowerCase(),domain:String(device.domain||device.entity_id.split('.')[0])}:{subnet_id:Number(device.subnet_id),device_id:Number(device.device_id),channel:Number(device.channel)}
    return {key:targetKey(item,kind),kind,label:device.name||device.entity_id||targetKey(item,kind),room:device.group||device.category||'',detail:device.entity_id||`${device.subnet_id}.${device.device_id}.${device.channel}`,dimmable:Boolean(device.dimmable)&&item.domain!=='switch',item}
  })
  const groups=(catalog.groups||[]).map(group=>({key:`group:${group.id}`,kind:'group',label:group.name||group.id,room:'Gruppo tapparelle',detail:group.id,item:{group_id:group.id}}))
  return [...groups,...devices]
}
function targetName(item,kind) { const key=targetKey(item,kind);return targets().find(target=>target.key===key)?.label||item.entity_id||item.group_id||`${item.subnet_id}.${item.device_id}.${item.channel}` }
function dimmable(item) { return targets().find(target=>target.key===targetKey(item,'light'))?.dimmable||item.brightness!==null&&item.brightness!==undefined }
function blank() { return {name:'',items:[],covers:[],combination_targets:[],run_enabled:true,onoff_enabled:false,ha_trigger_enabled:false,ha_trigger_id:'',trigger:{enabled:false,type:'none',time:'',offset_min:0}} }
function edit(id, force=false) {
  if(dirty&&!force&&!confirm('Hai modifiche non salvate. Vuoi cambiare scenario?'))return
  currentId=id||''
  const source=(catalog.items||[]).find(item=>String(item.id)===currentId)
  draft=source?structuredClone(source):blank()
  draft.items=Array.isArray(draft.items)?draft.items:[];draft.covers=Array.isArray(draft.covers)?draft.covers:[];draft.combination_targets=Array.isArray(draft.combination_targets)?draft.combination_targets:[]
  draft.trigger={enabled:false,type:'none',time:'',offset_min:0,...(draft.trigger||{})}
  revision=source?.revision||'';dirty=false;targetFilter='all'
  sessionStorage.setItem('eface-scene-id',currentId)
  render()
}
function message(value,error=false){const node=$('[data-scene-message]');node.textContent=value;node.classList.toggle('error',error)}
function renderList(){
  const q=filter.trim().toLocaleLowerCase('it')
  const items=(catalog.items||[]).filter(item=>String(item.name||'').toLocaleLowerCase('it').includes(q))
  $('[data-scene-list]').innerHTML=items.map(item=>`<button type="button" data-scene-select="${esc(item.id)}" class="scene-entry ${item.id===currentId?'selected':''}"><span class="scene-entry-icon">${item.running?'▶':item.onoff_enabled?'◉':'✦'}</span><span><strong>${esc(item.name)}</strong><small>${(item.items||[]).length} luci · ${(item.covers||[]).length} tapparelle${item.running?' · IN CORSO':''}</small></span><i>›</i></button>`).join('')||'<p class="scene-empty">Nessuno scenario trovato.</p>'
  $('[data-scene-stats]').innerHTML=`<strong>${catalog.items.length}</strong><span>scenari condivisi<br>${catalog.groups.length} gruppi cover disponibili</span>`
}
const check = (value,label,checked) => `<label class="scene-check"><input type="checkbox" data-scene-field="${value}" ${checked?'checked':''}><span>${label}</span></label>`
function renderSelected(){
  const lights=draft.items.map((item,index)=>`<article class="scene-target-row"><div class="scene-target-title"><span class="scene-target-icon">✦</span><div><strong>${esc(targetName(item,'light'))}</strong><small>${esc(item.entity_id||`${item.subnet_id}.${item.device_id}.${item.channel}`)}</small></div></div><div class="scene-target-controls"><select data-scene-item="${index}" data-field="state" aria-label="Stato luce"><option value="ON" ${item.state==='ON'?'selected':''}>Accendi</option><option value="OFF" ${item.state==='OFF'?'selected':''}>Spegni</option></select>${dimmable(item)?`<label>Luminosità <input type="number" min="0" max="255" step="1" data-scene-item="${index}" data-field="brightness" value="${item.brightness??''}" placeholder="nessuna"></label>`:''}<button type="button" data-scene-remove="item:${index}" aria-label="Rimuovi luce">×</button></div></article>`).join('')
  const covers=draft.covers.map((item,index)=>`<article class="scene-target-row"><div class="scene-target-title"><span class="scene-target-icon cover">▤</span><div><strong>${esc(targetName(item,'cover'))}</strong><small>${esc(item.entity_id||item.group_id||`${item.subnet_id}.${item.device_id}.${item.channel}`)}</small></div></div><div class="scene-target-controls"><select data-scene-cover="${index}" data-field="command" aria-label="Comando tapparella">${[['OPEN','Apri'],['CLOSE','Chiudi'],['STOP','Stop'],['SET_POSITION','Posizione']].map(([value,label])=>`<option value="${value}" ${item.command===value?'selected':''}>${label}</option>`).join('')}</select>${item.command==='SET_POSITION'?`<label>Posizione %<input type="number" min="0" max="100" data-scene-cover="${index}" data-field="position" value="${item.position??50}"></label>`:''}<button type="button" data-scene-remove="cover:${index}" aria-label="Rimuovi tapparella">×</button></div><details class="scene-cover-advanced"><summary>Apertura graduale e due fasi</summary><div class="scene-mini-grid"><label>Durata rampa (min)<input type="number" min="0" max="240" data-scene-cover="${index}" data-field="ramp_minutes" value="${item.ramp_minutes??0}"></label><label>Passo (sec)<input type="number" min="1" max="120" data-scene-cover="${index}" data-field="step_seconds" value="${item.step_seconds??5}"></label><label><input type="checkbox" data-scene-cover="${index}" data-field="two_phase_open" ${item.two_phase_open?'checked':''}> Apertura in due fasi</label><label>Prima fase %<input type="number" min="1" max="99" data-scene-cover="${index}" data-field="phase1_pct" value="${item.phase1_pct??25}"></label><label>Attesa seconda fase (min)<input type="number" min="0" max="240" data-scene-cover="${index}" data-field="phase2_delay_minutes" value="${item.phase2_delay_minutes??4}"></label></div></details></article>`).join('')
  return `<section class="scene-section"><div class="scene-section-heading"><div><small>02 · COMPOSIZIONE</small><h3>Dispositivi coinvolti</h3></div><span>${draft.items.length+draft.covers.length} elementi</span></div>${lights}${covers}${lights||covers?'':'<p class="scene-empty">Scegli luci o tapparelle dal catalogo qui sotto.</p>'}<div class="scene-add-shell"><div class="scene-add-head"><b>Aggiungi dal catalogo</b><input type="search" data-scene-target-search placeholder="Cerca stanza o dispositivo" aria-label="Cerca dispositivo"></div><nav class="scene-target-filters">${[['all','Tutti'],['light','Luci'],['cover','Tapparelle'],['group','Gruppi']].map(([value,label])=>`<button type="button" data-scene-target-filter="${value}" class="${targetFilter===value?'active':''}">${label}</button>`).join('')}</nav><div data-scene-target-list class="scene-catalog-list"></div></div></section>`
}
function renderCatalog(){
  const root=$('[data-scene-target-list]');if(!root)return
  const search=$('[data-scene-target-search]')?.value.trim().toLocaleLowerCase('it')||''
  const selected=new Set([...draft.items.map(item=>targetKey(item,'light')),...draft.covers.map(item=>targetKey(item,'cover'))])
  const found=targets().filter(target=>(targetFilter==='all'||target.kind===targetFilter)&&(!search||`${target.label} ${target.room} ${target.detail}`.toLocaleLowerCase('it').includes(search)))
  root.innerHTML=found.slice(0,100).map(target=>`<button type="button" data-scene-add="${esc(target.key)}" ${selected.has(target.key)?'disabled':''}><span class="scene-target-icon ${target.kind==='light'?'':'cover'}">${target.kind==='light'?'✦':'▤'}</span><span><strong>${esc(target.label)}</strong><small>${esc(target.room)} · ${esc(target.detail)}</small></span><b>${selected.has(target.key)?'AGGIUNTO':'+'}</b></button>`).join('')||'<p class="scene-empty">Nessun dispositivo trovato.</p>'
  if(found.length>100)root.insertAdjacentHTML('beforeend',`<p class="scene-empty">${found.length-100} altri risultati: affina la ricerca.</p>`)
}
function renderTrigger(){
  const tr=draft.trigger
  return `<section class="scene-section"><div class="scene-section-heading"><div><small>03 · ATTIVAZIONE</small><h3>Quando si avvia</h3></div></div><div class="scene-mini-grid">${check('trigger.enabled','Attivazione automatica',tr.enabled)}<label>Tipo<select data-scene-trigger="type">${[['none','Nessuno'],['time','Orario'],['sunrise','Alba'],['sunset','Tramonto'],['sveglia','Sveglia']].map(([key,label])=>`<option value="${key}" ${tr.type===key?'selected':''}>${label}</option>`).join('')}</select></label><label>Orario (se selezionato)<input type="time" data-scene-trigger="time" value="${esc(tr.time||'')}"></label><label>Offset minuti · alba/tramonto<input type="number" min="-1440" max="1440" data-scene-trigger="offset_min" value="${Number(tr.offset_min)||0}"></label></div><div class="scene-ha-trigger">${check('ha_trigger_enabled','Avvia anche da pulsante Home Assistant',draft.ha_trigger_enabled)}<label>Pulsante HA<select data-scene-field="ha_trigger_id"><option value="">Seleziona trigger</option>${(catalog.ha_triggers||[]).map(item=>`<option value="${esc(item.id)}" ${draft.ha_trigger_id===item.id?'selected':''}>${esc(item.name)}</option>`).join('')}</select></label>${admin?'<button type="button" data-scene-trigger-new>+ Crea pulsante HA</button>':''}</div>${admin?`<details class="scene-trigger-library"><summary>Gestisci pulsanti HA · ${catalog.ha_triggers.length}</summary>${catalog.ha_triggers.map(item=>`<div class="scene-trigger-library-row"><span>${esc(item.name)}</span><button type="button" data-scene-trigger-rename="${esc(item.id)}">Rinomina</button><button type="button" data-scene-trigger-delete="${esc(item.id)}">Elimina</button></div>`).join('')||'<p>Nessun pulsante creato.</p>'}</details>`:''}<p class="scene-help">RUN è un impulso. ON/OFF mantiene lo stato della scena. Puoi abilitarli entrambi.</p></section>`
}
function renderAdvanced(){
  return `<section class="scene-section"><details class="scene-combinations"><summary>Combinazioni HDL <small>· ${draft.combination_targets.length} associate</small></summary><p>Richiama anche switch combinazione BusPro con indirizzo e numero tasto. Questa funzione è distinta dai dispositivi luce.</p><div data-scene-combos>${draft.combination_targets.map((item,index)=>`<div class="scene-combo-row"><label>Subnet<input type="number" min="0" max="255" data-scene-combo="${index}" data-field="subnet_id" value="${item.subnet_id}"></label><label>Dispositivo<input type="number" min="0" max="255" data-scene-combo="${index}" data-field="device_id" value="${item.device_id}"></label><label>Tasto<input type="number" min="1" max="255" data-scene-combo="${index}" data-field="switch_number" value="${item.switch_number}"></label><button type="button" data-scene-remove="combo:${index}">×</button></div>`).join('')}</div><button type="button" data-scene-add-combo>+ Combinazione</button></details></section>`
}
function render(){
  renderList()
  if(!draft){$('[data-scene-editor]').innerHTML='<p>Seleziona uno scenario.</p>';return}
  $('[data-scene-editor]').innerHTML=`<div class="scene-editor-top"><div><small>${currentId?'MODIFICA SCENARIO':'NUOVO SCENARIO'}</small><h3>${esc(draft.name||'Dai un nome alla tua scena')}</h3><p>Salvato in e-HDL · visibile a tutti gli utenti</p></div><span class="scene-state ${draft.running?'running':''}">${draft.running?'IN CORSO':currentId?'ESISTENTE':'BOZZA'}</span></div>
    <section class="scene-section"><div class="scene-section-heading"><div><small>01 · IDENTITÀ</small><h3>Nome e modalità</h3></div></div><label class="scene-name">Nome scenario<input data-scene-field="name" maxlength="80" value="${esc(draft.name)}" placeholder="Es. Cinema serale"></label><div class="scene-mode-grid">${check('run_enabled','Impulso RUN',draft.run_enabled)}${check('onoff_enabled','Interruttore ON/OFF',draft.onoff_enabled)}</div></section>
    ${renderSelected()}${renderTrigger()}${renderAdvanced()}
    <div class="scene-footer"><div data-scene-review>${draft.items.length} luci · ${draft.covers.length} tapparelle · ${draft.combination_targets.length} combinazioni</div><div><button type="button" data-scene-duplicate ${currentId?'':'hidden'}>DUPLICA</button><button type="button" data-scene-delete class="danger" ${currentId?'':'hidden'}>ELIMINA</button><button type="button" data-scene-save class="primary">SALVA SCENARIO</button></div></div>
    ${currentId?`<div class="scene-test"><span>PROVA SCENARIO</span><div>${(draft.run_enabled?[['run','Esegui'],['stop','Ferma']]:[]).concat(draft.onoff_enabled?[['on','ON'],['off','OFF']]:[]).map(([command,label])=>`<button type="button" data-scene-command="${command}">${label}</button>`).join('')}</div></div>`:''}`
  renderCatalog()
}
async function load(keep=true){
  const id=keep?currentId||sessionStorage.getItem('eface-scene-id')||'':''
  catalog=await request('api/user/scenarios/editor')
  if(id&&(catalog.items||[]).some(item=>String(item.id)===id))edit(id,true)
  else edit('',true)
  const identity=await request('api/auth/status').catch(()=>({}))
  admin=identity.user==='admin'
  render()
}
function applyField(node){
  if(!draft)return
  const value=node.type==='checkbox'?node.checked:node.value
  if(node.dataset.sceneField){if(node.dataset.sceneField==='trigger.enabled')draft.trigger.enabled=value;else draft[node.dataset.sceneField]=value;dirty=true;if(node.dataset.sceneField==='name')$('.scene-editor-top h3').textContent=value||'Dai un nome alla tua scena';return}
  if(node.dataset.sceneTrigger){draft.trigger[node.dataset.sceneTrigger]=node.dataset.sceneTrigger==='offset_min'?Number(value):value;dirty=true;return}
  const index=node.dataset.sceneItem??node.dataset.sceneCover??node.dataset.sceneCombo
  const list=node.dataset.sceneItem!==undefined?'items':node.dataset.sceneCover!==undefined?'covers':'combination_targets'
  if(index!==undefined&&draft[list][Number(index)]){
    const key=node.dataset.field
    draft[list][Number(index)][key]=node.type==='checkbox'?node.checked:['brightness','position','ramp_minutes','step_seconds','phase1_pct','phase2_delay_minutes','subnet_id','device_id','switch_number'].includes(key)?value===''?null:Number(value):value
    if(list==='items'&&key==='state'&&value==='OFF')draft.items[Number(index)].brightness=null
    if(list==='covers'&&key==='command')draft.covers[Number(index)].position=value==='SET_POSITION'?50:null
    dirty=true
    if(key==='state'||key==='command')render()
  }
}
async function save(){
  if(busy)return
  const invalid=$('[data-scene-editor] input:invalid');if(invalid){invalid.reportValidity();return}
  if(!draft.name.trim()){message('Scrivi il nome dello scenario.',true);$('[data-scene-field="name"]').focus();return}
  busy=true;$('[data-scene-save]').disabled=true
  try{
    const result=await request(`api/user/scenarios/editor${currentId?`/${encodeURIComponent(currentId)}`:''}`,json(currentId?'PUT':'POST',{revision,spec:draft}))
    currentId=String(result.item?.id||currentId)
    await load(true)
    message('Scenario salvato in e-HDL. È disponibile anche nella pagina Scenari.')
  }catch(error){message(error.message,true)}finally{busy=false;$('[data-scene-save]').disabled=false}
}
card.addEventListener('click',async()=>{if(!panel.hidden){return}panel.hidden=false;document.body.style.overflow='hidden';try{await load(true)}catch(error){$('[data-scene-editor]').innerHTML=`<p class="scene-error">${esc(error.message)}</p>`}})
panel.addEventListener('input',event=>{if(event.target.matches('[data-scene-filter]')){filter=event.target.value;renderList()}else if(event.target.matches('[data-scene-target-search]'))renderCatalog();else if(event.target.matches('[data-scene-field="name"]'))applyField(event.target)})
panel.addEventListener('change',event=>{if(event.target.matches('[data-scene-field],[data-scene-trigger],[data-scene-item],[data-scene-cover],[data-scene-combo]'))applyField(event.target)})
panel.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return
  if(button.hasAttribute('data-scene-back')){if(dirty&&!confirm('Chiudere senza salvare le modifiche?'))return;panel.hidden=true;document.body.style.overflow='';return}
  if(button.hasAttribute('data-scene-reload')){if(dirty&&!confirm('Ricaricare e perdere le modifiche?'))return;try{await load(true);message('Scenari aggiornati da e-HDL.')}catch(error){message(error.message,true)}return}
  if(button.hasAttribute('data-scene-new'))return edit('')
  if(button.dataset.sceneSelect!==undefined)return edit(button.dataset.sceneSelect)
  if(button.dataset.sceneTargetFilter){targetFilter=button.dataset.sceneTargetFilter;$('.scene-target-filters .active')?.classList.remove('active');button.classList.add('active');renderCatalog();return}
  if(button.dataset.sceneAdd){const target=targets().find(item=>item.key===button.dataset.sceneAdd);if(!target)return;const base={command:'OPEN',position:null,ramp_minutes:0,step_seconds:5,two_phase_open:false,phase1_pct:25,phase2_delay_minutes:4};if(target.kind==='light')draft.items.push({...target.item,state:'ON',brightness:target.dimmable?255:null});else draft.covers.push({...base,...target.item,kind:target.kind==='group'?'group':target.item.entity_id?'ha':'single'});dirty=true;render();return}
  if(button.dataset.sceneRemove){const [kind,index]=button.dataset.sceneRemove.split(':');draft[kind==='item'?'items':kind==='cover'?'covers':'combination_targets'].splice(Number(index),1);dirty=true;render();return}
  if(button.hasAttribute('data-scene-add-combo')){draft.combination_targets.push({subnet_id:1,device_id:1,switch_number:1});dirty=true;render();return}
  if(button.hasAttribute('data-scene-save'))return save()
  if(button.hasAttribute('data-scene-duplicate')){const original=draft.name;currentId='';revision='';draft=structuredClone(draft);draft.name=`${original} · copia`.slice(0,80);dirty=true;render();return}
  if(button.hasAttribute('data-scene-delete')){if(!currentId||!confirm(`Eliminare definitivamente lo scenario «${draft.name}» da e-HDL?`))return;try{await request(`api/user/scenarios/editor/${encodeURIComponent(currentId)}?revision=${encodeURIComponent(revision)}`,{method:'DELETE'});currentId='';await load(false);message('Scenario eliminato da e-HDL.')}catch(error){message(error.message,true)}return}
  if(button.dataset.sceneCommand){if(!confirm(`Eseguire ora «${button.textContent.trim()}» su ${draft.name}?`))return;try{await request(`api/scenarios/${encodeURIComponent(currentId)}/command`,json('POST',{action:button.dataset.sceneCommand}));message('Comando inviato.');setTimeout(()=>load(true).catch(()=>{}),600)}catch(error){message(error.message,true)}return}
  if(button.hasAttribute('data-scene-trigger-new')){const name=prompt('Nome del nuovo pulsante trigger Home Assistant');if(!name?.trim())return;try{const created=await request('api/admin/scenario-triggers',json('POST',{name:name.trim()}));catalog.ha_triggers.push(created);draft.ha_trigger_enabled=true;draft.ha_trigger_id=created.id;dirty=true;render();message('Pulsante HA creato e associato. Salva lo scenario per collegarlo.')}catch(error){message(error.message,true)}}
  if(button.dataset.sceneTriggerRename){const current=catalog.ha_triggers.find(item=>item.id===button.dataset.sceneTriggerRename);if(!current)return;const name=prompt('Nuovo nome del pulsante HA',current.name);if(!name?.trim())return;try{await request(`api/admin/scenario-triggers/${encodeURIComponent(current.id)}`,json('PUT',{name:name.trim()}));current.name=name.trim();render();message('Pulsante HA rinominato.')}catch(error){message(error.message,true)}return}
  if(button.dataset.sceneTriggerDelete){const id=button.dataset.sceneTriggerDelete;const trigger=catalog.ha_triggers.find(item=>item.id===id);const linked=catalog.items.filter(item=>item.ha_trigger_enabled&&item.ha_trigger_id===id);if(!trigger||!confirm(`Eliminare il pulsante HA «${trigger.name}»?${linked.length?` Sarà scollegato da ${linked.length} scenari.`:''}`))return;try{await request(`api/admin/scenario-triggers/${encodeURIComponent(id)}?force=${linked.length?'true':'false'}`,{method:'DELETE'});if(draft.ha_trigger_id===id){draft.ha_trigger_id='';draft.ha_trigger_enabled=false;dirty=true}await load(true);message('Pulsante HA eliminato. Gli scenari associati sono stati scollegati in e-HDL.')}catch(error){message(error.message,true)}}
})
