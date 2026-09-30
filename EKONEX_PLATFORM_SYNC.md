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
- Risultato: il catalogo Home Assistant usa una lettura WebSocket condivisa con cache e single-flight; il widget Agenda e le notifiche Alexa hanno limiti di frequenza, cache e backoff esponenziale; le richieste Supervisor non autorizzate a `/addons` sono state rimosse; la riconnessione realtime browser usa backoff con jitter. Il commit `31f95f2` è stato pubblicato e la candidata `2.21.283` installata: Supervisor la riporta `started`, aggiornata e senza errori pertinenti nei log recenti.
- File modificati: backend e connettore Supervisor del componente, client web, file di versione, changelog, test e `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; `python -m compileall -q app`; suite completa `373 passed`; test mirati per assenza `/addons`, cache/single-flight, frequenza Agenda e backoff; `git diff --check`.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: `CHANGE-2026-008`; nessun contratto condiviso modificato.
- Compatibilità: invariati API pubbliche, formato eventi, slug, provider ID e dati persistenti.
- Dipendenze da altri componenti: nessuna nuova dipendenza; restano usati solo gli endpoint Home Assistant/Supervisor già ammessi.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: il primo campionamento post-installazione ha mostrato CPU variabile circa 18–33%, quindi il criterio sotto il 10% non è ancora soddisfatto e richiede una diagnosi separata dell'attività residua. Nessun loop recente `/addons` o Alexa `Bad Request` è stato rilevato.
