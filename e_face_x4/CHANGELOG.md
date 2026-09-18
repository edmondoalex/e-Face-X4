# Changelog

## 2.21.171 — 2026-09-18

- Integrato localmente HLS.js per riprodurre il live delle videocamere anche nei browser privi di supporto HLS nativo.
- Conservati audio, controlli, fallback a fotogrammi e rilascio del player alla chiusura.

## 2.21.170 — 2026-09-18

- La view della videocamera si apre immediatamente anche mentre il flusso live è in preparazione.
- Se HLS non parte, la finestra torna automaticamente ai fotogrammi aggiornati mostrando lo stato del fallback.

## 2.21.169 — 2026-09-18

- Ogni videocamera può usare modalità Fotogrammi oppure Video live + audio.
- Il video live usa lo stream HLS di Home Assistant, mantiene l'intera inquadratura e mostra i controlli multimediali.

## 2.21.168 — 2026-09-18

- L'anteprima videocamera aperta usa fotogrammi blob distinti per forzare il ridisegno nei browser mobili e nelle WebView.
- Le richieste sovrapposte vengono evitate e le risorse temporanee vengono liberate alla chiusura.

## 2.21.167 — 2026-09-18

- Aggiungendo una videocamera, Strumenti porta ora alla nuova riga e seleziona il suo nome senza tornare alla prima telecamera.

## 2.21.166 — 2026-09-18

- Le miniature delle videocamere nella pagina Sicurezza si aggiornano ogni 8 secondi.
- L'anteprima ingrandita aperta si aggiorna ogni secondo e interrompe le richieste alla chiusura.

## 2.21.165 — 2026-09-18

- Corregge il salvataggio delle videocamere create da browser che fornivano un identificatore interno non valido.
- Gli identificatori mancanti o non validi vengono riparati automaticamente senza perdere nome ed entità.

## 2.21.164 — 2026-09-18

- Strumenti mostra l'anteprima delle entità `camera.*` prima del salvataggio.
- Ogni videocamera ha il comando **SALVA E PROVA**, con conferma persistente e comparsa immediata nella pagina Sicurezza.
- Il salvataggio generale resta disponibile per l'ordine dei gruppi e delle videocamere.

## 2.21.163 — 2026-09-18

- Le videocamere di Sicurezza accettano ora anche entità e-Control `camera.*` oltre ai link.
- Le entità mostrano l'anteprima aggiornata nella UI Sicurezza e si aprono ingrandite al tocco, mantenendo l'ordine salvato in Strumenti.

## 2.21.162 — 2026-09-18

- Sicurezza: aggiunta la sezione ordinabile Videocamere con elenco persistente modificabile, nome, link, aggiunta, eliminazione e trascinamento.
- I collegamenti delle videocamere sono validati e apribili direttamente dalla pagina Sicurezza.
- Home dinamica: aggiunta l'altezza “Uniforme alla riga” per allineare Meteo e card immagine affiancate.

## 2.21.161 — 2026-09-17

- Le tessere delle app esposte in Guarda aprono ora direttamente la relativa app sul decoder Sky Q tramite il servizio LAN nativo.
- Il lancio verifica che l'app sia realmente installata, non bloccata e selezionata nella configurazione Admin.

## 2.21.160 — 2026-09-17

- Configurazione Sky Q: aggiunto l'inventario diretto del decoder con tutti i canali, tutte le registrazioni, tutte le app, quote e riepiloghi per stato e provenienza.
- Aggiunte ricerca e guida giornaliera apribile selezionando un canale, con titoli, orari, descrizioni e copertine disponibili.

## 2.21.159 — 2026-09-17

- Quando Sky Q è dentro un'app e non espone i metadati del contenuto, e-Face usa l'icona dell'app come cover in Guarda, Home Live e Sessioni.

## 2.21.158 — 2026-09-17

- Rimossa l'icona del canale dalla scheda Sky Q; resta il solo logo Sky.
- DoorBird: quando arriva una pressione del campanello e la cronologia locale restituisce 404, e-Face acquisisce e salva in modo persistente un fotogramma live per il widget Ultima chiamata.

## 2.21.157 — 2026-09-17

- Uniformate le dimensioni del logo Sky Q e del logo canale a 54×40 px, entrambi centrati nel proprio spazio.

## 2.21.156 — 2026-09-17

- Ridisegnata la coppia di loghi Sky Q: niente riquadri neri, logo Sky pulito sopra e logo canale più largo sotto, senza sovrapposizioni.

## 2.21.155 — 2026-09-17

- Ripristinato il widget Live Sky Q con la preview del contenuto corrente.
- Separati graficamente logo Sky e logo del canale nella scheda Guarda; il logo canale ora riempie il proprio riquadro senza sovrapposizioni.
- Ripristinato l'accesso diretto alla configurazione Player multimediali Control4; Sky Q dispone ora di una scheda Admin separata.

## 2.21.154 — 2026-09-17

- Configurazione Sky Q: ogni app permette di caricare un'icona PNG, JPEG, WebP o GIF personalizzata e persistente, con ripristino dell'icona automatica.
- Le icone personalizzate hanno priorità su quelle del decoder e vengono utilizzate anche nella pagina Guarda.

## 2.21.153 — 2026-09-17

- Ripristinata la composizione originale della scheda Sky Q: preview principale invariata, logo Sky mantenuto e logo del canale aggiunto sotto in dimensione leggibile.
- Nel widget Live della Home viene mostrato il logo del canale corrente, senza usare la preview del programma.

## 2.21.152 — 2026-09-17

- Le app Sky Q si possono riordinare tramite trascinamento; ordine e visibilità restano persistenti e vengono applicati anche alla pagina Guarda.
- Aggiunto un fallback grafico quando le icone interne del decoder non sono accessibili dalla LAN.
- La scheda Sky Q centra la cover e mostra il logo ufficiale del canale corrente al posto del logo generico della sorgente.

## 2.21.151 — 2026-09-17

- Admin Sky Q: mostra sotto la configurazione l'elenco completo delle app rilevate direttamente dal decoder, con icone originali e selezione singola, tutte o nessuna.
- La selezione salvata determina realmente quali app Sky Q vengono esposte nell'interfaccia Guarda.

## 2.21.150 — 2026-09-17

- Le app Sky Q vengono ora scoperte direttamente dal decoder invece di usare una lista manuale.
- Visualizzate 23 app utente reali con icone APPTRAY lette dal box; escluse app bloccate e componenti tecnici interni.

## 2.21.149 — 2026-09-17

- Serializzati tutti i comandi del telecomando Sky Q per evitare connessioni concorrenti e tasti persi.
- Le cifre ravvicinate vengono aggregate in una singola sequenza temporizzata: digitando 100 il decoder riceve ordinatamente 1, 0, 0.
- Frecce, colori e trasporto condividono la stessa coda nativa verso il decoder.

## 2.21.148 — 2026-09-17

- Le sezioni App Sky Q, Stanze e Sorgenti ora occupano tutta la larghezza e usano tessere compatte in righe orizzontali.
- Le app esposte riutilizzano le icone native Control4 e diventano richiami selezionabili quando la sorgente corrispondente è disponibile.
- La descrizione viene troncata anche nei dati renderizzati, oltre al limite grafico di due righe.

## 2.21.147 — 2026-09-17

- La descrizione Sky Q nel dettaglio è limitata a due righe con ellissi.
- La sorgente attiva è ora indicata esplicitamente sia per le sessioni video sia per quelle audio, nella Home e nel dettaglio.

## 2.21.146 — 2026-09-17

- Resi visibili e riconoscibili i quattro tasti Sky Q rosso, verde, giallo e blu nel telecomando video, con feedback alla pressione e cache CSS aggiornata.

## 2.21.145 — 2026-09-17

- Sky Q nativo: e-Face legge direttamente dal decoder stato, app, canale, programma, descrizione e copertina, senza Home Assistant.
- Telecomando Sky Q diretto per navigazione, canali, numeri, trasporto e tasti colorati; volume e spegnimento stanza restano su Control4.
- L'associazione segue la sorgente Control4 Sky Q in qualunque zona video, compresa Sala Cinema, senza vincolarla a una stanza.
- Configurazione e verifica diretta aggiunte in Strumenti → Player multimediali.

## 2.21.144 — 2026-09-17

- La cache e‑Voice ritenta automaticamente lo snapshot dopo uno stato offline iniziale, evitando che un 502 temporaneo durante il riavvio di Home Assistant lasci l'avviso bloccato.

## 2.21.143 — 2026-09-17

- I comandi canale video seguono il layout richiesto: CH sopra la freccia giù a sinistra e freccia su sopra CH a destra.

## 2.21.142 — 2026-09-17

- Home dinamica trasformata in compositore visuale a 12 colonne con anteprima, riempimento degli spazi e larghezze 25%, 33%, 50%, 66% e 100%.
- Il widget LIVE integra i comandi con le icone e-Face: precedente, play/pausa dinamico, successivo e stop, con feedback alla pressione; nelle sessioni video sono disponibili anche CH− e CH+ sia in Home sia nella scheda zona.

## 2.21.141 — 2026-09-17

- Gli slider volume della Home e di Sessioni non vengono più ricreati durante il trascinamento o la conferma del comando.
- Lo stato locale resta stabile mentre arrivano gli aggiornamenti intermedi del backend, eliminando il salto indietro e avanti del cursore.

## 2.21.140 — 2026-09-17

- La Home mostra il volume della stanza e, nelle sessioni multizona, il master relativo: spostandolo ogni zona mantiene la propria differenza di livello.
- Il mute master in Sessioni silenzia o riattiva tutte le zone senza aprire il dettaglio dei volumi.
- I controlli audio sono verdi e quelli video celesti; per i widget videosorveglianza e DoorBird l'altezza è configurabile in Strumenti (bassa, media o alta).

## 2.21.139 — 2026-09-17

- Videosorveglianza e DoorBird aggiornano il relativo widget immediatamente sull'evento reale; il monitor DoorBird ascolta sia campanello sia movimento. Il timer resta soltanto come recupero.

## 2.21.138 — 2026-09-17

- Rimosso il testo visibile “Accesi” dal filtro Luci in tutte le UI; resta soltanto l'icona con descrizione accessibile.
- I widget immagine della Home si aggiornano automaticamente ogni 15 secondi, al ritorno sulla pagina e alla ricezione di una chiamata DoorBird; il meteo ogni 10 minuti.

## 2.21.137 — 2026-09-17

- Ripristinati i livelli verticali dell'equalizzatore sui browser che non supportano gli slider verticali nativi, mantenendo il popup senza overflow.

## 2.21.136 — 2026-09-17

- Corretto l'overflow dell'equalizzatore WiiM: tutte le dieci bande restano dentro il popup senza barra orizzontale.
- Preset e comandi EQ mostrano selezione, pressione, attività in corso e conferma dell'azione eseguita.

## 2.21.135 — 2026-09-17

- La diagnostica DoorBird incrocia programmazione del pulsante, azione SIP e preferito associato e mostra un esito immediato SÌ/NO, la destinazione e le fasce orarie.
- L'esito distingue una rotta configurata dalla prova reale di consegna dell'INVITE SIP ad Asterisk.

## 2.21.134 — 2026-09-17

- In Installatore → Videocitofono arriva la lettura completa e non distruttiva di tutto ciò che la LAN API DoorBird espone: dispositivo, firmware, hardware, relè/controller, SIP, preferiti e programmazioni di tutti gli eventi.
- La schermata distingue esplicitamente i dati letti da quelli che DoorBird conserva soltanto nel portale/app e non rende disponibili alla LAN API.
- La diagnostica confronta automaticamente il percorso DoorBird con Asterisk/e-Face e segnala proxy e destinazione attesi.
- Le password possono essere mostrate esplicitamente dopo una nuova autenticazione admin; la lettura normale le mantiene oscurate.

