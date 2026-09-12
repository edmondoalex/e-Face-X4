# Changelog

## 2.7.0 — 2026-09-12

- Aggiunta in `Strumenti → Utente` la scelta dello sfondo senza accesso Admin.
- Disponibili cinque temi integrati oppure una foto personale fino a 4 MB.
- Lo sfondo può essere globale o specifico per ciascuna stanza, con possibilità di ereditare nuovamente quello globale.
- Configurazione e immagini sono salvate in modo atomico e persistente in `/data/backgrounds`.

## 2.6.0 — 2026-09-12

- Aggiunta in `Strumenti → Admin → Multimediale` la gestione delle icone delle sorgenti.
- È possibile caricare PNG, JPEG, WebP o GIF fino a 500 KB e ripristinare in ogni momento l'icona Control4/automatica.
- Le icone personalizzate sono salvate in `/data/source-icons` e hanno priorità su quelle native.

## 2.5.2 — 2026-09-12

- Aggiunte icone specifiche per tipo di apparato quando il driver Control4 non contiene un file icona nativo.
- Eliminato il simbolo di immagine rotta quando la libreria Composer indicata dal driver non è esposta dal Director.

## 2.5.1 — 2026-09-12

- Corretto `AttributeError` con driver Control4 che espongono `display_icons` in un formato non strutturato.
- Il precaricamento opzionale delle icone non può più portare offline l'intero connettore Control4.

## 2.5.0 — 2026-09-11

- Aggiunto il telecomando completo per le sessioni video Control4.
- I controlli vengono generati dalle capacità dichiarate dal proxy dell'apparato attivo: navigazione, tastierino, canali, pagine, trasporto, registrazione e funzioni specifiche.
- Aggiunti i quattro pulsanti colore per i driver che li trasportano tramite i comandi personalizzati Control4.
- Ogni comando è validato nuovamente rispetto alla sorgente video attiva nella stanza prima dell'invio.

## 2.4.2 — 2026-09-11

- Le icone Control4 vengono precaricate dal backend insieme allo snapshot e servite dalla memoria locale, evitando richieste e autenticazioni separate dal browser.
- Forzato l'aggiornamento della cache delle icone sorgente dopo ogni nuova versione.

## 2.4.1 — 2026-09-11

- Corretto il caricamento delle icone native dei device e delle sorgenti Control4 usando la mappa già acquisita dal Director.
- Le sessioni Control4 non mostrano più stanze rimaste accese soltanto per uno stato obsoleto senza esperienza audio/video attiva.
- Il selettore `+` limita le stanze a quelle sulle quali Control4 espone realmente la sorgente della sessione.
- Aggiornato il logo orizzontale e-Face X4.

## 2.4.0 — 2026-09-11

- Caricate dal Director le icone native dei singoli device e servizi Control4.
- Aggiunto un proxy locale sicuro con validazione di percorso, tipo MIME e dimensione.
- Mantenuta l'icona generica come fallback quando un driver non pubblica un asset grafico.

## 2.3.4 — 2026-09-11

- Rimossi i testi `AUDIO ON` e `VIDEO ON` dalle tessere.
- Audio attivo indicato in verde e video attivo in azzurro tramite bordo, icona e punto luminoso.

## 2.3.3 — 2026-09-11

- Evidenziate le stanze operative con indicatori distinti `AUDIO ON` e `VIDEO ON` basati sullo stato reale Control4.
- Separato graficamente lo stato operativo dalla semplice selezione del player.

## 2.3.2 — 2026-09-11

- Riconosciute come sessioni anche le stanze con una sorgente video Control4 attiva.
- Le sessioni contemporanee audio e video vengono elencate separatamente, ad esempio Spotify in Ufficio e Sky in Sala.

## 2.3.1 — 2026-09-11

- Rimosso il selettore duplicato `Tutte le stanze` dalle pagine Guarda e Ascolta.
- Separati i player nelle sezioni `Stanze` e `Sorgenti e servizi`.

## 2.3.0 — 2026-09-11

- Aggiunta la pagina Sessioni in stile Control4, con una scheda distinta per ogni sessione audio/video attiva.
- Ogni scheda mostra fonte, contenuto, copertina, volume e stanze associate e apre il relativo gestore.
- Il contatore in testata indica il numero di sessioni attive.
- Sostituita la scritta per aggiungere stanze con il solo pulsante `+`.

## 2.2.4 — 2026-09-11

