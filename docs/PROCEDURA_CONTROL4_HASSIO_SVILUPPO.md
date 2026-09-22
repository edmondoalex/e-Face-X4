# Procedura operativa Control4 ↔ Home Assistant/e-Face

Stato documentato: 14 settembre 2026, e-Face X4 2.21.7. Questo è il promemoria operativo per riprendere audio, video e, separatamente, videocitofono senza ripetere la fase esplorativa né chiedere all'utente prove manuali che possiamo fare noi. **All'inizio di ogni sessione verificare lo stato reale**: IP, ID, versione, credenziali disponibili e contenuto dei driver possono cambiare.

## 1. Topologia e confini

| Componente | Impianto di prova | Ruolo e fonte della verità |
| --- | --- | --- |
| Repository | `e-Face X4/e_face_x4` | Codice, test e documentazione; non contiene password/token di impianto. |
| Home Assistant | `192.168.3.24` | Supervisor, add-on e-Face, volume persistente `/data`. |
| Add-on e-Face | slug `d71ab5ec_e_face_x4`, container `app_d71ab5ec_e_face_x4` | Client Control4, API e UI. Verificare slug/container prima di usarli su altri impianti. |
| Controller Control4 | `192.168.3.10` | Director HTTPS/443, sorgenti, stanze, sessioni, driver e metadati reali. |
| Accesso tecnico attuale | SSH al solo HA di prova con chiave locale approvata | Sonda dentro il container e-Face, che **già** possiede la configurazione Control4. Non estrarre password/token. |

La porta 5021 è di Composer Pro, non l'API Director usata qui. Le credenziali Control4 sono in `/data/control4.json` dell'add-on; il codice le carica con `load_control4_config()` e ottiene token effimeri tramite `control4_director()`. Non stampare quel file, il bearer token, cookie, URL temporanei di login o risposte grezze che possano contenerli. `get_item_info`, snapshot, nomi e campi selezionati bastano per la maggior parte delle diagnosi.

Gli ID **non sono costanti di prodotto**. Valori osservati nell'impianto: Ufficio Alex stanza 51; Stations proxy 24; TuneIn 615; Spotify Connect 1569; Wireless Music Bridge proxy media-service 210 e protocollo 209; coda/sessioni 100002. Scoprire sempre gli ID dalla UI configuration, dalle `source_options` della stanza e da `get_item_info(id)` prima di inviare un comando.

## 2. Avvio ottimizzato di una sessione

1. Leggere questa procedura, il task specifico in `docs/`, `git status --short`, il changelog recente e i file del connettore interessato. Le modifiche non correlate sono dell'utente: non ripulire il worktree e non includerle nei commit.
2. Verificare read-only versione/stato dell'add-on. Su Windows, usare una chiave SSH locale **già autorizzata**, verificandone prima l'esistenza; la chiave temporanea usata il 14/09 era `%TEMP%\eface_c4_debug_20260914`, ma può non esistere in una sessione futura. Se manca, non inventare credenziali né far ripetere test all'utente: usare le diagnosi admin disponibili o chiedere il ripristino dell'accesso.
3. Eseguire **una sonda mirata dentro il container** per acquisire insieme: stanza, sorgente attiva, ID proxy, variabili pertinenti e dato del driver da verificare. Stampare solo campi non segreti. Raggruppare le letture indipendenti in una sola sonda quando possibile. Non iniziare con una sequenza di screenshot, refresh manuali o prove alla cieca.
4. Riprodurre il caso in un test locale con fixture di risposta reali ma **redatte**. Cambiare soltanto il livello che non funziona: Director/protocollo, normalizzazione, API, stato frontend, cache o CSS.
5. Eseguire `node --check app/static/assets/app.js`, `python -m pytest -q` da `e_face_x4`, `git diff --check`. Verificare anche i percorsi frontend in caso di UI/Ingress. Se si cambia asset JS/CSS, aggiornare il cache-buster in `app/static/index.html` e la versione in `config.yaml`, `app/main.py`, `CHANGELOG.md`.
6. Solo per una richiesta di modifica con aggiornamento autorizzato: commit dei **soli file pertinenti**, push, `ha store reload --no-progress` e `ha apps update <slug> --no-progress`. Attendere l'esito, poi verificare `ha apps info <slug> --raw-json` (versione `started`). Una risposta CLI «Command completed successfully» non prova da sola che la UI sia corretta.
7. Chiudere con una verifica end-to-end proporzionata. Se il comando causerebbe riproduzione, chiamata, abbinamento, rimozione o modifica delle credenziali su un impianto in uso, eseguire prima verifiche read-only e test con mock; chiedere all'utente **solo** la prova fisica realmente necessaria, indicando gesto e risultato atteso. Non presentare test unitari come prova dell'audio/video reale.

