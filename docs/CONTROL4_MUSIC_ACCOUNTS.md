# Account dei servizi musicali Control4 - requisito cliente

Il cliente usa solo e-Face: deve poter ricollegare i servizi musicali da e-Face, senza accedere a Control4 Navigator o Composer. La sessione finale deve essere quella usata dal driver Control4, verificata con una riproduzione reale. La UI Control4 resta solo uno strumento di assistenza dell'installatore, non un passaggio del flusso cliente.

Servizi con account da verificare: TuneIn, TIDAL, Deezer, Qobuz, Amazon Music, Apple Music e SoundMachine, secondo quelli effettivamente presenti nell'impianto. Spotify Connect e ShairBridge non rientrano nel flusso di login interno e-Face: l'associazione avviene nell'app del servizio o tramite protocollo di cast. Non mostrare loro il pulsante generico «Ricollega account».

## Fase 1 - ricognizione di sola lettura (2.20.65-2.20.66)

Nell'admin Control4, «Ricognizione servizi musicali» legge le sorgenti Ascolta e i soli nomi di variabili, comandi e campi esposti dai driver. Non trasmette valori, password o token e non esegue login/logout. Lo stato account resta `unknown` finché non è verificato su dati reali. Un link monouso di 10 minuti consente di condividere con il supporto questo inventario redatto. Nessun pulsante cliente di riconnessione va pubblicato sulla sola base di questa ricognizione.

## Fase 2 - stato verificato per driver

Ricognizione reale del 2026-09-13: i driver TuneIn 614, Deezer 1641, Amazon Music 1643, Apple Music 1645, Qobuz 1647, TIDAL 1649 e SoundMachine 1651 hanno proxy `media_service`. Gli ID successivi sono le sorgenti Ascolta, non un secondo account. TuneIn 589 e Deezer 599 sono ingressi `media_player` di un ricevitore. Nei metadati accessibili via Director `/api/v1/items/{id}/variables` e `/commands` non emergono variabili di stato account né comandi di accesso: solo Play Item, SelectAlbum, SelectPlaylist o StartFlow. Questa osservazione non dimostra che il driver non abbia una procedura interna: dimostra che **l'API Director attualmente usata da e-Face non espone un flusso di login utilizzabile**.

La documentazione ufficiale Control4 colloca l'accesso ai servizi nel Navigator e, per TuneIn, documenta anche proprietà/azioni in Composer. Le azioni Composer non sono automaticamente comandi dell'API Director. Il flusso OAuth2 del portale Control4 autorizza l'accesso al controller, non ai singoli provider musicali. Non usare nessuno dei due come scorciatoia non verificata.

Per ciascun driver identificare il segnale affidabile di account collegato, sessione scaduta e servizio irraggiungibile. «Free» è il livello di abbonamento, non un errore di autenticazione. Gli stati e-Face saranno `connected`, `reauth_required`, `service_unavailable`, `unknown`; in assenza di un segnale affidabile rimane `unknown`.

## Fase 3 - riconnessione interamente in e-Face

Per ogni servizio verificare un flusso supportato dal driver: avvio dell'autorizzazione da e-Face, eventuale OAuth/device-code/link esterno del provider, ritorno a e-Face, aggiornamento della sessione Control4 e test della riproduzione. Non salvare password dei provider nel vault e-Face. Un eventuale comando «Join»/«Login» va eseguito soltanto dopo averne verificato semantica e sicurezza sul driver reale.

Se un driver non espone un flusso integrabile, segnare esplicitamente il servizio come **non ancora supportato per il self-service** e valutare un'integrazione diversa. Non sostituire il requisito con istruzioni per aprire Navigator e non mostrare un successo fittizio.

Prossima verifica tecnica: ottenere documentazione o collaborazione del produttore del driver su un'interfaccia supportata di autorizzazione/riassociazione, partendo da TuneIn, e provarla su un account di test prima di creare la UI cliente. Se non esiste, la soluzione richiede un'integrazione media diversa che mantenga la riproduzione sui dispositivi desiderati; non basta duplicare le credenziali in e-Face.

## Traccia Deezer reale (2026-09-13)

Il driver Deezer usa l'azione Composer `LUA_ACTION` con `ACTION=Login` e parametri `username`/`password`. Il Navigator usa invece il proxy 5001 con `SettingChanged` per i due campi e poi `LogInCommand`; dopo il tentativo fallito è stato osservato `ConfirmAuthenticationRequired`. L'account Free usato nel test non è idoneo: Control4 richiede Premium o superiore per Deezer. Questo errore non permette quindi di validare un login riuscito.

