# TASK OBBLIGATORIO — Installazione e-Face X4 plug-and-play

Stato: **DA FARE — requisito tassativo prima della distribuzione in campo**.

Incremento 2.20.54: e-Face può assegnare a un account un interno personale 8302–8399 con password SIP casuale, distinta dal login e dall'8301 admin. La configurazione Asterisk è generata nell'admin solo dopo una nuova verifica della password admin. L'interno resta **in attesa** finché non viene applicato e confermato in Asterisk; non è una sincronizzazione automatica. Non aggiungere ancora questi interni al gruppo 8290 né dichiarare l'intercomunicazione utente-utente pronta: serve un provisioning persistente sicuro, poi test di registrazione, squillo e audio. L'8301 e il dialplan funzionante non vengono modificati da questa versione.

Primo incremento (e-Face 2.20.45): pannello admin **Preparazione impianto** con controlli di sola lettura per Asterisk, DoorBird e raggiungibilità UDP del server TURN. Non configura Asterisk, non attiva un impianto sulla VPS e non sostituisce la prova audio reale. Il task resta aperto finché tutti i criteri sotto sono soddisfatti.

Secondo incremento (e-Face 2.20.46): inventario unico **Credenziali impianto** nell'admin, con visualizzazione temporanea dopo nuova autenticazione e importazione delle credenziali SIP/DoorBird come copie esplicitamente non sincronizzate. Vedi [CREDENZIALI_IMPIANTO_2026-09-13.md](CREDENZIALI_IMPIANTO_2026-09-13.md). Il task resta aperto: il provisioning e il vault per-impianto non sono ancora implementati.

## Sincronizzazione credenziali: sequenza obbligatoria

Le copie importate nell'inventario non sono una sorgente verificata e **non devono essere applicate automaticamente**. Il primo target è l'interno SIP e-Face 8301; DoorBird e Control4 restano invariati durante questa migrazione.

1. Introdurre un connettore locale per Asterisk che operi **dentro l'add-on Asterisk** e accetti soltanto operazioni allowlist sugli interni gestiti da e-Face. Non montare `all_addon_configs:rw` in e-Face: darebbe accesso in scrittura alle configurazioni e ai segreti di tutti gli add-on.
2. Leggere lo stato effettivo dell'auth 8301 da Asterisk, confrontarlo senza esporre la password e marcare la copia in e-Face come verificata solo dopo una prova di autenticazione riuscita. Non interpretare il solo nome utente come prova.
3. Generare una nuova credenziale per l'impianto e conservarla nel vault e-Face con accesso ristretto. Preparare il browser SIP a utilizzare la credenziale distribuita da e-Face solo per l'utente autorizzato; il trasporto deve restare HTTPS/WSS e la risposta non deve essere memorizzabile in cache.
4. Prima di cambiare Asterisk, salvare una copia recuperabile della configurazione e verificare che la chiamata 8290 sia operativa. Applicare il cambio 8301, ricaricare PJSIP, confermare una registrazione e una chiamata bidirezionale. Se una verifica fallisce, ripristinare Asterisk e la credenziale precedente in e-Face.
5. Solo dopo il successo di 8301, affrontare SIP DoorBird e SIP Control4. La password di amministrazione DoorBird non è compresa nella LAN API pubblica: deve restare una procedura guidata nell'app DoorBird, senza presentarla come sincronizzata.

Le credenziali SIP e la configurazione delle chiamate dell'impianto di prova non vanno modificate finché il connettore, il backup e il rollback non sono implementati e testati. L'add-on Asterisk usa `pjsip_custom.conf` persistente; una modifica soltanto a runtime non basta per un'installazione definitiva.

### Stato impianto di prova: accesso AMI dedicato

Il 13 settembre 2026 è stato preparato `custom/manager.conf` nell'add-on Asterisk `3e533915_asterisk`, copiando integralmente il `default/manager.conf` generato e aggiungendo l'utente `eface`. La copia generata originale resta disponibile per il ripristino. L'utente ha solo `read=config` e `write=config`, ACL sul singolo IP interno osservato `172.30.33.5/32`, e una password casuale salvata **fuori dal repository** in `C:\Users\NUC Alex\.ssh\eface_ami_credential.txt` con ACL Windows limitata all'utente corrente. Non include privilegi `command` o `originate`.