Comando read-only di esempio (PowerShell; adattare la chiave dopo averla verificata):

```powershell
$efSshKey = Join-Path $env:TEMP 'eface_c4_debug_20260914'
if (-not (Test-Path -LiteralPath $efSshKey)) { throw 'Chiave tecnica non disponibile' }
ssh -i $efSshKey -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o MACs=hmac-sha2-256-etm@openssh.com -c aes256-ctr root@192.168.3.24 'ha apps info d71ab5ec_e_face_x4 --raw-json'
```

L'opzione MAC/cifrario ha reso compatibile la connessione a questo HA; non è una configurazione universale. Preferire `docker exec -i <container> python3 -` con uno script Python passato via stdin quando serve il client già configurato. Non passare il risultato di `load_control4_config()` a `print`, né esportare il token. Esempio di **sola lettura**:

```powershell
$efProbe = @'
import asyncio
from app.connectors.control4_media import Control4MediaConnector
from app.control4 import load_control4_config

async def main():
    snapshot = await Control4MediaConnector(load_control4_config()).snapshot()
    for item in snapshot.get("items", []):
        if item.get("room") == "Ufficio Alex":
            print({key: item.get(key) for key in ("room", "source", "active_source_id", "title", "active_experience")})
            print([(source["label"], source["key"], source["source_id"]) for source in item.get("source_options", [])])

asyncio.run(main())
'@
$efProbe | ssh -i $efSshKey -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o MACs=hmac-sha2-256-etm@openssh.com -c aes256-ctr root@192.168.3.24 'docker exec -i app_d71ab5ec_e_face_x4 python3 -'
```

## 3. Director: capire prima lo schema, poi comandare

`app/control4.py` gestisce login Control4 e client Director. `app/connectors/control4_media.py` legge UI configuration, stanze e variabili. Un comando REST `/api/v1/items/{proxy_id}/commands` può restituire solo un **acknowledgement**, non il contenuto del menu o la conferma della riproduzione. Il proxy `media_service` non va confuso con il dispositivo protocollo/Lua collegato.

Per i menu media-service lo schema è descritto dal **driver installato**. Leggere manifest XML/JSON e, se accessibile, sorgente Lua del driver senza eseguirlo né copiarlo integralmente in Git/chat. Nell'impianto il pacchetto Wireless Music Bridge era leggibile in sola lettura via `/c4z/wireless_music_bridge/driver.xml` e `/driver.lua` sul controller; usare `curl.exe` su Windows se `Invoke-WebRequest` fallisce. Un vecchio pacchetto `TuneIn.c4z` OS2 analizzato nel repository **non è** prova del driver TuneIn corrente. Non inviare `GetTabList` o altri comandi solo per somiglianza di nome: verificare capability, tab, firma `ARGS`, valori default e azioni effettive.

Pattern verificato in `app/control4_msp.py`:

1. Scoprire `proxy_id` e `room_id`, convalidare `get_item_info(proxy_id)`/`proxy == media_service`.
2. Aprire `C4Websocket` e sottoscrivere **prima** del POST il proxy. Attendere l'ack della sottoscrizione (nel codice attuale: 2 secondi).
3. Creare `SEQ` e `NAVID` unici. Inviare `ROOMID`, `SEQ`, `NAVID`, `LOCALE=it_IT`, `ARGS` XML serializzato con escaping (`<args><arg name="...">...</arg></args>`).
4. Ascoltare `OnDataToUI.data.RESPONSE`; accettare solo la coppia `SEQ`/`NAVID` richiesta e leggere `DATA`. Gestire timeout/errore, scollegare il WebSocket.
5. **Non generalizzare** il flag async: il Wireless Music Bridge ha restituito la lista `PairedDeviceList` con `is_async=True`; con `False` rispondeva solo `SendToDevice`. Altri driver usano il percorso standard del proprio adattatore. Il flag si decide per comando/driver su prova reale.

Moduli già presenti: `control4_msp.py` TuneIn, `control4_msp_catalog.py` Amazon/TIDAL e altri cataloghi compatibili, `control4_spotify.py` Spotify Connect, `control4_stations.py` Stations, `control4_bridge.py` Bluetooth. Non creare un'unica mappa di comandi per tutti: stessa cornice UI, adattatori specifici. Per menu e azioni utilizzare token temporanei server-side associati a proxy/stanza/tab e verificare scadenza; non mandare al browser dati Bluetooth o blob raw inutili.