- Resa sempre visibile l'icona del gestore sessione nella testata usando un simbolo vettoriale incorporato, compatibile con Home Assistant Ingress.

## 2.2.3 — 2026-09-11

- Spostato il gestore della sessione audio/video nella testata, a sinistra del menu con i tre puntini.
- Il comando resta disponibile da ogni pagina quando almeno una stanza multimediale è attiva.
- Rimossa l'icona duplicata dalla scheda del player.

## 2.2.2 — 2026-09-11

- Il gestore sessione mostra fonte audio, contenuto e stanze attualmente in riproduzione.
- I volumi delle stanze attive sono sempre visibili.
- Il pulsante `+ Aggiungi o rimuovi stanze` apre la selezione delle zone come in Control4.

## 2.2.1 — 2026-09-11

- Aggiunto in alto a destra il pulsante della sessione multiroom con il numero di stanze.
- Il pulsante apre il gestore generale audio/video: volume generale, volumi indipendenti, aggiunta e rimozione stanze.

## 2.2.0 — 2026-09-11

- Ripristinato Aggiungi stanza con i comandi nativi Digital Media `ADD_ROOMS_TO_SESSION` e `REMOVE_ROOMS_FROM_SESSION`.
- Evitata la selezione diretta delle sorgenti, che generava sessioni audio duplicate in Control4.
- Aggiunti volume generale della sessione e volume indipendente per ogni stanza.
- Corretta la rimozione delle stanze Control4 e protetta la stanza proprietaria della sessione.

## 2.1.1 — 2026-09-11

- Mantenuto disabilitato il join multiroom Control4 finché non è disponibile il comando Digital Media corretto.
- Impedita la selezione diretta del driver riproduttore, che crea sorgenti duplicate nella pagina Sessioni Control4.

## 2.0.3 — 2026-09-11

- Impedito al valore obsoleto `OK_playing` di Control4 di sovrascrivere una pausa appena comandata.
- L'icona resta Play dopo la pausa e torna Pausa quando l'utente riprende la riproduzione.
- L'override viene eliminato automaticamente al cambio brano, sorgente o spegnimento della stanza.
- Stabilizzati anche mute e volume: l'interfaccia mantiene il valore richiesto fino alla conferma del Director.

## 2.0.2 — 2026-09-11

- Collegati i comandi Control4 nativi precedente e successivo (`SKIP_REV`/`SKIP_FWD`).
- Corretto il frontend affinché mostri soltanto i controlli dichiarati realmente dal connettore.
- Nascosto il comando zone quando il Director non espone il relativo controllo sicuro.
- Distinto lo stato pausa dallo stato acceso quando il servizio pubblica lo stato di trasporto.
- Resi immediati nell'interfaccia mute, volume, play, pausa, stop e spegnimento, con successiva conferma realtime.
- Estesa la sottoscrizione WebSocket ai dispositivi audio e volume effettivamente collegati alla stanza.
- Sostituiti i simboli testuali con icone vettoriali in stile Control4, senza riquadri sui trasporti.

## 2.0.1 — 2026-09-11

- Ridisegnato il player Ascolta come barra Control4 a tutta larghezza e responsive.
- Importati da `CURRENT MEDIA INFO` titolo, artista, album, formato e copertina correnti.
- Le copertine vengono servite attraverso e-Face con fingerprint e domini CDN convalidati.

## 2.0.0 — 2026-09-11

- Aggiunto il connettore multimediale nativo Control4 Director sulla rete locale.
- Importate esclusivamente le stanze Listen e Watch configurate in Control4, con sorgenti distinte per esperienza.
- Aggiunti stato realtime via WebSocket, volume, mute, play, pausa, stop, spegnimento stanza e selezione sorgente.
- Mantenute selezione, classificazione audio/video e riordino installatore anche per i player Control4.
- Le credenziali restano locali nell'add-on e i token temporanei Control4 non vengono esposti al browser.

## 1.6.4 — 2026-09-11

- Normalizzati automaticamente gli URL dei connettori aggiungendo o correggendo lo schema HTTP/HTTPS.

## 1.6.3 — 2026-09-11

- Mostrato il tipo e il dettaglio reale degli errori di parsing/trasporto e-Therm per la diagnosi dal container.

## 1.6.2 — 2026-09-11

- Corretta la priorità del connettore: l'indirizzo manuale LAN prevale sulla scoperta automatica.
- Raggruppati i termostati usando anche il campo piano (`floor`) di e-Therm.

