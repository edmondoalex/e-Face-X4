# Collegamento Ekonex Platform

### Comandi Comfort Netatmo e release cumulativa - 2026-10-03

- Release candidata `2.21.304`: include integralmente la precedente candidata `2.21.303` e aggiunge il comando dei dispositivi climate Home + Control/Netatmo.
- Il consumer Smart Home riconosce `device_class=climate`, espone temperatura, setpoint, modalita' e richiesta termica e abilita `set_target` quando autorizzato dal producer.
- La scheda Comfort riusa il layout termostato esistente con pulsanti meno/piu'; il comando viene inviato soltanto tramite la rotta Smart Home e-Control validata.
- Test completi: `419 passed`; test Smart Home mirati `32 passed`; sintassi JavaScript, compilazione Python e diff check superati.
- Nessun setpoint reale inviato durante il collaudo automatico.

### Integrazioni esterne e meteo dettagliato - 2026-10-02

- Versione candidata locale: `2.21.303`.
- Le diciture visibili `HA`/`Home Assistant` del catalogo dispositivi sono sostituite da `Integrazioni esterne`; gli identificativi tecnici `home_assistant`, Discovery, MQTT e i collegamenti esistenti restano invariati.
- `GET /api/home/weather` estende in modo additivo la risposta con `hourly` e nuovi campi giornalieri Open-Meteo per cinque giorni. Il riquadro Home apre un pannello responsive con selezione del giorno, riepilogo e andamento orario.
- La vista dispositivi conserva nel DOM il renderer attivo; il filtro `Extra > Senza stanza` non può più riutilizzare il renderer Sicurezza. Il click del menu stanza viene inoltre fermato prima di raggiungere controlli sottostanti.
- Nessun contratto condiviso modificato e nessuna nuova credenziale o dipendenza esterna introdotta.
- Nessun commit, push, aggiornamento o deploy eseguito.

Questo progetto fa parte dell'ecosistema coordinato Ekonex.

Fonte condivisa ufficiale:

`../_EKONEX_PLATFORM/`

Prima di modificare identità, ruoli, API, eventi, licenze, pairing, cloud/locale/offline o sicurezza, leggere tutti i documenti indicati in `../_EKONEX_PLATFORM/README.md`.

## Regole per il Codex di questo progetto

1. Lavorare soltanto in questo progetto.
2. Non cambiare unilateralmente un contratto condiviso.
3. Usare una proposta `CHANGE-YYYY-NNN` per modifiche trasversali.
4. Conservare retrocompatibilità con le installazioni esistenti.
5. Non inserire segreti o dati cliente nei documenti.
6. A fine lavoro compilare la sezione handoff qui sotto.
7. Non modificare direttamente lo stato centrale: consegnare l'handoff al coordinatore e-Manager.

## Handoff corrente

### Coerenza eventi DoorBird - 2026-10-02

- Versione candidata locale: `2.21.302`.
- Diagnosi live: il pulsante `102` (`Primo Piano`) e il relativo timestamp venivano salvati indipendentemente dal JPEG; in caso di snapshot fallito restava visibile il chiamante precedente. Il refresh Home risalvava inoltre lo stesso storico, rendendo recente il file senza creare un nuovo evento.
- Chiamata e movimento usano ora bundle verificati con hash SHA-256, timestamp, stazione e origine. Una chiamata senza immagine mostra indisponibilità; non riusa più il vecchio JPEG.
- Il polling movimento aggiorna il bundle soltanto quando cambia realmente l'immagine restituita dalla cronologia; la migrazione del vecchio record conserva l'orario se il JPEG è invariato.
- Nessun contratto condiviso, identificativo, MQTT o Discovery modificato.
- Nessun commit, push, aggiornamento o deploy eseguito.

### Scheda Meteo responsive - 2026-10-02

- Versione candidata locale: `2.21.302`.
- La scheda Meteo usa container query e scala in base alla propria larghezza, indipendentemente dal viewport generale.
- Le altezze Bassa, Media, Alta e Uniforme hanno dimensioni effettive; nei formati stretti o bassi vengono ridotti progressivamente dettagli, tipografia, icone e numero di giorni visibili senza sovrapposizioni.
- Test mirati Home/versione/health: `3 passed`; JavaScript, compilazione Python e diff check superati.
- Nessun commit, push, aggiornamento o deploy eseguito.

### Correzione Preferiti media - 2026-10-02