## 2.21.133 — 2026-09-17

- Località meteo ed entità dell'ultimo evento videosorveglianza sono ora impostazioni uniche dell'impianto, condivise da tutte le UI.
- I precedenti valori telecamera salvati per utente o dispositivo vengono migrati automaticamente e rimossi al primo salvataggio globale.

## 2.21.132 — 2026-09-17

- Corretto lo storico DoorBird: Ultima chiamata usa `doorbell` e Ultimo movimento usa `motionsensor`, come previsto dalla LAN API ufficiale.

## 2.21.131 — 2026-09-16

- Gestione stanze riconosce anche le sessioni create dal percorso WiiM condiviso quando Control4 non pubblica ancora il gruppo.
- Ogni stanza della sessione mantiene il proprio slider volume, separato dal volume generale del master.

## 2.21.130 — 2026-09-16

- Nasce e-Face Composer con progetto Audio/Video persistente, versionato e indipendente dai produttori.
- La prima sincronizzazione importa automaticamente stanze e player Control4 e il WiiM configurato, generando capacità ed endpoint sicuri.
- La nuova mappa futuristica in Strumenti mostra salute, diagnostica e topologia e consente di spostare i dispositivi tra gli ambienti.
- Ogni salvataggio del progetto mantiene una copia locale di sicurezza.

## 2.21.129 — 2026-09-16

- I singoli brani SoundCloud salvati con la stella e-Face compaiono ora nella sezione Preferiti insieme agli altri servizi.
- Un errore SoundCloud non elimina più automaticamente playlist o brani salvati.
- Prima di ogni modifica della libreria SoundCloud viene mantenuta una copia locale di sicurezza.

## 2.21.128 — 2026-09-16

- Il video DoorBird durante la chiamata usa ora una cache JPEG backend condivisa, evitando uno stream MJPEG separato per ogni browser.
- I destinatari aggiornano l'anteprima dalla cache senza saturare il limite di connessioni del DoorBird.
- Se un aggiornamento temporaneo fallisce, il backend mantiene l'ultimo fotogramma valido invece di mostrare un'immagine rotta.

## 2.21.127 — 2026-09-16

- L'interno admin 8301 è ora incluso nel gruppo DoorBird “Tutti”, quindi l'admin può realmente rispondere oltre a vedere l'anteprima.
- Le chiamate provenienti dal gruppo 8290, da 8201 e dai nomi DoorBird/Ingresso/Cancello attivano sempre il video anche sugli utenti personali.
- Il test DoorBird invia anche le notifiche push ai cellulari configurati, oltre a chiamare gli interni SIP attivi.
- Prima dell'arrivo SIP l'interfaccia indica chiaramente che sta attendendo l'audio e mantiene “Rispondi” disabilitato.

## 2.21.126 — 2026-09-16

- La suoneria video DoorBird condivisa ora si arresta automaticamente dopo 45 secondi se il browser non riceve la sessione SIP.
- Il pulsante di chiusura interrompe subito suoneria e anteprima anche nella fase precedente alla chiamata SIP.
- L'arrivo della vera sessione SIP prende il controllo della suoneria senza lasciare timer indipendenti attivi.

## 2.21.125 — 2026-09-16

- Il backend mantiene un solo monitor eventi per ogni DoorBird e distribuisce la chiamata a tutti i browser e-Face collegati.
- Alla pressione del campanello Intercom si apre automaticamente mostrando subito il video live DoorBird, indipendentemente dall'interno SIP che risponde.
- In Strumenti > Videocitofono è disponibile il test completo "PROVA CHIAMATA + VIDEO", che verifica insieme chiamata SIP, notifica UI e anteprima video.

## 2.21.124 — 2026-09-16

- La località meteo è ora unica per l'intero impianto: basta configurarla una volta e viene proposta automaticamente su tutti i dispositivi.
- La località già salvata sul primo pannello viene recuperata automaticamente come configurazione condivisa.
- Cambiando la località da qualsiasi pannello, il nuovo valore viene applicato a tutti.

## 2.21.123 — 2026-09-16

- Cliccando su Ultimo evento, Ultima chiamata o Ultimo movimento si apre ora un visualizzatore fotografico grande.
- Il popup è adattivo, usa quasi tutto lo schermo e si chiude con pulsante, sfondo o tasto Esc.

## 2.21.122 — 2026-09-16

- Corretto il widget Meteo che restava visibile nonostante fosse stato disattivato in Home dinamica.
- La scelta “Mostra” ora ha priorità assoluta sulle regole grafiche di tutti i widget Home.

## 2.21.121 — 2026-09-16

- La località meteo accetta città e provincia, ad esempio `Bra,Cuneo`, selezionando il risultato geografico corretto.
- Sostituite le icone meteo mancanti con simboli atmosferici indipendenti dal catalogo locale.
- Widget meteo rifinito con profondità, bagliore, animazione atmosferica, pannello previsioni in vetro e resa adattiva premium.

## 2.21.120 — 2026-09-16

- Un solo stream SSE e‑Voice viene ora condiviso dal backend e‑Face tra tutti i browser collegati.
- Gli eventi `player.updated` vengono aggregati per 350 ms, producono un solo snapshot in cache e vengono poi distribuiti a tutti i client.
- I heartbeat non interrogano lo snapshot; la riconnessione usa backoff 2, 4, 8, 15 e massimo 30 secondi e chiude sempre lo stream precedente.
- Il bootstrap dei browser legge la cache condivisa e non genera polling parallelo verso e‑Voice mentre il realtime è attivo.

## 2.21.119 — 2026-09-16

- Il meteo non dipende più da Home Assistant: la località si configura in Strumenti → Home dinamica ed è distinta per dispositivo.
- Nuovo widget meteo panoramico con ora locale, condizione, temperatura percepita, umidità, vento e previsione a cinque giorni.
- Grafica atmosferica adattiva e layout specifici per le dimensioni Compatto, Medio e Largo.

## 2.21.118 — 2026-09-16

- L'ultima chiamata DoorBird usa ora l'evento locale `ring`, richiesto dal firmware installato.
- Se la chiamata è conservata soltanto nel cloud DoorBird e la cronologia LAN risponde vuota, il widget mostra l'immagine diretta della postazione invece di “Immagine non disponibile”.

## 2.21.117 — 2026-09-16

- Home dinamica ora viene salvata per singolo browser/dispositivo oltre che per account: pannelli diversi collegati come `admin` non si sovrascrivono più.
- La configurazione dell'account resta il modello iniziale finché il singolo dispositivo non salva la propria personalizzazione.
- Corretto il recupero dell'ultima chiamata DoorBird usando anche la modalità compatibile con firmware che non accettano il filtro evento esplicito.
- Stabilizzata la larghezza dei contatori rapidi nella griglia Home.

## 2.21.116 — 2026-09-16

- Corretto il widget Largo: le vecchie regole interne di Riepilogo, Stati e Live non possono più restringerlo alle prime colonne della nuova griglia Home.

## 2.21.115 — 2026-09-16

- Le dimensioni Home ora controllano una vera griglia: Compatto occupa un terzo, Medio metà riga e Largo tutta la riga; su mobile i widget restano a colonna singola.
- Il pulsante del DoorBird viene instradato automaticamente al gruppo Intercom configurato e la rotta viene verificata a ogni avvio di e-Face.

## 2.21.114 — 2026-09-16

- La configurazione della Home dinamica e la telecamera dell'ultimo evento sono ora separate per utente autenticato.
- Ripristinati gli anelli di selezione vuoti nelle finestre di scelta stanza, senza reintrodurre bordi nelle schede e-Face.
- Il guasto temporaneo del servizio Ekonex Voice locale viene descritto correttamente come indisponibilità Home Assistant con nuovo tentativo automatico, senza l'indicazione fuorviante sulle credenziali.

## 2.21.113 — 2026-09-16

- Aggiunti alla Home dinamica i widget Meteo, ultimo evento videosorveglianza, ultima chiamata DoorBird e ultimo movimento DoorBird.
- Le immagini Home passano da proxy autenticati e-Face: credenziali Home Assistant e DoorBird non vengono inviate al browser.
- Il meteo usa automaticamente la prima entità `weather.*`; la videosorveglianza usa `camera.nvr_32ch_ext_ultimo_evento`.

## 2.21.112 — 2026-09-16

- Aggiunta la Home dinamica: widget persistenti selezionabili, riordinabili tramite trascinamento e dimensionabili da Strumenti utente.
- I widget mantengono gli aggiornamenti realtime e riutilizzano i controlli esistenti senza duplicare lo stato.

## 2.21.111 — 2026-09-16

- Ingrandito il tastierino PIN esclusivamente quando viene aperto dagli scenari nella pagina Scorciatoie.
- Le categorie della pagina Scorciatoie possono essere compresse ed espanse mantenendo lo stato durante gli aggiornamenti realtime.
- Rimossi globalmente i bordi visibili dell'interfaccia, mantenendo colori, riempimenti e stati.
- Lo stato del sistema di sicurezza nelle Scorciatoie è scritto per esteso su una riga separata.
- Rimossi dalle schede scenario i testi esplicativi e lo stato `ATTIVO`: lo scenario richiamato è indicato soltanto dal colore.

## 2.21.110 — 2026-09-16

- Sostituite le frecce delle Scorciatoie con il trascinamento tramite maniglia, coerente con le altre pagine di ordinamento.
- Il trascinamento funziona sia sulle categorie sia sui dispositivi interni alla categoria.

## 2.21.109 — 2026-09-16

- Corretto il contenitore del pannello Scorciatoie in Strumenti: il click ora apre la configurazione.

## 2.21.108 — 2026-09-16

- I termostati e-Therm con `display_only` diventano automaticamente sonde in sola visualizzazione e rifiutano i comandi anche lato server.
- Aggiunta la cella Home Scorciatoie e la relativa pagina con controlli grandi, categorie separate e aggiornamento realtime.
- In Strumenti utente è possibile scegliere i dispositivi di ogni categoria e riordinare categorie e dispositivi.

## 2.21.107 — 2026-09-16

- Corretto l'indice della selezione coda WiiM: ora parte il brano premuto, non quello precedente.

## 2.21.106 — 2026-09-16

- Le playlist SoundCloud senza brani risolvibili vengono eliminate e spariscono subito dai Preferiti, senza schede fantasma con errore 502.
- Il salvataggio ricrea in modo sicuro una playlist selezionata ma nel frattempo rimossa dal backend, evitando l'errore `Lista SoundCloud non trovata`.

## 2.21.105 — 2026-09-16

- Ripristinati titolo, artista, cover e servizio SoundCloud quando il firmware riproduce la lista tramite `CustomPushUrl`.

## 2.21.104 — 2026-09-16

- Dopo il fallback diretto, e-Face ripristina la coda SoundCloud senza interrompere il flusso e attende lo stato reale del player.

## 2.21.103 — 2026-09-16

- Consentiti gli URL SoundCloud firmati nel fallback di riproduzione diretta, mantenendo la validazione HTTPS.

## 2.21.102 — 2026-09-16

- Il richiamo playlist verifica lo stato `playing`; sulle liste da un brano usa l'URL diretto se il firmware lascia ferma la coda custom.

## 2.21.101 — 2026-09-16

- Corretto il DIDL-Lite delle playlist SoundCloud inviate alla coda WiiM.
- Dopo la creazione della coda viene inviato Play esplicito e viene verificato che WiiM abbia accettato numero e titoli dei brani.

## 2.21.100 — 2026-09-16

- Gli errori dei comandi mostrano ora il nome dell'operazione che li ha generati.
- I fallimenti temporanei dei refresh automatici non producono più avvisi rossi casuali: conservano i dati correnti e riprovano in background.
- Le playlist SoundCloud eliminano automaticamente i brani non più risolvibili dal WiiM, aggiornano il Preferito e avviano quelli validi.

