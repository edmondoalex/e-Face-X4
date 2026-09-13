# Audio remoto e-Face X4 / Asterisk — 13 settembre 2026

## Obiettivo e perimetro

Rendere possibile l'audio WebRTC della postazione e-Face 8301 anche fuori dalla LAN, senza cambiare il dialplan `8290`, il DoorBird o gli endpoint Control4. La chiamata SIP via Cloudflare Tunnel funzionava già, ma su rete mobile era muta: il tunnel HTTPS/WebSocket non trasporta automaticamente RTP/ICE.

## Modifiche eseguite

- VPS eVoice `169.58.200.54`: installato Coturn 4.6.1 come servizio `coturn` autonomo. Non sono stati modificati Caddy, Docker o i servizi eVoice.
- Configurazione del relay: `/etc/turnserver.conf`, derivata da [`deploy/coturn-eface.conf`](../deploy/coturn-eface.conf). Copia della configurazione precedente: `/etc/turnserver.conf.pre-eface-20260913`. Listener UDP/TCP 3478, porte relay UDP 49160–49260, autenticazione obbligatoria, niente accesso anonimo.
- Creato l'account TURN dedicato `eface` nel database Coturn. La password non è nel repository né in questo documento: è salvata sul PC di sviluppo in `C:\Users\NUC Alex\.ssh\eface_turn_credential.txt`. Non copiarla in chat o su Git.
- Asterisk Home Assistant: creato `custom/rtp.conf` nell'add-on `3e533915_asterisk`, dal modello [`deploy/rtp.conf.template`](../deploy/rtp.conf.template), con STUN/TURN verso la VPS. Non sono stati toccati `extensions.conf` né `pjsip_custom.conf`. La configurazione RTP personalizzata entra in funzione al riavvio dell'add-on Asterisk.
- e-Face X4 2.20.44: aggiunta configurazione TURN riservata all'admin in **Strumenti → Videocitofono**. La password è salvata in `/data/intercom_turn.json` con permessi `0600`, non viene restituita dal normale endpoint di amministrazione e viene letta dalla sola postazione SIP admin per configurare WebRTC. Se TURN non è configurato, resta la modalità LAN preesistente.
- Quando TURN è configurato, la casella “Connessione rapida (solo rete locale)” viene deselezionata automaticamente. Se l'utente la seleziona, usa il vecchio percorso locale senza relay.

## Verifiche già eseguite

- Coturn `active`, listener sulla sola interfaccia pubblica VPS; autenticazione e inoltro di prova riusciti sulla VPS con `turnutils_uclient`, 0 pacchetti persi.
- Porta TCP 3478 raggiungibile dal PC esterno. La raggiungibilità UDP dalla rete mobile resta da verificare.
- Test applicativi e-Face: `73 passed`.

## Attivazione e prova finale

1. Aggiornare l'add-on e-Face alla versione 2.20.44.
2. In **Strumenti → Videocitofono → Audio da remoto (TURN)** impostare `turn:169.58.200.54:3478?transport=udp`, utente `eface` e la password dal file locale indicato sopra. Salvare. Non utilizzare il dominio Cloudflare proxied per TURN.
3. Riavviare **solo** l'add-on Asterisk perché carichi `custom/rtp.conf`; controllare che l'interno 8301 e i tablet tornino raggiungibili.
4. Da telefono su rete mobile aprire `https://eface-easas.e-control.tech/intercom`, registrare 8301 e verificare che “Connessione rapida (solo rete locale)” sia deselezionata. Ripetere la chiamata simulata `channel originate Local/8290@doorbird-inbound application Echo` e verificare audio bidirezionale.
5. Se resta muta, verificare la porta **UDP 3478** e l'intervallo **UDP 49160–49260** nel firewall del provider VPS, e raccogliere gli stati ICE del browser e `pjsip show channelstats` durante la chiamata. Il precedente errore `STUN request: Network is unreachable` da solo non prova che il relay sia raggiungibile da Asterisk.

## Ripristino

- e-Face: svuotare il campo server TURN nel pannello admin e salvare; il test LAN torna a usare `iceServers: []`.
- Asterisk: rimuovere **solo** `custom/rtp.conf` creato per questa modifica (oppure ripristinare l'eventuale backup `custom/rtp.conf.before-eface-turn-20260913.bak`, se presente) e riavviare il solo add-on Asterisk. Gli altri file custom restano invariati.
- VPS: `systemctl disable --now coturn`; ripristinare la copia `/etc/turnserver.conf.pre-eface-20260913` solo se si vuole tornare alla configurazione del pacchetto. Non eliminare dati eVoice.

## Riferimenti tecnici

- [Asterisk: ICE, STUN e TURN](https://docs.asterisk.org/Configuration/Miscellaneous/Interactive-Connectivity-Establishment-ICE-in-Asterisk/)
- [Coturn: configurazione di riferimento](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf)
- [Cloudflare: applicazioni pubblicate con Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/)
