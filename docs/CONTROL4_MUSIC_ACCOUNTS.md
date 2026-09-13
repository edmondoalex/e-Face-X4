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

### Amazon Music: azione e proprietà Composer osservate

La schermata Composer dell'impianto mostra sul driver Amazon Music l'azione **Get Link For Authentication** e la proprietà **Authentication URL**. Questo fornisce una pista concreta: generare il collegamento tramite l'azione del driver e leggere la proprietà aggiornata, senza chiedere credenziali Amazon a e-Face. L'URL mostrato è temporaneo e sensibile: non copiarlo in log, diagnosi, repository o documentazione. La schermata non prova ancora che l'azione Composer e la proprietà siano accessibili tramite l'API REST del Director usata da e-Face; i normali comandi `/api/v1/items/{id}/commands` non le elencano.

Nel driver Amazon la proprietà **Debug Mode** risulta attiva. Verificare separatamente l'effetto della disattivazione e non supporre che lo stesso interruttore esista o protegga il driver Deezer, la cui traccia ha esposto una password. Solo dopo una prova end-to-end aggiungere il pulsante cliente in e-Face. Le somiglianze osservate con TuneIn e TIDAL non autorizzano a riutilizzare il comando Amazon senza prove per quei driver.

La traccia Lua del 2026-09-13 ha confermato `ExecuteCommand: LUA_ACTION` con `ACTION=GetLinkForAPIAuthentication`. In e-Face 2.20.72 una prova admin invia tale comando al driver e verifica in un solo passaggio, senza restituire URL, se un link `link.ctrl4.co` compare nella risposta REST, nella scheda del driver o nelle variabili e se cambia dopo l'azione. Il primo test REST ha restituito i campi `name`, `result`, `seq` con `result` testuale, ma il valore è stato intenzionalmente oscurato: non prova ancora se il link sia direttamente nella risposta. La nuova prova scioglie questo dubbio senza esporre il collegamento.

Esito reale della prova 2.20.72: il comando REST viene accettato, ma il link non compare né nella risposta, né nella scheda item, né nelle variabili; le ultime due letture sono riuscite. La proprietà `Authentication URL` visibile in Composer non è quindi disponibile tramite queste tre superfici REST. Non aggiungere altri pulsanti cliente basati su queste API: occorre verificare un'interfaccia di lettura proprietà/risposta Navigator supportata dal driver o dal produttore. Un ipotetico driver ponte non è soluzione confermata finché non è dimostrato che possa leggere la proprietà di un altro driver in modo autorizzato.

## Analisi del pacchetto TuneIn.c4z fornito (2026-09-13)

Il pacchetto fornito contiene `driver.xml` e `driver.lua`; il manifest dichiara versione **131**, modificata il 2022-10-06. Non è stato eseguito. L'installatore ha chiarito che è il **driver legacy OS2**, non il driver TuneIn attivo. La sua procedura non va usata come base per implementare il TuneIn attuale in e-Face.

Questo driver **non contiene** l'azione Amazon `GetLinkForAPIAuthentication`, né una proprietà `Authentication URL`, né riferimenti a `link.ctrl4.co`. Il suo percorso utente passa dal menu Navigator **Settings**: `GetBrowseSettingsMenu` richiede una pagina TuneIn e, quando riceve `Register.aspx`, estrae un codice di registrazione dalla risposta e lo presenta all'utente. Il codice viene quindi associato sul sito TuneIn; non richiede che e-Face gestisca la password TuneIn. Il pacchetto definisce anche una proprietà `Status`, aggiornata dall'azione `UpdateStatus`, ma la visibilità di tale proprietà tramite Director REST non è dimostrata.

Le azioni Composer `Join`/`Drop` operano diversamente: `Join` usa Username e Password del driver e invia la password come parametro di un URL verso TuneIn. **Non usare questo percorso per il self-service e-Face** e non raccogliere password TuneIn nell'admin e-Face. Per un'integrazione sicura occorre verificare se il menu Settings e la risposta del codice siano raggiungibili tramite l'interfaccia Control4 che e-Face può usare, oppure ottenere un'interfaccia supportata del produttore. Non assimilare questo pacchetto al flusso Amazon/TIDAL solo sulla base di schermate visivamente simili.

## Analisi pacchetti Amazon, Deezer e Qobuz (2026-09-13)

Sono stati letti, senza eseguirli, i tre `.c4z` forniti. I manifest dichiarano Amazon Music v70, Deezer v148 e Qobuz v23; lo screenshot Composer di Amazon mostra invece Driver Version 79. Quindi almeno il pacchetto Amazon non coincide con il driver attivo e i dettagli vanno verificati sul sistema reale prima dell'implementazione.

I tre pacchetti contengono Lua cifrato (`lua/squished.lua.encrypted`): il comportamento interno non è direttamente ispezionabile. I manifest XML e la documentazione inclusa confermano però che Amazon ha l'azione `GetLinkForAPIAuthentication`, la proprietà `Authentication URL` e uno schermo Navigator `GetSettings`/`LogInCommand` con parametri `username` e `password` fissi come segnaposto. Il link di login è visibile anche nella UI media-service Control4 secondo la documentazione del pacchetto. Deezer e Qobuz espongono invece l'azione `Login` con parametri reali `username`/`password` e, nel Navigator, campi credenziali e `LogInCommand`. Tutti e tre hanno `GetSettings` come comando **PROTOCOL** per lo stato account, ma il manifest non dimostra che sia invocabile via REST Director né che il suo risultato possa essere letto da e-Face.

La documentazione Deezer del pacchetto conferma che un account a pagamento è richiesto. Il file XML indica `Debug Mode` per tutti e tre, con default `Off`; questo non prova che disattivarlo impedisca il logging in chiaro della password, già osservato nel driver Deezer attivo. Nessun form credenziali cliente va esposto finché tale rischio non è risolto.

## Criteri di completamento

1. Il cliente rinnova un account scaduto usando solo e-Face e il provider, senza UI Control4; la stessa sorgente riproduce poi musica.
2. Test separato per TuneIn, TIDAL, Deezer, Qobuz e gli altri servizi presenti; differenze dei driver documentate.
3. «Free», logout e guasto di rete restano distinti; Spotify Connect e ShairBridge non hanno un login e-Face generico.
4. Nessuna password/token del provider nei file e-Face, nelle API diagnostiche, nei log o nel repository.
5. Una sorgente senza stato esposto rimane `unknown` e non genera falsi avvisi.

Fonti Control4: [gestione dei servizi da Listen](https://docs.control4.com/help/c4/user/userguide/content/topics/entertainment/basics-listen.htm) e [accesso tramite Navigator](https://docs.control4.com/help/c4/software/cpro/dealer-composer-help/content/composerpro_userguide/adding_a_media_service.htm). Queste descrivono il flusso Control4 esistente, non attestano che il flusso self-service e-Face sia già disponibile.
