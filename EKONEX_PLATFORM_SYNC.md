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
- Obiettivo: mantenere sincronizzati in tempo reale gli stati e-HDL su tutte le interfacce e-Face aperte.
- Risultato: rimossa la connessione e-HDL indipendente per ogni browser; la connessione centrale già dotata di riconnessione distribuisce ora in fan-out gli eventi sanitizzati di luci, cover, sensori e scenari a tutti i client e notifica anche i cambi d'inventario.
- File modificati: `e_face_x4/app/main.py`, file di versione e test del componente, `e_face_x4/CHANGELOG.md`, `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; `python -m pytest tests/test_app.py -q` (133 test superati); regressione dedicata al fan-out centrale; controllo integrità diff.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: nessuno; nessuna modifica trasversale proposta o implementata.
- Compatibilità: invariati formato degli eventi e API browser; nessuna modifica a contratti condivisi o dati persistenti.
- Dipendenze da altri componenti: nessuna nuova dipendenza; usa il WebSocket e-HDL già esistente.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: prova contemporanea su almeno due interfacce fisiche dopo il rilascio; nessuna proposta CHANGE necessaria.