## 1.6.1 — 2026-09-11

- Aggiunto supporto completo all'autenticazione e-Therm none/basic/token.
- Resi diagnostici gli errori del connettore: HTTP, autenticazione, timeout e connessione rifiutata.

## 1.6.0 — 2026-09-11

- Aggiunto il connettore e-Therm Plus KS con scoperta automatica sulla porta 8080.
- Importati in Comfort temperatura, setpoint, umidità, stagione, richiesta e PWM dei termostati.
- Aggiunti i comandi setpoint e predisposta autenticazione Bearer.

## 1.5.0 — 2026-09-11

- Aggiunti indicatori live colorati alle icone di navigazione per luci, extra, cover, sicurezza, multimedia e clima attivi.

## 1.4.3 — 2026-09-11

- Ridisegnata la barra filtri Luci come Control4: Stanza, icona circolare solo accesi e Tutto.
- Aggiunti gli stati visivi chiaro/scuro per ambito e filtro selezionati.

## 1.4.2 — 2026-09-11

- Impediti i comandi involontari durante lo scorrimento touch delle schede.
- Eliminati i bordi di stato acceso da tutte le luci, incluse RGB.

## 1.4.1 — 2026-09-11

- Sostituito il menu stanza nativo con un selettore personalizzato in stile e-Face, responsive e touch-friendly.

## 1.4.0 — 2026-09-11

- Rimossi i conteggi dall'intestazione delle pagine dispositivo.
- Aggiunti nella pagina Luci i filtri Control4: Stanza, Solo accesi e Tutto.

## 1.3.4 — 2026-09-11

- Uniformato il bordo delle schede RGB a quello delle altre luci, eliminando bordo e alone colorati.

## 1.3.3 — 2026-09-11

- Slider dimmer bianco da spento e riempimento giallo proporzionale alla luminosità.
- Portando il dimmer a 0% viene inviato il comando OFF.

## 1.3.2 — 2026-09-11

- Spostato il master RGB sulla scheda e riservata l'apertura della tavola colori alla sola icona quadrata.
- Rimossi invito testuale e codice HEX; il tocco sulla scheda esegue ON/OFF.

## 1.3.1 — 2026-09-11

- Rimossi i pulsanti ON/OFF dalle schede luci e switch: il comando ora avviene toccando la scheda.

## 1.3.0 — 2026-09-11

- Aggiunto pannello popup RGB con master, ruota colore, palette, HEX e controllo separato dei tre canali.
- Mantenuta nella pagina Luci una scheda RGB compatta con colore reale.

## 1.2.1 — 2026-09-11

- Resa l'intensità luminosa dell'icona proporzionale alla percentuale reale del dimmer.

## 1.2.0 — 2026-09-11

- Riconosciute le luci dimmerabili e aggiunto il controllo luminosità live.
- Raggruppati i canali red/green/blue e-HDL in un unico dispositivo RGB.
- Aggiunti selettore colore, master RGB e comandi ON/OFF nativi X4.

## 1.1.0 — 2026-09-11

- Rimossi gli scenari dalla pagina Luci.
- Aggiunta una categoria Scenari autonoma nella navigazione principale.
- Disposti gli scenari in una griglia senza scorrimento: 3 colonne desktop, 2 tablet e 1 cellulare.
- Aggiunta l'icona Scenari configurabile nelle opzioni.

## 1.0.2 — 2026-09-11

- Impedito alla fascia Scenari di allargare orizzontalmente l'intera interfaccia.
- Limitato lo scorrimento orizzontale al solo elenco delle card scenario.
- Ottimizzata la fascia per tablet e cellulare con card adattive, scorrimento touch e pulsanti maggiorati.

## 1.0.1 — 2026-09-11

- Rimossa la pagina e-HDL incorporata che interrompeva lo stile X4.
- Ricostruiti i richiami scenario come schede native e-Face compatte e responsive.
- Collegati stato, Run/Stop e Accendi/Spegni al WebSocket realtime.

## 1.0.0 — 2026-09-11

- Incorporata nella pagina Luci la gestione scenari completa e originale di e-HDL.
- Supportati richiamo, stato, Run/Stop, ON/OFF, creazione, modifica, eliminazione e trigger.
- Aggiunto un proxy interno ristretto alle sole API necessarie agli scenari, senza esporre token o indirizzi.
- Collegato anche il WebSocket dell'editor per gli aggiornamenti live.

