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

Il nucleo di validazione, scrittura atomica, backup, rollback e recovery da journal ha test automatici. **Mancano** packaging dell'add-on, API autenticata, inclusione iniziale nel dialplan/PJSIP, verifica integrata con Asterisk, prova su riavvio/aggiornamento e migrazione del sito reale. Non usare questo modulo per comandare l'impianto in produzione.