- Versione candidata: `2.21.301`.
- Le strisce Recenti/Preferiti su PC scorrono trascinando le copertine e tramite rotellina; i pulsanti stella e rimozione restano esclusi dal gesto drag.
- I preferiti brano WiiM vengono riprodotti appena `BrowseQueueEx` restituisce nome preset e ID stabile esatti, anche se il totale della coda è ancora parziale; nessun fallback per nome o posizione arbitraria.
- Dopo la selezione dell'indice esatto viene inviato esplicitamente `play`, evitando che il preset resti nella pausa protettiva usata durante la ricerca.
- Test mirati superati; pubblicazione e aggiornamento dell'add-on autorizzati dall'utente il 02/10/2026.

### Compatibilita' ID Home Assistant nelle viste e-Face - 2026-10-02

- Candidata locale: `2.21.300`; nessun push o aggiornamento impianto eseguito.
- Diagnosi live: il bootstrap e-Face riceve tutti i 40 dispositivi HA Smart Home, visibili e classificati (`lights:3`, `extra:37`); il problema residuo era la migrazione degli ID da `entity_id` a `ha:entity_id` nelle viste e Scorciatoie persistenti.
- Il normalizzatore conserva ora gli entity ID HA come alias canonici; viste aperte, ripristino sessione e Scorciatoie risolvono alias vecchi e nuovi senza duplicare schede.
- Corretto anche il falso negativo di due test DoorBird: fixture JPEG resa coerente con la validazione minima del runtime, senza modifica alla logica DoorBird.
- Test completi eseguiti in due gruppi per evitare il noto esaurimento memoria Windows: `406 passed` + `10 passed`; test CHANGE mirati `31 passed`; JavaScript, compile Python e diff check superati.

### Correzione cronologia DoorBird - 2026-10-02

- Versione candidata: `2.21.299`.
- La Home recupera prima la cronologia LAN `motionsensor`, salva atomicamente il JPEG più recente e usa la copia locale soltanto come fallback offline; il monitor movimento riallinea fotogramma e timestamp prima della notifica realtime.
- La postazione primaria migra le precedenti etichette predefinite `Cancello` e `Ingresso · DoorBird` in `Doorbird Cancello`, senza sovrascrivere eventuali nomi personalizzati diversi.
- Il gruppo cover nelle Scorciatoie è mostrato come `Cover-Portoni`; chiavi tecniche, selezioni e ordine persistente restano invariati.
- Test mirati: `7 passed`; sintassi JavaScript, compilazione Python e diff check superati. La suite completa è stata interrotta dopo 29 test senza errori perché il processo Windows ha esaurito memoria durante WMI/pyControl4.
- Nessun push, aggiornamento, installazione o deploy eseguito.

### Esito CHANGE-2026-013 - 2026-10-01

- Versione candidata: `2.21.298`.
- Commit locale: `ea00d8e` (`Edit Hub organization from e-Face 2.21.298`).
- Gestisci dispositivi usa caricamento lazy e ricerca; non crea piu' tutti i rami nascosti e non salva un ordine generale privo di effetto.
- I dispositivi Hub sono modificabili da e-Face; piano, stanza, gruppi, categorie, ordine per pagina, visibilita' e icona vengono salvati tramite proxy ristretto nell'archivio autorevole Hub.
- Gli scenari sono esclusi dal contenitore generico e restano nel ramo Scenari.
- Scorciatoie globali e-Face invariate e non trasferite all'Hub.
- Test: suite completa `410 passed`, JavaScript valido, Python compile e diff check superati.
- Gate: nessun push, installazione o deploy eseguito.

