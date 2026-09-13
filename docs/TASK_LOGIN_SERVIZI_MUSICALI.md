# TASK — Login dei servizi musicali senza app Control4

## Risultato confermato: Amazon Music

Il 2026-09-13, con e-Face 2.20.76, il pulsante **Ascolta → Sorgenti e servizi → Ricollega Amazon Music** ha aperto il link temporaneo generato dal controller. Dopo l'autenticazione del provider, la pagina callback Control4 ha mostrato **Success!**, come nell'app Control4. Questo prova il completamento del passaggio browser; non prova ancora che il driver risulti collegato o che la musica parta.

Procedura tecnica da conservare per le nuove installazioni e per gli altri driver che supportano questo flusso:

1. Con il token Director dell'impianto, aprire il WebSocket `dataToUi` e sottoscrivere il driver media-service e il suo eventuale ID protocollo.
2. Solo dopo la sottoscrizione, inviare `LUA_ACTION` con `ACTION=GetLinkForAPIAuthentication` all'ID del driver Amazon Music. Non sostituirlo con `LogInCommand`, `GET_AUTH_URL` o `LOGIN` senza una prova sul driver reale.
3. Attendere l'evento contenente `https://link.ctrl4.co/...`, verificare schema e host, e consegnare il link solo alla sessione e-Face che lo ha richiesto.
4. Non salvare o registrare URL, codice callback, token o password; usare `Cache-Control: no-store`.

La pista di ascoltare gli eventi prima del comando è stata suggerita da **Gemini**: grazie per la dritta, confermata dal test reale.

## Da completare tassativamente

- [ ] Verificare nel Director che Amazon Music risulti collegato dopo la callback `Success!`.
- [ ] Avviare una traccia Amazon Music da e-Face e confermare la riproduzione; solo allora segnare il flusso Amazon come completato end-to-end.
- [ ] Mostrare in e-Face lo stato account effettivo e un messaggio di conferma/errore dopo il ritorno dal browser, senza dedurlo dalla sola callback.
- [ ] Verificare driver per driver TuneIn, TIDAL, Deezer, Qobuz e Apple Music: azione di login, evento/link o campi credenziali, logout, errori e riproduzione. Non applicare automaticamente la soluzione Amazon agli altri.
- [ ] Mantenere Spotify Connect e ShairBridge fuori da un login generico; preservare il requisito che i clienti usino e-Face senza accesso all'app Control4.