Questa traccia riguarda **solo Deezer**. TuneIn usa un meccanismo di associazione distinto, documentato come Join/Drop/Update Status; non riutilizzare `LUA_ACTION Login` né imporre un form email/password universale. L'interfaccia e-Face potrà avere una sezione account comune, ma l'implementazione dovrà essere un adattatore specifico per ogni servizio e driver.

La guida Control4 TuneIn Quick Setup descrive anche un flusso tramite **codice di registrazione**: il Navigator mostra il codice e l'utente lo inserisce nel proprio account TuneIn sotto My Info > Devices > Add Reg. Code. La guida è storica (OS 2.4, 2013), perciò la presenza di quel flusso nel driver installato va verificata prima di implementarlo. Se ancora disponibile, e-Face potrebbe mostrare il codice senza trattare la password TuneIn; questo è il candidato preferibile per il self-service. Fonte: https://docs.control4.com/docs/product/tunein/quick-setup/latest

Osservazione dell'impianto: **Amazon Music si comporta come TuneIn** nella fase di associazione, diversamente dal form credenziali del driver Deezer. Trattarlo come candidato a flusso esterno/codice, ma non assumere che il formato del codice, l'URL o le azioni del driver siano uguali a TuneIn senza una traccia specifica Amazon. La documentazione Control4 conferma Amazon Music come servizio nativo ma non descrive qui il protocollo di associazione: https://docs.control4.com/docs/product/control4-software/dealer-release-notes/english/revision/Z

Osservazione dell'impianto: anche **TIDAL** si comporta come TuneIn durante l'associazione. Includerlo nella ricognizione di tipo esterno/codice, senza assumere che URL, token e azioni del suo driver siano intercambiabili con TuneIn o Amazon.

Schermate reali del 2026-09-13: Amazon Music, TIDAL e TuneIn mostrano nel Navigator «Account Status: Logged Out» e, premendo «Accedi», un collegamento temporaneo sotto `https://link.ctrl4.co/…`. Il log Amazon registra `LogInCommand` sul proxy Navigator 5001 con i segnaposto `username` e `password`, non la password dell'account Amazon. Il collegamento può essere trattato come credenziale temporanea: non inserirlo nei log, nei ticket o nel repository e non riutilizzare quello già condiviso in uno screenshot. Per il self-service e-Face deve avviare la stessa procedura per il servizio selezionato, ottenere il collegamento dal driver, mostrarlo solo all'utente autenticato e verificare l'avvenuta associazione; `GET_SETUP` tramite REST non ha esposto questi dati nei test TuneIn/Amazon. L'uso dei comandi Navigator attraverso l'API Director REST è ancora da verificare, non va dato per supportato.

Osservazione dell'impianto: **Qobuz** si comporta come Deezer nella fase di login con credenziali. Non includerlo nel flusso a codice. Prima di esporre un form e-Face, verificare separatamente il comando del driver Qobuz, i requisiti dell'abbonamento e soprattutto se il suo logging può contenere la password, come osservato per Deezer.

**Blocco di sicurezza:** la traccia Lua del driver registra in chiaro i parametri dell'azione e anche il valore del campo password inserito nel Navigator. La password presente nella traccia condivisa va ruotata e non deve essere copiata nel repository, nei test, nei ticket o nei log e-Face. Non abilitare il login cliente tramite `LUA_ACTION` finché non è verificato che il logging del driver sia disattivabile o che esista un flusso di autorizzazione alternativo che non scrive la password in chiaro. La forma dell'azione vista in Composer non dimostra ancora che `LUA_ACTION` sia accettata dall'endpoint REST del Director per il driver Deezer.

## Criteri di completamento

1. Il cliente rinnova un account scaduto usando solo e-Face e il provider, senza UI Control4; la stessa sorgente riproduce poi musica.
2. Test separato per TuneIn, TIDAL, Deezer, Qobuz e gli altri servizi presenti; differenze dei driver documentate.
3. «Free», logout e guasto di rete restano distinti; Spotify Connect e ShairBridge non hanno un login e-Face generico.
4. Nessuna password/token del provider nei file e-Face, nelle API diagnostiche, nei log o nel repository.
5. Una sorgente senza stato esposto rimane `unknown` e non genera falsi avvisi.

Fonti Control4: [gestione dei servizi da Listen](https://docs.control4.com/help/c4/user/userguide/content/topics/entertainment/basics-listen.htm) e [accesso tramite Navigator](https://docs.control4.com/help/c4/software/cpro/dealer-composer-help/content/composerpro_userguide/adding_a_media_service.htm). Queste descrivono il flusso Control4 esistente, non attestano che il flusso self-service e-Face sia già disponibile.
