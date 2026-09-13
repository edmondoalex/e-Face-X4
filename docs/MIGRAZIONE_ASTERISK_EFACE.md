# Migrazione Asterisk e-Face — non eseguire ancora

Stato: preparazione. L'impianto attuale usa l'add-on `3e533915_asterisk`; la variante `e_asterisk` ha uno slug diverso e **non** prende automaticamente il posto dell'add-on esistente. Non avviare i due add-on insieme: la rete host e le porte SIP/RTP possono entrare in conflitto.

## Condizioni da provare prima di qualsiasi fermo

1. Costruire e avviare la variante in un ambiente Home Assistant di prova, non nell'impianto in funzione. Verificare che l'immagine base fissata a digest contenga Python 3 e usi i percorsi `cont-init.d`, `services.d` e `/etc/asterisk/pjsip.conf` attesi.
2. Verificare che il provisioner ascolti soltanto sulla rete interna raggiungibile da e-Face; nessun servizio di provisioning deve essere esposto su LAN, Internet o Cloudflare Tunnel. Verificare che il token sia unico per impianto, non stampato nei log e non salvato nel repository.
3. Simulare su copia delle configurazioni: recupero del journal dopo interruzione, riavvio, ricreazione del container e aggiornamento dell'immagine. Controllare che `/config/asterisk/eface/phones.json` e `pjsip.conf` sopravvivano e che il `#include` sia effettivamente caricato anche quando esiste un `custom/pjsip.conf`.
4. Verificare l'intero percorso e-Face → Asterisk: creazione 8302, reload, endpoint visibile, registrazione WebSocket, chiamata/audio, revoca e rollback in caso di errore. Non basta che l'API risponda 200.
5. Verificare che 8301, 8290, due tablet Control4 e DoorBird rimangano invariati; provare chiamate in entrambe le direzioni, anche da rete mobile.

## Preparazione della migrazione reale

1. Concordare una finestra di manutenzione. Fino ad allora, nessuna modifica o riavvio dell'add-on attuale.
2. Eseguire un backup completo Home Assistant che includa l'add-on attuale e la sua cartella `addon_configs/3e533915_asterisk`; verificarne la leggibilità e annotare versione e opzioni dell'add-on. Non copiare password nei log o nei documenti.
3. Confrontare i file `custom/` e gli include Asterisk, annotando i file usati per DoorBird, 8301, gruppo 8290, WS e TURN. Preparare una copia di prova nella nuova cartella add-on senza alterare l'originale.
4. Preparare il token per-impianto tramite un flusso di associazione sicuro. L'integrazione e-Face, la verifica di salute e la riconciliazione degli interni devono essere già testate prima dello switch.

## Switch e criteri di ritorno

Solo dopo i test: fermare l'add-on precedente, avviare la variante, verificare prima 8301/8290/DoorBird/Control4 e poi gli interni personali. Se una chiamata di base fallisce, fermare la variante e riavviare **l'add-on originale con la sua cartella originale**, senza sovrascriverla. Il ritorno è completo solo quando le chiamate di base tornano a funzionare. Le credenziali personali nuove restano in attesa fino a nuova verifica.

## Stato attuale

Questa procedura è un piano, non una migrazione eseguita. La variante non è stata costruita in Home Assistant né provata contro l'impianto reale; il suo avvio resta manuale e sperimentale. Non dichiarare il provisioning automatico pronto finché tutte le condizioni sopra non passano.