Nel Wireless Music Bridge: `PairedDeviceList` legge i dispositivi; `BtConnectDisconnect` e `BtRemoveDevice` richiedono Name/Addr/Connected/Paired dell'elemento reale. Un `BtRemoveDevice` con Addr vuoto può essere pericoloso: il backend valida l'indirizzo. Pairing usa `BtAddDevice`, notifica `DriverNotification`/`Authenticate` e poi `BtAuthenticate`. La **scheda sorgente** seleziona il bridge nella stanza; **copertina/icona del player** apre il popup. Non confondere connessione Bluetooth e selezione della fonte audio.

## 4. Audio, video e stato UI: livelli da non mescolare

| Sintomo | Prima lettura/prova automatica | Errore tipico da evitare |
| --- | --- | --- |
| Clic su sorgente apre menu ma non suona | `source_options.key` (`listen:<id>`/`watch:<id>`), `active_source_id`, `CURRENT_AUDIO_DEVICE`/`CURRENT_VIDEO_DEVICE`; `select_source` del room connector | Trattare l'apertura del popup come selezione/riproduzione. |
| Voce del menu selezionata ma player resta vecchio | Ack del comando, `CURRENT MEDIA INFO`, `PLAYING_AUDIO_DEVICE`, `QUEUE_STATUS_V2`, aggiornamento bootstrap/UI | Deducere «play riuscito» da HTTP 200 o fare solo refresh CSS. |
| Due sessioni che dovrebbero essere una | `QUEUE_STATUS_V2` su 100002, owner/members e `normalize_control4_groups` | Unire per titolo/cover o dividere per nome sorgente: stesso contenuto non significa stessa sessione. |
| Logo AIRPLAY o generico errato | `active_source_id`, `medSrcDev`, `source_options`, override in Strumenti e `api/control4/source-icon/<id>` | Usare `audioFormat` o la cover del brano come identità della sorgente. |
| Cover mancante/dinamica | URL originale solo attraverso la diagnosi server redatta; origine/porta/status/MIME/dimensione/redirect, `content_fingerprint` | Esporre URL con token, disattivare la protezione SSRF o nascondere l'errore con un'immagine casuale. |
| Menu video/telecomando | esperienza `watch`, ID della sorgente video attiva, azioni remote dichiarate, `video_remote` validato sul dispositivo | Mandare comandi telecomando a una sorgente non attiva o supporre che video Control4 significhi videocitofono SIP già integrato. |

Per le stanze Control4 `select_source` usa `C4Room.set_audio_source(id)` per `listen` e `set_video_and_audio_source(id)` per `watch` (`connectors/control4_media.py`). Gli eventi `CURRENT MEDIA INFO` descrivono spesso **il brano corrente**, mentre `GetHistoryItemsByRooms` descrive il **contenitore** (playlist/stazione) da cui proviene. Spotify Connect può mostrare titolo/artista/cover del brano senza un URI riproducibile (`mediaid` assente, ID brano nella coda vuoto). In quel caso la stella del player salva la **playlist più recente verificata della stanza**, con il suo nome reale; non inventare un preferito brano che poi non si può suonare. Stations usa invece l'ID stazione verificato nel catalogo. Non scambiare i preferiti e-Face con i «Preferiti alla stanza» di Control4.

Persistenza: favoriti e-Face `/data/control4_media_favorites.json`, copie cover `/data/control4_favorite_artwork/`, voci recenti nascoste `/data/control4_hidden_recents.json`, icone sorgenti personalizzate/visibilità in `/data/source-icons/`; il catalogo Stations è in `/data/control4_stations_catalog.json`. Sono dati dell'utente: non eliminare/reinizializzare per correggere UI o cache. La cronologia Director può cambiare, perciò salvare nel preferito `driver_id`/proxy, key riproducibile e metadati necessari; la cover deve avere fallback con logo della **sorgente**, non del brano.

La schermata logo iniziale è disattivata per default dalla 2.21.84 perché l'app installata mostra già la propria icona. L'Admin può abilitarla e impostare 0,5–30 secondi; la scelta è persistita atomicamente in `/data/startup.json` e viene applicata server-side alla Home, così da non produrre un lampo del logo quando è disattivata.

**Cover dinamica di una playlist Spotify (verifica 14/09/2026):** «Main Stage» ha la stessa `key` nei Recenti e nei Preferiti, ma il `content_fingerprint` della cronologia è cambiato dopo il cambio brano; il Preferito ha ancora il fingerprint precedente e una copia immagine persistente. È l'effetto atteso dell'implementazione 2.21.4: `recently_played()` aggiorna la mappa della cover dal Director, mentre `/api/control4/favorites/artwork` serve la copia fissata quando fu salvato il preferito. Non è perdita del preferito né errore del logo servizio. **Scelta UI ancora aperta:** se si vuole la stessa cover dinamica in entrambe le barre, aggiornare solo la cache cover del preferito quando una voce con la stessa `key` riappare con fingerprint nuovo, validando MIME/dimensione/origine e mantenendo la vecchia immagine se il fetch fallisce. Non sovrascrivere la copertina persistente solo perché l'URL del Director è cambiato: scaricare e validare prima, sostituire atomicamente; testare refresh e reboot. L'ID della sorgente e la `key` riproducibile restano immutati.

