# Task: Video Intercom Control4 ↔ e-Face

Ultimo aggiornamento: 15 settembre 2026  
Stato: audio funzionante; H.264 negoziato; Control4 → e-Face mostra alcuni fotogrammi iniziali e poi si blocca; variante driver pronta ma non ancora installata.

## Obiettivo finale

Ottenere chiamate audio/video bidirezionali e stabili tra i touch Control4 T3 e i dispositivi personali e-Face, mantenendo:

- chiamata e risposta dalla pagina Videocitofono;
- nome corretto di chiamante e destinatario;
- anteprima locale durante la composizione;
- video remoto già predisposto alla risposta;
- chiusura sincronizzata su entrambi i lati;
- chiamate successive immediatamente disponibili;
- compatibilità con notifiche PWA, DND, gruppi e dispositivi solo audio.

## Topologia verificata

| Componente | Valore nell'impianto di prova |
| --- | --- |
| Home Assistant | `192.168.3.24` |
| Controller Control4 | `192.168.3.10` |
| Container e-Face | `app_d71ab5ec_e_face_x4` |
| Container Asterisk | `app_d71ab5ec_asterisk_eface` |
| e-Face installato a fine sessione | `2.21.69`, stato `started` |
| Asterisk e-Face | `6.2.0-eface.11` |
| Registrazione Asterisk verso Control4 | account `8100`, stato verificato `Registered` |
| Touch Ufficio | T3 7" In-Wall, identità SIP/MAC `000FFF8003AA`, interno e-Face `8291` |
| Touch Tavolo | T3 10" Tabletop, identità SIP/MAC `000FFF83319F`, interno e-Face `8292` |
| Poco | dispositivo personale e-Face `8303` |
| PC NUC | dispositivo personale e-Face `8302` |

Le credenziali non sono riportate qui. Usare esclusivamente quelle già salvate in Control4/Asterisk; non stamparle nei log e non inserirle nel repository.

## Scoperta fondamentale sul collegamento Control4

Il driver Control4 **Universal SIP Phone (Communication)** non collega Control4 a un PBX esterno nel modo inizialmente ipotizzato. È l'endpoint SIP esterno, in questo caso Asterisk/e-Face, che deve registrarsi al server SIP interno del controller Control4.

È stata quindi aggiunta e verificata la registrazione outbound Asterisk:

```ini
[control4-eface-registration]
type=registration
transport=transport-udp
outbound_auth=control4-test-auth
server_uri=sip:192.168.3.10:5060
client_uri=sip:8100@192.168.3.10
contact_user=8100
retry_interval=10
forbidden_retry_interval=30
max_retries=20
```

La password resta nel file live e non va copiata nella documentazione.

## Configurazione Asterisk live effettuata

File: `/config/asterisk/custom/pjsip_custom.conf`.

Sono presenti le identificazioni degli INVITE Control4 in base all'header `From`, perché le chiamate arrivano dall'IP del controller e usano come utente SIP il MAC del touch:

```ini
[control4-t3-ufficio-identify]
type=identify
endpoint=control4-t3-ufficio-test
match_header=From: /sip:000FFF8003AA@/

[control4-t3-tavolo-identify]
type=identify
endpoint=control4-t3-tavolo-test
match_header=From: /sip:000FFF83319F@/
```

Sugli endpoint Ufficio e Tavolo è stato aggiunto `rtp_symmetric=yes`. L'endpoint Ufficio consente `alaw,ulaw,h264`; verificare sempre lo stato reale con `pjsip show endpoint control4-t3-ufficio-test` prima di altre modifiche.

File: `/config/asterisk/custom/extensions.conf`.

Durante la diagnosi è stata aggiunta questa rotta temporanea:

```asterisk
exten => 8100,1,Dial(PJSIP/8303,40)
```

Questa rotta serve soltanto al test punto-punto: premendo **Asterisk** sul touch Control4 viene chiamato il Poco `8303`. Non è la destinazione finale di produzione. In seguito `8100` dovrà instradare l'utente, dispositivo o gruppo scelto dall'architettura definitiva.

Backup creati sul volume Asterisk:

- `/config/asterisk/custom/pjsip_custom.conf.before-control4-inbound-20260915.bak`
- `/config/asterisk/custom/pjsip_custom.conf.before-control4-registration-20260915.bak`
- `/config/asterisk/custom/pjsip_custom.conf.before-control4-symmetric-rtp-20260915.bak`
- backup di `extensions.conf` con suffisso `.before-control4-8100-20260915.bak`

Non ripristinare questi file alla cieca: prima confrontarli con la configurazione corrente perché possono esserci modifiche successive.

## Risultati SIP/SDP verificati

L'INVITE Ufficio → Asterisk contiene:

```text
X-C4-Start-With-Video: true
m=video ... RTP/AVP 96
a=rtpmap:96 H264/90000
a=fmtp:96 packetization-mode=1;profile-level-id=42801F
a=rtcp-fb:96 ccm fir
a=rtcp-fb:96 ccm tmmbr
a=rtcp-fb:96 nack
a=rtcp-fb:96 nack pli
```

