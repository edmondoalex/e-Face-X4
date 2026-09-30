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
- Obiettivo: arrestare le animazioni LIVE quando audio/video è in pausa e mantenere sincronizzato lo stato dell'icona Energia senza aprire la relativa pagina.
- Risultato: stato grafico LIVE collegato allo stato reale del player; aggiunto aggiornamento autonomo e leggero dell'indicatore Energia ogni dieci secondi e al ritorno in primo piano.
- File modificati: `e_face_x4/app/static/assets/app.js`, `e_face_x4/app/static/assets/home-live-media.css`, file di versione e test del componente, `e_face_x4/CHANGELOG.md`, `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; `python -m pytest tests/test_app.py -q` (130 test superati); controllo integrità diff.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: nessuno; nessuna modifica trasversale proposta o implementata.
- Compatibilità: nessuna modifica ad API, contratti condivisi o dati persistenti; comportamento compatibile con gli stati player esistenti e l'API Energia già consumata da e-Face.
- Dipendenze da altri componenti: nessuna nuova dipendenza; e-Face continua a leggere l'endpoint Energia esistente.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: verifica visiva su player fisico in pausa e osservazione dell'indicatore Energia per almeno un cambio di flusso; nessuna proposta CHANGE necessaria.
