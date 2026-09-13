# TASK OBBLIGATORIO — Installazione e-Face X4 plug-and-play

Stato: **DA FARE — requisito tassativo prima della distribuzione in campo**.

Primo incremento (e-Face 2.20.45): pannello admin **Preparazione impianto** con controlli di sola lettura per Asterisk, DoorBird e raggiungibilità UDP del server TURN. Non configura Asterisk, non attiva un impianto sulla VPS e non sostituisce la prova audio reale. Il task resta aperto finché tutti i criteri sotto sono soddisfatti.

Secondo incremento (e-Face 2.20.46): inventario unico **Credenziali impianto** nell'admin, con visualizzazione temporanea dopo nuova autenticazione e importazione delle credenziali SIP/DoorBird come copie esplicitamente non sincronizzate. Vedi [CREDENZIALI_IMPIANTO_2026-09-13.md](CREDENZIALI_IMPIANTO_2026-09-13.md). Il task resta aperto: il provisioning e il vault per-impianto non sono ancora implementati.

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
