# TASK — Accesso tecnico persistente a Control4 per lo sviluppo

Stato: **DA FARE**. Questo task non riguarda la sola cover: deve rendere ripetibile la diagnosi e lo sviluppo delle funzioni Control4 senza dipendere dalla sessione del PC installatore.

## Stato verificato il 13 settembre 2026

- Controller dell'impianto di prova: `192.168.3.10`.
- Le API Director usate da e-Face e `pyControl4` sono raggiunte via **HTTPS 443**. La **5021** è una porta di Composer Pro, non l'endpoint API da configurare in e-Face. La 5120 non risultava aperta nel test dal PC.
- Da questa sessione il controller risponde sulla 443 ma rifiuta le richieste senza token (`401`). Le credenziali e-Face sono nell'add-on, in `/data/control4.json`, non nel repository né automaticamente sul PC. Non dedurre da una porta aperta che l'accesso autenticato funzioni.
- `Strumenti → Amministrazione → Control4 → TEST CONNESSIONE` ottiene un nuovo token Director con le credenziali già salvate e lo riusa per le chiamate successive. La password può restare vuota nel modulo se è già configurata.
- `DIAGNOSI COVER` interroga il Director dall'add-on e verifica l'URL dell'immagine; il risultato è accessibile solo all'admin e non espone URL completi, token o password.
- Diagnosi reale della cover Radio RapTz in Ufficio Alex: host `192.168.3.36`, HTTP `415`, 0 byte. Il rifiuto nasce dalla allowlist e-Face, non dal token Director. Il fix consente host immagini privati nella stessa `/24` del Director e IP privati aggiuntivi autorizzati esplicitamente in Strumenti; resta da confermare la cover visibile dopo aggiornamento.
- Dopo la 2.20.57 il `415` persisteva. La prima diagnostica mostrava solo l'host e nascondeva la porta dell'URL: la 2.20.58 mostra schema e porta e ammette porte applicative alte (>=1024) per gli host LAN autorizzati. L'ipotesi della porta non è ancora confermata dalla diagnosi reale.
- La 2.20.58 introduce un link diagnostico **monouso di 10 minuti**, creato da admin e-Face, che restituisce soltanto lo stato delle cover. È un primo canale di lettura per il supporto, non un accesso generale al Director: il task di accesso tecnico completo resta aperto.

## Procedura provvisoria per una sessione di sviluppo

1. Verificare che l'add-on e-Face sia online e che l'account Control4 configurato sia valido. Non cambiare password, porte o impostazioni SIP solo per diagnosticare i media.
2. In e-Face aprire **Strumenti → Amministrazione → Control4** e premere **TEST CONNESSIONE**. Se fallisce, registrare solo tipo di errore, HTTP status e momento; non copiare token, cookie o password nei log o nelle chat.
3. Per una cover assente, avviare il brano e premere **DIAGNOSI COVER**. Confrontare: metadati immagine mancanti, host bloccato, errore HTTP/redirect, MIME non immagine, file troppo grande, oppure immagine valida ma errore frontend. Verificare anche la richiesta `/api/media/<registry_id>/artwork` nel browser. Correggere soltanto la causa osservata.
4. Annotare l'esito in questo task e aggiungere un test di regressione. Non dichiarare risolto il problema senza vedere la cover sul dispositivo reale.

## Accesso definitivo da realizzare

- Introdurre nell'admin e-Face una **sessione diagnostica temporanea, read-only e a privilegi minimi** che permetta allo sviluppatore autorizzato di interrogare stato e metadati Control4 attraverso l'add-on, senza ricevere le credenziali Control4 né un token Director riutilizzabile.
- Autorizzazione esplicita dell'admin impianto, durata breve, revoca immediata, limiti di frequenza, audit delle operazioni, risposta senza segreti e accesso limitato alle API necessarie. Niente proxy generico verso il Director o accesso Composer remoto.
- Mantenere separati i permessi di lettura diagnostica e le future operazioni di scrittura/comando. Ogni comando mutativo richiede una progettazione e un'approvazione specifiche.
- Documentare bootstrap, recupero dopo reinstallazione, scadenza/rotazione token e comportamento con controller offline. La procedura deve funzionare anche da remoto e su nuovi impianti, senza dipendere dal PC usato per lo sviluppo.

## Criteri di completamento

1. In una nuova sessione, con il consenso dell'admin, lo sviluppatore può ottenere una diagnosi Control4 senza farsi comunicare password o token Director.
2. L'accesso scade o viene revocato e non permette comandi, lettura di segreti o accesso arbitrario alla LAN.
3. Test automatici coprono autorizzazione, scadenza, revoca, assenza di segreti, limite richieste e regressioni media; test manuale conferma il funzionamento su e-Face installato.
4. La cover della sorgente di prova viene visualizzata sul dispositivo reale, oppure è documentato un limite comprovato della sorgente Control4.