## 0.9.1 — 2026-09-11

- Spostati in Extra anche gli output BusPro salvati da e-HDL come `type: light` e `category: Switch`.
- Allineata la classificazione Luci/Extra alla logica effettiva di e-HDL.

## 0.9.0 — 2026-09-11

- Aggiunta la categoria Extra dedicata agli switch, come in e-HDL.
- Separati switch e luci nelle pagine e nei conteggi.
- Aggiunta l'icona Extra configurabile nelle opzioni dell'add-on.

## 0.8.0 — 2026-09-11

- Collegato il canale WebSocket realtime di e-HDL tramite un ponte interno sicuro.
- Aggiornato direttamente il singolo dispositivo alla ricezione di eventi BusPro, senza richiedere snapshot.
- Attivato il polling di riserva ogni 30 secondi soltanto quando il WebSocket non è disponibile.

## 0.7.5 — 2026-09-11

- Sostituito il logo della testata con il marchio orizzontale `EKONEX e-Face X4`.
- Ottimizzate trasparenza, ritaglio e dimensioni responsive del nuovo asset.

## 0.7.4 — 2026-09-11

- Graduata la colorazione celeste delle cover in base alla posizione 0–100%.
- Aumentati progressivamente anche alone e bordo durante l'apertura.

## 0.7.3 — 2026-09-11

- Switch verdi da spenti e rossi da accesi.
- Cover grigie da chiuse e celesti da aperte.
- Lock verdi da chiusi e rossi da aperti o sbloccati.

## 0.7.2 — 2026-09-11

- Evidenziate in giallo le icone delle luci accese, in stile e-HDL.
- Aggiornato automaticamente l'indicatore visivo insieme allo stato live.

## 0.7.1 — 2026-09-11

- Riconosciuti come luci i dispositivi BusPro storici privi del campo `type`, come fa e-HDL.
- Mostrati i comandi ON/OFF anche su questi dispositivi.
- Aggiunto il tipo sensore `air` usato dallo snapshot e-HDL.

## 0.7.0 — 2026-09-11

- Collegati i comandi reali ON/OFF, apertura/arresto/chiusura e blocco/sblocco.
- Verificato ogni dispositivo lato server prima dell'inoltro del comando a e-HDL.
- Migliorata la compatibilità della lettura stati BusPro.

## 0.6.2 — 2026-09-11

- Visualizzati valore e unità dei sensori BusPro nelle pagine dispositivo.
- Gestiti gli stati dedicati per temperatura, umidità, luminosità, aria, gas e presenza.
- Aggiornata automaticamente ogni 10 secondi anche la pagina di dettaglio aperta.

## 0.6.1 — 2026-09-11

- Eliminata la dipendenza dalla cache icone del BusPro.
- Aggiunta una cache MDI autonoma e persistente in e-Face X4.
- Scaricati gli SVG solo dalla sorgente ufficiale MDI con nomi validati.
- Evitata la lampadina segnaposto identica per tutte le categorie.
- Invalidata automaticamente la vecchia cache del browser a ogni versione dell'add-on.

## 0.6.0 — 2026-09-11

- Aggiunta la sezione `Icone navigazione` nella configurazione dell'add-on.
- Sostituiti i simboli Unicode con icone MDI configurabili.
- Ereditata per ogni dispositivo l'icona scelta in e-HDL BusPro MQTT.
- Aggiunto un proxy SVG ristretto e sicuro verso la libreria icone del BusPro.
- Mantenuti fallback visivi quando un'icona non è disponibile.

## 0.5.0 — 2026-09-11

- Sostituiti i popup con vere pagine interne alla shell e-Face X4.
- Categorie, ambienti e `Vedi tutti` aprono una vista completa con griglia dispositivi.
- Aggiunti intestazione della sezione, conteggio e comando indietro.
- Il logo riporta sempre alla dashboard principale.

## 0.4.2 — 2026-09-11

- Allineata la navigazione alle categorie Guarda, Ascolta, Luci, Oscuranti, Comfort e Sicurezza.
- Ogni categoria apre direttamente i dispositivi pertinenti.
- Resa scorrevole la navigazione a sei voci su smartphone.

## 0.4.1 — 2026-09-11

