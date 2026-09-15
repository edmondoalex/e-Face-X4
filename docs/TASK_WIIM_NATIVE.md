# Task: integrazione WiiM nativa in e-Face

Stato iniziale: 15 settembre 2026.

## Decisione

L'integrazione profonda sarà un provider e-Face nativo che comunica direttamente con WiiM. Home Assistant non sarà il backend funzionale e Control4 resterà responsabile soltanto della selezione della sorgente e della distribuzione audio nelle stanze.

Il percorso applicativo è esplicitamente **e-Face → WiiM**. Né Home Assistant né il proxy media-service Control4 devono trovarsi nel percorso di navigazione, lettura dello stato o comando del dispositivo WiiM. L'associazione con una stanza Control4 è opzionale e successiva alla scelta del contenuto.

## Impianto verificato

- WiiM Pro `192.168.3.52`, collegato via Ethernet e raggiungibile in HTTPS.
- Firmware osservato: `Linkplay.4.8.827634`; progetto hardware `WiiM_Pro_with_gc4a`.
- Control4: protocollo Linkplay `1666`, media-service `1667`, amplifier `1668`, rete `1669`; driver `WiiM-Pro.c4z` versione 19.
- Sorgente Control4: `listen:1667`, tipo `RF_WIIM_WS_MUSIC`, attiva durante la sonda in Ufficio Alex e disponibile in più stanze.
- Home Assistant 2026.8.3 contiene già l'integrazione ufficiale `wiim`, scoperta via Zeroconf, ma viene considerata troppo limitata per l'interfaccia richiesta.

## Dati nativi già verificati

Le API locali `getStatusEx`, `getPlayerStatus` e `getMetaInfo` restituiscono stato, volume, mute, posizione, durata, titolo/artista/album, identificativo traccia, sample rate, bit depth, bitrate e URL della cover. I campi testuali del player possono essere codificati in esadecimale UTF-8.

Il driver Control4 espone comandi base, 12 preset, code e repeat/shuffle. Il suo Lua è cifrato; il manifest dichiara soltanto le schede Presets e Queue, quindi non offre il catalogo profondo dei servizi.

## Architettura prevista

1. Client WiiM LAN sicuro, limitato a IPv4 private, timeout breve e output normalizzato.
2. Inventario/discovery nativo di uno o più WiiM, senza dipendenza funzionale da HA o Control4.
3. Player completo: metadata, cover proxy/cache, qualità, timeline, volume, mute, repeat e shuffle.
4. Preset, coda, ingressi, EQ e multiroom WiiM.
5. Collegamento opzionale con la stanza Control4 che sta usando quella sorgente.
6. Adattatori separati per ricerca e librerie Spotify, TIDAL, Qobuz, Amazon Music e altri servizi, usando solo API/autorizzazioni supportate. L'API locale WiiM non va trattata come catalogo universale.

## Avanzamento 2.21.70

Creati `app/connectors/wiim.py` e `tests/test_wiim.py` con validazione LAN, client HTTPS, decodifica metadata e snapshot normalizzato. È disponibile in Amministrazione la scheda WiiM nativa con configurazione persistente, test diretto e riepilogo del dispositivo. Il salvataggio avviene soltanto dopo una verifica positiva, così un indirizzo errato non sostituisce una configurazione funzionante.

Restano da sviluppare l'inventario multi-player/discovery, la pagina WiiM per l'utente, i comandi completi e gli adattatori dei servizi musicali.

## Avanzamento 2.21.71

Aggiunta la pagina WiiM nella navigazione principale con polling diretto ogni due secondi, cover, metadata, timeline, qualità, volume, mute, trasporto e preset. I comandi ammessi sono tradotti server-side tramite una allowlist; il browser non può inviare comandi Linkplay arbitrari. Restano aperti discovery multi-player, coda/ingressi/EQ/multiroom e gli adattatori autenticati per i cataloghi dei servizi musicali.

## Avanzamento 2.21.72

Predisposta la funzione multiroom con endpoint nativo read-only basato su `getStatusEx` e `multiroom:getSlaveList`. Sul WiiM Pro di prova il protocollo WMRM 4.3 risponde correttamente e il player risulta autonomo. La UI mostra già ruolo, gruppo e membri; le operazioni distruttive di join/kickout non vengono esposte finché non saranno verificate con almeno due WiiM reali.

## Decisione interfaccia e cataloghi — 15/09/2026

La console player introdotta nelle versioni 2.21.71–72 viene spostata dalla navigazione utente all'area Amministrazione e conservata come strumento di debug. La futura esperienza utente musicale sarà una pagina distinta, orientata a ricerca, libreria e scelta della zona, non una copia della console tecnica.

