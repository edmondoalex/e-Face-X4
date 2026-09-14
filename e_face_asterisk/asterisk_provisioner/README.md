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

`startup.py` orchestra questa sequenza **prima** dell'avvio Asterisk e rifiuta di operare se il daemon è già avviato. I test simulano due avvii, transazione interrotta e file custom modificato. Il punto d'aggancio verificato nel sorgente [TECH7Fox 6.2.0](https://github.com/TECH7Fox/asterisk-hass-addons/blob/v6.2.0/asterisk/rootfs/etc/cont-init.d/asterisk.sh) è dopo il suo init che rigenera i default e ripristina i symlink da `/config/asterisk/custom`, ma prima che s6 avvii il servizio Asterisk. Il bootstrap non è ancora invocato da alcuna immagine add-on.

La configurazione upstream usa `host_network: true` e `ingress_port: 8088`. Un server HTTP legato solo a `127.0.0.1` **non è raggiungibile** dal container e-Face; non allargare il bind a `0.0.0.0` con il solo Bearer in chiaro. Il canale TLS qui sotto è ancora codice non pubblicato. Non far partire contemporaneamente una variante Asterisk e l'add-on esistente: condividerebbero le porte SIP/HTTP.

Incremento locale successivo: `service.make_https_server()` espone la stessa API **solo via TLS** su un indirizzo IPv4 privato esplicito, mai wildcard; `app/asterisk_provisioner_client.py` verifica l'impronta SHA-256 del certificato **prima di inviare** il Bearer e la password SIP. Un test end-to-end con certificato temporaneo conferma creazione/revoca e il blocco quando l'impronta non coincide. `identity.py` genera certificato, chiave e token unici sotto `/config/asterisk/eface`, li riusa dopo il riavvio e rifiuta identità parziali o permessi insicuri. [Python SSL](https://docs.python.org/3/library/ssl.html) documenta `SSLContext`/TLS; qui il pin esplicito sostituisce la validazione CA per un certificato privato, ma **non** autorizza a scaricare automaticamente un'impronta non fidata.

Mancano ancora il pairing autenticato che consegna a e-Face impronta e token senza esporli, l'avvio del servizio nella variante add-on, controllo firewall/porta, test di persistenza in un container ricreato e la migrazione live. Fino ad allora l'API HTTPS non è pubblicata né usata dall'app. La chiave e il token sono dati d'impianto: mai in Git, log, screenshot o risposte admin non protette.

**Mancano** packaging della variante Asterisk, pairing autenticato fra i due container, esecuzione dell'include PJSIP e del dialplan sulla variante controllata, verifica integrata con Asterisk, prova su riavvio/aggiornamento e migrazione del sito reale. Non usare questi moduli per comandare l'impianto in produzione.