## 2.21.99 — 2026-09-16

- Player WiiM: pannello Equalizzatore con sorgenti separate, on/off, 10 bande grafiche e tutti i preset del dispositivo.
- EQ WiiM: applicazione delle bande e salvataggio di preset custom con nome scelto dall'utente.

## 2.21.98 — 2026-09-16

- Playlist SoundCloud storiche: migrazione automatica dell'ordinamento, così tornano visibili a sinistra.
- La copertina della playlist resta quella del primo brano e non cambia a ogni aggiunta.
- Riproduzione SoundCloud: se le credenziali API sono rifiutate, usa gli stream ancora disponibili nella coda nativa WiiM.
- Errori Preferiti: una risposta HTML non produce più il messaggio tecnico `Unexpected token`.

## 2.21.97 — 2026-09-16

- Preferiti: ordine unico tra tutti i servizi, dal piu recente a sinistra al meno recente a destra.
- Playlist SoundCloud: aggiungere un brano a una lista esistente la riporta tra i Preferiti piu recenti.
- Salvataggio SoundCloud: se l'ID traccia manca nel refresh corrente, il server lo recupera dallo snapshot o dalla coda WiiM.

## 2.21.96 — 2026-09-16

- Sessioni: il selettore delle stanze resta aperto durante gli aggiornamenti realtime e conserva le scelte non ancora applicate.
- Player WiiM: lo slider non viene più ricreato a zero dai refresh generali; posizione e durata arrivano soltanto dal polling nativo WiiM.
- Playlist SoundCloud: il salvataggio usa uno snapshot WiiM fresco e un eventuale errore nel refresh grafico non viene più mostrato come errore di salvataggio.
- Player WiiM: l'ultima posizione valida resta visibile anche quando un aggiornamento realtime ricrea la scheda.

## 2.21.95 — 2026-09-16

- Corretto il riconoscimento SoundCloud quando il WiiM è sovrapposto alla stanza Control4: servizio, ID traccia e metadati nativi restano separati dal nome della sorgente Control4.
- La stella apre ora la gestione playlist SoundCloud invece del vecchio salvataggio legato ai preset WiiM.

## 2.21.94 — 2026-09-16

- WiiM: mostra il servizio reale accanto all’artista nel player.
- SoundCloud: dalla stella si può creare una playlist e‑Face con nome scelto dall’utente oppure aggiungere il brano a una lista esistente.
- SoundCloud: il richiamo della playlist risolve URL freschi, crea la coda WiiM completa e prosegue automaticamente tra i brani.
- Player WiiM: cliccando sulla copertina si apre la coda con il brano corrente evidenziato e selezione diretta delle tracce.

## 2.21.93 — 2026-09-16

- Preferiti WiiM: il richiamo di un brano usa il nome interno completo della coda, così `PlayQueueWithIndex` seleziona la traccia memorizzata invece del brano generico del preset.

## 2.21.92 — 2026-09-16

- Home: la sezione Ambienti mostra una sola riga e si espande o richiude dal titolo.
- Dispositivi: rinominato “Vedi tutti” in “Tutti i dispositivi”.
- Filtri: aggiunti Stanza, Accesi e Tutto sia alla vista completa sia a ogni singola stanza.

## 2.21.91 — 2026-09-16

- Ogni comando programma più letture di conferma dello stato reale; le richieste arrivate durante un refresh non vengono più perse.
- Home, pagina stanza, Sessioni e Gestione stanze vengono ridisegnate dallo stesso snapshot confermato.
- Durante sessioni multimediali attive è presente una sincronizzazione di sicurezza ogni cinque secondi, oltre agli eventi realtime.

## 2.21.90 — 2026-09-16

- Le stanze Control4 instradate sullo stesso WiiM vengono consolidate immediatamente in un'unica sessione, anche durante il ritardo transitorio dei metadati gruppo.
- Dopo aggiunta o rimozione di una stanza viene eseguita una seconda sincronizzazione differita del gruppo.

## 2.21.89 — 2026-09-16

- Il richiamo di un preferito brano WiiM mantiene in pausa il preset dinamico finché non ritrova l'ID esatto; un brano diverso non viene più lasciato in riproduzione.
- Se il provider rigenera il preset senza il brano salvato, e-Face conserva il preferito e restituisce un errore esplicito.

## 2.21.88 — 2026-09-16

- e-Face memorizza la stanza che avvia una sessione come master e tratta le stanze aggiunte successivamente come slave.
- Il master e-Face persistito prevale sull'owner tecnico Control4 per apertura cover e volume generale.

## 2.21.87 — 2026-09-16

- Il click sulla cover della sessione in Home apre sempre la stanza master dichiarata da Control4, anche durante stati transitori del master.

## 2.21.86 — 2026-09-16

- Ripristinati volume e mute individuali delle stanze Control4 quando la sorgente attiva è WiiM.
- Il master multiroom applica ora una variazione relativa, preservando la differenza tra i volumi delle stanze.
- Rimossa l'etichetta stanza duplicata nel player; il nome stanza sostituisce i metadati `unknown` ed è più leggibile.
- Aggiunti contratto tecnico e test automatici contro la regressione del volume master.

## 2.21.85 — 2026-09-16

- Rende WiiM la fonte autorevole del player e-Face per stato, traccia, artista, album, cover, volume e mute quando la stanza Control4 usa la sorgente WiiM.
- Invia play, pausa, stop, precedente, successivo, volume e mute direttamente alle API WiiM; Control4 resta soltanto per selezione sorgente, spegnimento stanza e distribuzione zone.
- Espone il WiiM come player e-Face autonomo quando non è collegato a una stanza Control4 attiva, preparando l’uso audio senza Control4.
- Esegue la lettura WiiM in parallelo agli altri provider per non allungare il bootstrap della Home.

## 2.21.84 — 2026-09-16

- Rimuove fondo, riquadro e spaziatura artificiale dal piccolo badge e-Face dei preferiti brano WiiM.
- Colora l’icona Comfort della navigazione in ambra durante Heat, celeste durante Cool e metà ambra/metà celeste quando entrambe le richieste sono attive.
- Disattiva per impostazione predefinita il logo iniziale duplicato e aggiunge in Admin il comando per riattivarlo scegliendo una durata tra 0,5 e 30 secondi.

## 2.21.83 — 2026-09-16

- Impedisce al richiamo di un preferito brano WiiM di agganciare la coda transitoria da un solo elemento mentre il preset è ancora in caricamento.
- Attende fino a 15 secondi nome corretto, brano stabile e almeno due elementi prima di usare `PlayQueueWithIndex`, conservando così la prosecuzione del preset.
- Salva nei nuovi preferiti anche la dimensione originaria della coda e segnala esplicitamente preset eliminati o code non completate.

## 2.21.82 — 2026-09-15

- Include nel pacchetto Git le 31 icone Control4/player caricate manualmente nell’add-on, mantenendo prioritarie le personalizzazioni future dell’utente.
- Risolve le icone prima per ID reale della sorgente e poi per nome portabile, senza dipendere dalla cache del Director dopo un riavvio.
- Distingue nei Preferiti i brani WiiM salvati da e-Face con il badge e-Face; i preset nativi conservano il badge WiiM.

## 2.21.81 — 2026-09-15

- Mostra la X anche sui preset WiiM e, dopo conferma, elimina realmente lo slot dal dispositivo tramite `SetKeyMapping`, facendolo sparire anche da e-Face.
- Ordina i preferiti e-Face persistenti dal più recente al meno recente, mantenendo i preset WiiM nel naturale ordine degli slot.
- Conserva il richiamo dei brani salvati tramite numero del preset e ID traccia anche dopo successive rinominazioni del preset.

## 2.21.80 — 2026-09-15

- La stella del player salva il brano WiiM corrente insieme al preset di origine e al suo ID stabile, senza conservare l'URL audio temporaneo.
- Il richiamo riapre il preset, cerca nuovamente il brano nella coda e lo avvia con `PlayQueueWithIndex`, mantenendo la riproduzione dei brani successivi.
- Aggiunge lettura paginata della coda WiiM tramite il namespace proprietario verificato `schemas-wiimu-com` e segnala chiaramente i brani non più presenti.

## 2.21.79 — 2026-09-15

- Aggiunge al player Ascolta, quando la sorgente attiva è WiiM, lo slider operativo di avanzamento con tempo trascorso e residuo.
- Integra shuffle e repeat nativi WiiM accanto ai controlli Control4 già presenti, mostrando lo stato attivo e preservando tutte le combinazioni di ripetizione.
- Adatta il player esteso a desktop e mobile senza aggiungere pulsanti privi di una funzione reale.

## 2.21.78 — 2026-09-15

- Quando si richiama un preset WiiM dai Preferiti, e-Face avvia il preset e seleziona subito la sorgente WiiM nella stanza Control4 corrente.
- Valida stanza e sorgente configurata e segnala esplicitamente l'eventuale successo parziale, senza dichiarare completato un routing Control4 fallito.

## 2.21.77 — 2026-09-15

- Integra automaticamente i preset nativi WiiM nella barra Preferiti di e-Face senza copiarli o richiedere credenziali dei provider.
- Mostra per ogni preset cover, icona del servizio e icona WiiM; il tocco richiama direttamente il preset sul player.
- Rimuove dall'Admin la configurazione SoundCloud API a pagamento e indica il percorso nativo tramite WiiM.

## 2.21.76 — 2026-09-15

- Aggiunge in Amministrazione una console SoundCloud completa per il collaudo prima dell'integrazione in Ascolta.
- Supporta ricerca separata di brani, playlist e artisti, navigazione delle raccolte e suggerimenti correlati.
- Avvia sul WiiM gli stream SoundCloud ufficiali preferendo AAC HLS 160 kbps e mantiene visibile il player live e-Face.
- Conserva cronologia e preferiti SoundCloud locali e-Face senza richiedere accesso all'account personale.

## 2.21.75 — 2026-09-15

- Allinea i comandi WiiM alle icone MDI già usate nella sezione Ascolta, con SVG visibili anche sotto Ingress/PWA.
- Aggiunge in Amministrazione la ricerca di prova del catalogo SoundCloud con titolo, autore e copertina.
- Invalida in sicurezza il token SoundCloud quando cambiano le credenziali.

## 2.21.74 — 2026-09-15

- Rende operativo lo slider di avanzamento con seek nativo WiiM in secondi e impedisce al polling di spostarlo mentre l'utente lo trascina.
- Uniforma i controlli della console alle icone media e-Face e aggiunge shuffle, ripetizione, stop, aggiungi e preferito; shuffle e repeat comandano realmente il WiiM.
- Avvia l'adattatore SoundCloud ufficiale con configurazione protetta in Admin, token Client Credentials riutilizzabile e ricerca normalizzata delle tracce tramite URN.

## 2.21.73 — 2026-09-15

- Sposta la console tecnica WiiM dalla navigazione principale alla sezione Admin, dove resta disponibile per debug e verifiche future.
- Introduce il registro degli adattatori musicali profondi, con Spotify come primo provider da configurare e stato esplicito per TIDAL, Qobuz, Amazon Music, radio/podcast e librerie UPnP/DLNA.
- Protegge la pagina della console WiiM con ruolo amministratore e documenta il confine tra API locali del player e cataloghi ufficiali dei servizi.

## 2.21.72 — 2026-09-15

- Prepara il multiroom WiiM nativo con lettura diretta di ruolo, nome gruppo, membri e versione del protocollo WMRM.
- Aggiunge al player una sezione Multiroom già collegata alle API; i comandi di unione e separazione restano volutamente disabilitati finché non saranno verificati sui dispositivi reali.