Le combinazioni di colori dei popup e delle schede devono derivare dalle impostazioni persistenti di Strumenti. Verificare desktop e mobile, stato dopo refresh e riavvio, clic e feedback senza obbligare l'utente a fare refresh manuale. Un test CSS/DOM locale non prova il comportamento sul controller reale.

## 5. Cosa è già verificato e cosa no

- Il 15/09/2026 l'endpoint locale Home Assistant `/api/evoice/media/snapshot` ha risposto `200` in circa 11 secondi dopo un riavvio, oltre il timeout generale e-Face di 4 secondi. Dalla `2.21.63` il solo connettore eKonex Voice locale usa almeno 15 secondi, mantenendo invariati i timeout degli altri provider; verificare stato e tempo senza stampare il contenuto della risposta o il token Supervisor.

- Verificati su impianto: accesso via container e-Face al Director con credenziali già salvate; `PairedDeviceList` asincrono del bridge; ID sorgente stanza; lettura di `CURRENT MEDIA INFO`, cronologia e `QUEUE_STATUS_V2`; menu TuneIn/Spotify/Stations/bridge; deploy add-on e verifica versione; ultimi test locali: 125 verdi alla 2.21.7. La versione corrente va sempre riverificata.
- Riproduzione/favoriti radio Stations confermati dall'utente. Per Spotify la cronologia della stanza e `Recently Played` del driver mostravano «Big Boom In The Room» come playlist, mentre il player mostrava i singoli brani. L'endpoint della stella playlist è implementato; una prova fisica successiva resta distinta dai test unitari.
- Audio/video Control4 della dashboard e **videocitofono DoorBird/SIP** sono percorsi diversi. Quest'ultimo ha pagina SIP di prova, relay WebSocket Asterisk, impostazioni TURN e diagnostica DoorBird/AMI; il provisioning automatico sicuro degli interni personali, il video citofonico integrato e la prova completa chiamata/audio LAN+remoto **non** sono completati. Vedere `e_face_asterisk/asterisk_provisioner/README.md` e `docs/TASK_INSTALLAZIONE_PLUG_AND_PLAY.md`. Non dedurre che il videocitofono sia pronto dal funzionamento delle sorgenti video Control4.
- Il vecchio obiettivo di un accesso diagnostico portabile, temporaneo e a privilegi minimi per futuri impianti resta aperto. La chiave SSH attuale è un canale operativo **di questo sito**, non un requisito plug-and-play e non va inclusa nell'app per i clienti.

## 6. Regola per ridurre davvero i test dell'utente

Prima di chiedere un gesto manuale, rispondere internamente a quattro domande: **quale livello è guasto? quale dato reale manca? posso leggerlo senza mutare nulla? quale singola prova fisica confermerebbe la correzione?** Se la risposta è disponibile in Director, manifest, variabili, storico, test o container, prenderla lì. Chiedere all'utente solo ciò che richiede effettivamente il suo dispositivo o il suo account (ascoltare l'audio, verificare il display/mobile, pairing Bluetooth, conferma di un login, squillo DoorBird). Ogni prova richiesta deve dire azione esatta, risultato atteso e cosa registrare se fallisce. Non chiedere screenshot/refresh ripetuti per sostituire una diagnosi che l'add-on può fare.

## 7. Quando aggiornare automaticamente questo task

L'agente non deve aspettare un promemoria dell'utente: nello stesso turno in cui verifica un nuovo meccanismo Control4/HA o risolve un guasto che generalizza a più sorgenti, aggiorna questa procedura (o il task specifico) con: **data, evidenza ottenuta, confine di sicurezza, comando/sonda ripetibile e risultato ancora da verificare**. Lo fa anche dopo una modifica alla persistenza o un test reale che conferma/smentisce un'ipotesi. Non apre un task separato per ogni dettaglio puramente estetico e non scrive credenziali o dump integrali. La regola è resa scopribile alle sessioni future tramite `AGENTS.md` alla radice del repository.

## Liste e-Control/Alexa nella Home (22/09/2026)

