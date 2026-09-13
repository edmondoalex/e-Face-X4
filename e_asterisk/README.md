# e-Face Asterisk — variante di sviluppo

Questa variante usa come base l'immagine TECH7Fox Asterisk 6.2.0 fissata a digest e aggiunge il provisioner e-Face. **Non installarla sull'impianto esistente**: la migrazione, l'autenticazione tra add-on, il dialplan e i test su restart/upgrade non sono ancora completati. La variante ha un nuovo slug e una directory add-on diversa dall'Asterisk attuale.

La configurazione degli interni e-Face sarà custodita in `/config/asterisk/eface` dell'add-on Asterisk, non nel filesystem effimero del container. Il token `eface_provision_token` deve essere unico per impianto e non può essere predefinito uguale per tutti.
