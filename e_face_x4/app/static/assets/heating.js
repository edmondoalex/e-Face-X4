const tabs = [['status','Stato'],['modules','Moduli'],['setpoints','Regolazioni'],['flows','Percorsi'],['solar','Solare'],['resistances','Resistenze'],['plant','Impianto'],['boilers','Caldaie'],['mixer','Miscelatrice'],['zones','Zone']]
const names = {resistenze_volano:'Resistenze volano',volano_to_acs:'Volano → ACS',volano_to_puffer:'Volano → Puffer',puffer_to_acs:'Puffer → ACS',impianto:'Impianto riscaldamento',gas_emergenza:'Caldaia gas emergenza',caldaia_legna:'Caldaia legna',solare:'Solare',miscelatrice:'Miscelatrice',curva_climatica:'Curva climatica',pdc:'Pompa di calore'}
const controls = [
  ['acs','setpoint_c','ACS · setpoint',40,85,'°C'],['acs','max_c','ACS · limite massimo',50,85,'°C'],
  ['volano','max_c','Volano · limite massimo',40,95,'°C'],['volano','min_to_acs_c','Volano · minimo verso ACS',35,75,'°C'],
  ['puffer','max_c','Puffer · limite massimo',50,90,'°C'],['puffer','setpoint_c','Puffer · setpoint',40,90,'°C'],['puffer','min_to_acs_c','Puffer · minimo verso ACS',40,80,'°C'],
  ['impianto','volano_min_c','Impianto · minimo volano',35,80,'°C'],['impianto','puffer_min_c','Impianto · minimo puffer',35,80,'°C'],
  ['resistance','export_on_min_w','Resistenze · soglia export',0,6000,'W']
]
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))
const number = (value, unit='°C') => Number.isFinite(Number(value)) ? `${Number(value).toFixed(unit === 'W' ? 0 : 1)} ${unit}` : '—'
const card = (title, body, wide=false) => `<article class="heating-card${wide?' wide':''}"><h3>${esc(title)}</h3>${body}</article>`
const reading = (label,value,unit='°C') => card(label,`<strong class="value">${number(value,unit)}</strong>`)
const relay = key => { const item=snapshot.actuators?.[key];return item?card(item.name||key,`<strong class="value ${item.state==='on'?'heating-ok':'heating-muted'}">${esc(String(item.state||'—').toUpperCase())}</strong><small>Sola lettura</small>`):'' }
let snapshot, active='status', loading=false, timer, root

