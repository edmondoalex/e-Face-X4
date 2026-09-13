# Account dei servizi musicali Control4 - requisito cliente

Il cliente usa solo e-Face: deve poter ricollegare i servizi musicali da e-Face, senza accedere a Control4 Navigator o Composer. La sessione finale deve essere quella usata dal driver Control4, verificata con una riproduzione reale. La UI Control4 resta solo uno strumento di assistenza dell'installatore, non un passaggio del flusso cliente.

Servizi con account da verificare: TuneIn, TIDAL, Deezer, Qobuz, Amazon Music, Apple Music e SoundMachine, secondo quelli effettivamente presenti nell'impianto. Spotify Connect e ShairBridge non rientrano nel flusso di login interno e-Face: l'associazione avviene nell'app del servizio o tramite protocollo di cast. Non mostrare loro il pulsante generico «Ricollega account».

## Fase 1 - ricognizione di sola lettura (2.20.65-2.20.66)

Nell'admin Control4, «Ricognizione servizi musicali» legge le sorgenti Ascolta e i soli nomi di variabili, comandi e campi esposti dai driver. Non trasmette valori, password o token e non esegue login/logout. Lo stato account resta `unknown` finché non è verificato su dati reali. Un link monouso di 10 minuti consente di condividere con il supporto questo inventario redatto. Nessun pulsante cliente di riconnessione va pubblicato sulla sola base di questa ricognizione.

## Fase 2 - stato verificato per driver

Per ciascun driver identificare il segnale affidabile di account collegato, sessione scaduta e servizio irraggiungibile. «Free» è il livello di abbonamento, non un errore di autenticazione. Gli stati e-Face saranno `connected`, `reauth_required`, `service_unavailable`, `unknown`; in assenza di un segnale affidabile rimane `unknown`.

## Fase 3 - riconnessione interamente in e-Face

Per ogni servizio verificare un flusso supportato dal driver: avvio dell'autorizzazione da e-Face, eventuale OAuth/device-code/link esterno del provider, ritorno a e-Face, aggiornamento della sessione Control4 e test della riproduzione. Non salvare password dei provider nel vault e-Face. Un eventuale comando «Join»/«Login» va eseguito soltanto dopo averne verificato semantica e sicurezza sul driver reale.

Se un driver non espone un flusso integrabile, segnare esplicitamente il servizio come **non ancora supportato per il self-service** e valutare un'integrazione diversa. Non sostituire il requisito con istruzioni per aprire Navigator e non mostrare un successo fittizio.

## Criteri di completamento

1. Il cliente rinnova un account scaduto usando solo e-Face e il provider, senza UI Control4; la stessa sorgente riproduce poi musica.
2. Test separato per TuneIn, TIDAL, Deezer, Qobuz e gli altri servizi presenti; differenze dei driver documentate.
3. «Free», logout e guasto di rete restano distinti; Spotify Connect e ShairBridge non hanno un login e-Face generico.
4. Nessuna password/token del provider nei file e-Face, nelle API diagnostiche, nei log o nel repository.
5. Una sorgente senza stato esposto rimane `unknown` e non genera falsi avvisi.

Fonti Control4: [gestione dei servizi da Listen](https://docs.control4.com/help/c4/user/userguide/content/topics/entertainment/basics-listen.htm) e [accesso tramite Navigator](https://docs.control4.com/help/c4/software/cpro/dealer-composer-help/content/composerpro_userguide/adding_a_media_service.htm). Queste descrivono il flusso Control4 esistente, non attestano che il flusso self-service e-Face sia già disponibile.