## 2.21.71 — 2026-09-15

- Aggiunge nella navigazione utente la pagina WiiM nativa con cover, metadata, timeline, qualità audio, stato e volume aggiornati direttamente dalla LAN.
- Abilita play/pausa, stop, precedente, successivo, mute e regolazione volume senza passare da Home Assistant o Control4.
- Mostra e richiama i preset salvati nel WiiM, mantenendo Control4 fuori dal percorso dei comandi del player.

## 2.21.70 — 2026-09-15

- Aggiunge in Amministrazione la configurazione WiiM nativa e-Face → WiiM, con verifica diretta del player sulla LAN e riepilogo di modello, firmware, stato, volume e brano.
- Introduce il client HTTPS WiiM per stato, metadati, cover e qualità audio, senza usare Home Assistant come backend.
- Mantiene separata l'associazione Control4 opzionale, usata soltanto per sorgente e distribuzione nelle stanze, e impedisce il salvataggio se il test diretto fallisce.

## 2.21.69 — 2026-09-15

- Riduce da 60 secondi a 1,5 secondi il blocco anti-duplicato dopo il rifiuto o la chiusura di una chiamata: una nuova chiamata non riceve più erroneamente `486 Busy`.
- Chiude la scheda chiamata quando la sessione SIP o la PeerConnection risulta realmente terminata, evitando chiamate fantasma senza audio dopo la chiusura dal touch Control4.

## 2.21.68 — 2026-09-15

- Abilita la prima prova video H.264 e-Face → tablet Control4 Ufficio/8100; Tavolo resta audio come riferimento.

## 2.21.67 — 2026-09-15

- La testata grande mostra sempre `Chiamata a <interno>` o `Chiamata da <interno>`; la riga tecnica SIP sottostante è nascosta.
- Durante il video la scheda chiamata non resta sticky sopra l'immagine e non ne copre la parte superiore.
- Corregge il controllo aggiornamenti Intercom rimasto alla 2.21.61, che provocava un falso reload e la scomparsa dell'elenco ogni 30 secondi.

## 2.21.66 — 2026-09-15

- Apre sempre il pannello video nelle chiamate verso interni e-Face, anche quando la camera locale è disattivata.
- Porta automaticamente in primo piano i controlli e il video della chiamata avviata da una riga più in basso nell'elenco.
- Mostra il nome dell'interno chiamato durante composizione, squillo e conversazione.
- Porta direttamente in vista l'anteprima della camera locale prima dell'invio della chiamata, così il chiamante può sistemare l'inquadratura durante lo squillo.
- Sul dispositivo chiamato apre il video e prepara l'anteprima camera già durante lo squillo; il microfono resta inattivo fino a RISPONDI.

## 2.21.65 — 2026-09-15

- Invia il Web Push della chiamata prima della preparazione di microfono e camera.
- Marca le chiamate Intercom come Web Push ad alta urgenza per ridurre l'accodamento sui telefoni Android in standby.
- Rilevazione Director: i T3/T4 installati espongono proxy Intercom e il progetto include l'agente Video Intercom; la relativa abilitazione SIP verrà basata sulla negoziazione reale, non su una classificazione audio fissa.

## 2.21.64 — 2026-09-15

- Stabilizza l'elenco Intercom: i controlli del dispositivo corrente non vengono più eliminati e ricreati a ogni refresh invariato.
- Ignora le risposte obsolete quando due aggiornamenti degli interni si sovrappongono.

## 2.21.63 — 2026-09-15

- Evita falsi `ReadTimeout` di eKonex Voice locale durante la ricostruzione delle entità dopo un riavvio Home Assistant.
- Aggiorna il service worker PWA insieme agli asset Intercom.

## 2.21.62 — 2026-09-15

- Apre subito il pannello video nelle chiamate e-Face e mostra l'esito reale dell'accesso alla camera.
- Considera tutti gli interni personali compatibili con la ricezione video, indipendentemente dalla camera del destinatario.
- Aggiunge fallback camera e rilevamento più robusto dell'offerta video in ingresso.

## 2.21.61 — 2026-09-15

- Video SIP/WebRTC H.264 e VP8 per dispositivi e-Face e telefoni VoIP compatibili, con negoziazione automatica e fallback audio.
- Anteprima DoorBird durante lo squillo, video remoto e locale, disattivazione video e cambio camera frontale/posteriore durante la conversazione.
- Capacità e preferenze video persistenti per ogni dispositivo nella sezione Utente; i Control4 audio-only restano compatibili nei gruppi misti.

## 2.21.60 — 2026-09-15

- Postazioni esterne in cima e dispositivo corrente subito sotto, senza pulsante CHIAMA e con livelli audio e DND persistente.
- Icona Intercom dinamica: grigia offline, verde disponibile, rossa durante lo squillo e gialla in conversazione.
- Gestione Admin dei gruppi Intercom con selezione degli interni; Tutti (8290) segue automaticamente il DND e-Face e lascia ai Control4 il DND nativo.

## 2.21.59 — 2026-09-15

- La splash nativa della PWA usa nero puro per sfondo e barra di sistema, eliminando definitivamente il precedente verde-petrolio dalle nuove installazioni.

## 2.21.58 — 2026-09-15

- L'Intercom usa lo sfondo scelto in Personalizzazione e non il precedente gradiente verde-petrolio fisso.
- Testata PWA e superfici della lista Intercom passano all'antracite neutro; nessuna splash aggiuntiva viene mostrata dal percorso notifica.

## 2.21.57 — 2026-09-15

- Il tocco sulla notifica porta l'eventuale finestra e-Face già aperta direttamente al collegamento Intercom della chiamata; se non esiste, ne apre una nuova.

## 2.21.56 — 2026-09-15

- Ripristinata la suoneria Classica nel selettore, così i dispositivi con una preferenza precedente non mostrano un valore vuoto e possono salvare correttamente.

## 2.21.55 — 2026-09-15

- Il primo tocco sulla Home, sugli Strumenti o sull'Intercom sblocca preventivamente il canale audio della suoneria nei WebView Android che vietano l'autoplay.

## 2.21.54 — 2026-09-15

- Quando il Tablet 4 apre automaticamente l'Intercom, la pagina visibile riavvia il campanello HTML precedentemente bloccato nell'iframe nascosto.

## 2.21.53 — 2026-09-15

- Il Tablet 4 riproduce la chiamata con un elemento audio reale in autoplay; WebAudio resta disponibile come riserva.
- Aggiunte cinque suonerie selezionabili per dispositivo con timbro da campanello.
- TERMINA rifiuta definitivamente la chiamata entrante e blocca le riconsegne SIP della stessa chiamata.

## 2.21.52 — 2026-09-15

- Anche la pagina Strumenti mantiene un client Intercom registrato in background e apre automaticamente la schermata di risposta senza perdere la chiamata.

## 2.21.51 — 2026-09-15

- Sul tablet la suoneria viene riattivata appena l'Intercom nascosto diventa visibile, evitando l'attesa dell'AudioContext sospeso nell'iframe.
- A volume 100 la suoneria Classica/Doppio tono usa ora il livello WebAudio pieno e un timbro più udibile sugli altoparlanti di cellulari e tablet.

## 2.21.50 — 2026-09-15

- Rimossi i colori verde petrolio dal caricamento e dal modulo Login: superfici antracite, campi neri e accento grigio coerenti con la UI.
- Il Login mostra il logo e-Face e non precompila più impropriamente l'utente `admin`.

## 2.21.49 — 2026-09-15

- La sessione persistente usa `SameSite=Lax`: Android può presentarla quando e-Face viene aperta da PWA o notifica, mantenendo HttpOnly, Secure su HTTPS e la protezione Origin delle API mutative.

## 2.21.48 — 2026-09-15

- Aggiorna forzatamente lo script Home che riceve dall'Intercom nascosto l'evento di chiamata, evitando che tablet con cache precedente squillino senza aprire la schermata di risposta.

## 2.21.47 — 2026-09-15

- Le notifiche di chiamata usano un accesso monouso di breve durata associato al dispositivo: Android può aprire direttamente Intercom anche quando non condivide il cookie della PWA.
- L'accesso monouso viene consumato al primo utilizzo e rinnova la sessione persistente solo se consentito per quell'utente.
- Quando Admin abilita `Persistenza: Sì`, il login emette sempre la sessione persistente senza dipendere da una seconda casella eventualmente rimasta in cache sul dispositivo.

## 2.21.46 — 2026-09-15

- Con e-Face già aperta, una chiamata in ingresso porta automaticamente il tablet alla sezione Intercom.
- Il pannello Rispondi/Termina è ora il primo elemento della pagina e rimane visibile in alto durante la chiamata.

## 2.21.45 — 2026-09-15

- Il tap sulla notifica apre sempre la pagina Intercom autonoma, evitando il passaggio Home/iframe che su alcuni Android non avviava la registrazione SIP.
- Durante il risveglio viene mostrato immediatamente il nome del chiamante e lo stato di collegamento.

## 2.21.44 — 2026-09-15

- Compatibilità con i tablet/WebView privi di `crypto.randomUUID()`: il dispositivo personale viene ora creato e riceve il proprio interno.
- La testata mostra il nome utente dell'account attualmente autenticato.

## 2.21.43 — 2026-09-15

- Il tap sulla notifica apre direttamente la sezione Videocitofono anche quando la PWA era già aperta sulla Home.
- La chiamata parte senza l'attesa artificiale di 3,5 secondi e la suoneria e-Face ha un livello più alto.
- Lo sfondo della Home segue direttamente il preset o la foto scelti in Personalizzazione.

## 2.21.42 — 2026-09-15

- Aggiunge Web Push/PWA per avvisare un dispositivo personale anche quando e-Face è chiusa.
- La notifica persistente apre direttamente Intercom; le sottoscrizioni sono private, revocabili e associate al singolo dispositivo.
- Le chiamate avviate dalla rubrica e-Face inviano il push prima del tentativo SIP.

## 2.21.41 — 2026-09-15

- Aggiunge in Strumenti > Utente > Videocitofono nome, suoneria, volume, vibrazione, modalità silenziosa e prova audio per il dispositivo in uso.
- Salva le preferenze centralmente per dispositivo e le applica automaticamente alle chiamate Intercom.

## 2.21.40 — 2026-09-15

- Distingue cellulari, tablet e PC nella rubrica Intercom con icone dedicate e migra automaticamente i dispositivi già registrati.

## 2.21.39 — 2026-09-15

- Aggiunge suoneria locale ripetuta e vibrazione alle chiamate Intercom in ingresso, con arresto su risposta o termine.
- Mostra un comando Attiva suoneria se il browser blocca la riproduzione automatica.

## 2.21.38 — 2026-09-15

- Rimuove dalla schermata Videocitofono la vecchia gestione SIP manuale per utente: cellulari, tablet e PC usano soltanto i dispositivi personali automatici.
- Mostra il numero interno nella rubrica Intercom anche per tablet Control4 e postazioni esterne DoorBird.

## 2.21.37 — 2026-09-15

- Rende il comando Esci da e-Face visibile a tutti gli utenti nell'area comune di Strumenti.

## 2.21.36 — 2026-09-15

- Consente all'admin di abilitare o revocare l'accesso persistente separatamente per ogni utente.
- La revoca invalida le sessioni esistenti; gli account senza permesso restano limitati a 12 ore anche se il dispositivo chiede di essere ricordato.

## 2.21.35 — 2026-09-15

- Aggiunge l'accesso persistente per dispositivi fidati, revocabile con logout, cambio password, disattivazione o eliminazione utente.

## 2.21.34 — 2026-09-15

- Prepara gli account per la futura origine VPS senza esporre password: origine locale persistente, stato sincronizzazione e data creazione.
- Mostra in Admin l'origine account e l'opzione VPS disabilitata finché inviti firmati, anti-replay e audit non saranno operativi.