La guida ufficiale WiiM descrive ricerca universale e navigazione per brani, artisti, album, playlist, stazioni e show nell'app WiiM Home. L'API HTTP locale ufficialmente documentata non espone però un catalogo universale equivalente. Architettura scelta: adattatori e-Face separati per ciascun servizio e relativa autorizzazione ufficiale; WiiM resta la destinazione locale di riproduzione. Primo provider da preparare: Spotify. Non verranno acquisiti token privati dell'app WiiM né usate API cloud non documentate.

Servizi richiesti per l'inventario: Amazon Music, BBC Radio, Calm Radio, Deezer, Hotmix, iHeartRadio, SoundCloud, YouTube Music, Spotify, TIDAL, Qobuz, radio/podcast, libreria locale e gli ulteriori servizi che emergeranno dal dispositivo/app. `Apri flusso di rete` è prioritario perché può usare direttamente URL audio o playlist supportati dal WiiM. YouTube Music non dispone di un catalogo pubblico ufficiale adatto a questa integrazione: verranno valutati soltanto Cast, apertura dell'app o futuri percorsi ufficiali, non scraping o token privati.

## Avanzamento 2.21.74

Il seek usa il comando ufficiale `setPlayerCmd:seek:<secondi>` ed è collegato allo slider della console. Aggiunti i controlli e-Face per shuffle/ripetizione e predisposte le azioni playlist/preferito per il catalogo.

SoundCloud diventa il primo provider. Implementati archivio credenziali protetto, Client Credentials OAuth e ricerca tracce con identificatori URN. La configurazione richiede Client ID e Client Secret di un'app SoundCloud; non usa la password personale. Restano da implementare OAuth utente con PKCE per likes/playlist personali e il relay di playback autorizzato verso WiiM.

## Avanzamento 2.21.76

Prima dell'inserimento nella pagina utente Ascolta è disponibile in Amministrazione una console SoundCloud di collaudo a tutto schermo. Riusa il player WiiM nativo e supporta ricerca di brani, playlist e artisti, apertura di playlist/profili, correlati, cronologia e preferiti locali e-Face. Il backend richiede uno stream ufficiale con OAuth, preferisce HLS AAC 160/96 e passa il relativo URL HTTPS al comando WiiM documentato `setPlayerCmd:play:url`; credenziali e token restano server-side. Da verificare fisicamente: durata effettiva dei signed URL sul firmware installato e riproduzione continua. Likes e libreria personale SoundCloud richiedono ancora consenso utente OAuth Authorization Code + PKCE.

## Avanzamento 2.21.77

Scelta corretta dopo verifica dei costi: non usare l'API SoundCloud a pagamento nel percorso utente. I preset nativi del WiiM vengono aggiunti dinamicamente ai Preferiti e-Face, con cache di 10 secondi, cover, icona del servizio e icona WiiM. Non sono copiati nell'archivio preferiti e non mostrano il comando Rimuovi: la fonte della verità resta l'app WiiM.

Sonda read-only del 15/09/2026 sul WiiM di prova: quattro preset disponibili, uno Spotify, uno YouTube Music e due SoundCloud. Il descrittore `http://<wiim>:49152/description.xml` espone AVTransport, RenderingControl, ConnectionManager, PlayQueue e QPlay. Gli ID e i nomi dei preset devono sempre essere letti dal dispositivo, non fissati nel codice. Il tocco su un preset e-Face richiama `MCUKeyShortClick:<indice>`; la prova audio fisica resta distinta dai test automatici.

## Avanzamento 2.21.78

Il richiamo di un preset è ora coordinato con Control4: e-Face valida la stanza corrente e il `control4_source_id`, avvia il preset direttamente sul WiiM e seleziona poi `listen:<control4_source_id>` nella stanza tramite il comando nativo Control4 `set_audio_source`. In questo modo una sessione precedente, per esempio Spotify Connect, non resta selezionata nella stanza. La UI continua a eseguire il refresh immediato e differito di stato e copertina. Se il preset è partito ma Control4 non accetta il cambio sorgente, l'endpoint restituisce un errore esplicito di successo parziale.

## Task aperto: richiamo esatto di un brano cloud

Obiettivo: consentire a e-Face di salvare e richiamare lo stesso brano attualmente riprodotto dal WiiM, anche quando proviene da YouTube Music, SoundCloud o un altro servizio cloud, senza usare API private o sottrarre credenziali all'app WiiM.

