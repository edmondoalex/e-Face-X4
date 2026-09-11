const $ = (selector) => document.querySelector(selector)

function apiUrl(path) {
  const base = location.pathname.endsWith('/') ? location.pathname : `${location.pathname}/`
  return new URL(path.replace(/^\//, ''), `${location.origin}${base}`).toString()
}

function icon(name) {
  return { light: '✦', climate: '❄', shield: '⬡', energy: 'ϟ' }[name] || '◇'
}

function render(data) {
  const dashboard = data.dashboard || {}
  const home = dashboard.home || {}
  $('#home-name').textContent = home.name || 'Casa'
  $('#weather').textContent = home.temperature ? `${home.temperature}°C · ${home.weather || ''}` : 'Sistema connesso'
  $('#mode').textContent = data.mode === 'demo' ? 'ANTEPRIMA DEMO' : 'LIVE'
  $('#mode').classList.toggle('live', data.mode === 'live')

  $('#widgets').innerHTML = (dashboard.widgets || []).map((w, index) => `
    <article class="metric-card tone-${index % 4}">
      <div class="card-top"><span class="symbol">${icon(w.icon)}</span><span class="status-dot"></span></div>
      <p>${escapeHtml(w.title)}</p><strong>${escapeHtml(w.value)}</strong><small>${escapeHtml(w.detail)}</small>
      <div class="wave"></div>
    </article>`).join('')

  $('#rooms').innerHTML = (dashboard.rooms || []).map((room) => `
    <button class="room-card ${escapeHtml(room.accent || '')}">
      <span class="room-glow"></span><span class="room-name">${escapeHtml(room.name)}</span>
      <small>${Number(room.devices) || 0} dispositivi</small><b>↗</b>
    </button>`).join('') || '<p class="empty">Nessuna stanza configurata.</p>'

  const media = dashboard.media
  $('#media').hidden = !media
  if (media) {
    $('#track-title').textContent = media.title || 'Nessun titolo'
    $('#track-detail').textContent = [media.artist, media.source, media.room].filter(Boolean).join(' · ')
    $('#volume').value = Number(media.volume) || 0
    $('#volume-value').textContent = `${Number(media.volume) || 0}%`
  }
  $('#app').classList.remove('loading')
}

function escapeHtml(value) {
  const node = document.createElement('span')
  node.textContent = String(value ?? '')
  return node.innerHTML
}

function showError(message) {
  const notice = $('#notice')
  notice.textContent = message
  notice.hidden = false
}

async function boot() {
  const hour = new Date().getHours()
  $('#greeting').textContent = hour < 12 ? 'Buongiorno' : hour < 18 ? 'Buon pomeriggio' : 'Buonasera'
  try {
    const response = await fetch(apiUrl('api/bootstrap'), { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    render(await response.json())
  } catch (error) {
    $('#app').classList.remove('loading')
    showError(`e-Face X4 non riesce a caricare i dati (${error.message}).`)
  }
}

$('#theme').addEventListener('click', () => document.body.classList.toggle('light'))
$('#volume').addEventListener('input', (event) => { $('#volume-value').textContent = `${event.target.value}%` })
document.querySelectorAll('.dock button').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('.dock button').forEach((item) => item.classList.remove('active'))
  button.classList.add('active')
  const target = button.dataset.view
  if (target === 'media') $('#media').scrollIntoView({ behavior: 'smooth', block: 'center' })
  else if (target === 'rooms') $('#rooms').scrollIntoView({ behavior: 'smooth', block: 'center' })
}))

boot()