## 2.21.33 — 2026-09-15

- Aggiunge in Amministrazione l'eliminazione definitiva degli utenti, con protezione di admin e controllo delle risorse Intercom associate.

## 2.21.32 — 2026-09-15

- Stabilizza i colori dell'icona master Energia durante refresh e variazioni rapide dei feed.

## 2.21.31 — 2026-09-15

- Usa `mdi:coolant-temperature` nel master Comfort e divide icona/testo fra riscaldamento e raffrescamento quando entrambi sono attivi.

## 2.21.30 — 2026-09-15

- L'icona master Energia segue il colore del flusso dominante di ogni impianto e si divide quando i feed hanno colori differenti.

## 2.21.29 — 2026-09-15

- Uniforma gli slider volume delle schede media: verde per audio e celeste per video.

## 2.21.28 — 2026-09-15

- Rimuove il verde fisso dalla barra di stato Android, dalla barra di navigazione mobile e dal primo frame di caricamento.

## 2.21.27 — 2026-09-15

- Applica sfondo e colore card salvati già nel primo HTML, eliminando il lampo verde durante l'avvio.
- Estende la palette scelta a Strumenti, Amministrazione, wizard, Intercom e login senza alterare i colori semantici di stato.
- Allinea la versione mostrata in Strumenti alla versione reale dell'add-on.

## 2.21.26 — 2026-09-15
- Ogni cellulare, tablet o PC con un account e-Face personale ottiene un proprio interno SIP 8302–8349 al primo accesso Intercom. L’identità del browser, inventario e credenziali sono persistenti; Asterisk conferma il provisioning prima che e-Face consegni le credenziali. Admin può rinominare e revocare ogni dispositivo. Gli account SIP manuali legacy non vengono rimossi. Il client riceve chiamate quando Intercom è aperto; chiamate con app chiusa/background non sono ancora supportate.

## 2.21.25 — 2026-09-15
- Admin → Videocitofono aggiunge Telefoni VoIP: account SIP generici registrabili 8350–8399, scelta audio/audio+video, credenziali persistenti e recuperabili con password admin, modifica e revoca. Intercom mostra i telefoni con endpoint confermato. Il video del client e-Face non è ancora implementato: la compatibilità video tra dispositivi SIP va provata sul modello reale.

## 2.21.24 — 2026-09-14
- Il wizard salva nuovi tablet Control4 (8293–8299) con nome e SIP User Name di Composer, e chiede al provisioner Asterisk una rotta SIP isolata usando il proxy beta esistente. Le rotte 8290–8292 non vengono modificate. Intercom mostra i nuovi tablet solo come chiamabili se la rotta è confermata; squillo e audio richiedono ancora un test reale.

## 2.21.23 — 2026-09-14
- Il wizard Intercom ora è il punto di ingresso anche per le modifiche: apre Control4, Videocitofono e Credenziali; ogni sezione permette di tornare al passo precedente e il wizard rilegge i dati salvati. Il passo corrente resta sul dispositivo. I nuovi tablet non sono dichiarati configurabili finché il provisioning Asterisk non è pronto.

## 2.21.22 — 2026-09-14
- Preparazione impianto diventa una configurazione guidata Intercom in quattro passi. Include il tutorial Composer per aggiungere e-Face come dispositivo esterno, l'AOR 8301 ricavato dall'IP Asterisk, la posizione di SIP Information dei tablet, collegamenti alle configurazioni Admin e verifica rete. Distingue password Director, SIP Control4 e SIP e-Face senza esporle. La guida segnala esplicitamente che il provisioning dei nuovi tablet non è ancora implementato e non modifica le rotte beta.

## 2.21.21 — 2026-09-14
- Le due postazioni interne Control4 (8291 e 8292) possono essere rinominate da Strumenti → Admin → Videocitofono. Le etichette sono persistenti in e-Face e si aggiornano nella pagina Intercom; SIP, Asterisk e nomi dei tablet restano invariati.

## 2.21.20 — 2026-09-14
- Prima di chiamare una postazione esterna, e-Face verifica e prepara il suo SIP via API DoorBird. Evita il rifiuto 603 quando un altro sistema ha ripristinato il chiamante autorizzato del DoorBird Ingresso a Control4; non esegue scritture periodiche mentre non si chiama.

## 2.21.19 — 2026-09-14
- SALVA E CONFIGURA in Admin verifica e, se necessario, riapplica l'autorizzazione SIP anche al DoorBird Ingresso già esistente. È stato osservato un ripristino esterno del suo chiamante autorizzato a Control4 dopo i riavvii; la configurazione resta controllabile da e-Face senza interventi su Asterisk.

## 2.21.18 — 2026-09-14
- Le nuove postazioni esterne vengono preparate completamente da Admin e-Face: l'API DoorBird abilita le chiamate SIP in ingresso e autorizza Asterisk, salvando i valori precedenti; poi il provisioner configura e verifica la rotta persistente. In caso di errore e-Face prova a ripristinare entrambi i lati e non abilita CHIAMA.

## 2.21.17 — 2026-09-14
- Intercom: elenco persistente di fino a otto postazioni esterne in Strumenti → Admin → Videocitofono. Ogni postazione ha nome, IP, porta HTTP, credenziale server-side e interno SIP 82xx; e-Face configura e verifica la rotta SIP persistente tramite il provisioner Asterisk associato, poi abilita CHIAMA e video. La pagina Intercom aggiorna l'elenco senza ricarica. Il DoorBird Ingresso mantiene la rotta 8201 e le credenziali esistenti. Nessun gruppo di chiamata in ingresso viene ancora modificato.

## 2.21.16 — 2026-09-14
- Intercom: pulsante CHIAMA per la postazione esterna DoorBird. Il numero 8201 usa la chiamata SIP peer-to-peer tramite Asterisk; la configurazione del DoorBird e il dialplan sono mantenuti in modo persistente. La pagina rileva nuove versioni ogni 30 secondi e si aggiorna automaticamente, aspettando la fine di un'eventuale chiamata.

## 2.21.15 — 2026-09-14
- Il client Intercom si aggancia al RTCPeerConnection anche se JsSIP lo ha creato prima del listener, recupera la traccia audio già presente tramite `getReceivers()` e avvia i contatori RTP. Evita che l'indicatore resti fermo su «Audio in ingresso: in attesa» e che il player perda l'evento della traccia. Da verificare con chiamata reale.

## 2.21.14 — 2026-09-14
- Audio Intercom: ricezione sul cellulare tramite elemento audio nativo, senza passaggio dell'uscita attraverso WebAudio. Durante la chiamata mostra pacchetti audio ricevuti e stato del player; se il browser blocca la riproduzione compare ATTIVA AUDIO. Il volume dell'uscita diretta arriva al 100%, mentre il guadagno microfono resta invariato. Correzione da verificare con una chiamata reale.

## 2.21.13 — 2026-09-14
- Intercom può chiamare singolarmente i tablet Control4: Ufficio 8291 e Tavolo 8292, oltre al gruppo 8290. Sul sito beta i numeri sono aggiunti al dialplan persistente con backup del file precedente. In modalità remota il browser propone solo candidati TURN relay per evitare tentativi verso indirizzi privati non raggiungibili, in seguito a un caso di audio monodirezionale; l'esito audio richiede ancora prova fisica.

## 2.21.12 — 2026-09-14
- Chiamate remote: JsSIP invia la descrizione audio appena è disponibile un candidato TURN relay, senza aspettare la fine di tutta la raccolta ICE; il tasto Termina mostra subito lo stato di chiusura e non accetta pressioni duplicate. L'accesso HTTP locale su IP non può usare il microfono del browser: per le prove audio serve il dominio HTTPS.

## 2.21.11 — 2026-09-14
- La schermata Intercom mostra solo le postazioni e toglie le descrizioni superflue. Collegamento SIP e impostazioni audio passano a Strumenti → Admin → Videocitofono; il client SIP dell'app si registra automaticamente all'apertura di e-Face e resta attivo durante la navigazione interna. Il video DoorBird si apre solo nella schermata Intercom.

## 2.21.10 — 2026-09-14
- Intercom usa l'organizzazione a elenco delle postazioni del riferimento Control4 fornito dall'utente, ma mantiene sfondo, schede e colori e-Face. Anteprima DoorBird compatta (180 px, 115 px su telefono) espandibile; controlli di chiamata visibili solo durante la conversazione e impostazioni esistenti raccolte in un pannello.

## 2.21.9 — 2026-09-14
- Intercom entra nella barra laterale con l'icona a barre e sorriso, grigia quando inattiva. La schermata citofono è integrata nella sezione e-Face; il video DoorBird MJPEG continuo passa da un proxy autenticato e limitato, con ripiego sui fotogrammi.

## 2.21.8 — 2026-09-14
- La pagina citofono mostra immagini live DoorBird aggiornate mentre è visibile. e-Face recupera JPEG con la credenziale salvata, senza esporla al browser; accesso autenticato, risposta non memorizzabile e limite di dimensione.

## 2.21.7 — 2026-09-14
- La stella del player Spotify salva/rimuove la playlist più recente della stanza, verificata nel contesto Control4, anziché cercare il titolo del brano in riproduzione. Il preferito mantiene il nome della playlist e resta riproducibile dalla cronologia.

## 2.21.6 — 2026-09-14
- Preferiti Spotify: quando la copertina temporanea non è disponibile compare il logo Spotify, non un'icona musicale generica. I preferiti precedenti recuperano e salvano l'ID del servizio dalla cronologia quando ancora presente. Anche i piccoli loghi sotto i preferiti usano l'icona reale della sorgente configurata in e-Face.

## 2.21.5 — 2026-09-14
- Stella del player Stations: salva o rimuove la stazione attiva dai Preferiti e-Face usando l'ID verificato nel catalogo, indipendentemente dalla cronologia Control4. L'indicatore LIVE conserva le dimensioni della scheda e mostra otto barre animate, rispettando il movimento ridotto.

## 2.21.4 — 2026-09-14
- Le copertine dei Preferiti ricavati dalla cronologia vengono salvate sul volume persistente. Le immagini già disponibili vengono recuperate quando possibile; se mancano, resta visibile l'icona del servizio anziché una cella vuota.

## 2.21.3 — 2026-09-14
- Wireless Music Bridge: la scheda sorgente seleziona il bridge nella stanza; il popup Bluetooth si apre dalla copertina o dall'icona del player quando la sorgente è attiva.

## 2.21.2 — 2026-09-14
- Wireless Music Bridge: popup e-Face con elenco Bluetooth letto dal driver Control4 tramite richieste asincrone, connessione/disconnessione, aggiunta dispositivo con conferma, aggiornamento lista e rimozione con conferma. Nessun elenco statico né comandi TuneIn riutilizzati.

## 2.21.1 — 2026-09-14
- Stella nel player Ascolta per aggiungere o rimuovere subito il contenuto riproducibile presente nella cronologia Control4 dai Preferiti e-Face, con stato grigio/acceso. In Strumenti → Icone sorgenti, Nascondi/Mostra salva sul volume persistente quali sorgenti non devono comparire tra le scelte e-Face.

## 2.21.0 — 2026-09-14
- Popup musicali: superfici e accenti seguono il tema schede salvato in Strumenti. Grafite predefinito ora è grigio neutro; gli altri temi restano selezionabili. I preset Spotify senza copertina mostrano il logo Spotify e le voci informative un'icona dedicata; gli altri servizi usano icone coerenti come fallback.

## 2.20.99 — 2026-09-14
- Spotify Connect: popup e-Face con Preset, Ascoltate di recente e Impostazioni basati sui comandi del driver Control4. Preset e recenti si possono riprodurre nella stanza corrente e aggiungere ai Preferiti e-Face persistenti; nessuna voce Preferito alla stanza Control4 nel menu.

