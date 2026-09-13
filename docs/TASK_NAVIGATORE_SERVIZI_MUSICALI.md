# Navigatore servizi musicali Control4 in e-Face

Stato al 13 settembre 2026: **non completato**. Il popup provvisorio della 2.20.79 è stato rimosso nella 2.20.80 perché non forniva il navigatore richiesto e si apriva anche su sorgenti MP3 generiche. Non sono ancora disponibili Sfoglia, Cerca, Preferiti e i menu azioni del driver.

## Comportamento richiesto

- Clic sulla cover in Ascolta: popup della sorgente attiva (TuneIn, Amazon Music, TIDAL e, in seguito, altri media service).
- Clic fuori, Esc o Chiudi: chiusura del solo popup, senza interrompere la musica.
- Schede e schermate fornite dal driver: Home, Sfoglia, Preferiti, Cerca e impostazioni quando presenti. Non fissare gli stessi tab per tutti i servizi. **Nel popup**, riprendere il navigatore delle foto Control4: intestazione della sorgente, schede orizzontali, righe a tutta larghezza con icona/cover, titolo, sottotitolo e menu ⋮, più ricerca dedicata, nello stile cromatico e-Face. **Sotto il player nella vista Ascolta**, niente cronologia globale: mostrare invece i preferiti del solo servizio attivo come griglia di cover senza scritte visibili, una volta disponibili dal driver.
- Cartelle, contenuti, immagini e menu azioni letti dal driver; selezione di una stazione/brano avvia la riproduzione nella stanza corretta.
- Preferiti dell'account del servizio e preferiti della stanza Control4 restano distinti.

## Protocollo verificato nella documentazione ufficiale

- Specifica MSP OS 3.2.1: https://github.com/control4/docs-driverworks/blob/master/media_service_proxy/MSP%20Driver%20Development%20Documentation%20OS%203.2.1.pdf
- Libreria comune Snap One: https://github.com/control4/drivers-common-public/blob/master/global/msp.lua
- Il Navigator invia `ROOMID`, `NAVID`, `SEQ` e `ARGS` al Media Service Proxy. Il driver restituisce `DATA_RECEIVED` con gli stessi `NAVID` e `SEQ`; `DATA` contiene XML di lista, collezione o navigazione.
- La UI del driver definisce `Tabs`, `Screens`, `DataCommand`, `DefaultAction`, `ItemActionIdsProperty` e `ItemDefaultActionProperty`. Gli `ARGS` degli elementi vengono dalla selezione, non da un elenco di comandi universale.
- Le foto e il log Composer del sistema reale mostrano `GetTabList`, `Browse` (`screenId=HomeScreen` per Amazon), `GetSettingsScreen`, `GetSettings`; il driver restituisce il link di autenticazione con eventi separati.

## Punto tecnico ancora da verificare sul Director reale

L'API REST `POST /api/v1/items/{id}/commands` usata oggi da e-Face invia comandi generici, ma non è documentata come client Navigator MSP. Prima di mostrare schede operative serve verificare se un comando `Browse` con sessione `NAVID` produce i `DATA_RECEIVED` correlati, oppure individuare il canale Navigator usato dall'app Control4. Non convertire un `200` del comando in «navigazione riuscita» se i dati XML non arrivano.

## Implementazione successiva

1. Acquisire una singola traccia completa richiesta/risposta `GetTabList` e `Browse` dal Director o dall'emulatore, senza credenziali nei log e senza aggiornamenti ripetuti dell'add-on.
2. Costruire un adattatore backend per sessione `NAVID` per coppia stanza/servizio, correlazione `SEQ`, timeout, parsing XML sicuro e whitelist di comandi/azioni realmente dichiarati dal driver.
3. Rendere in e-Face le schede e i contenuti ricevuti, con back stack, ricerca, loading/errori, cover via proxy immagini già esistente e azioni per elemento.
4. Verificare su TuneIn, Amazon e TIDAL: apertura sorgente senza audio, ricerca e scelta contenuto, Play, preferito servizio, preferito stanza, ritorno al player e chiusura esterna.