- Resa funzionale la voce `Vedi tutti` degli ambienti.
- Collegati i pulsanti Stanze, Multimedia, Sicurezza e Tutti i dispositivi.
- Aggiunte etichette descrittive alle icone della navigazione laterale.

## 0.4.0 — 2026-09-11

- Rese cliccabili categorie e stanze con elenco dei dispositivi reali.
- Mostrato lo stato disponibile per ogni dispositivo BusPro o Home Assistant.
- Deduplicati gli ambienti senza distinzione tra maiuscole e minuscole.
- Corretta la leggibilità di titolo, quantità e descrizione nelle schede.
- Nascosti i riquadri camera dimostrativi in modalità live.

## 0.3.2 — 2026-09-11

- Aggiunto il rilevamento automatico di e-HDL BusPro MQTT tramite Supervisor.
- Usato il DNS interno dell'add-on per evitare rifiuti di connessione sulla rete host.
- Mantenuto l'indirizzo configurato dall'utente come fallback.

## 0.3.1 — 2026-09-11

- Mostrato nella UI il motivo per cui un connettore è offline.
- Distinti errori HTTP, timeout, connessione rifiutata e risposta non valida.
- Nascosto correttamente il player quando non esistono dati multimediali live.

## 0.3.0 — 2026-09-11

- Normalizzati dispositivi e stanze provenienti da e-HDL BusPro MQTT.
- La modalità live mostra conteggi reali di luci, cover, serrature e sensori.
- Aggiunto lo stato online/offline dei connettori nella barra superiore.
- Aggiunto aggiornamento automatico ogni 10 secondi, sospeso quando la pagina non è visibile.
- Mantenuto il confine architetturale: nessun motore BusPro è incluso in e-Face X4.

## 0.2.4 — 2026-09-11

- Applicato il marchio orizzontale ufficiale fornito dall'utente.
- Rimossa la ricostruzione HTML del wordmark.
- Mantenuto il nome configurabile dell'abitazione subito dopo il logo.

## 0.2.3 — 2026-09-11

- Separati simbolo, wordmark e nome dell'abitazione nella testata.
- Usato il simbolo e-Face senza scritta, seguito da `e-Face X4` e dal nome configurabile.

## 0.2.2 — 2026-09-11

- Sostituita la scritta tipografica e-Face X4 con il logo ufficiale completo.
- Allineati logo, nome configurabile dell'abitazione e stato demo su un'unica riga.

## 0.2.1 — 2026-09-11

- Mostrato il nome fisso e-Face X4 accanto al logo.
- Aggiunta l'opzione `home_name` per configurare il nome dell'abitazione.
- Separato visivamente il nome del prodotto dal nome dell'impianto.

## 0.2.0 — 2026-09-11

- Ridisegnata la dashboard secondo il nuovo riferimento X4.
- Navigazione laterale su tablet e inferiore su smartphone.
- Aggiunte barra contestuale, pillole di stato e griglia domotica compatta.
- Introdotti pannello clima dominante, anteprime camera e player persistente.
- Mantenuta l'identità originale e-Face X4 senza asset Control4.

## 0.1.4 — 2026-09-11

- Rimossa la modalità `host_network` per evitare conflitti con altri add-on.
- Aggiunta la porta web esterna configurabile, predefinita su `8130`.
- Mantenuto Home Assistant Ingress sulla porta interna isolata `8099`.

## 0.1.3 — 2026-09-11

- Corretto il blocco `expected a URL` con indirizzi dei connettori vuoti.
- Gli indirizzi vengono accettati vuoti finché il relativo connettore è disabilitato.

## 0.1.2 — 2026-09-11

- Resi opzionali tutti i parametri della configurazione iniziale.
- La modalità demo può avviarsi senza configurare BusPro o e-Voice.
- Mantenuti fallback sicuri lato applicazione per opzioni assenti.

## 0.1.1 — 2026-09-11

- Introdotto il marchio ufficiale e-Face X4.
- Aggiunti logo e icona per il catalogo Home Assistant.
- Aggiunti favicon, icona Apple Touch e manifest PWA.
- Allineata la dashboard alla palette rossa e antracite del marchio.

## 0.1.0 — 2026-09-11

- Prima fondazione installabile tramite Home Assistant Ingress.
- Dashboard X4 responsive con modalità chiara e scura.
- Modalità demo esplicita.
- Architettura modulare dei connettori.
- Primo connettore in sola lettura per e-HDL BusPro MQTT.
- Endpoint di salute e test contro l'esposizione delle credenziali.
# 1.9.1