Il file personalizzato è stato caricato dopo il riavvio del solo add-on Asterisk. L'utente AMI dedicato è autenticabile dall'indirizzo e-Face `172.30.33.5`; il client e i test sono in `app/asterisk_ami.py` e `tests/test_asterisk_ami.py`, con diagnostica nella UI admin. L'AMI resta una prova tecnica e non va considerata sincronizzazione delle credenziali SIP.

**Esito dopo il riavvio:** il login AMI è riuscito dall'IP `172.30.33.5`, ma `GetConfig` ha rifiutato `pjsip_custom.conf`. L'add-on espone `custom/*.conf` tramite symlink verso `/addon_configs`, cioè fuori da `/etc/asterisk`; Asterisk blocca per progetto GetConfig/UpdateConfig su file esterni alla directory di configurazione. **Non impostare `live_dangerously=yes`**: disabiliterebbe questa protezione. L'AMI preparata è solo diagnostica e non costituisce il canale di provisioning. Il percorso definitivo richiede un'interfaccia strettamente limitata dentro l'add-on Asterisk, che modifichi il suo file persistente e applichi rollback atomico. Prima della distribuzione valutare la rimozione dell'utente AMI `eface`, ormai non necessario al provisioning.

Ripristino: rimuovere **solo** `custom/manager.conf` preparato per e-Face e riavviare il solo add-on Asterisk. Il file `default/manager.conf` e gli altri `custom/*.conf` restano invariati. Non eliminare il file della credenziale locale prima di aver completato il ripristino.

## Obiettivo

Distribuire gli stessi add-on e la stessa configurazione di base in tutti gli impianti. L'installatore deve poter attivare e-Face, Asterisk e il videocitofono con una procedura guidata, senza modificare file di configurazione, copiare password tra macchine o eseguire comandi Asterisk manuali.

## Attività

- Creare nell'area admin e-Face una procedura di prima attivazione con codice impianto rilasciato dalla VPS eVoice.
- Generare e conservare credenziali distinte per ogni impianto e per ogni interno/utente; non includere segreti nell'immagine degli add-on o nel repository Git.
- Rilevare o richiedere solo i dati realmente variabili (IP del controller/door station, dispositivi, utenti) e validare gli indirizzi prima del salvataggio.
- Configurare automaticamente la parte e-Face, Asterisk, SIP/WebRTC e TURN tramite integrazioni supportate, con backup della configurazione precedente e ripristino in caso di errore.
- Fornire una verifica guidata: registrazione SIP, chiamata ai destinatari, risposta, audio bidirezionale in LAN e da rete mobile, esito leggibile con istruzioni di correzione.
- Prevedere revoca, rotazione credenziali, sostituzione della VPS e recupero di un impianto senza dipendere dal PC usato durante l'installazione.
- Preparare un pacchetto di backup/ripristino cifrato e una procedura documentata per migrazione a un nuovo Home Assistant.

## Criteri di completamento

1. Un impianto nuovo parte da add-on standard identici a quelli degli altri clienti.
2. L'installatore inserisce un codice di attivazione e completa i soli dati specifici dell'impianto nell'interfaccia e-Face.
3. Non sono necessari accesso SSH, modifica di `*.conf`, interventi su Cloudflare o copia manuale di password per la normale installazione.
4. Il test finale conferma chiamata e audio in entrambe le direzioni, sia in LAN sia su rete mobile.
5. Un'installazione esistente, incluso l'impianto di prova attuale, resta funzionante durante aggiornamento o errore di provisioning; il ripristino è testato.
6. Segreti di impianti diversi sono isolati, revocabili e non appaiono in log, API pubbliche, documentazione o Git.

La configurazione manuale verificata il 13 settembre 2026 resta il riferimento tecnico, **non** la procedura definitiva per i clienti. Vedi [INTERCOM_TURN_2026-09-13.md](INTERCOM_TURN_2026-09-13.md).
