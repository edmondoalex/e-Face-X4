# Navigatore servizi musicali Control4 in e-Face

Stato al 13 settembre 2026: **non completato**. Il popup provvisorio della 2.20.79 è stato rimosso nella 2.20.80 perché non forniva il navigatore richiesto e si apriva anche su sorgenti MP3 generiche. La 2.20.81 ripristina la sezione «Ascoltati di recente» sotto il player; non va confusa con la Home/Recents interna al servizio. Non sono ancora disponibili Sfoglia, Cerca, Preferiti e i menu azioni del driver.

## Comportamento richiesto

- Clic sulla cover in Ascolta: popup della sorgente attiva (TuneIn, Amazon Music, TIDAL e, in seguito, altri media service).
- Clic fuori, Esc o Chiudi: chiusura del solo popup, senza interrompere la musica.
- Schede e schermate fornite dal driver: Home, Sfoglia, Preferiti, Cerca e impostazioni quando presenti. Non fissare gli stessi tab per tutti i servizi. **Nel popup**, riprendere il navigatore delle foto Control4: intestazione della sorgente, schede orizzontali, righe a tutta larghezza con icona/cover, titolo, sottotitolo e menu ⋮, più ricerca dedicata, nello stile cromatico e-Face. **Sotto il player nella vista Ascolta**, mantenere la striscia globale «Ascoltati di recente» e aggiungere in futuro i preferiti del solo servizio attivo come griglia di cover senza scritte visibili, una volta disponibili dal driver. Non mettere la cronologia globale dentro il popup.
- Cartelle, contenuti, immagini e menu azioni letti dal driver; selezione di una stazione/brano avvia la riproduzione nella stanza corretta.
- Preferiti dell'account del servizio e preferiti della stanza Control4 restano distinti.

## Protocollo verificato nella documentazione ufficiale

- Specifica MSP OS 3.2.1: https://github.com/control4/docs-driverworks/blob/master/media_service_proxy/MSP%20Driver%20Development%20Documentation%20OS%203.2.1.pdf
- Libreria comune Snap One: https://github.com/control4/drivers-common-public/blob/master/global/msp.lua
- Il Navigator invia `ROOMID`, `NAVID`, `SEQ` e `ARGS` al Media Service Proxy. Il driver restituisce `DATA_RECEIVED` con gli stessi `NAVID` e `SEQ`; `DATA` contiene XML di lista, collezione o navigazione.
- La UI del driver definisce `Tabs`, `Screens`, `DataCommand`, `DefaultAction`, `ItemActionIdsProperty` e `ItemDefaultActionProperty`. Gli `ARGS` degli elementi vengono dalla selezione, non da un elenco di comandi universale.
- Le foto e il log Composer del sistema reale mostrano `GetTabList`, `Browse` (`screenId=HomeScreen` per Amazon), `GetSettingsScreen`, `GetSettings`; il driver restituisce il link di autenticazione con eventi separati.

## Diagnosi storica precedente alla verifica live

Il test reale su TuneIn 614 ha escluso la normale API `POST /api/v1/items/{id}/commands` come ingresso sufficiente per il Navigator: `GetTabList` restituisce `result: 1` (intero), senza XML né `NAVID`; sul canale `dataToUi` compaiono eventi `LUA_OUTPUT` e aggiornamenti proprietà, non una risposta MSP correlata. Non convertire un `200` del comando in «navigazione riuscita».

Nell'APK dell'app Control4 per Android sono presenti i modelli `MSPResponse` (`navId`, `seq`, `data`) e `MSPEvent` (`name`, `navId`, `rooms`, `args`). Il modello media service dell'app sottoscrive `MediaService.observeResponse()` e `observeEvent()`; la prima emissione è una `Variable.value` convertita in `MSPResponse`. Questo indica che la risposta MSP va cercata nella sottoscrizione di variabili del media service, non nei soli eventi `LUA_OUTPUT`. L'endpoint/protocollo concreto che genera tale variabile va ancora individuato. Gli esempi non verificati `GetItems`/`SendItems`, `container_id=root` e `PLAY_MEDIA` ricevuti in chat **non** sono un contratto API e non vanno implementati come se fossero osservati.