- Corretto il test Control4: le stanze sono lette dalla configurazione UI Director anziché da una categoria inesistente.
- Il risultato mostra stanze, sorgenti ed esperienze Control4 (`watch`, `listen`, ecc.).

# 1.9.0

- Aggiunta in Strumenti Admin la configurazione protetta dell'integrazione Control4 nativa.
- Aggiunto test reale con autenticazione account, token Director e lettura locale delle stanze.
- Le credenziali Control4 sono conservate solo localmente con permessi file restrittivi e non vengono mai restituite al browser.

# 1.8.1

- Aggiunto il riordino verticale dei player tramite trascinamento nell'area Admin multimediale.
- L'ordine personalizzato viene salvato e applicato all'elenco Dispositivi e servizi.
- Il trascinamento usa Pointer Events ed è compatibile con mouse, tablet e telefono.

# 1.8.0

- Aggiunta la pagina dedicata Strumenti, aperta dal menu a tre puntini e predisposta per nuove funzioni.
- Separate le sezioni Utente e Admin / Installatore.
- Protetta l'area Admin con password configurabile nelle opzioni dell'add-on e sessione HttpOnly di otto ore.
- Aggiunta la configurazione persistente dei player: visibilità e classificazione Audio, Video o entrambe.
- Le preferenze vengono applicate localmente a Guarda e Ascolta senza dipendere dalle Aree Home Assistant.

# 1.7.12

- Ascolta include sia i player audio (`listen`) sia quelli video (`watch`), perché ogni player video dispone anche dell'audio.
- Guarda resta limitato ai soli player video (`watch`).

# 1.7.11

- Ogni media player locale è trattato come stanza e usa il proprio nome visibile, senza richiedere un'Area Home Assistant.
- Inclusi anche i media player dinamici non registrati o privi di area.

# 1.7.10

- La pagina Guarda include esclusivamente videocamere, campanelli e player classificati `watch`.
- I player classificati soltanto `listen` restano esclusivamente nella pagina Ascolta.
- Nel collegamento locale, i media player `tv` sono classificati video; gli altri restano audio.

# 1.7.9

- Il selettore stanze di Guarda e Ascolta usa soltanto le stanze dei dispositivi multimediali mostrati, non tutte le aree Home Assistant.
- Guarda include player audio e video; Ascolta resta limitato ai player audio.

# 1.7.8

- Aggiunta l'autenticazione Bearer all'upgrade HTTP del WebSocket Supervisor richiesta da Home Assistant.
- Rimosso il percorso WebSocket `/core/api/websocket`, non previsto dall'API Supervisor.

# 1.7.7

- Nascoste le barre di scorrimento native nei menu stanze, sorgenti e selezione zone, mantenendo lo scorrimento touch e con rotella.

# 1.7.6

- Corretto il collegamento WebSocket locale con fallback automatico tra proxy Supervisor e endpoint diretto Home Assistant.
- Nessuna configurazione URL, token o installation_id richiesta per il collegamento locale.

# 1.7.5

- Esclusi da Guarda e Ascolta i player senza area Home Assistant.
- Aggiunto cache-busting agli asset frontend per applicare subito menu e stili aggiornati.

# 1.7.4

- Aggiornamenti media mirati senza ricostruzione continua della pagina.
- Inclusi i media player dinamici non presenti nel registro entità Home Assistant.
- Stabilizzata la geometria delle pagine Guarda e Ascolta.

# 1.7.3

- Il selettore stanze di Guarda e Ascolta mostra tutte le aree Home Assistant, anche senza player.

# 1.7.2

- Aumentato a 16 MB il limite controllato dei frame WebSocket Home Assistant per impianti con registri entità estesi.

# 1.7.1

- Collegamento multimediale locale automatico tramite Home Assistant e Supervisor.
- Aggiunta gestione stanze/sessioni con join, unjoin e volume relativo di gruppo.
- Backend cloud Ekonex Media mantenuto come opzione, non più obbligatorio.

# 1.7.0

- Prima integrazione Ekonex Media con player, controlli, sorgenti, artwork e realtime SSE.
- Pagine Guarda e Ascolta con selezione stanza e layout responsive ispirato a Control4 X4.
# 2.8.0