La risposta WebRTC del Poco accetta H.264 con `packetization-mode=1` e `profile-level-id=42001f`, oltre a VP8. Asterisk risponde al Control4 accettando H.264 `42801F`. Pertanto:

- il video è realmente offerto dal T3;
- H.264 è negoziato su entrambi i rami;
- il primo fotogramma viene decodificato dal Poco;
- il riquadro e il decoder WebRTC non sono la causa primaria del fermo immagine.

## Evidenza RTP determinante

Durante una chiamata reale Asterisk ha ricevuto video dal controller su `192.168.3.10:21340`, payload H.264 96, e lo ha inoltrato al relay TURN del Poco come payload 99.

Sono stati osservati circa 120 pacchetti video, 32 timestamp RTP distinti, distribuiti su circa 13 secondi. In una finestra successiva di cinque secondi, mentre l'audio era ancora attivo, i contatori erano:

```text
Control4 video in: 0
Poco video out: 0
```

Il comportamento percepito dall'utente coincide: alcuni primi fotogrammi, poi un'immagine congelata o nera. Asterisk non può inoltrare fotogrammi che il controller ha smesso di trasmettere.

La chiamata reale delle 18:01 è rimasta in bridge dalle 18:01:07 alle 18:02:02. L'audio è rimasto attivo fino alla chiusura; il video si era già fermato.

## Driver Control4 attuale e causa probabile

Driver installato:

- nome: `Universal SIP Phone (Communication)`;
- produttore: Control4;
- versione pacchetto: 26;
- versione Lua: 1.2.6;
- data del manifest: 2014/2015;
- file: `intercom_universal.c4z`.

Il manifest originale dichiara:

```xml
<has_camera>false</has_camera>
<has_display>false</has_display>
<audio_codecs_supported></audio_codecs_supported>
<vidio_codecs_supported></vidio_codecs_supported>
```

L'ultimo nome è anche scritto `vidio` invece di `video`. La documentazione ufficiale del proxy Intercom afferma che **Send Video**, **Camera Enabled**, Monitor Mode e le altre funzioni video non hanno effetto quando `has_camera=false`. Questo spiega perché `Camera Enabled=True` in Composer non è una prova sufficiente e perché **Send Video** risultava non selezionabile.

Il Lua del driver è sostanzialmente uno stub generico. La proprietà `Camera Enabled` invia `CAMERA_ENABLED_CHANGED`, ma non gestisce RTP, FIR, PLI o keyframe. Il flusso SIP/media è gestito dall'infrastruttura Intercom del controller.

## Variante driver preparata

Artefatto locale:

`Driver Control4/e-Face Universal SIP Video.c4z`

È una copia di prova del pacchetto già presente sul controller, modificata soltanto nel manifest:

```xml
<name>e-Face SIP Video (Communication)</name>
<model>e-Face SIP Video</model>
<version>27</version>
<has_camera>true</has_camera>
<has_display>true</has_display>
<audio_codecs_supported>G711 ULAW, G711 ALAW</audio_codecs_supported>
<video_codecs_supported>H264</video_codecs_supported>
```

Il file è stato riaperto come ZIP e il manifest è stato validato come XML. Non è stato ancora importato in Composer e non costituisce ancora una soluzione verificata. È ignorato da Git perché deriva da codice proprietario Control4 presente sull'impianto: conservarlo localmente, non pubblicarlo.

## Correzioni e-Face completate oggi

Versione `2.21.69`, commit `d35bb8e`:

1. Il blocco anti-duplicato dopo la chiusura/rifiuto di una chiamata è stato ridotto da 60 secondi a 1,5 secondi. Il vecchio valore causava risposte `486 Busy` alle chiamate immediatamente successive.
2. La scheda chiamata viene chiusa anche quando la sessione JsSIP risulta terminata o la `RTCPeerConnection` passa a `closed/failed`. Questo evita la chiamata fantasma senza audio rimasta sul Poco dopo la chiusura dal touch.
3. Versione, service worker e cache-buster aggiornati; add-on distribuito e verificato `started` alla 2.21.69.
4. Verifica locale completata: `node --check`, `git diff --check` e `200 passed` con pytest.

Sequenza osservata che ha permesso di identificare il vecchio blocco:

- chiamata terminata alle 17:58:54;
- tentativi alle 17:58:58, 17:59:04 e 17:59:24 rifiutati dal Poco come occupato;
- nessun canale Asterisk era rimasto attivo;
- la causa era `rejectIncomingUntil = Date.now() + 60000` nel client.

## Problemi ancora aperti

### 1. Installare e provare la variante video

Serve un backup del progetto Control4. Poi in Composer Pro:

1. importare `e-Face Universal SIP Video.c4z`;
2. aggiungerlo come **nuovo** dispositivo, senza eliminare il driver originale;
3. configurare temporaneamente un interno SIP di test distinto, se il controller non consente due endpoint con `8100`;
4. verificare che **Send Video** diventi selezionabile;
5. impostare `Camera Enabled=True` e `Send Video` attivo;
6. verificare registrazione SIP e presenza nell'elenco Intercom;
7. eseguire una chiamata Ufficio → e-Face e controllare RTP per almeno 30 secondi;
8. soltanto dopo il successo trasferire `8100` e gli eventuali binding dal driver originale.

