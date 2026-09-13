# Credenziali impianto nell'admin e-Face X4

Versione iniziale: **2.20.46**. Accesso: **Strumenti → Amministrazione → Credenziali impianto**.

## Cosa è disponibile

- Un inventario unico mostra stato e nome utente di admin e-Face, Control4, TURN, SIP DoorBird, SIP e-Face, SIP Control4 e amministrazione DoorBird. La risposta dell'inventario non contiene password.
- La password admin e-Face non è recuperabile: può soltanto essere cambiata nella gestione utenti, perché è memorizzata come hash.
- Le password Control4 e TURN già salvate dall'app possono essere visualizzate temporaneamente dopo una nuova conferma della password admin, senza creare copie aggiuntive.
- Le credenziali SIP e DoorBird possono essere importate come **copie di riferimento**. La copia è salvata in `/data/credential_inventory.json` con permessi `0600`; l'importazione **non cambia** password o utenti nei dispositivi e non sincronizza Asterisk.
- Una password rivelata scompare dalla pagina dopo 30 secondi o alla chiusura della pagina. L'API di rivelazione richiede la password admin, limita i tentativi falliti e imposta `Cache-Control: no-store`.

## Limiti e sicurezza

- Questa è una centralizzazione dell'interfaccia, non ancora un vault cifrato o il provisioning automatico promesso per le nuove installazioni. I file `/data/control4.json`, `/data/intercom_turn.json` e `/data/credential_inventory.json` contengono segreti necessari al funzionamento o alla consultazione: includerli solo in backup protetti e non copiarli su Git.
- SSH root e chiavi della VPS **non** vanno importati nell'add-on e-Face. Saranno gestiti dal sistema di provisioning della VPS con privilegi limitati.
- Prima importazione: verificare le credenziali dalla fonte originale. Le copie SIP/DoorBird possono diventare obsolete se modificate sul dispositivo; il pannello lo indica esplicitamente.
- Il passo successivo è sostituire le copie non sincronizzate con credenziali per-impianto generate e distribuite automaticamente, con revoca, rotazione, audit e recupero.

## Verifiche

- Suite e-Face: `75 passed`.
- Test: accesso admin obbligatorio, password assente dall'inventario, nuova autenticazione per rivelare, risposta non memorizzabile, account utente normale escluso, importazione marcata `synchronized: false`.

Il requisito plug-and-play resta aperto in [TASK_INSTALLAZIONE_PLUG_AND_PLAY.md](TASK_INSTALLAZIONE_PLUG_AND_PLAY.md).