- Integrazione nativa Ksenia lares con aree, zone, stati di allarme, inserimento, disinserimento ed esclusione zone.
- Nuova vista Sicurezza dedicata e riepilogo dinamico in Home.
- Il player compatto nella pagina ambiente apre ora la vista multimediale completa della stanza.
- Telecomando video ridisegnato in stile Control4, con icone uniformi e layout adattivo per tablet e smartphone.
# 2.8.1

- Slider audio/video con riempimento colorato compatibile: verde per audio e celeste per video.
- Stati ON/OFF e card dispositivi adattivi senza interruzioni di testo sui tablet.
- Telecomando rifinito con icone centrate e layout responsive.
- Slider sessione comandabile direttamente e sincronizzato con le singole zone.
# 2.8.2

- Il comando `+` delle sessioni video apre nuovamente Gestione stanze per aggiungere o rimuovere ambienti, senza aprire il telecomando.
# 2.8.3

- Connettore Ksenia più resiliente: timeout dedicato e conservazione dell'ultimo stato valido durante rallentamenti temporanei.
- Le 21 aree e 102 zone non scompaiono più per un singolo timeout dell'API Ksenia.
# 2.9.0

- Scenari Ksenia ARM, DISARM e PARTIAL disponibili come comandi rapidi nella pagina Sicurezza.
- Stato dettagliato delle aree: disinserita, inserita ritardata, inserita immediata, ritardo ingresso/uscita e allarme.
- Conferma esplicita prima dell'esecuzione di uno scenario di sicurezza.
# 2.9.1

- Clic fuori dal pallino su tutti gli slider Sessioni: variazione protetta di ±2%; il trascinamento mantiene l'impostazione diretta.

# 2.10.0

- Ogni comando Ksenia richiede il PIN reale della centrale: scenari, aree e inclusione/esclusione zone.
- Il PIN non viene salvato: apre una sessione temporanea, esegue il comando e la chiude.
- Errori distinti per codice errato, centrale non raggiungibile e risposta HTTP non valida.
- Stato sicurezza aggiornato subito dopo il comando e ricontrollato a intervalli ravvicinati.

# 2.10.1

- La finestra del codice Ksenia si chiude immediatamente premendo Conferma; eventuali errori vengono mostrati nell'interfaccia principale.

# 2.11.0

- Zone Ksenia ridisegnate in formato slim senza etichette testuali di stato.
- Icone dinamiche per porte, finestre, tapparelle, movimento interno/esterno e altri sensori.
- Sensore a riposo verde e sensore attivo/aperto rosso, con icona coerente allo stato.
- Zone escluse attenuate e contrassegnate graficamente con `!` color ambra.

# 2.11.1

- Stati Ksenia ricevuti direttamente dallo stream SSE dell'addon, senza attendere il refresh generale.
- Aggiornamento incrementale e immediato di aree, zone e scenari nella schermata Sicurezza.

# 2.12.0

- Modalità di inserimento mostrata nel riepilogo Sicurezza accanto allo stato delle aree.
- Nome dell'ultimo scenario Ksenia eseguito, modalità personalizzata per comandi area e stato disinserito senza aree attive.

# 2.12.1

- Modalità di inserimento letta direttamente dal campo reale Ksenia `systems.ARM.D` (per esempio `SOLO ESTERNO`).
- Rimossa la deduzione locale `Personalizzata`: il riepilogo segue ora la descrizione trasmessa dalla centrale, anche in realtime.

# 2.12.2

- Riepilogo Sicurezza compatto su una sola riga.
- Rimosse le diciture `Sistema Ksenia lares` e memoria dal riepilogo principale.

# 2.12.3

- Card degli scenari Ksenia più sottili, con la sola icona e il nome dello scenario.
- Rimosse le descrizioni ripetitive di inserimento totale, parziale e disinserimento.

# 2.12.4

- Le aree con memoria mostrano soltanto `DISINSERITA`; il tipo di memoria resta rappresentato dall'icona ambra e dal relativo suggerimento accessibile.

# 2.13.0

- Aree inserite immediatamente in rosso, incluse icona a scudetto, bordo e stato.
- Aree inserite con ritardo in giallo, incluse icona a scudetto, bordo e stato.
- Rimossi i bordi esterni da riepilogo, scenari, aree e zone della pagina Sicurezza.
- Serrature separate dal layout delle zone sensore, con pulsanti adattivi che non escono più dalle card.
- Rimossa l'icona a occhio dalle zone: il comando `ESCLUDI` o `INCLUDI` appare soltanto toccando la card.
