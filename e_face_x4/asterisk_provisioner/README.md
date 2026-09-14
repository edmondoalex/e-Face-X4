# Provisioner Asterisk e-Face (in sviluppo, non installato)

Questo componente sarà eseguito **dentro una variante controllata dell'add-on Asterisk**. Il modulo `managed_config.py` è il nucleo di persistenza e non viene chiamato dall'e-Face attuale.

## Regole non negoziabili

- Stato, configurazione generata, backup e journal in `/config/asterisk/eface/`, cartella persistente dell'add-on Asterisk.
- Il provisioner modifica solo i propri file; non riscrive le sezioni esistenti DoorBird, Control4, 8301 o 8290.
- L'inclusione dei file gestiti nella configurazione Asterisk avverrà durante una migrazione una tantum, con backup e rollback.
- Nessun interno è «attivo» in e-Face prima che Asterisk lo mostri e che registrazione, chiamata e audio siano stati verificati.
- L'API tra e-Face e Asterisk dovrà essere locale, autenticata con segreto unico per impianto, limitata a create/revoke/rotate degli interni e-Face, senza accesso a percorsi o comandi arbitrari.
- Dopo riavvio e aggiornamento dell'add-on, i file gestiti devono essere ricostruibili dallo stato persistente, e una transazione interrotta deve ripristinare l'ultima configurazione valida.

## Stato

Il nucleo di validazione, scrittura atomica, backup, rollback e recovery da journal ha test automatici. Il 14/09/2026 è stata aggiunta `service.py`: API HTTP locale con token Bearer per impianto, payload e percorsi allowlist, risposta senza password e binding su `127.0.0.1`. I test verificano autenticazione, rifiuto di interno 8301 e campi arbitrari, creazione e revoca. Il servizio **non è avviato** nell'add-on attuale e il token di test non è una credenziale d'impianto.

L'adapter `asterisk_adapter.py` esegue soltanto `pjsip reload` e `pjsip show endpoint <8302–8399>`, senza shell né comandi forniti dal client. Una risposta CLI inattesa è errore, non conferma di provisioning. I test usano output Asterisk redatto osservato sul sito; non equivalgono a una prova SIP reale.

Verifica read-only dell'impianto di prova, 14/09/2026: `/config` è un bind mount del container Asterisk; `/etc/asterisk/pjsip_custom.conf` è un symlink verso `/config/asterisk/custom/pjsip_custom.conf`, incluso da `/etc/asterisk/pjsip.conf`. Il file custom non include ancora `/config/asterisk/eface/pjsip.conf`. Il futuro installer deve fare una migrazione **una tantum** di quel solo include con backup e rollback, e verificarne il caricamento dopo riavvio e ricreazione del container. Non scrivere il file generato sotto `/etc/asterisk` o nel filesystem effimero dell'immagine.

`include_migration.py` implementa la parte file di tale migrazione: richiede prima `ManagedConfig.reconcile_file()` per creare `/config/asterisk/eface/pjsip.conf`, conserva un backup byte-per-byte nella stessa directory persistente, aggiunge un solo `#include` assoluto, ripristina su errore di reload e rifiuta il rollback se qualcuno ha modificato nel frattempo il file custom. [La documentazione Asterisk](https://docs.asterisk.org/Fundamentals/Asterisk-Configuration/Asterisk-Configuration-Files/Using-The-include-tryinclude-and-exec-Constructs/) indica che `#include` carica il file nel punto della direttiva e che, se il file manca, il modulo non viene caricato: perciò la creazione del file gestito **precede** sempre l'include. Testato solo su file temporanei; l'include non è stato installato sul sito.

**Mancano** packaging della variante Asterisk, collegamento autenticato fra i due container senza esporre l'API fuori dall'impianto, esecuzione dell'include PJSIP e del dialplan sulla variante controllata, verifica integrata con Asterisk, prova su riavvio/aggiornamento e migrazione del sito reale. Non usare questi moduli per comandare l'impianto in produzione.
