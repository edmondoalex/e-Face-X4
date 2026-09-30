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
- Obiettivo: completare la sincronizzazione generale degli indicatori fra interfacce e rinominare localmente il connettore multi-bus in `e-Control HUB`.
- Risultato: oltre al fan-out realtime centrale, ogni client riconcilia snapshot completo e scenari a connessione, riconnessione e ritorno in primo piano; gli scenari vengono caricati anche senza aprire la pagina. Tutte le diciture visibili locali usano `e-Control HUB`, mantenendo invariati slug, provider ID ed endpoint.
- File modificati: codice UI/backend e connettore del componente, traduzione e documentazione utente locale, file di versione e test, `e_face_x4/CHANGELOG.md`, `EKONEX_PLATFORM_SYNC.md`.
- Test eseguiti: `node --check app/static/assets/app.js`; suite completa `tests/test_app.py`; regressioni dedicate al fan-out, alla riconciliazione generale e al nuovo nome; controllo integrità diff.
- Contratti/versioni usati: Platform governance 1.0; API compatibility policy 1.0; Identity draft-1; Event draft-1; Licensing draft-1.
- Change ID: nessuno; nessuna modifica trasversale proposta o implementata.
- Compatibilità: invariati formato eventi, API, slug `e_hdl_buspro_mqtt`, provider ID `buspro` e dati persistenti; nessuna modifica a contratti condivisi.
- Dipendenze da altri componenti: nessuna nuova dipendenza; usa il WebSocket e-HDL già esistente.
- Attività richieste agli altri Codex: nessuna.
- Rischi o decisioni ancora aperte: il rebranding tecnico del componente e-Control HUB resta trasversale e richiederebbe una proposta CHANGE; qui è stato applicato solo il nome visibile locale. Resta la prova contemporanea su almeno due interfacce fisiche.