## 2.20.98 — 2026-09-14
- Nuova barra Preferiti persistente nella scheda Ascolta, condivisa tra stanze. Le radio Stations e i contenuti riproducibili di TuneIn, Amazon Music e TIDAL hanno l'azione "Aggiungi come preferito in e-Face"; anche gli ascolti recenti possono essere aggiunti con ★. La riproduzione usa la stanza attualmente comandata. Il menu non mostra più i preferiti della stanza Control4.

## 2.20.97 — 2026-09-14
- Stations: Internet Radio nella scheda Sorgenti usa l'icona fornita dall'utente come risorsa locale, indipendente dall'icona restituita da Control4.

## 2.20.96 — 2026-09-14
- Stations: se il driver della singola radio non è tra le sorgenti della stanza, il player mostra la sorgente Stations invece del precedente AirPlay. La copertina codificata nei metadata Control4 è risolta tramite il Director.

## 2.20.95 — 2026-09-14
- Stations: copertine dal Director nel popup, sorgente e titolo reali nel player dopo la selezione, aggiornamento immediato e palette del popup allineata alle schede utente. Catalogo stazioni salvato in /data per mantenere il riconoscimento dopo il riavvio.

## 2.20.94 — 2026-09-14
- Stations: la tessera Sorgenti e servizi apre il navigatore Control4 con Radio, Sorgenti e Generi. Selezione stazioni e preferito della stanza usano i comandi del proxy Stations.

## 2.20.93 — 2026-09-14
- Player Control4: il navigatore si apre anche per Amazon Music e TIDAL. Schede lette dal driver; Amazon Home e sottocategorie navigate con Browse/SelectItem, azioni di riproduzione del driver e stato account. TIDAL mostra le sue schede e lo stato account; il controller al momento segnala Logged Out.
- Palette utente: verificati i componenti delle schede e popup; anche le schede generiche e Ora in riproduzione seguono il colore scelto, oltre al navigatore musicale e al pannello Nascosti.

## 2.20.92 — 2026-09-14
- Il nome della stanza nel player generale e' testo semplice, senza bordo ne' riquadro.

## 2.20.91 — 2026-09-14
- Player delle viste generali Ascolta e Guarda: etichetta con il nome della stanza comandata, anche su mobile, usando la palette scelta dall'utente. Nella vista stanza resta solo l'intestazione esistente.

## 2.20.90 — 2026-09-14
- Navigatore TuneIn e pannello Nascosti: le superfici seguono la palette delle schede scelta dall'utente, anziché usare sfondi grigi fissi.

## 2.20.89 — 2026-09-14
- Ascoltati di recente: × aggiorna subito la UI senza refresh pagina; Nascosti mostra le fonti da ripristinare singolarmente. Rimossa dalla UI l'azione che azzerava tutti i nascosti.
- Stato nascosti scritto in modo atomico e serializzato su /data, per mantenerlo dopo refresh, riavvio e aggiornamento.

## 2.20.88 — 2026-09-14
- Ascoltati di recente: i pulsanti Nascondi (×) e Ripristina funzionano anche quando gli account utente opzionali non sono configurati; con account attivi resta richiesto il login.

## 2.20.87 — 2026-09-14
- TuneIn: corretta la lettura delle azioni separate da spazi; tap sulla stazione avvia Play e il menu offre preferiti del servizio e della stanza. Verificati sul Director Play e Follow/Unfollow con ripristino dello stato iniziale.
- Sessioni Control4: Digital Media mostra il servizio effettivo indicato da `PLAYING_AUDIO_DEVICE`; stanze con stesso servizio, cover e album vengono mostrate nella stessa sessione logica quando una usa la coda digitale.
- Ascoltati di recente: schede allineate e possibilità di nascondere singoli elementi in e-Face e ripristinarli; la cronologia del Director non viene modificata.

## 2.20.86 — 2026-09-14
- Anche la cover grande apre il navigatore TuneIn. Aggiunta la scheda Impostazioni con stato e nome utente, senza esporre la password restituita dal driver.

## 2.20.85 — 2026-09-14
- Navigatore TuneIn reale nel popup di Ascolta: Home, Sfoglia, Preferiti, ricerca, categorie, paginazione e azioni del driver. Comunicazione MSP verificata sul Director con XML ARGS e risposta WebSocket correlata; URL interni protetti sul server.

## 2.20.84 — 2026-09-13
- Rimossi da Strumenti i controlli diagnostici musicali non più necessari e le relative API di prova. Restano i flussi di associazione account e la diagnostica cover.

## 2.20.83 — 2026-09-13
- La diagnostica MSP attende che `dataToUi` sia effettivamente sottoscritto prima di inviare il comando; osserva eventi su tutti gli ID e classifica il `result` senza esporlo.

## 2.20.82 — 2026-09-13
- Diagnostica MSP TuneIn: ascolta gli eventi del driver prima di inviare `GetTabList` e verifica la correlazione `NAVID`/`SEQ` senza esporre dati privati.

## 2.20.81 — 2026-09-13
- Ripristinati gli «Ascoltati di recente» sotto il player in Ascolta: la richiesta precedente riguardava soltanto il popup del servizio, non questa sezione. Nessuna cronologia viene mostrata nel popup.
- La striscia dei recenti ora si scorre trascinando col mouse su Windows, senza barra visibile; la rotella mantiene lo scorrimento normale della pagina.

## 2.20.80 — 2026-09-13
- Rimosso il popup provvisorio aperto dalla cover: non era il navigatore MSP richiesto e compariva anche per sorgenti generiche come MP3. La navigazione dei servizi resta da integrare con dati e azioni reali del driver.
- Ridotta la verbosità predefinita a WARNING, disabilitati anche i log informativi Uvicorn e limitati a uno al minuto per sorgente gli avvisi di riconnessione realtime. Riconnessioni fallite usano un backoff progressivo fino a 30 secondi.
- Rimossa dalla vista Ascolta la sezione globale «Ascoltati di recente» e le sue richieste periodiche: nel navigatore futuro compariranno invece i preferiti del solo servizio attivo, come cover senza etichette visibili.

## 2.20.79 — 2026-09-13
- La cover del player Control4 in Ascolta apre un popup contestuale alla stanza e alla sorgente attiva. Clic fuori, Esc o Chiudi richiudono il popup senza fermare la riproduzione.
- Nel popup sono richiamabili gli ascolti recenti del servizio attivo. La navigazione MSP di Sfoglia, Cerca e Preferiti non è ancora collegata: il popup lo dichiara esplicitamente, senza mostrare controlli fittizi.

## 2.20.78 — 2026-09-13
- Aggiunta in Strumenti → Account musicali una prova TuneIn sul driver attivo: prima tenta l'azione di generazione link usata da Amazon/TIDAL, poi il login Navigator con i segnaposto del protocollo se non arriva un link. Il link viene preso solo dagli eventi del controller e mai salvato.
- Il metodo specifico del TuneIn installato resta da confermare sul controller reale; nessuna credenziale TuneIn viene richiesta o trasmessa.

## 2.20.77 — 2026-09-13
- Spostato il ricollegamento dei servizi da Ascolta a **Strumenti → Account musicali**, accessibile anche agli utenti non amministratori. L'area raggruppa i driver musicali rilevati sul controller e distingue i servizi disponibili da quelli ancora da integrare.
- Amazon Music resta operativo; la riproduzione da e-Face è stata confermata dopo la callback di autorizzazione.
- Predisposto TIDAL nello stesso flusso a link perché il pacchetto fornito dichiara la medesima azione `GetLinkForAPIAuthentication`; in UI è marcato come prova finché il controller reale non conferma il risultato. TuneIn legacy, Deezer e Qobuz non vengono trattati come equivalenti senza verifica.

## 2.20.76 — 2026-09-13
- Confermato sul controller reale che `LUA_ACTION / GetLinkForAPIAuthentication` produce un link nel flusso eventi Director; tra gli eventi osservati compare anche `UPDATE_PROPERTY`.
- In Ascolta, quando Amazon Music è tra le sorgenti Control4, gli utenti e-Face possono richiedere un link temporaneo e aprirlo nel browser per ricollegare l'account. Il link non viene salvato né scritto nei log.
- La diagnosi admin Amazon consente di scegliere tra azione Composer e comando Navigator, impostare 1–30 secondi di osservazione e verificare se gli endpoint proprietà del Director sono leggibili. Sono esposti solo gli esiti, mai il link.

## 2.20.75 — 2026-09-13
- La diagnosi eventi Amazon si collega al flusso Director prima di inviare l'azione Composer reale `LUA_ACTION / GetLinkForAPIAuthentication` e attende fino a 15 secondi un eventuale link. La precedente prova inviava `LogInCommand`, quindi non verificava il comportamento dell'azione mostrata in Composer.
- La diagnostica continua a restituire solo presenza e struttura degli eventi, senza URL o token. Il login cliente resta disabilitato finché il test sul controller reale non conferma il flusso.

## 2.20.74 — 2026-09-13
- Aggiunta una diagnosi riservata degli eventi Amazon Music: apre il flusso `dataToUi` prima del comando Navigator e rileva se il link di associazione arriva come evento, senza esporre URL, token o dati account.
- Il canale è quello già usato da e-Face per gli aggiornamenti multimediali; il login cliente resta disabilitato finché l'esito reale non conferma il collegamento.

## 2.20.73 — 2026-09-13
- Aggiunta una diagnosi riservata dei comandi Navigator `GetSettings` per Amazon Music, Deezer e Qobuz, più `LogInCommand` Amazon con i soli segnaposto del driver. La risposta segnala soltanto esito, struttura e presenza di un link; non espone credenziali né URL.
- Nessun login cliente attivato: la compatibilità dei comandi PROTOCOL tramite Director REST va verificata sul driver reale.

## 2.20.72 — 2026-09-13
- La prova Amazon Music esegue una diagnosi completa in un clic: individua il link nella risposta del comando, nella scheda driver o nelle variabili e segnala se è cambiato dopo l'azione, senza esporre il valore.
- La diagnostica distingue inoltre le letture non disponibili dai campi leggibili ma privi del link.

## 2.20.71 — 2026-09-13
- Aggiunta in Admin Control4 la prova dell'azione Composer Amazon Music `LUA_ACTION / GetLinkForAPIAuthentication`, confermata sul driver reale. Mostra solo la struttura della risposta, senza esporre il collegamento temporaneo.
- Documentata la proprietà Composer `Authentication URL` come possibile fonte del link; la lettura via API Director resta da verificare prima di pubblicare il login cliente.

## 2.20.70 — 2026-09-13
- Aggiunta TIDAL alla verifica in sola lettura dell'associazione dei servizi musicali, seguendo il flusso esterno osservato nell'impianto e non il login password del driver Deezer.
- Registrato Qobuz come driver a credenziali distinto da TuneIn/Amazon/TIDAL; nessun login password viene ancora attivato.

## 2.20.69 — 2026-09-13
- La verifica di associazione TuneIn/Amazon legge anche la struttura interna del campo `result` quando il Director la restituisce come JSON o XML, senza mostrare valori o codici.

## 2.20.68 — 2026-09-13
- I portoni `cover.*` restano visibili anche in Sicurezza, nella sezione «Accessi e portoni», oltre che in Oscuranti; i comandi rimangono quelli cover.
- Aggiunto nell'admin Control4 un controllo mirato della configurazione di associazione TuneIn e Amazon Music. Mostra soltanto i nomi dei campi, mai valori, codici, token o password.
- Deezer resta escluso da questo controllo: il suo flusso usa credenziali e il driver ha esposto la password nei log durante il test.

