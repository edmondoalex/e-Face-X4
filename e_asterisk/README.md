# e-Face Asterisk — variante di sviluppo

Questa variante usa come base l'immagine TECH7Fox Asterisk 6.2.0 fissata a digest e aggiunge il provisioner e-Face. **Non installarla sull'impianto esistente**: la migrazione, l'autenticazione tra add-on, il dialplan e i test su restart/upgrade non sono ancora completati. La variante ha un nuovo slug e una directory add-on diversa dall'Asterisk attuale.

La configurazione degli interni e-Face sarà custodita in `/config/asterisk/eface` dell'add-on Asterisk, non nel filesystem effimero del container. Il token `eface_provision_token` deve essere unico per impianto e non può essere predefinito uguale per tutti.
# Associazione iniziale (solo variante di sviluppo)

Se `eface_provision_token` resta vuoto, il provisioner genera un codice monouso di 16 caratteri, valido 30 minuti, e lo mostra nel log dell'add-on Asterisk. Nell'admin e-Face, sezione Videocitofono, usare **Associa Asterisk** e inserire codice e password admin e-Face. La chiave risultante e' generata casualmente e salvata nei dati persistenti dei due add-on; il codice viene eliminato. Un nuovo codice scaduto viene generato al successivo controllo `/v1/health` (o al riavvio del solo servizio). Il token impostato manualmente nelle opzioni rimane una compatibilita' provvisoria e non e' necessario nel flusso guidato.

Questo flusso non e' ancora un test in un'installazione Home Assistant reale. Non installare la variante nell'impianto in funzione.