- Dalla e-Face `2.21.227`, Home dinamica scopre le entità `todo.*` tramite la REST API locale di e-Control e permette di scegliere una sola lista attiva per impianto. Non codificare ID o nomi Alexa: su ogni installazione possono cambiare.
- La lettura degli elementi usa `todo.get_items` con `return_response`; aggiunta, completamento/ripristino e rimozione usano rispettivamente `todo.add_item`, `todo.update_item` e `todo.remove_item` **senza** `return_response`, perché e-Control rifiuta la richiesta di risposta per questi servizi. Il token Supervisor resta server-side e non viene restituito al browser.
- Verifica live read-only del 22/09: l'impianto di prova espone la lista interna e le liste Shopping/To-do dell'integrazione Alexa Devices; la Shopping list riporta un conteggio non nullo. La prova non ha letto i nomi dei prodotti né inviato comandi.
- Controllo ripetibile redatto: dal container e-Face interrogare `http://supervisor/core/api/states` con il token ambiente e stampare soltanto `entity_id`, `friendly_name` e conteggio delle entità il cui ID inizia per `todo.`. Per il contratto di scrittura usare il test mock `test_home_shopping_list_discovers_and_controls_econtrol_todo`, non una lista reale.
- Regressione `2.21.228`: prova end-to-end sulla sola lista interna vuota con elemento tecnico temporaneo; add, lettura, complete, restore e remove hanno risposto `200` e la pulizia finale ha confermato l'assenza dell'elemento. La lista Alexa dell'utente non è stata modificata.
- Misura Alexa reale del 22/09: un elemento tecnico temporaneo è diventato leggibile dopo circa 1,44 secondi e la sua eliminazione dopo circa 0,8 secondi; pulizia finale confermata. Dalla `2.21.229` la UI applica quindi subito la modifica in modo ottimistico e riconcilia a 1,8/3,5/6 secondi, evitando di ripristinare visivamente lo snapshot Alexa ancora vecchio.
- Correzione `2.21.230`: il refresh sintetico della tessera deve precaricare anche gli elementi. Se il popup viene aperto mentre la richiesta è già in corso, il refresh completo viene accodato; senza questa regola la finestra poteva restare su «Caricamento…». Le icone principali della lista sono SVG incorporati perché gli URL icona protetti possono non essere risolti nel contesto Ingress.
- Verifica Alexa del 22/09/2026: con Core `2026.8.3`/`aioamazondevices 14.2.2` i sensori agenda potevano restare indisponibili; dopo l'aggiornamento Core sono tornati a esporre timestamp ISO. Dalla `2.21.235` le Routine rilevano soltanto `sensor.*_next_alarm`, `*_next_timer` e `*_next_reminder`, consentono offset da -180 a +180 minuti e deduplicano sull'identità del timestamp; uno stato `unavailable` non avvia nulla.
- Contratto Agenda `2.21.236` (22/09/2026): e-Face ricava l'ID dispositivo Alexa associando i sensori agenda tramite i registri WebSocket `config/entity_registry/list` e `config/device_registry/list`; invia solo il servizio consentito `alexa_devices.send_text_command`. La pagina scopre inoltre ogni `calendar.*` via REST e crea eventi con `calendar.create_event`; la sorgente può essere Alexa, agenda interna persistente o un calendario scoperto ed è configurabile in Home dinamica. Non memorizzare credenziali Amazon né fissare device/entity ID nel codice.
- Correzione live `2.21.238`: un Echo può essere unito nel registro a entità di più integrazioni. Per `send_text_command` usare soltanto il `device_id` ricavato da un'entità con `platform == alexa_devices`; un sensore omonimo di Alexa Media Player produce `ServiceValidationError: does not belong to integration alexa_devices`. Nell'impianto italiano i suffissi verificati sono anche `_prossima_sveglia`, `_prossimo_timer` e `_prossimo_promemoria`, non solo quelli inglesi.

# Gruppi Intercom e-Face (15/09/2026)

- Asterisk e-Face `6.2.0-eface.9` gestisce i gruppi `8280–8289` e il gruppo automatico Tutti `8290` tramite `/config/asterisk/eface/intercom_groups.json` e `intercom_groups.conf`.
- Al primo avvio la sola rotta legacy `8290` viene migrata verso il contesto isolato `eface-groups`; il sorgente precedente viene conservato in `extensions.before-intercom-groups.bak` e ogni errore di reload provoca rollback.
- e-Face `2.21.60` mantiene Tutti sincronizzato con i tablet Control4, i telefoni VoIP e i dispositivi personali che hanno DND disattivato. Il DND dei tablet Control4 resta nativo e non viene duplicato da e-Face.
- I gruppi personalizzati si configurano in Amministrazione > Videocitofono selezionando gli interni; nessuna credenziale SIP viene salvata nell'inventario dei gruppi.
- Verifica minima dopo una distribuzione: salute dei due add-on, `dialplan show 8290@eface-test`, `dialplan show 8290@eface-groups`, contenuto non sensibile dell'inventario gruppi e una chiamata reale per convalidare squillo/audio.
- Distribuzione beta verificata il 15/09/2026: Asterisk `6.2.0-eface.9` e e-Face `2.21.60` avviati; health e-Face positivo; backup della rotta legacy presente; `8290@eface-groups` caricato con i Control4 `8291/8292` e gli interni personali correnti `8302–8307`. Gli asset pubblicati espongono ordinamento postazioni esterne, controlli dispositivo/DND e icone dinamiche. Squillo e audio restano una verifica fisica, non deducibile dal solo dialplan.