function summary() {
  const d=snapshot.decision||{}, c=d.computed||{}, i=d.inputs||{}, s=snapshot.status||{}
  const alarms=Array.isArray(c.alarms)?c.alarms:[]
  return `<div class="heating-grid">
    ${card('Collegamento',`<strong class="value ${s.ha_connected?'heating-ok':'heating-error'}">${s.ha_connected?'Online':'Non collegato'}</strong><p>e-ThermoMind ${esc(s.version||'')} · ${esc(s.runtime_mode||'—')}</p>${alarms.length?`<p class="heating-error">${esc(alarms.map(a=>typeof a==='string'?a:a.message||a.code).join(' · '))}</p>`:''}`)}
    ${card('Acqua calda sanitaria',`<strong class="value">${number(i.t_acs)}</strong><p>Destinazione: ${esc(c.dest||'—')} · Sorgente: ${esc(c.source_to_acs||'—')}</p><p>${esc(c.dest_reason||'')}</p>`)}
    ${card('Accumuli',`<p>Volano <strong>${number(i.t_volano)}</strong></p><p>Puffer <strong>${number(i.t_puffer)}</strong></p><p>Solare <strong>${number(i.t_solare_mandata)}</strong></p>`)}
    ${card('Riscaldamento',`<strong class="value">${c.impianto?.active?'In funzione':'Fermo'}</strong><p>${esc(c.impianto?.reason||'')}</p>`)}
    ${card('Curva climatica',`<p>Esterno ${number(i.t_esterna)}</p><p>Mandata ${number(i.t_mandata_miscelata)}</p><p>${esc(c.curva_climatica?.reason||'')}</p>`)}
  </div><h3 class="heating-section-title">Cosa sta facendo adesso</h3><div class="heating-grid">${Object.entries(c.module_reasons||{}).map(([key,value])=>card(names[key]||key,`<p>${esc(value)}</p>`)).join('')||card('Dettagli','<p>Nessun dettaglio disponibile.</p>')}</div>`
}
function modules() {
  const entries=Object.entries(snapshot.modules||{})
  return `<p class="heating-muted">I moduli sono globali e persistenti. Spegnere un modulo può fermare pompe, valvole o resistenze gestite da e-ThermoMind.</p><div class="heating-grid">${entries.map(([key,on])=>card(names[key]||key,`<button type="button" data-module="${esc(key)}" data-value="${on?'off':'on'}" class="${on?'on':'off'}">${on?'ON · Disattiva':'OFF · Attiva'}</button><p>${esc(snapshot.decision?.computed?.module_summaries?.[key]||'')}</p>`)).join('')}</div>`
}
function setpoints() {
  const groups={ACS:controls.slice(0,2),Volano:controls.slice(2,4),Puffer:controls.slice(4,7),Impianto:controls.slice(7,9),Resistenze:controls.slice(9)}
  return `<p class="heating-muted">Ogni valore viene salvato separatamente; niente modifica finché non premi Salva.</p>${Object.entries(groups).map(([group,items])=>`<h3 class="heating-section-title">${group}</h3><div class="heating-grid">${items.map(([section,key,label,min,max,unit])=>card(label,`<label>Valore (${unit})<input type="number" min="${min}" max="${max}" step="${unit==='W'?1:0.5}" value="${esc(snapshot.setpoints?.[section]?.[key]??'')}" data-setpoint="${section}.${key}"></label><small>Intervallo ${min}–${max} ${unit}</small><div><button type="button" data-save-setpoint="${section}.${key}">Salva</button></div>`)).join('')}</div>`).join('')}
    ${card('Stagione',`<label>Modalità<select data-season><option value="winter" ${snapshot.setpoints?.impianto?.season_mode==='winter'?'selected':''}>Inverno</option><option value="summer" ${snapshot.setpoints?.impianto?.season_mode==='summer'?'selected':''}>Estate</option></select></label><button type="button" data-save-season>Salva stagione</button><p>In estate il riscaldamento è bloccato.</p>`,true)}`
}
function flows() {
  const c=snapshot.decision?.computed||{}, i=snapshot.decision?.inputs||{}, f=snapshot.forces||{}
  const pairs=[['Solare','solare','t_solare_mandata','t_acs'],['Volano → ACS','volano_to_acs','t_volano','t_acs'],['Volano → Puffer','volano_to_puffer','t_volano','t_puffer'],['Puffer → ACS','puffer_to_acs','t_puffer','t_acs']]
  return `<div class="heating-grid">${pairs.map(([label,key,from,to])=>card(label,`<p>Sorgente: <strong>${number(i[from])}</strong></p><p>Destinazione: <strong>${number(i[to])}</strong></p><p>Δ ${number(Number(i[from])-Number(i[to]))}</p><p>Modulo ${snapshot.modules?.[key]?'ON':'OFF'}</p><p>${esc(c.module_reasons?.[key]||c.module_summaries?.[key]||'')}</p>`)).join('')}
    ${card('Forza ACS da Puffer',`<p>${f.acs?.active?`Attiva · ${Math.ceil((f.acs.remaining_s||0)/60)} min restanti`:'Non attiva'}</p><div class="heating-actions"><input type="number" min="1" max="240" value="30" data-force-minutes="acs" aria-label="Durata in minuti"><button data-force="acs" data-active="true">Avvia</button><button data-force="acs" data-active="false">Stop</button></div>`)}
    ${card('Scarica Volano in Puffer',`<p>${f.volano?.active?`Attiva · ${Math.ceil((f.volano.remaining_s||0)/60)} min restanti`:'Non attiva'}</p><p>${esc(f.volano?.reason||'')}</p><div class="heating-actions"><input type="number" min="1" max="240" value="30" data-force-minutes="volano" aria-label="Durata in minuti"><button data-force="volano" data-active="true" ${f.volano?.can_apply===false?'disabled':''}>Avvia</button><button data-force="volano" data-active="false">Stop</button></div>`)}
    ${card('Scarico automatico',`<label>Trigger<select data-dump-trigger><option value="time" ${snapshot.setpoints?.volano?.evening_dump_trigger==='time'?'selected':''}>Orario</option><option value="entity" ${snapshot.setpoints?.volano?.evening_dump_trigger==='entity'?'selected':''}>Entità RUN</option></select></label><button data-save-dump="evening_dump_trigger">Salva trigger</button><label>Ora avvio<input type="number" min="0" max="23.99" step="0.25" data-dump-hour value="${esc(snapshot.setpoints?.volano?.evening_dump_after_h??'')}"></label><button data-save-dump="evening_dump_after_h">Salva ora</button><label>Entità RUN<input type="text" data-dump-entity value="${esc(snapshot.setpoints?.volano?.evening_dump_run_entity??'')}" placeholder="switch.nome_entita"></label><button data-save-dump="evening_dump_run_entity">Salva entità</button>`)}</div>`
}
function solar() {
  const i=snapshot.decision?.inputs||{}, c=snapshot.decision?.computed||{}
  const values=[['Mandata solare',i.t_solare_mandata],['Collettore',i.collettore_tsa1],['Ritorno solare',i.collettore_tse],['Serbatoio',i.collettore_twu],['Temperatura esterna',i.collettore_temp_esterna]]
  return `<div class="heating-grid">${card('Stato collettore',`<strong class="value">${esc(i.collettore_status||'—')}</strong><p>${esc(i.collettore_status2||'')}</p><p>Ultimo dato: ${esc(i.collettore_datetime||'—')}</p>`)}${values.map(([label,value])=>reading(label,value)).join('')}${reading('Portata',i.collettore_flow_lmin,'L/min')}${reading('Pompa PWM',i.collettore_pwm_pct,'%')}${reading('Energia oggi',i.collettore_energy_day_kwh,'kWh')}${reading('Energia totale',i.collettore_energy_total_kwh,'kWh')}${['r8_valve_solare_notte_low_temp','r9_valve_solare_normal_funz','r10_valve_solare_precedenza_acs','r18_valve_ritorno_solare_basso','r19_valve_ritorno_solare_alto'].map(relay).join('')}${card('Decisione solare',`<p>${esc(c.module_reasons?.solare||'')}</p>`,true)}</div>`
}
function resistances() {
  const i=snapshot.decision?.inputs||{}, c=snapshot.decision?.computed||{}
  return `<div class="heating-grid">${reading('Potenza resistenze',i.resistenze_volano_power,'W')}${card('Step attuale',`<strong class="value">${esc(c.resistance_step??'—')} / 3</strong>`)}${reading('Export rete',i.grid_export_w,'W')}${reading('Extra safe',i.extra_safe_w,'W')}${reading('Disponibile calcolato',c.available_power_w,'W')}${reading('Volano alto',i.t_volano_alto)}${reading('Volano basso',i.t_volano_basso)}${['generale_resistenze_volano_pdc','r22_resistenza_1_volano_pdc','r23_resistenza_2_volano_pdc','r24_resistenza_3_volano_pdc'].map(relay).join('')}${card('Decisione resistenze',`<p>${esc(c.module_reasons?.resistenze_volano||'')}</p>`,true)}</div>`
}
function boilers() {
  const i=snapshot.decision?.inputs||{}, c=snapshot.decision?.computed||{}, g=c.gas_emergenza||{}, w=c.caldaia_legna||{}
  return `<h3 class="heating-section-title">Gas emergenza</h3><div class="heating-grid">${card('Stato gas',`<p>Necessaria: <strong>${g.need?'Sì':'No'}</strong></p><p>Domanda: <strong>${g.demand?'ON':'OFF'}</strong></p><p>Volano OK: ${g.vol_ok?'Sì':'No'} · Puffer OK: ${g.puf_ok?'Sì':'No'}</p>`)}${['gas_boiler_power','gas_boiler_ta'].map(relay).join('')}${card('Decisione gas',`<p>${esc(c.module_reasons?.gas_emergenza||'')}</p>`)}</div><h3 class="heating-section-title">Caldaia legna</h3><div class="heating-grid">${reading('Mandata',i.t_mandata_caldaia_legna)}${reading('Ritorno',i.t_ritorno_caldaia_legna)}${reading('Caldaia',i.t_caldaia_legna)}${card('Stato legna',`<p>Modulo: ${w.enabled?'ON':'OFF'} · Alimentazione: ${w.power?'ON':'OFF'} · TA: ${w.ta?'ON':'OFF'}</p><p>${esc(w.reason||'')}</p>`)}${['r30_alimentazione_caldaia_legna','r20_ta_caldaia_legna'].map(relay).join('')}</div>`
}
function mixer() {
  const i=snapshot.decision?.inputs||{}, c=snapshot.decision?.computed||{}, m=c.miscelatrice||{}, curve=c.curva_climatica||{}
  return `<div class="heating-grid">${reading('Mandata',i.t_mandata_miscelata)}${reading('Ritorno',i.t_ritorno_miscelato)}${reading('Setpoint mandata',m.setpoint)}${reading('Differenza mandata/ritorno',m.delta_tr)}${card('Miscelatrice',`<strong class="value">${esc(m.action||'—')}</strong><p>${esc(m.reason||'')}</p>`)}${reading('Esterno',i.t_esterna)}${reading('Setpoint curva',curve.setpoint)}${reading('Offset curva',curve.offset)}${card('Curva climatica',`<p>Modulo ${snapshot.modules?.curva_climatica?'ON':'OFF'} · pendenza ${esc(curve.slope??'—')}</p><p>${esc(c.module_reasons?.curva_climatica||'')}</p>`)}${['r16_cmd_miscelatrice_alza','r17_cmd_miscelatrice_abbassa'].map(relay).join('')}</div>`
}
function plant() {
  const c=snapshot.decision?.computed||{}, i=snapshot.decision?.inputs||{}
  const readings=[['Mandata miscelata',i.t_mandata_miscelata],['Ritorno miscelato',i.t_ritorno_miscelato],['Esterno',i.t_esterna],['Volano alto',i.t_volano_alto],['Volano basso',i.t_volano_basso],['Puffer alto',i.t_puffer_alto],['Puffer medio',i.t_puffer_medio],['Puffer basso',i.t_puffer_basso],['Caldaia legna',i.t_caldaia_legna]]
  const sp=snapshot.setpoints?.impianto||{}
  return `<div class="heating-grid">${card('Impianto',`<p><strong>${c.impianto?.active?'Attivo':'Fermo'}</strong> · Fonte ${esc(c.impianto?.source||'—')} · Selezione ${esc(c.impianto?.selector||'—')}</p><p>${esc(c.impianto?.reason||'')}</p>`,true)}
    ${card('Selezione sorgente',`<label>Sorgente<select data-plant-source><option value="AUTO" ${sp.source_mode==='AUTO'?'selected':''}>AUTO</option><option value="PDC" ${sp.source_mode==='PDC'?'selected':''}>PDC/Volano</option><option value="PUFFER" ${sp.source_mode==='PUFFER'?'selected':''}>Puffer</option></select></label><button data-save-plant="source_mode">Salva sorgente</button>`)}
    ${card('Disponibilità sorgenti',`<label><input type="checkbox" data-plant-ready="pdc_ready" ${sp.pdc_ready?'checked':''}> PDC/Volano ready</label><button data-save-plant="pdc_ready">Salva PDC/Volano</button><label><input type="checkbox" data-plant-ready="puffer_ready" ${sp.puffer_ready?'checked':''}> Puffer ready</label><button data-save-plant="puffer_ready">Salva Puffer</button><p>Questi consensi sono manuali in e-ThermoMind.</p>`)}
    ${readings.map(([label,val])=>card(label,`<strong class="value">${number(val)}</strong>`)).join('')}${['miscelatrice','curva_climatica','gas_emergenza','caldaia_legna','resistenze_volano'].map(key=>card(names[key],`<p>${esc(c.module_reasons?.[key]||'')}</p><p>${esc(c.module_summaries?.[key]||'')}</p>`)).join('')}</div>`
}
function zones() {
  const zones=snapshot.decision?.zones||[]
  return `<p class="heating-muted">Il setpoint agisce sulla zona e-Control collegata a e-ThermoMind. Lo stato del termostato resta in sola lettura.</p><div class="heating-grid">${zones.map(zone=>card(zone.entity_id?.replace(/^climate\./,'').replaceAll('_',' ')||'Zona',`<p>${esc(zone.group||'')} · ${esc(zone.state||'—')} · ${zone.active?'Richiesta calore':'Nessuna richiesta'}</p><p>Temperatura ${number(zone.temperature)}</p><label>Setpoint (°C)<input type="number" min="5" max="35" step="0.5" value="${esc(zone.setpoint??'')}" data-zone-temp="${esc(zone.entity_id)}"></label><button data-save-zone="${esc(zone.entity_id)}">Salva</button>`)).join('')||card('Zone','<p>Nessuna zona disponibile.</p>')}</div>`
}
const views={status:summary,modules,setpoints,flows,solar,resistances,plant,boilers,mixer,zones}
function render() {
  if (!root||!snapshot) return
  root.querySelector('#heating-tabs').innerHTML=tabs.map(([id,label])=>`<button type="button" data-heating-tab="${id}" class="${active===id?'active':''}" aria-current="${active===id?'page':'false'}">${label}</button>`).join('')
  root.querySelector('#heating-content').innerHTML=views[active]()
}
async function load(force=false) {
  if (loading||document.hidden||root?.hidden) return
  loading=true
  try {
    const res=await fetch('api/user/heating',{cache:'no-store'})
    const data=await res.json().catch(()=>({}))
    if (!res.ok) throw new Error(data.detail||`HTTP ${res.status}`)
    snapshot=data
    if (force || !root.querySelector('#heating-content').contains(document.activeElement)) render()
  } catch(error) { root.querySelector('#heating-content').innerHTML=`<p class="heating-notice">${esc(error.message)}</p>` }
  finally { loading=false }
}
async function command(payload,button) {
  button.disabled=true
  try {
    const send=()=>fetch('api/user/heating/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    let res=await send()
    if(res.status===403&&payload.kind==='module'&&!payload.pin){const pin=prompt('PIN e-ThermoMind richiesto per modificare i moduli');if(pin===null)return;payload.pin=pin;res=await send()}
    const data=await res.json().catch(()=>({}))
    if (!res.ok) throw new Error(data.detail||`HTTP ${res.status}`)
    await load(true)
  } catch(error) { alert(`Riscaldamento: ${error.message}`) }
  finally { button.disabled=false }
}
export function initHeating() {
  document.head.insertAdjacentHTML('beforeend','<link rel="stylesheet" href="assets/heating.css?v=2.21.209">')
  const nav=document.createElement('button');nav.dataset.view='heating';nav.title='Riscaldamento';nav.innerHTML='<img class="heating-nav-icon" src="assets/heating.svg" alt=""><span>Riscaldamento</span>'
  document.querySelector('.rail [data-view="comfort"]').after(nav)
  root=document.createElement('section');root.id='heating-view';root.className='heating-view';root.hidden=true
  root.innerHTML='<header class="detail-header"><button id="heating-back" aria-label="Torna alla home">‹</button><div><h2>Riscaldamento</h2><small>e-ThermoMind</small></div><button id="heating-reload" aria-label="Aggiorna riscaldamento">↻</button></header><nav id="heating-tabs" aria-label="Blocchi riscaldamento"></nav><div id="heating-content" aria-live="polite"><p>Caricamento…</p></div>'
  document.querySelector('main').append(root)
  root.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return
    if(button.id==='heating-back') return document.querySelector('.horizontal-logo').click()
    if(button.id==='heating-reload') return load(true)
    if(button.dataset.heatingTab){active=button.dataset.heatingTab;sessionStorage.setItem('eface-heating-tab',active);render();return}
    if(button.dataset.module){const key=button.dataset.module;const value=button.dataset.value==='on';command({kind:'module',key,value},button);return}
    if(button.dataset.saveSetpoint){const [section,key]=button.dataset.saveSetpoint.split('.');const input=root.querySelector(`[data-setpoint="${section}.${key}"]`);if(input?.reportValidity())command({kind:'setpoint',section,key,value:Number(input.value)},button);return}
    if(button.dataset.saveSeason)return command({kind:'setpoint',section:'impianto',key:'season_mode',value:root.querySelector('[data-season]').value},button)
    if(button.dataset.savePlant){const key=button.dataset.savePlant;const value=key==='source_mode'?root.querySelector('[data-plant-source]').value:root.querySelector(`[data-plant-ready="${key}"]`).checked;command({kind:'setpoint',section:'impianto',key,value},button);return}
    if(button.dataset.saveDump){const key=button.dataset.saveDump;const input=key==='evening_dump_trigger'?root.querySelector('[data-dump-trigger]'):key==='evening_dump_after_h'?root.querySelector('[data-dump-hour]'):root.querySelector('[data-dump-entity]');if(input.reportValidity())command({kind:'setpoint',section:'volano',key,value:key==='evening_dump_after_h'?Number(input.value):input.value},button);return}
    if(button.dataset.saveZone){const input=[...root.querySelectorAll('[data-zone-temp]')].find(item=>item.dataset.zoneTemp===button.dataset.saveZone);if(input?.reportValidity())command({kind:'zone',entity_id:button.dataset.saveZone,temperature:Number(input.value)},button);return}
    if(button.dataset.force){const target=button.dataset.force,active=button.dataset.active==='true';const input=root.querySelector(`[data-force-minutes="${target}"]`);if(!active||input?.reportValidity())command({kind:'force',target,active,minutes:Number(input?.value||30)},button)}
  })
  try { active=sessionStorage.getItem('eface-heating-tab')||'status';if(!views[active])active='status' } catch {}
  timer=setInterval(()=>{if(!root.hidden)load()},10000)
}
export function openHeating() { root.hidden=false;load(true) }
export function closeHeating() { if(root)root.hidden=true }