Dettaglio verificato nell'APK: `MediaService.observeResponse()` ha annotazione `VariableMethod(dataToUi=true, value="data.RESPONSE", type=MSPResponse)`; `observeEvent()` usa `data.EVENT`. La libreria nativa `MSPModel` espone `getTabs`, `getScreen`, `back`, `search`, `executeFavorite` e produce i comandi tramite `MSPModelClient`. Questo conferma che non è un generico albero JSON `GetItems`/`SendItems`.

## Implementazione successiva

1. Acquisire una singola traccia completa richiesta/risposta `GetTabList` e `Browse` dal Director o dall'emulatore, senza credenziali nei log e senza aggiornamenti ripetuti dell'add-on.
2. Costruire un adattatore backend per sessione `NAVID` per coppia stanza/servizio, correlazione `SEQ`, timeout, parsing XML sicuro e whitelist di comandi/azioni realmente dichiarati dal driver.
3. Rendere in e-Face le schede e i contenuti ricevuti, con back stack, ricerca, loading/errori, cover via proxy immagini già esistente e azioni per elemento.
4. Verificare su TuneIn, Amazon e TIDAL: apertura sorgente senza audio, ricerca e scelta contenuto, Play, preferito servizio, preferito stanza, ritorno al player e chiusura esterna.

## Verifica sul Director del 14/09/2026 e prima integrazione

- TuneIn v26 installato: dispositivo Lua `614`, proxy UI `media_service` `615` con binding `5001`. Il secondo Ã¨ il target REST per la navigazione.
- Il file `driver.xml` della v26 conferma `GetTabList`, `GetBrowseScreen`, i tab `Home`, `Browse`, `Favorites`, `Settings` e il filtro di ricerca `fulltextsearch`.
- `ARGS` non puÃ² essere vuoto: il driver produce `LUA_ERROR parsedArgs nil`. Con XML `<args/>`, `GetTabList` ha restituito sul WebSocket `OnDataToUI` del proxy `615` il campo `data.RESPONSE = {NAVID, SEQ, DATA}` e quattro tab reali.
- `GetBrowseScreen` richiede `screenId=BrowseScreen`, `tabId`, `offset` e `limit` dentro gli `<arg name="...">`; senza paginazione `DATA` Ã¨ vuoto. Verificati live Browse con otto categorie e figlio Local Radio con stazioni reali. Ricerca verificata con `search=relax` e `filter=fulltextsearch`.
- La versione 2.20.86 introduce il primo popup TuneIn e l'adattatore backend. `Url` e `GuideId` rimangono nel server sotto ID temporanei: non sono trasmessi al browser. La scheda Impostazioni espone solo stato e nome utente, mai la password del driver. Ancora da collaudare sulla UI installata: Play, Follow/Unfollow, preferito stanza e comportamento visuale del popup. Amazon e TIDAL richiedono l'analisi dei rispettivi `driver.xml` prima di estendere l'adattatore.
- Il 14/09/2026 l'utente ha confermato la navigazione funzionante. V2.20.87 corregge il parser `actions_list`: il driver separa gli ID delle azioni con spazi, non virgole. `Play` come azione predefinita deve funzionare anche senza `actions_list`. Play Ã¨ stato verificato passando da ENERGY Hits 2026 a ENERGY Dance e tornando alla stazione iniziale; Follow/Unfollow sono stati verificati e ripristinati.
- Due stanze che mostrano la stessa radio possono avere percorsi tecnici diversi: Ufficio Alex `CURRENT_AUDIO_DEVICE=100002` (Digital Media), `PLAYING_AUDIO_DEVICE=615` (TuneIn), Sala entrambi `615`. Con la stessa cover e lo stesso album, la UI ora le presenta come una sessione logica e usa l'icona TuneIn in entrambe. Il Director non le segnala come un'unica coda nativa.