# Video Intercom e-Face (15/09/2026)

- Prova reale Control4 Ufficio → Poco del 15/09/2026: H.264 viene negoziato e il primo fotogramma è decodificato, ma il touch interrompe poi il video mentre l'audio resta attivo. Il manifest 2015 del driver Control4 `Universal SIP Phone (Communication)` dichiara staticamente `has_camera=false`, `has_display=false` e `videosource=False`; la proprietà dinamica `Camera Enabled=True` non basta quindi a dimostrare un flusso video continuo. Prima di intervenire sul driver confrontare RTP/RTCP tra squillo e risposta; non attribuire il fermo immagine al decoder WebRTC quando Asterisk non riceve più RTP video dal controller.
- La stessa prova ha rilevato due regressioni client separate: il blocco anti-duplicato di 60 secondi generava `486 Busy` alle chiamate immediatamente successive e la UI poteva conservare una chiamata fantasma dopo la chiusura Control4. Dalla 2.21.69 il blocco dura 1,5 secondi e la scheda viene azzerata anche su sessione terminata o PeerConnection `closed/failed`.

- La lettura Director reale del 15/09/2026 conferma che i T3/T4 hanno proxy `intercomproxy` dedicati (`Intercom`, `Intercom 2`, `Intercom 3`) e che il progetto contiene l'agente `control4_agent_videointercom`; sono inoltre presenti i proxy Universal SIP Phone e Asterisk e-Face. Quindi i tablet Control4 non vanno classificati genericamente come incapaci di video. Questo però non cambia da solo il profilo PJSIP Asterisk corrente, che espone soltanto alaw/ulaw: prima di abilitarlo occorre mappare proxy/endpoint e verificare l'offerta SDP reale, mantenendo separati comandi Director `ANSWER/REJECT/HANGUP` e trasporto media SIP.
- Su Android è stato osservato che un Web Push normale poteva restare accodato fino alla riattivazione del Poco. Dalla `2.21.65` il push parte prima di microfono/camera ed è inviato con `Urgency: high` e topic stabile; TTL resta 60 secondi per evitare notifiche di chiamate ormai concluse.

- Prova reale: la chiamata Poco `8303` verso PC `8302` ha squillato, risposto ed è entrata nel bridge, ma non è comparso alcun elemento video nonostante entrambi i dispositivi risultassero abilitati. In e-Face `2.21.62` il pannello viene aperto prima della richiesta camera, mostra permesso o errore effettivo, usa un fallback camera senza vincoli avanzati e non deduce più la possibilità di ricevere video dalla camera del destinatario. La presenza delle immagini resta da confermare con una chiamata reale.

- Gli endpoint WebRTC personali e i telefoni con profilo `voip_video` negoziano H.264/VP8 mantenendo sempre i codec audio. Se la destinazione rifiuta il video con errore di compatibilità, il client riprova una volta solo audio.
- La capacità camera viene rilevata dal dispositivo e salvata con le preferenze `video_enabled` e `camera_facing`; la camera viene richiesta soltanto all'avvio/risposta di una chiamata video, non al semplice caricamento della pagina.
- Il video remoto e locale usa elementi distinti; durante la conversazione l'utente può sospendere la propria traccia o sostituirla con la camera frontale/posteriore senza ricreare la sessione SIP.
- Sull'impianto beta, `core show codecs` conferma H.264 e VP8. I proxy SIP Control4 correnti e `doorbird-p2p-test` espongono soltanto alaw/ulaw: restano audio nei gruppi misti. DoorBird fornisce l'anteprima del chiamante attraverso il proxy video HTTP già autenticato, senza esporre credenziali al browser.
- Test di sorgente e dialplan non provano il video fisico: dopo la distribuzione verificare una chiamata e-Face↔e-Face con camera, una e-Face↔VoIP video e l'anteprima di una chiamata DoorBird; Control4 richiederà una futura configurazione video del proprio proxy Composer/Asterisk prima di poter negoziare immagini SIP.
- Distribuzione beta completata il 15/09/2026 con e-Face `2.21.61` e Asterisk `6.2.0-eface.11`: health positivo, provisioner HTTPS nuovamente raggiungibile, endpoint personali caricati con `opus/alaw/ulaw/h264/vp8`, inventari gruppi leggibili. Gli interni `8306` e `8307`, aperti dopo l'aggiornamento, hanno rilevato e attivato la capacità video; `8302–8305` la rileveranno alla prossima apertura. Durante la verifica è emersa una gara di avvio: il provisioner ora attende fino a 45 secondi `core waitfullybooted` e resta fail-closed oltre il limite. La resa video/audio fisica rimane distinta da queste prove automatiche.
# Vincolo volume sessioni WiiM/Control4

