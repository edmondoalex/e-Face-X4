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
- Obiettivo: ripristinare la risposta rapida dei comandi Control4, soprattutto al primo utilizzo dopo aggiornamento o riavvio dell'add-on.
- Risultato: misurata autenticazione iniziale Director di circa 2,76 s contro letture successive di 12–15 ms; la sessione locale Control4 viene ora autenticata e verificata durante l'avvio, prima che l'interfaccia accetti comandi.
- File modificati: `e_face_x4/app/main.py`, file di versione e test del componente, `e_face_x4/CHANGELOG.md`, `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: sonda read-only Director; `node --check app/static/assets/app.js`; `python -m pytest tests/test_app.py -q` (131 test superati); controllo integrità diff.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: nessuno; nessuna modifica trasversale proposta o implementata.
- Compatibilità: nessuna modifica ad API, contratti condivisi o dati persistenti; viene anticipata all'avvio un'autenticazione Control4 già necessaria al primo comando.
- Dipendenze da altri componenti: nessuna nuova dipendenza; richiede il Director Control4 già configurato per il componente.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: prova percettiva sul dispositivo fisico dopo il rilascio; nessuna proposta CHANGE necessaria.