Riferimento tecnico da riesaminare: progetto community `cvdlinden/wiim-httpapi`, che documenta l'API HTTP LinkPlay/WiiM e in particolare `MCUKeyShortClick:<preset>:<track>`. Il secondo parametro seleziona una traccia, numerata da 1, all'interno del contenuto associato al preset. Il progetto è un proxy/OpenAPI sopra la medesima API locale del dispositivo e non offre autonomamente accesso ai cataloghi o agli stream protetti dei provider.

Evidenza read-only del 15/09/2026 sul WiiM Pro firmware `Linkplay.4.8.827634`, durante la riproduzione YouTube Music di “GIGI D'AGOSTINO - RADICI DAG - [ IERI E OGGI MIX VOL 1 ]”:

- `getMetaInfo` espone titolo, artista, copertina e `trackId`, ma non un URL audio riproducibile;
- `getPlayerStatus` restituisce `vendor=YouTubeMusic`, `mode=10`, `plicurr=0` e `plicount=0`;
- `getPresetInfo` restituisce `url=unknow` per tutti i sei preset cloud;
- `getStatusEx.preset_key=12` indica il numero di tasti preset disponibili, non il preset corrente;
- non è quindi possibile associare in modo affidabile il brano corrente a una coppia `<preset>:<track>` usando i dati osservati.

Prova mutante controllata del 15/09/2026 sul preset 6 “Cover e remix” (YouTube Music): il firmware accetta `MCUKeyShortClick:6:1` e `MCUKeyShortClick:6:2` restituendo `OK` e cambia effettivamente brano. La prima sequenza ha prodotto rispettivamente “Universe Of Love (Extended Mix)” e “Just a Film”. Ripetendo però lo stesso comando `MCUKeyShortClick:6:1` è partito “9 PM (Till I Come)”, non “Universe Of Love”. Lo shuffle era disattivato (`loop=4`) e `plicurr/plicount` sono rimasti entrambi a zero. Su questo preset cloud il parametro traccia non costituisce quindi un identificatore stabile: il richiamo rigenera o ricarica una coda YouTube Music dinamica.

### Percorso UPnP verificato

Una cattura passiva limitata esclusivamente all'IP del WiiM ha mostrato che WiiM Home apre sul PC una callback HTTP UPnP (`NOTIFY /Event`) per AVTransport e PlayQueue. Gli eventi contengono dati che `getPlayerStatus`/`getMetaInfo` non espongono: `CurrentTrackURI`, metadati DIDL-Lite, ID playlist e brano, indice corrente e numero elementi. Non è necessario mantenere uno sniffer: la stessa informazione è ottenibile direttamente e in sola lettura con l'azione SOAP `GetPositionInfo` su `/upnp/control/rendertransport1`.

Prova end-to-end del 15/09/2026: e-Face ha letto in memoria URI firmato e metadati di “GIGI D'AGOSTINO - RADICI DAG - [ IERI E OGGI MIX VOL 1 ]”, ha avanzato a “Amore Mio (T'AMO T'AMO T'AMO)” e ha poi inviato `SetAVTransportURI` seguito da `Play`. Il WiiM è tornato esattamente al primo titolo. L'URL non è stato stampato, versionato o conservato dopo la prova.

Questa verifica dimostra il richiamo esatto **finché il CurrentTrackURI firmato è valido**. Prima dell'integrazione utente occorre misurarne la scadenza, verificare comportamento dopo riavvio e distinguere contenuti riutilizzabili da URL temporanei. L'archivio e-Face non deve persistere URL firmati oltre il necessario né esporli al browser; URI e metadati devono restare server-side. Se il link è scaduto, la UI deve dichiararlo senza ripiegare silenziosamente sul preset dinamico.

La riproduzione del solo `CurrentTrackURI` termina dopo quel brano perché `SetAVTransportURI` non ricostruisce la coda. `BrowseQueue` sul servizio WiiM `PlayQueue:1` ha invece restituito la coda YouTube Music corrente completa: 50 tracce, `SearchUrl`, ID, metadati, URL, `LastPlayIndex` e nome lista. Prova reale con `PlayQueueWithIndex`: dal brano “Do You Hear Me” è stato eseguito Next verso “Surrender (Birretta Edit)”, poi l'indice 1 ha richiamato esattamente “Do You Hear Me” e un nuovo Next è tornato a “Surrender”. Il richiamo via coda conserva quindi la prosecuzione, a differenza del singolo URI.

`BackUpQueue` applicato a una copia rinominata del contesto cloud ha restituito HTTP 500; la coda temporanea di test è stata rimossa. Non considerare quindi ancora verificata la persistenza di una coda cloud nominata nel WiiM. La prossima sonda deve analizzare `CreateQueue`/`ReplaceQueue` e soprattutto `GetQueueOnline`/`SearchQueueOnline`, che potrebbero rigenerare gli URL scaduti da `SearchUrl` e ID senza conservare token nel file preferiti.

