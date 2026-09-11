# Changelog

## 0.4.1 — 2026-09-11

- Resa funzionale la voce `Vedi tutti` degli ambienti.
- Collegati i pulsanti Stanze, Multimedia, Sicurezza e Tutti i dispositivi.
- Aggiunte etichette descrittive alle icone della navigazione laterale.

## 0.4.0 — 2026-09-11

- Rese cliccabili categorie e stanze con elenco dei dispositivi reali.
- Mostrato lo stato disponibile per ogni dispositivo BusPro o Home Assistant.
- Deduplicati gli ambienti senza distinzione tra maiuscole e minuscole.
- Corretta la leggibilità di titolo, quantità e descrizione nelle schede.
- Nascosti i riquadri camera dimostrativi in modalità live.

## 0.3.2 — 2026-09-11

- Aggiunto il rilevamento automatico di e-HDL BusPro MQTT tramite Supervisor.
- Usato il DNS interno dell'add-on per evitare rifiuti di connessione sulla rete host.
- Mantenuto l'indirizzo configurato dall'utente come fallback.

## 0.3.1 — 2026-09-11

- Mostrato nella UI il motivo per cui un connettore è offline.
- Distinti errori HTTP, timeout, connessione rifiutata e risposta non valida.
- Nascosto correttamente il player quando non esistono dati multimediali live.

## 0.3.0 — 2026-09-11

- Normalizzati dispositivi e stanze provenienti da e-HDL BusPro MQTT.
- La modalità live mostra conteggi reali di luci, cover, serrature e sensori.
- Aggiunto lo stato online/offline dei connettori nella barra superiore.
- Aggiunto aggiornamento automatico ogni 10 secondi, sospeso quando la pagina non è visibile.
- Mantenuto il confine architetturale: nessun motore BusPro è incluso in e-Face X4.

## 0.2.4 — 2026-09-11

- Applicato il marchio orizzontale ufficiale fornito dall'utente.
- Rimossa la ricostruzione HTML del wordmark.
- Mantenuto il nome configurabile dell'abitazione subito dopo il logo.

## 0.2.3 — 2026-09-11

- Separati simbolo, wordmark e nome dell'abitazione nella testata.
- Usato il simbolo e-Face senza scritta, seguito da `e-Face X4` e dal nome configurabile.

## 0.2.2 — 2026-09-11

- Sostituita la scritta tipografica e-Face X4 con il logo ufficiale completo.
- Allineati logo, nome configurabile dell'abitazione e stato demo su un'unica riga.

## 0.2.1 — 2026-09-11

- Mostrato il nome fisso e-Face X4 accanto al logo.
- Aggiunta l'opzione `home_name` per configurare il nome dell'abitazione.
- Separato visivamente il nome del prodotto dal nome dell'impianto.

## 0.2.0 — 2026-09-11

- Ridisegnata la dashboard secondo il nuovo riferimento X4.
- Navigazione laterale su tablet e inferiore su smartphone.
- Aggiunte barra contestuale, pillole di stato e griglia domotica compatta.
- Introdotti pannello clima dominante, anteprime camera e player persistente.
- Mantenuta l'identità originale e-Face X4 senza asset Control4.

## 0.1.4 — 2026-09-11

- Rimossa la modalità `host_network` per evitare conflitti con altri add-on.
- Aggiunta la porta web esterna configurabile, predefinita su `8130`.
- Mantenuto Home Assistant Ingress sulla porta interna isolata `8099`.

## 0.1.3 — 2026-09-11

- Corretto il blocco `expected a URL` con indirizzi dei connettori vuoti.
- Gli indirizzi vengono accettati vuoti finché il relativo connettore è disabilitato.

## 0.1.2 — 2026-09-11

- Resi opzionali tutti i parametri della configurazione iniziale.
- La modalità demo può avviarsi senza configurare BusPro o e-Voice.
- Mantenuti fallback sicuri lato applicazione per opzioni assenti.

## 0.1.1 — 2026-09-11

- Introdotto il marchio ufficiale e-Face X4.
- Aggiunti logo e icona per il catalogo Home Assistant.
- Aggiunti favicon, icona Apple Touch e manifest PWA.
- Allineata la dashboard alla palette rossa e antracite del marchio.

## 0.1.0 — 2026-09-11

- Prima fondazione installabile tramite Home Assistant Ingress.
- Dashboard X4 responsive con modalità chiara e scura.
- Modalità demo esplicita.
- Architettura modulare dei connettori.
- Primo connettore in sola lettura per e-HDL BusPro MQTT.
- Endpoint di salute e test contro l'esposizione delle credenziali.
