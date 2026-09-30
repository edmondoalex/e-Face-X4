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
- Obiettivo: eliminare il ritardo residuo di 1–2 secondi sui comandi Play/Pausa/Stop Control4.
- Risultato: individuati fino a due snapshot Control4 completi eseguiti prima del comando per distinguere sorgenti Sky Q e WiiM; la UI ora trasmette l'ID della sorgente attiva già nota e il backend instrada immediatamente il comando, conservando lo snapshot come fallback per client precedenti.
- File modificati: `e_face_x4/app/main.py`, `e_face_x4/app/static/assets/app.js`, file di versione e test del componente, `e_face_x4/CHANGELOG.md`, `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; `python -m pytest tests/test_app.py -q` (132 test superati); regressione dedicata che vieta lo snapshot nel percorso rapido; controllo integrità diff.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: nessuno; nessuna modifica trasversale proposta o implementata.
- Compatibilità: campo locale opzionale `active_source_id` nella richiesta interna UI/backend; client precedenti continuano a usare il controllo completo. Nessuna modifica a contratti condivisi o dati persistenti.
- Dipendenze da altri componenti: nessuna nuova dipendenza; routing locale verso Director, Sky Q e WiiM invariato.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: prova percettiva sul dispositivo fisico dopo il rilascio; nessuna proposta CHANGE necessaria.
