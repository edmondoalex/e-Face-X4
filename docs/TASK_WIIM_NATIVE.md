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
