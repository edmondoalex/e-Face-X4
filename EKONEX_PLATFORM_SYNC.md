# Collegamento Ekonex Platform

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