Sostituire direttamente il driver originale senza backup è un'azione distruttiva e non va eseguita automaticamente.

### 2. Se il video continua a fermarsi

Acquisire una sola chiamata completa con SIP, RTP e RTCP, distinguendo chiaramente:

- fase di squillo/early media;
- risposta `200 OK` e `ACK`;
- istante dell'ultimo pacchetto H.264 Control4;
- Receiver Report, PLI e FIR sui due rami;
- eventuale BYE/re-INVITE/UPDATE proprietario Control4.

Ipotesi da verificare, in ordine:

1. Control4 interrompe il video dopo la risposta perché l'endpoint remoto è ancora classificato senza camera/display.
2. Il controller richiede un cambio di stato proxy o un header proprietario dopo la risposta.
3. Asterisk non trasferisce al ramo RTP/AVP il feedback PLI/FIR ricevuto dal WebRTC; in tal caso valutare un media gateway con gestione esplicita RTCP, non una correzione CSS/JS.
4. Il T3 usa il video solo come early media finché il proxy non abilita `Send Video` per la sessione stabilita.

Non partire modificando profili H.264: il primo fotogramma già decodificato prova che il profilo corrente è almeno compatibile.

### 3. Chiusura chiamata bidirezionale

Dopo la 2.21.69 verificare fisicamente:

- chiusura dal touch → scheda Poco scompare entro pochi secondi;
- nuova chiamata entro cinque secondi → non riceve `486 Busy`;
- chiusura dal Poco → il touch torna alla pagina Intercom;
- nessun canale residuo in `core show channels verbose`.

### 4. Stabilità del touch

Durante un test il touch è diventato completamente nero e poi ha ricaricato Intercom. Non è stato dimostrato che Asterisk abbia causato il riavvio della UI. Controllare log Control4/Director e carico del touch se il comportamento si ripete. Non confondere questo evento con il solo riquadro video nero del Poco.

### 5. Destinazione definitiva dell'interno 8100

La rotta attuale chiama solo `8303`. Definire se `8100` debba chiamare:

- l'ultimo dispositivo dell'utente;
- un utente con più dispositivi;
- un gruppo e-Face;
- un gruppo “Tutti” rispettando DND;
- una schermata di scelta sul touch, se tecnicamente supportata.

## Procedura rapida per la prossima sessione

1. Leggere `AGENTS.md`, `docs/PROCEDURA_CONTROL4_HASSIO_SVILUPPO.md` e questo task.
2. Verificare `git status --short`; le due immagini non tracciate nella cartella `e_face_x4` appartengono all'utente e non vanno toccate.
3. Verificare versioni e stato reali dei due add-on.
4. Verificare `pjsip show registrations`, endpoint Ufficio/Tavolo, identifies e rotta `8100` senza stampare password.
5. Fare backup del progetto Control4 in Composer.
6. Importare la variante come nuovo driver e controllare prima le capability/checkbox, senza rimuovere l'originale.
7. Per la prova fisica chiedere un solo gesto: Ufficio → endpoint e-Face, risposta, 30 secondi di movimento davanti alla camera, poi chiusura dal touch.
8. Durante quel singolo test catturare già SIP+RTP+RTCP e statistiche canali; non chiedere prove ripetute senza nuova informazione.
9. Se la variante risolve il flusso, documentare configurazione Composer e rendere definitiva la rotta. Se non lo risolve, conservare l'originale e passare all'analisi RTCP/proxy.

## Comandi diagnostici utili

Eseguire tramite il canale SSH tecnico già autorizzato, verificandone prima la disponibilità. Non includere in output pubblico chiavi, password, token o URL Ingress.

```text
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'pjsip show registrations'
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'pjsip show endpoint control4-t3-ufficio-test'
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'pjsip show identifies'
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'pjsip show channels'
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'pjsip show channelstats'
docker exec app_d71ab5ec_asterisk_eface asterisk -rx 'core show channels verbose'
```

Per una cattura, limitare il filtro all'host Control4 e alle porte SIP/media pertinenti, scrivere in `/tmp`, interrompere appena conclusa la chiamata e cancellare la cattura dopo aver estratto soltanto i dati tecnici necessari. I dump SIP possono contenere identificativi e non vanno committati.

## Criteri di completamento

Il task sarà concluso solo quando una prova reale dimostrerà contemporaneamente:

- video Control4 → Poco fluido per almeno 60 secondi;
- video Poco → Control4 fluido per almeno 60 secondi;
- audio bidirezionale stabile;
- chiusura da entrambi i lati sincronizzata;
- seconda chiamata immediata senza `Busy`;
- touch stabile senza schermata nera/riavvio;
- rotta `8100` non più temporaneamente vincolata al solo Poco;
- configurazione e rollback documentati senza credenziali.