- Data: 2026-09-30
- Obiettivo: eseguire `CHANGE-2026-008` fino al gate del commit locale, eliminando i loop CPU/log di e-Face.
- Risultato: la candidata locale `2.21.287` conserva tutte le ottimizzazioni CPU e l'avvio HLS resiliente. Se la diretta non parte, il visualizzatore passa ora a fotogrammi realmente aggiornati ogni tre secondi, con lettura fresca limitata a una ogni due secondi e attiva soltanto finché la finestra resta aperta. La versione installata riportata dal work order è `2.21.284`; nessun nuovo push o deploy è stato eseguito in questa sessione.
- File modificati: backend e connettore Supervisor del componente, client web, file di versione, changelog, test e `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; suite completa precedente `376 passed`; dopo il fallback fotogrammi, tre regressioni mirate versione/cache-buster/monitor-HLS superate. Un riesame completo di `test_app.py` è stato interrotto perché non avanzava nell'ambiente locale, senza errori prodotti.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: `CHANGE-2026-008`; nessun contratto condiviso modificato.
- Compatibilità: invariati API pubbliche, formato eventi, slug, provider ID e dati persistenti.
- Dipendenze da altri componenti: nessuna nuova dipendenza; restano usati solo gli endpoint Home Assistant/Supervisor già ammessi.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: media CPU sotto il 10%, avvio HLS con un solo clic e movimento del fallback a fotogrammi devono essere verificati su Windows e Android dopo revisione e installazione autorizzata della `2.21.287`.

## Handoff aggiuntivo — visibilità portoni in Sicurezza

- Data: 2026-09-30
- Problema verificato: `Portone Alex` e `Portone Luca` arrivano correttamente da e-Control HUB come entità HA di dominio `cover`, tipologia configurata `lock`, ma non comparivano in “Accessi e portoni”.
- Causa: nel classificatore UI la regola generica `kind === 'cover'` veniva valutata prima della regola specifica per garage/portoni, rendendo irraggiungibile la categoria Sicurezza.
- Correzione: la regola specifica dei portoni ha ora precedenza sui cover generici; candidata `2.21.288`.
- Test: sintassi JavaScript valida; regressione specifica e controlli versione/cache-buster superati (`3 passed` complessivi nel gruppo finale). La suite completa è stata interrotta dopo 23 test senza errori perché non avanzava nell'ambiente locale, comportamento già osservato nella sessione.
- Contratti condivisi: nessuna modifica; API, identificativi, persistenza e formato eventi invariati.
- Gate: modifica pronta in commit locale; nessun push o deploy eseguito.
- Push autorizzato ed eseguito: `origin/main` aggiornato da `9f109eb` a `1a8a1e6`; inclusi i commit `cc079cc` e `1a8a1e6`. Installazione dell'add-on non eseguita.

## Handoff aggiuntivo — scenari Ksenia nella pagina Sicurezza

- Data: 2026-09-30
- Evidenza: gli scenari Ksenia erano presenti nelle Scorciatoie ma assenti da Sicurezza; il connettore li esponeva correttamente.
- Causa: `securityDevices()` accettava soltanto dispositivi assegnati alla categoria `security`, mentre gli `alarm_scenario` mantengono correttamente la categoria generale `scenarios`.
- Correzione: gli `alarm_scenario` sono inclusi esplicitamente anche nell'insieme Sicurezza senza rimuoverli dalla pagina Scenari; candidata `2.21.289`.
- Test: sintassi JavaScript valida e gruppo mirato Ksenia/classificazione/versione superato (`5 passed`).
- Contratti condivisi: invariati. Gate: commit locale; nessun nuovo push o deploy.

## Handoff aggiuntivo — struttura e ordinamento Scorciatoie

- Data: 2026-09-30
- Risultato: il gruppo cover nelle Scorciatoie è denominato `Varchi`; Sicurezza mostra sottosezioni nell'ordine `Serrature e portoni`, `Scenari`, `Partizioni`, `Zone`, quindi sistema/sensori quando presenti.
- Editor: i master di “Ordina scorciatoie” partono collassati, si aprono singolarmente e restano trascinabili tramite la maniglia dedicata; il pulsante di apertura è separato dalla maniglia.
- Versione candidata: `2.21.290`.
- Test: sintassi dei client `app.js` e `tools.js` valida; sei regressioni mirate superate.
- Contratti condivisi: invariati. Nessun nuovo push o deploy.
- Push autorizzato ed eseguito: `origin/main` aggiornato da `1fdf8e0` a `90fc494`, includendo `14ed232` e `90fc494`. Installazione add-on non eseguita.

## Handoff aggiuntivo — ordine Scorciatoie controllato dall'utente

- Data: 2026-09-30
- Evidenza live: l'editor salvava `Sistema di sicurezza` come primo elemento, ma il renderer `2.21.290` riordinava le sottosezioni per tipo; durante bootstrap incompleti un salvataggio poteva inoltre perdere ID selezionati.
- Correzione: master, sottosezioni e schede seguono l'ordine salvato; la sottosezione è posizionata in base al primo suo elemento trascinato. Gli ID selezionati temporaneamente assenti vengono preservati e il rilascio del drag è acquisito anche fuori dall'elenco.
- Versione: `2.21.291`; test mirati `6 passed`, sintassi JavaScript valida.
- Contratti condivisi invariati; pubblicazione autorizzata dall'utente.
- Push eseguito: `origin/main` aggiornato da `356257c` a `59225bc`. Installazione add-on non eseguita.

## Handoff analisi - e-Control Hub Smart Home HDL/Ksenia

- Data: 2026-10-01
- Verificato in sola lettura il collegamento diretto: e-Face legge `/api/user/snapshot`, ma normalizza solo `payload.devices`; il ramo `payload.ksenia` e ignorato e il comando risolve soltanto target HDL legacy.
- Registrata nel work order condiviso la proposta additiva: ramo versionato `smart_home` con organizzazione globale risolta e identita obbligatoria `source` + `device_id`; nuova rotta utente `POST /api/user/smart-home/{source}/{device_id}/command` con dispatch interno HDL/Ksenia.
- Definita deduplicazione solo per identita tecnica e confine rigido: partizioni, inserimenti, bypass, zone e funzioni di sicurezza restano esclusivamente nel connettore Ksenia protetto.
- MQTT, Discovery e identificativi esistenti restano invariati. Serve approvazione di una CHANGE trasversale prima dell'implementazione.
- Nessuna modifica al codice, commit, push, aggiornamento o deploy eseguita.

## Handoff preparazione CHANGE-2026-011

- Data: 2026-10-01
- Letti CHANGE e work order aggiornati. Il gate impone attesa della revisione producer prima di modificare il runtime e-Face.
- Aggiunte una fixture sintetica del contratto `smart_home` e prove contrattuali per schema, identita `source:device_id`, organizzazione, collisioni native e separazione della sicurezza.
- Test CHANGE: `4 passed, 2 xfailed` intenzionali e strict; rappresentano parser e comando futuri, ancora bloccati dal gate producer.
- Regressione BusPro/configurazione: `9 passed`; soli warning FastAPI preesistenti.
- Runtime, versione, MQTT, Discovery e identificativi invariati. Nessun commit, push, aggiornamento o deploy.

## Handoff preparazione parita multi-bus CHANGE-2026-011

- Data: 2026-10-01
- Letto il work order aggiornato con requisiti di pagine storiche, preferenze persistenti, parita funzionale e neutralita rispetto ai driver.
- Aggiunta fixture sintetica di parita per `hdl`, `ksenia` e `futurebus`, con classi/capability equivalenti, categorie storiche, capability negate e ciclo di persistenza rename/offline/restart/update/backup-restore.
- Aggiunti test della matrice, del confine Sicurezza e della compatibilita dell'archivio organizzazione esistente con chiavi canoniche multi-bus.
- Esito aggregato CHANGE: `10 passed, 5 xfailed` strict e intenzionali in attesa del producer.
- Analisi: `device_organization` supporta gia chiavi canoniche, multi-categoria, ordine e visibilita; dopo il gate serviranno alias HDL legacy e integrazione coordinata di pagine, realtime, routine, preferiti e scorciatoie.
- Runtime, versione, MQTT, Discovery e identificativi invariati. Nessun commit, push, aggiornamento o deploy.

## Handoff implementazione consumer CHANGE-2026-011

- Data: 2026-10-01
- Producer consumato: e-Control Hub `0.1.459`, commit approvati `ff11416` + `d07e301`, contratto `smart_home` v1.
- Implementato il consumer driver-neutral con identita canonica `source:device_id`, organizzazione e icone autorevoli Hub, fallback `payload.devices` per Hub precedenti e alias espliciti per le preferenze HDL legacy.
- I comandi multi-bus usano esclusivamente `/api/user/smart-home/{source}/{device_id}/command` e rispettano capability, disponibilita, sola lettura e stato orfano dichiarati dal producer.
- Aggiunte proiezione nelle pagine storiche, scenari e routine; deduplicazione HA soltanto per entity ID esatto. Partizioni, inserimenti, bypass e sicurezza Ksenia restano nel connettore protetto esistente.
- Versione candidata: `2.21.293`.
- Test: suite CHANGE `17 passed` senza xfail; suite completa e-Face `397 passed`; sintassi JavaScript, compilazione Python e `git diff --check` superati.
- MQTT, Discovery e identificativi esistenti invariati. Nessun push, aggiornamento, installazione, deploy o release eseguito.

## Handoff correzioni revisione consumer CHANGE-2026-011

- Data: 2026-10-01
- Correzione autorita: le preferenze e-Face legacy in conflitto sono conservate nel record diagnostico e nell'archivio esistente, ma non sovrascrivono nome, stanza, icona, categorie, ordine o visibilita ricevuti da e-Control Hub.
- Correzione sicurezza: filtro difensivo normalizzato applicato a `device_class`, `native_type`, capability e comandi; intercetta plurali, prefissi e varianti con trattino/underscore delle famiglie allarme, partizione, zona, inserimento e bypass.
- Versione candidata correttiva: `2.21.294`.
- Gate invariato: commit correttivo locale; nessun push, aggiornamento, installazione, deploy o release.

## Handoff aggiuntivo — widget Luci accese

- Data: 2026-09-30
- Correzione: il clic su una luce del widget Home “Luci accese” apre la pagina generale `Luci accese` con filtro attivo, mostrando tutte e sole le luci accese dell'impianto anziché la singola stanza.
- Versione candidata: `2.21.292`; sintassi JavaScript valida e tre test mirati superati.
- Compatibilità: nessuna modifica a contratti, API o persistenza. Nessun push/deploy eseguito.