## Catalogo dispositivi routine (20/09/2026)

- In e-Face `2.21.218`, il blocco JSON `protected_cover` contiene `bypass_switches` (solo entità e-Safe `switch.e_safe_zone_<n>_bypass_ctrl` presenti in HA), `enable_delay_seconds` (0–30), `move_seconds` (1–180) e `steps` con sole azioni dirette su cover/luci. Solo admin può salvare o attivare routine che lo contengono; modalità `single`, niente repeat/parallel. Il motore verifica ogni switch OFF, salva il journal in `/data/routines.sqlite3` prima del primo ON, conferma l'ON, esegue le cover e tenta sempre l'OFF verificato. Il journal non viene rimosso finché il ripristino non è confermato; il loop lo ritenta dopo crash/riavvio. Se HA è irraggiungibile non è possibile garantire fisicamente lo stato delle zone: controllare e-Safe prima di riattivare la routine. Test automatici con mock di errore/cancel/recupero; nessuna esclusione reale comandata nel test.
- In `2.21.219` la registrazione di un evento non può interrompere la sequenza di ripristino delle altre zone. Anche con database pieno il journal già confermato rimane, così l'OFF viene ritentato. Test di regressione con due bypass e registro guasto.
- Evidenza live read-only del 20/09: `cover.buspro_cover_finestra_cucina` e `cover.buspro_cover_porta_sala_cx` hanno `supported_features=15` (posizionamento disponibile); `cover.buspro_cover_no_gruppo_tapparelle_1degp_no` ha `supported_features=11` (senza posizione). I sette switch e-Safe richiesti erano tutti `off`. Lettura ripetibile dal container e-Face con `docker exec -i app_d71ab5ec_e_face_x4 python -` e API `http://supervisor/core/api/states/<entity_id>`, usando il token ambiente senza stamparlo. Questo prova le capacità dichiarate, non il movimento fisico né l'esito della prossima esecuzione.

- Dalla `2.21.216` l'editor visuale apre anche `choose` con rami stato/sole/intervallo e blocchi azione/timer/verifica. Serializza nello stesso JSON persistente di Routine Professional; un test riproduce la routine alba+tramonto con `time_window`, 900 secondi e cover `17`, validando salvataggio e riapertura senza inviare comandi fisici. I nodi avanzati non rappresentati (es. `parallel`, `repeat`, `if`) rimangono bloccati alla modifica visuale per non perdere dati.
- Dalla `2.21.217` i blocchi e le scelte del visuale hanno duplicazione indipendente (`structuredClone`) e trascinamento uniforme con maniglia ☰; il registro/JSON continua a persistere nello stesso DB. Il 20/09 il catalogo live e-HDL conferma `17` = Finestra Cucina (1.104.2), `21` = Porta Sala CX (1.104.1), e `cover-group-no-pct:gruppo_tapparelle_1p` con 7 membri, compreso `21`. La routine dell'utente supera la validazione con i passi notturni `[wait 900, close gruppo, wait 1, stop 21]`: lo stop dopo un secondo è una scelta esplicita dell'utente e non va rimosso o allungato. Test ripetibile senza movimento: `python -m pytest tests/test_routines.py -q`.

- Lettura live e-HDL `GET /api/user/snapshot`: 175 dispositivi, fra cui 14 cover BusPro singole con indirizzo subnet/device/channel e 7 gruppi cover. Le cover singole non hanno `entity_id`; e-Face le normalizza in `BusproConnector` e le mostra nel catalogo routine. Il limite frontend di 80 opzioni impediva di raggiungerne alcune. Rimosso in `2.21.215`.
- Le cover singole chiamate “Porta …” sono oscuranti, non serrature: trigger e condizioni leggono lo stato tramite `state_key` HDL; apri/chiudi/stop passano al connettore e-HDL. I dispositivi di tipo `lock` hanno blocca/sblocca, con avviso di rischio per lo sblocco automatico. Non inviare comandi di prova fisici per verificare il catalogo.
- In Admin > Routine Professional il catalogo è leggibile e ricercabile. I filtri `block_sensitive_names` e `hide_readonly_actions` si salvano globalmente nella tabella `routine_settings` del database persistente `/data/routines.sqlite3`. Il filtro dei nomi non si applica a cover o lock; gli allarmi restano esclusi dalle azioni e i comandi fuori whitelist restano vietati anche quando i filtri sono spenti. Verifica ripetibile: `python -m pytest tests/test_routines.py -q`, poi lettura autenticata del catalogo dopo deploy, senza azionare dispositivi.