## 2.20.67 — 2026-09-13
- I portoni configurati come `cover.*` vengono trattati come cover anche se e-HDL li classifica come serrature: compaiono in Oscuranti con comandi Apri, Stop e Chiudi.
- Corretto l'instradamento dei comandi dei portoni verso l'API cover e-HDL, evitando HTTP 400; i vecchi comandi lock/unlock restano compatibili durante l'aggiornamento.

## 2.20.66 — 2026-09-13
- La ricognizione ora cerca anche i driver musicali nell'inventario del Director, oltre alle sorgenti Ascolta, e mostra i nomi dei comandi e delle variabili pertinenti.
- Resta una diagnosi di sola lettura: nessun login, logout o valore di credenziale viene esposto.

## 2.20.65 — 2026-09-13
- Avviata la ricognizione di sola lettura dei driver musicali Control4: sorgenti Ascolta e nomi di variabili e comandi disponibili, senza valori di account o password.
- Aggiunto un link diagnostico monouso per analizzare quali servizi possono offrire uno stato di login affidabile.

## 2.20.64 — 2026-09-13
- Riconosciute le cover inviate dal Director come `application/octet-stream` quando i byte sono JPEG, PNG, GIF o WebP validi.
- Se una cover manca o fallisce, il riquadro mostra il logo della sorgente Control4 invece di restare vuoto.

## 2.20.63 — 2026-09-13
- Le cover Control4 che usano l'alias locale `http://director` vengono scaricate dall'IP del Director configurato in e-Face.
- Documentate le modalità di origine cover osservate e aggiunti test di compatibilità per l'alias locale.

## 2.20.62 — 2026-09-13
- Recuperate tutte le note di rilascio mancanti dalla 2.20.22 alla 2.20.61.
- Aggiunto un controllo automatico che richiede una voce changelog per la versione corrente.

## 2.20.61 — 2026-09-13
- Le cover Control4 possono provenire da qualsiasi CDN pubblico; gli indirizzi interni restano soggetti alle regole di sicurezza LAN.

## 2.20.60 — 2026-09-13
- Aggiunto il dominio Sonos Radio osservato per le cover, prima della regola generale della 2.20.61.

## 2.20.59 — 2026-09-13
- Mostrato il logo dell'apparato Control4 attivo accanto alla cover; supportato il nome Sonos esteso del controller.

## 2.20.58 — 2026-09-13
- Supportate le porte applicative alte dei server cover LAN; aggiunti porta e schema alla diagnosi e un link diagnostico monouso.

## 2.20.57 — 2026-09-13
- Consentite cover da apparati nella rete del Director e da altri IP privati autorizzati nell'admin.

## 2.20.56 — 2026-09-13
- Documentate le porte Control4 nell'admin; aggiunto il pulsante Diagnosi cover e il riuso del nuovo token dopo il test connessione.

## 2.20.55 — 2026-09-13
- Introdotta la diagnostica admin delle cover Control4 e la gestione dei redirect verso host consentiti.

## 2.20.54 — 2026-09-13
- Preparata l'assegnazione degli interni SIP personali; l'attivazione automatica su Asterisk resta da completare.

## 2.20.53 — 2026-09-13
- Memorizzata sul dispositivo la scelta tra connessione audio locale e remota.

## 2.20.52 — 2026-09-13
- Aggiunta la verifica delle credenziali DoorBird conservate nell'admin e-Face.

## 2.20.51 — 2026-09-13
- La postazione SIP e-Face usa la credenziale salvata nell'inventario admin.

## 2.20.50 — 2026-09-13
- Chiariti gli errori di lettura AMI e normalizzato l'input di verifica.

## 2.20.49 — 2026-09-13
- Mostrati la fase della diagnostica AMI e l'IP sorgente di e-Face.

## 2.20.48 — 2026-09-13
- Aggiunta una sonda AMI dedicata per la diagnostica Asterisk, senza alterare le chiamate.

## 2.20.47 — 2026-09-13
- Chiarito che le credenziali importate sono copie non verificate; aggiunta la loro rimozione sicura.

## 2.20.46 — 2026-09-13
- Creato l'inventario centralizzato delle credenziali con visualizzazione protetta nell'admin.

## 2.20.45 — 2026-09-13
- Aggiunto il controllo preliminare di sola lettura per l'installazione in campo.

## 2.20.44 — 2026-09-13
- Aggiunto il relay TURN separato per l'audio del citofono da remoto.

## 2.20.43 — 2026-09-13
- Aggiunti i controlli di guadagno per altoparlante e microfono nel browser.

## 2.20.42 — 2026-09-13
- Inviata l'offerta SIP locale dopo il primo candidato ICE utilizzabile.

## 2.20.41 — 2026-09-13
- Rimossa l'attesa STUN esterna dalla prova citofono in LAN.

## 2.20.40 — 2026-09-13
- Mostrati gli errori del microfono prima di avviare una chiamata.

## 2.20.39 — 2026-09-13
- Aggiunta la postazione SIP e-Face di prova e un ponte WebSocket autenticato verso Asterisk.

## 2.20.38 — 2026-09-13
- Aggiornate icona Android e favicon con un nuovo percorso dell'asset.

## 2.20.37 — 2026-09-13
- Aggiornato il logo della scheda add-on e-Face.

## 2.20.36 — 2026-09-13
- Riorganizzata la pagina Strumenti; aggiunti gestione utenti admin e nuovo branding dell'app.

## 2.20.35 — 2026-09-13
- Reindirizzato alla Home il vecchio URL di avvio dell'app Android.

## 2.20.34 — 2026-09-13
- Il logo nella pagina Strumenti torna alla Home.

## 2.20.33 — 2026-09-13
- Corretto l'URL di avvio della PWA Android.

## 2.20.32 — 2026-09-13
- Aggiunto il login admin opzionale per e-Face X4.

## 2.20.31 — 2026-09-13
- Evitata la creazione di una stanza Clima fittizia per dispositivi privi di stanza.

## 2.20.30 — 2026-09-13
- Aggiunto l'ordinamento delle sezioni Sicurezza e stabilizzate le schede scenario.

## 2.20.29 — 2026-09-13
- Allineate le icone delle serrature ai dispositivi e centrati i comandi.

## 2.20.28 — 2026-09-13
- Allineata la modalità allarme totale allo scenario Away e differenziati i colori per categoria.

## 2.20.27 — 2026-09-13
- Caricato lo sfondo di Strumenti prima della visualizzazione iniziale.

## 2.20.26 — 2026-09-13
- Aggiunto il riordino degli ambienti trascinando le schede e applicato il tema scelto.

## 2.20.25 — 2026-09-13
- Corretti i colori delle schede termostato in riscaldamento e raffrescamento.

## 2.20.24 — 2026-09-13
- Conservate le differenze di volume tra stanze Control4 e aggiunto il mute delle zone.

## 2.20.23 — 2026-09-13
- Ripristinate le schede senza bordi e le icone delle serrature sorgente.

## 2.20.22 — 2026-09-13
- Aggiunti l'ordine configurabile degli ambienti e il bagliore di stato delle schede.

## 2.20.20 — 2026-09-12

- Rimossa la scheda Comfort dalla barra dei contatori Home, lasciando la sezione Comfort principale invariata.
- Ridistribuite le quattro schede rimanenti su tutta la larghezza.

## 2.20.19 — 2026-09-12

- Centrato otticamente lo splash screen sui telefoni compensando il margine interno del PNG.

## 2.20.18 — 2026-09-12

- Usata l'immagine completa e-Face X4 by Ekonex come splash screen di avvio per 5 secondi.

## 2.20.17 — 2026-09-12

- Centralizzato nel backend il volume generale relativo delle sessioni Control4.
- Rimossa l'assegnazione ottimistica dello stesso volume a tutte le stanze.

## 2.20.16 — 2026-09-12

- Aggiunta schermata iniziale con logo e-Face X4 per 5 secondi e dissolvenza verso l'app.

## 2.20.15 — 2026-09-12

- Ricomposte le sessioni Wireless Music Bridge anche quando Control4 non fornisce una cover e il fingerprint artwork è assente.
- Separata l'identità del flusso audio dal fingerprint usato esclusivamente per le copertine.

## 2.20.14 — 2026-09-12

- Ricomposte le sessioni Control4 multi-stanza prive di queue tramite route audio e fingerprint del flusso.
- Evitata l'unione basata sul solo titolo: sorgente Control4 e contenuto devono coincidere.

## 2.20.13 — 2026-09-12

- Recuperato direttamente `QUEUE_STATUS_V2` dal Digital Media client Control4.
- Ignorati i valori queue vuoti per ricomporre correttamente le sessioni multi-stanza.

## 2.20.12 — 2026-09-12

- Mantenuto l'ultimo snapshot e-Voice valido durante i timeout transitori del proxy Supervisor.
- Evitato il falso avviso di indirizzo o autenticazione quando la richiesta successiva torna regolarmente online.

## 2.20.11 — 2026-09-12

- Mostrato il tasto Spegni sugli Echo che supportano STOP anche quando Alexa non dichiara TURN_OFF.
- Il tasto Spegni degli Echo arresta la riproduzione tramite `media_stop` sull'API locale e-Voice.

## 2.20.10 — 2026-09-12

- Aggiunto il comando Seleziona tutti nella scelta degli Echo per i messaggi TTS.

## 2.20.9 — 2026-09-12

- Evidenziati e animati anche gli Echo e-Voice quando sono in riproduzione o buffering.

## 2.20.8 — 2026-09-12

- Mostrato il comando Spegni sugli Echo che dichiarano il supporto `TURN_OFF`.
- Tradotto il comando UI `turn_off` nell'operazione locale e-Voice `power_off`.
- Ripristinata la regolazione relativa del volume generale Control4, mantenendo le differenze tra le stanze.

## 2.20.7 — 2026-09-12

- Abilitato il caricamento delle copertine degli Echo tramite l'endpoint artwork locale di e-Voice.
- Generato un fingerprint stabile da titolo, artista e album quando l'API locale non lo fornisce.

## 2.20.6 — 2026-09-12

- Salvato il volume originale di ogni Echo prima del messaggio TTS.
- Ripristinato automaticamente il volume 10 secondi dopo l'invio del messaggio.
- Protetto il volume originale anche in caso di più messaggi consecutivi.

## 2.20.5 — 2026-09-12

- Aggiunto il volume comune del messaggio nella sezione TTS.
- Impostato il volume su ogni Echo selezionato prima dell'invio del messaggio.
- Memorizzato localmente il volume TTS scelto per gli invii successivi.

## 2.20.4 — 2026-09-12

- Selezionato correttamente l'Echo cliccato entrando dalla pagina Ambiente.
- Reso TTS accessibile sull'Echo abilitato anche entrando dalla stanza, non soltanto dalla pagina Ascolta.

## 2.20.3 — 2026-09-12

- Esteso il pannello TTS e-Voice a tutta la larghezza della pagina.
- Allineati ogni Echo e il relativo comando DND nella stessa cella della griglia.
- Visualizzato il pannello esclusivamente sul player e-Voice per cui TTS è stato abilitato nell'Admin.
- Verificate lato server provider e capability TTS prima di salvare le preferenze.
- Rimossa l'esportazione residua del vecchio connettore diretto a Home Assistant.

## 2.20.2 — 2026-09-12

- Rimossa la validazione bloccante "Seleziona Media o TTS" dalla configurazione Player.
- Disattivato automaticamente Mostra quando Audio, Video e TTS sono tutti esclusi.
- Inclusa la casella TTS nella sincronizzazione automatica delle opzioni del player.

## 2.20.1 — 2026-09-12

- Limitati TTS e DND esclusivamente ai player provenienti da e-Voice.
- Nascosto il pannello messaggi quando il player selezionato appartiene a Control4.
- Bloccati lato server eventuali comandi TTS/DND indirizzati a Control4.

