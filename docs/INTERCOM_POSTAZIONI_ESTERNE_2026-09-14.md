# Intercom e-Face: postazioni esterne (beta, 14/09/2026)

## Stato verificato sul sito

- e-Face X4 `2.21.20` e Asterisk e-Face `6.2.0-eface.3` avviati.
- Ingresso DoorBird `192.168.2.30`, chiamata e-Face `8301` → `8201` → SIP P2P DoorBird; gruppo esistente `8290` invariato.
- Asterisk provisioner TLS associato a e-Face; certificato verificato con pin SHA-256 e token conservato solo in `/data/asterisk_provisioner.json` del container e-Face. Il servizio è su `192.168.3.24:9443`.
- Rotte aggiuntive in `/config/asterisk/eface/external_stations.json` e `external_routes.conf` nel container Asterisk; un solo `#include` nel contesto `[eface-test]` del dialplan persistente. Backup precedente: `/config/asterisk/eface/extensions.before-external-routes.bak`.
- Elenco e credenziali per dispositivo in `/data/external_stations.json` di e-Face (file 0600). Se il file manca, Ingresso è derivato dalle impostazioni DoorBird/credenziali già presenti.
- Testata aggiunta e rimozione di una rotta `8202` da e-Face, con verifica dopo riavvio di Asterisk. La rotta di prova è stata rimossa; nessuna postazione fittizia è rimasta.

## Flusso Admin plug-and-play

In **Strumenti → Admin → Videocitofono → Postazioni esterne**, aggiungere nome, IP privato, porta HTTP, interno SIP `8202`–`8289` e utente/password DoorBird con permesso **API operator**. Premere **SALVA E CONFIGURA**. Il backend:

1. valida i dati e verifica l'associazione TLS con il provisioner Asterisk;
2. legge lo stato SIP del DoorBird e salva una copia 0600 in `/data/doorbird_sip_backups` prima di modificarlo;
3. abilita SIP, le chiamate in ingresso e autorizza l'IP Asterisk, senza modificare la registrazione SIP preesistente;
4. invia le rotte al provisioner, che scrive in `/config`, ricarica il dialplan e verifica l'interno; solo allora e-Face salva la postazione come chiamabile.

Se un passaggio fallisce, e-Face non abilita **CHIAMA** e tenta il ripristino della rotta e delle impostazioni SIP precedenti. Le password non compaiono negli endpoint browser. Fino a otto postazioni totali sono previste. La pagina Intercom rilegge l'elenco ogni 30 secondi, senza refresh manuale.

## Particolarità DoorBird + Control4 osservata

Il DoorBird Ingresso riporta periodicamente `INCOMING_CALL_USER=192.168.3.10` (controller Control4) anche dopo che l'API ha confermato `192.168.3.24` (Asterisk). Con il primo valore, una INVITE da Asterisk con identità `8301` riceve `603 Decline`; dopo la preparazione SIP e-Face, la stessa prova riceve `200 OK`. Per non riscrivere continuamente il dispositivo, il pulsante **CHIAMA** prepara la singola postazione immediatamente prima della chiamata. Il salvataggio da Admin può riapplicare la configurazione anche all'Ingresso. Non assumere che la sola modifica SIP sul DoorBird resti stabile; verificare con `sip.cgi?action=status` e una INVITE reale.

## Prossimo passo: gruppi interni

Non sono ancora stati creati gruppi personalizzati né modificato l'instradamento dei pulsanti delle postazioni esterne. Il successivo lavoro deve associare ogni DoorBird a uno o più gruppi interni configurabili da Admin e-Face, mantenendo `8290` operativo. Per nuove postazioni, aggiungere anche l'identificazione PJSIP per IP e la destinazione del pulsante DoorBird tramite API/schedule, con verifica e backup; non usare un unico endpoint di ingresso per dispositivi diversi.

## Procedura di verifica rapida

1. Controllare che entrambi gli add-on siano `started` e che il provisioner risponda con TLS pin valido.
2. Leggere `GET /v1/external-stations` dal client e-Face; confrontare con `/data/external_stations.json`, senza esporre token/password.
3. Verificare `dialplan show 8201@eface-test` e un interno aggiuntivo `82xx@eface-test` dopo salvataggio/riavvio.
4. Per Ingresso, leggere `sip.cgi?action=status` prima della chiamata; se autorizza Control4, la preparazione deve riportarlo ad Asterisk e l'INVITE deve ricevere `200 OK`, non `603`.
5. Verificare `dialplan show 8290@default` e nessuna chiamata residua. Non ripetere chiamate fisiche se il log SIP ha già dimostrato il risultato.