## Finestra oraria Routine (20/09/2026)

- Schema persistente condiviso: condizione `{"type":"time_window","start":{"kind":"sunset","offset_minutes":0},"end":{"kind":"time","at":"23:00"}}`. Ogni estremo ammette `kind=time` con `at=HH:MM`, oppure `kind=sunrise|sunset` con `offset_minutes` intero tra -180 e +180. Inizio incluso, fine esclusa; se la fine precede l'inizio si usa una finestra oltre mezzanotte (es. tramonto→alba). Inizio e fine identici sono rifiutati.
- La condizione è disponibile nell'editor visuale e in Routine Professional. Le finestre solari richiedono posizione/fuso validi da HA; le finestre solo orarie usano il fuso `Europe/Rome` già impiegato dallo scheduler. Non aggiunge trigger ripetuti né comandi, quindi non apre nuovi loop; il controllo avviene solo quando arriva un trigger esistente.
- Test ripetibile senza azionare dispositivi: `python -m pytest tests/test_routines.py -q`. Il registro degli eventi indica soglie calcolate e ora di verifica; non è stata necessaria una prova fisica per il contratto temporale.

## Scenari e-HDL in Strumenti (20/09/2026)

- Evidenza: le letture live `GET /api/user/light_scenarios`, `/api/user/light_scenarios_status`, `/api/user/devices`, `/api/cover_groups` e `/api/user/scenario_ha_triggers` mostrano 11 scenari persistiti in e-HDL. La nuova UI e-Face usa il catalogo sorgente e non mantiene una seconda copia degli scenari.
- Contratto di scrittura verificato nel codice e-HDL: `POST/PUT/DELETE /api/user/light_scenarios[/{id}]`; luci BusPro/HA con stato e luminosità, tapparelle singole/gruppo/HA con comandi, posizione e rampa, combinazioni BusPro, RUN/ON-OFF, orario/alba/tramonto/sveglia e trigger HA. La libreria dei trigger HA usa la porta amministrativa e-HDL e richiede l'account admin e-Face.
- Confine di sicurezza: e-Face verifica i target contro il catalogo live, limita numeri e quantità, non accetta URL/comandi arbitrari e rifiuta modifiche concorrenti tramite impronta dello scenario letto. I target orfani già presenti possono essere mantenuti durante una modifica, non aggiunti di nuovo. Eliminare un trigger HA scollega gli scenari associati: richiede conferma esplicita.
- Controllo ripetibile senza azionare l'impianto: leggere i cinque endpoint, validare ogni scenario esistente contro catalogo/gruppi/trigger, eseguire `python -m pytest tests/test_scenario_editor.py -q`. Le prove RUN/ON/OFF da UI mutano l'impianto e restano manuali e confermate dall'utente.
- Distribuzione verificata: e-Face `2.21.210` risulta `started`, `/health` risponde con la versione corretta e l'asset Scene Studio è servito con HTTP 200. La resa visiva autenticata e l'azionamento fisico non sono deducibili da queste sonde e non sono stati provati automaticamente.
- Estensione `2.21.211`: lo snapshot utente e-HDL include `cover_groups` (7 gruppi verificati il 20/09/2026). e-Face li normalizza come `cover-group:{id}` nella pagina Oscuranti, aggregando stato e posizione dei membri senza creare stanze; OPEN/CLOSE/STOP passano a `POST /api/control/cover_group/{id}` dopo verifica dell'ID nel catalogo live. Ordine e flag UI dei gruppi usano `device_organization` persistente condivisa, categoria `covers`.
- Estensione `2.21.213`: e-HDL pubblica anche la variante discovery `group_{id}_no_pct`, che comanda lo stesso gruppo fisico con OPEN/CLOSE/STOP raw senza percentuale. La sonda HA ha trovato 7 entità corrispondenti; e-Face espone quindi 7 schede aggiuntive `cover-group-no-pct:{id}` con posizione sempre assente e preferenze di visibilità/ordine indipendenti, senza scrivere nuovi gruppi e-HDL né creare stanze.

Quando WiiM è selezionato come sorgente di una stanza Control4, WiiM è autorevole soltanto per metadati e trasporto. Volume e mute devono essere letti e comandati tramite Control4, stanza per stanza. Il master multiroom applica un delta relativo: 40/50 con +10 deve produrre 50/60, mai due valori uguali. Il contratto eseguibile è documentato in `e_face_x4/docs/TASK_VOLUME_MASTER_PROPORZIONALE.md` e protetto dai test.