## 2.20.0 — 2026-09-12

- Integrata l'API Media locale di Ekonex Voice 0.1.8-beta.37 tramite il proxy autenticato di Home Assistant Supervisor.
- Collegati snapshot, comandi media, TTS, DND, artwork e stream SSE direttamente al componente e-Voice.
- Conservata l'API Media cloud come trasporto alternativo quando URL e ID impianto sono configurati.
- Nessun accesso diretto di e-Face al registro dei media player Home Assistant.

## 2.19.9 — 2026-09-12

- Rimosso il fallback silenzioso che esponeva come e-Voice i media player letti direttamente da Home Assistant.
- Il provider e-Voice usa ora esclusivamente l'API Media e-Voice configurata (`base_url`, `installation_id` e credenziale).
- Se l'API e-Voice non è configurata o raggiungibile, e-Face la dichiara non disponibile senza sostituirla con dati Hassio.

## 2.19.8 — 2026-09-12

- Esclusi gli Echo in pausa dalla sezione LIVE e dal conteggio sessioni.
- Considerati attivi per e-Voice soltanto gli stati playing e buffering.
- Mantenuti visibili nella stanza i player paused, idle e standby senza indicarli come in riproduzione.

## 2.19.7 — 2026-09-12

- Consolidati gli alias dello stesso Echo anche quando e-Voice assegna stanze tecniche differenti.
- Basata la deduplicazione e-Voice sul contenuto riprodotto anziché sul nome della stanza.
- Mantenute escluse dalla deduplicazione tutte le sessioni Control4.

## 2.19.6 — 2026-09-12

- Consolidate le entità duplicate dello stesso Echo in una sola sessione e-Voice.
- Usati stanza e contenuto riprodotto per riconoscere i duplicati logici.
- Mantenuta completamente separata la deduplicazione dalle sessioni Control4.

## 2.19.5 — 2026-09-12

- Ripristinate le stanze multimediali Control4 legittime.
- Conservate le nuove stanze assegnate manualmente ai dispositivi e-Voice.
- Rimossa la doppia applicazione delle preferenze che perdeva l'origine della stanza personalizzata.
- Ripristinati gli ambienti reali contenenti soltanto zone di sicurezza.
- Esclusi dagli Ambienti solo partizioni, scenari e contenitori tecnici dell'allarme.

## 2.19.4 — 2026-09-12

- Impedito ai media player e-Voice di creare card Ambiente autonome.
- Mostrati gli Echo soltanto all'interno delle stanze domotiche già esistenti.
- Esclusi gli stati Alexa idle e standby dal conteggio delle sessioni attive.

## 2.19.3 — 2026-09-12

- Separate rigorosamente le sessioni e-Voice dalle sessioni Control4.
- Filtrate per provider le stanze aggiungibili, i membri e i comandi di gruppo.
- Rifiutati dal backend tentativi di unire player appartenenti a provider diversi.

## 2.19.2 — 2026-09-12

- Usata la stanza e-Voice configurata prima di costruire le card Ambienti.
- Evitata la creazione di ambienti separati con il nome tecnico degli Echo.
- Usata come valore iniziale l'area Home Assistant reale, quando disponibile.

## 2.19.1 — 2026-09-12

- Caricati contemporaneamente Control4 ed e-Voice senza priorità esclusiva.
- Mantenuti separati comandi, artwork, gruppi e realtime dei due provider.
- Mostrati nell'Admin anche gli Echo e i media player esposti da e-Voice quando Control4 è configurato.

## 2.19.0 — 2026-09-12

- Aggiunta configurazione Admin dei dispositivi e-Voice ed Echo.
- Aggiunte rinomina e stanza locali, visibilità e abilitazioni Audio, Video e TTS.
- Aggiunto invio TTS verso uno o più Echo dalla pagina Ascolta.
- Aggiunto comando DND per i dispositivi che lo dichiarano nelle capacità e-Voice.
- Supportati gli Echo solo TTS senza esporli come normali player multimediali.

## 2.18.5 — 2026-09-12

- Eliminato il lampo teal e delle card provvisorie durante il refresh.
- L'interfaccia appare solo dopo l'applicazione di sfondo, palette e dati correnti.
- Mantenuta visibile la diagnostica quando il caricamento non riesce.

## 2.18.4 — 2026-09-12

- Estesa la palette delle card a popup PIN, sicurezza, RGB, sessioni, stanze e telecomando.
- Uniformati filtri, menu, campi e controlli interni alla palette selezionata.
- Applicata la palette anche alla pagina Strumenti fin dal caricamento.
- Conservati i colori semantici degli stati e dei dispositivi.

## 2.18.3 — 2026-09-12

- Allineate su smartphone le card Sicurezza e Comfort in due metà identiche.
- Uniformate le cinque card riepilogo e le righe degli ambienti.
- Regolarizzata la barra mobile in gruppi esatti da cinque icone, senza elementi tagliati.

## 2.18.2 — 2026-09-12

- Rimossa la dicitura ridondante `SESSIONE AUDIO/VIDEO` dalla finestra Gestione stanze.
- Ripulite le testate da etichette descrittive duplicate nelle finestre RGB e nelle pagine Strumenti.

## 2.18.1 — 2026-09-12

- La palette scelta viene applicata anche alle card riepilogo Sicurezza e Comfort della Home.
- Logo Strumenti ampliato e affiancato a un titolo più discreto.
- Rimossi i cerchi decorativi da tutte le frecce di navigazione.

## 2.18.0 — 2026-09-12

- Aggiunta in `Strumenti → Utente` la scelta persistente del colore delle card.
- Disponibili cinque palette curate: Grafite, Petrolio, Notte, Ardesia e Calda.
- Le tinte di allarme e di stato restano in evidenza indipendentemente dalla palette.

## 2.17.5 — 2026-09-12

- Le card Energia adottano un antracite freddo coerente con lo sfondo, lasciando i colori ai soli flussi.

## 2.17.4 — 2026-09-12

- Le card Energia aggiornano automaticamente valori, icone e direzioni ogni 2 secondi.
- L'aggiornamento si arresta quando si apre una dashboard o si lascia la pagina, senza lampeggiamenti.

## 2.17.3 — 2026-09-12

- Aggiunta la percentuale di carica accanto alla potenza istantanea della batteria.
- Lo stato rete a zero viene mostrato neutro, senza indicarlo come prelievo.

## 2.17.2 — 2026-09-12

- Le dashboard Energia mostrano un'icona dinamica per produzione FV, batteria, prelievo e immissione in rete.
- Disposte due dashboard per riga a tutta larghezza, con colori energetici coerenti.
- Rimossa la card introduttiva e affidato lo scorrimento alla pagina e-Face.
- Migliorata la connessione automatica a e-SunMind in modalità `host_network`.

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

# 2.14.0

- Card area ridotte a scudetto e nome; toccandole si apre il pannello Inserisci, Inserisci con ritardo o Disinserisci.
- Tastierino PIN Ksenia integrato nell'app, senza richiamare la tastiera del dispositivo.
- Sezioni Stato aree e Zone richiudibili con un tocco e senza contatore visibile.
- Lo scudetto del riepilogo segue lo stato: verde a riposo, giallo ritardato, rosso immediato o in allarme.

# 2.14.1

- Serrature chiuse/bloccate in verde e aperte/sbloccate in rosso, sia nell'icona sia nello stato testuale.
- Stati serratura sconosciuti mantenuti neutri per evitare falsi allarmi visivi.

# 2.14.2

- Eliminati definitivamente bordi, contorni focus e ombre residue dalle card Aree e Zone.

# 2.15.0

- Modalità grafica senza bordi estesa alle card di Home, Luci, Extra, Scenari, Cover, Comfort, Sicurezza, Audio e Video.
- Conservati colori e indicatori di stato, oltre ai bordi funzionali di input, slider e finestre di comando.

# 2.15.1

- Corretto il contenitore dei comandi area che comprimeva e sovrapponeva i pulsanti.
- Popup area ridisegnato con icona centrale più leggibile, azioni separate e layout responsive.
- Popup area e tastierino PIN ulteriormente semplificati: dimensioni ridotte, niente elementi decorativi e un solo comando di conferma.

# 2.15.2

- Rimossi dall'interfaccia tutti i riferimenti al marchio della centrale: titoli, nomi, avvisi ed errori usano ora termini generici di sicurezza.
- Le aree, le zone e gli scenari di allarme non generano più pseudo-stanze nell'elenco Ambiente e rimangono raccolti nella sezione Sicurezza.

# 2.15.3

- Corretto il riempimento verde/celeste dello slider nelle Sessioni quando il volume viene regolato a scatti cliccando sulla barra.
- Ogni tocco fuori dal cursore continua a modificare il volume di 2 punti e ora aggiorna immediatamente anche la parte colorata.

# 2.16.0

- Aggiunto nella barra riepilogativa della Home lo stato Sicurezza con scudetto dinamico e modalità corrente della centrale.
- Il nuovo riepilogo apre direttamente la sezione Sicurezza ed è adattivo su tablet e smartphone.
- Comfort rimane a sinistra e Sicurezza a destra sui display larghi; un tocco sullo sfondo vuoto di una sezione riporta alla Home.
- Anche il logo e-Face nell'intestazione riporta alla Home con tocco, Invio o barra spaziatrice.

# 2.16.1

- Un tocco sulla cover di una sessione LIVE o dell'elenco Sessioni apre direttamente il controllo media della stanza associata.

# 2.16.2

- Riepilogo Home riunito in un'unica barra continua: Sicurezza a sinistra e Comfort a destra, senza impilamento su tablet.

# 2.16.3

- Corretto il conflitto della griglia che disponeva Comfort sotto Sicurezza e limitava il riepilogo a metà larghezza.

# 2.16.4

- Centrato il separatore tra temperatura interna ed esterna con due colonne simmetriche e spaziature uniformi su desktop, tablet e smartphone.

# 2.16.5

- La modalità di sicurezza dispone ora di spazio prioritario e non viene abbreviata sui display larghi.
- Su smartphone il riepilogo mostra scudetto e modalità, compattando il conteggio delle aree.
- Rimossa l'etichetta ridondante `SICUREZZA` dal riepilogo Home.
- Scudetto rosso per inserimenti immediati o allarmi, giallo per inserimenti ritardati e verde a sistema disinserito.
- Lo scudetto Sicurezza del menu verticale usa esattamente lo stesso colore del riepilogo Home.

# 2.16.6

- Logo e-Face leggermente ingrandito e testata riallineata verticalmente tra marchio, nome casa, stato LIVE, orologio e comandi.

# 2.16.7

- Tutte le intestazioni Stanze dei controlli media, compresa `Stanze in riproduzione`, aprono e chiudono gli elementi successivi mantenendo lo stato durante gli aggiornamenti.
- Rimossa la freccia dal riepilogo Sicurezza per lasciare alla modalità tutto lo spazio necessario senza ritagli.

# 2.16.8

- Corretto il controllo HEAT/COOL/OFF: lo stato dei pulsanti segue modalità e stagione impostate, non la sola richiesta termica istantanea.
- Aggiunto l'aggiornamento immediato della card dopo i comandi clima, in attesa della conferma del dispositivo.

# 2.16.9

- Corretto il pulsante Stanze: lo stato aperto/chiuso ora forza il ridisegno immediato della sezione.

# 2.17.0

- Aggiunta la sezione Energia con autodiscovery dell'addon e-SunMind e proxy compatibile con Home Assistant Ingress.
- Il menu Energia apre un catalogo pulito delle plance/impianti configurati in e-SunMind; la dashboard scelta mantiene grafici, flussi, storico e configurazione originali.
- La struttura del catalogo supporta automaticamente ulteriori impianti e dashboard aggiunti in futuro a e-SunMind.