Sonda successiva: il contesto della coda “Cover e remix” dichiara `ContentType=station`, 200 elementi e un `SearchUrl` verso `youtubemediaconnect.googleapis.com/v1/playlists/<id>:loadItems`. La chiamata diretta al SearchUrl restituisce 401 perché l'autorizzazione resta nel modulo WiiM/YouTube Music; non va copiata dall'app. `GetQueueOnline` ha restituito HTTP 500 sia con QueueName `0` sia con il nome lista e con le varianti di ID playlist ricavate dal DIDL/SearchUrl. Il contratto SCPD non dichiara valori ammessi o default per QueueType/QueueAutoInsert. Occorre quindi catturare la richiesta SOAP originale generata da WiiM Home durante il caricamento/rinnovo della coda, oppure ricostruire la firma dei parametri dal modulo locale, prima di implementare il rinnovo automatico.

Prossime verifiche, in ordine:

1. Salvare fixture redatte di `getPlayerStatus`, `getMetaInfo` e `getPresetInfo` per ciascun provider e confrontare i campi durante avvio preset, cambio traccia e riapertura dell'app WiiM.
2. Implementare un client UPnP server-side minimo per `GetPositionInfo`, `SetAVTransportURI`, `Play`, `BrowseQueue` e `PlayQueueWithIndex`, con validazione LAN, XML sicuro, timeout e URL mai restituiti al browser; AVTransport e PlayQueue hanno già confermato URI, indice, coda e DIDL-Lite aggiuntivi.
3. Ripetere `MCUKeyShortClick:<preset>:<track>` su un preset locale o una playlist statica con indice noto: la prova YouTube Music è completata e ha dimostrato che lo stesso indice non è deterministico per quel contenuto cloud.
4. Se il firmware continua a nascondere indice e URI per i servizi cloud, limitare la funzione ai provider/contenuti che restituiscono un riferimento riproducibile e mostrare chiaramente “richiama preset” invece di promettere “richiama brano”.
5. Non memorizzare token dell'app WiiM, URL firmati privati o credenziali dei provider e non dedurre il numero traccia dal solo titolo, perché shuffle e duplicati renderebbero il richiamo inaffidabile.

Criterio di completamento: la prova nella stessa sessione è riuscita. Per chiudere il task resta da dimostrare che e-Face gestisce correttamente link valido e link scaduto, senza esporre URI firmati, e che dopo il richiamo aggiorna Control4, titolo, copertina e posizione iniziale.

## Avanzamento 2.21.79

Il player principale Ascolta riconosce la sorgente WiiM attiva nella stanza Control4 e integra la timeline nativa: polling ogni due secondi di posizione/durata, tempo trascorso e residuo, e seek tramite `setPlayerCmd:seek:<secondi>`. Shuffle e repeat agiscono direttamente sul WiiM e preservano le modalità combinate LinkPlay 0–5; precedente, play/pausa, successivo, volume e zone restano sul percorso Control4 già operativo per la stanza. Il pulsante coda non viene mostrato finché non dispone di un pannello utente completo e realmente comandabile.

## Verifica PlayQueue del 15/09/2026

Il `description.xml` reale dichiara il service type proprietario `urn:schemas-wiimu-com:service:PlayQueue:1`, non `urn:schemas-upnp-org:service:PlayQueue:1`. Endpoint e azione corretti con namespace errato restituiscono sistematicamente SOAP/HTTP 500 e avevano falsato parte delle sonde precedenti.

Con il namespace corretto, `BrowseQueue` e `BrowseQueueEx` rispondono 200 sulla coda YouTube Music attiva. `BrowseQueueEx` con indice 0 e limite 10 restituisce esattamente 10 elementi, mentre `BrowseQueue` ne restituisce 200; il contesto dichiara `ContentType=station` e `LastPlayIndex=6`. Sul firmware osservato, i valori di `QueueName` provati (`0`, titolo della lista e ID provider) hanno restituito la medesima coda attiva: non considerarli quindi identificatori convalidati finché non vengono confrontate più code.

`GetQueueOnline` continua a restituire 500 anche usando il namespace corretto, l'ID playlist rilevato e una matrice minima `QueueType={station,0,1,10}` / `QueueAutoInsert={0,1}`. Resta necessario acquisire la richiesta originale di WiiM Home. La cattura va limitata a `192.168.3.52:49152`; questa porta usa HTTP in chiaro e non richiede MITM TLS. Non conservare URL firmati o dati di autorizzazione presenti nel `QueueContext`.
