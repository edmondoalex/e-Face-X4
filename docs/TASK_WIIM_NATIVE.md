# Task: integrazione WiiM nativa in e-Face

Stato iniziale: 15 settembre 2026.

## Decisione

L'integrazione profonda sarà un provider e-Face nativo che comunica direttamente con WiiM. Home Assistant non sarà il backend funzionale e Control4 resterà responsabile soltanto della selezione della sorgente e della distribuzione audio nelle stanze.

Il percorso applicativo è esplicitamente **e-Face → WiiM**. Né Home Assistant né il proxy media-service Control4 devono trovarsi nel percorso di navigazione, lettura dello stato o comando del dispositivo WiiM. L'associazione con una stanza Control4 è opzionale e successiva alla scelta del contenuto.

## Impianto verificato

- WiiM Pro `192.168.3.52`, collegato via Ethernet e raggiungibile in HTTPS.
- Firmware osservato: `Linkplay.4.8.827634`; progetto hardware `WiiM_Pro_with_gc4a`.
- Control4: protocollo Linkplay `1666`, media-service `1667`, amplifier `1668`, rete `1669`; driver `WiiM-Pro.c4z` versione 19.
- Sorgente Control4: `listen:1667`, tipo `RF_WIIM_WS_MUSIC`, attiva durante la sonda in Ufficio Alex e disponibile in più stanze.
- Home Assistant 2026.8.3 contiene già l'integrazione ufficiale `wiim`, scoperta via Zeroconf, ma viene considerata troppo limitata per l'interfaccia richiesta.

## Dati nativi già verificati

Le API locali `getStatusEx`, `getPlayerStatus` e `getMetaInfo` restituiscono stato, volume, mute, posizione, durata, titolo/artista/album, identificativo traccia, sample rate, bit depth, bitrate e URL della cover. I campi testuali del player possono essere codificati in esadecimale UTF-8.

Il driver Control4 espone comandi base, 12 preset, code e repeat/shuffle. Il suo Lua è cifrato; il manifest dichiara soltanto le schede Presets e Queue, quindi non offre il catalogo profondo dei servizi.

## Architettura prevista

1. Client WiiM LAN sicuro, limitato a IPv4 private, timeout breve e output normalizzato.
2. Inventario/discovery nativo di uno o più WiiM, senza dipendenza funzionale da HA o Control4.
3. Player completo: metadata, cover proxy/cache, qualità, timeline, volume, mute, repeat e shuffle.
4. Preset, coda, ingressi, EQ e multiroom WiiM.
5. Collegamento opzionale con la stanza Control4 che sta usando quella sorgente.
6. Adattatori separati per ricerca e librerie Spotify, TIDAL, Qobuz, Amazon Music e altri servizi, usando solo API/autorizzazioni supportate. L'API locale WiiM non va trattata come catalogo universale.

## Avanzamento 2.21.70

Creati `app/connectors/wiim.py` e `tests/test_wiim.py` con validazione LAN, client HTTPS, decodifica metadata e snapshot normalizzato. È disponibile in Amministrazione la scheda WiiM nativa con configurazione persistente, test diretto e riepilogo del dispositivo. Il salvataggio avviene soltanto dopo una verifica positiva, così un indirizzo errato non sostituisce una configurazione funzionante.

Restano da sviluppare l'inventario multi-player/discovery, la pagina WiiM per l'utente, i comandi completi e gli adattatori dei servizi musicali.

## Avanzamento 2.21.71

Aggiunta la pagina WiiM nella navigazione principale con polling diretto ogni due secondi, cover, metadata, timeline, qualità, volume, mute, trasporto e preset. I comandi ammessi sono tradotti server-side tramite una allowlist; il browser non può inviare comandi Linkplay arbitrari. Restano aperti discovery multi-player, coda/ingressi/EQ/multiroom e gli adattatori autenticati per i cataloghi dei servizi musicali.
