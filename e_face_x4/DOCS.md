# e-Face X4 0.1.0

Questa prima versione serve a verificare installazione, Ingress e impostazione grafica.

## Avvio rapido

1. Installare e avviare l'add-on.
2. Aprire la Web UI.
3. Lasciare `demo_mode` attivo per visualizzare la dashboard dimostrativa.

## Porta web

Ingress usa internamente la porta `8099`. Per l'accesso diretto Home Assistant pubblica per
impostazione predefinita la porta `8130`, modificabile nella sezione **Rete** dell'add-on.

Esempio: `http://IP_HOME_ASSISTANT:8130`.

## Collegamento e-HDL BusPro MQTT

Disattivare la modalità demo solo quando almeno un connettore reale è stato configurato.
Per il primo connettore impostare:

- `buspro.enabled`: abilita il collegamento;
- `buspro.base_url`: indirizzo locale dell'add-on, normalmente `http://IP_HOME_ASSISTANT:8124`;
- `buspro.token`: valorizzare solo se e-HDL BusPro MQTT utilizza autenticazione token.

Il token resta nel file delle opzioni dell'add-on e non viene restituito al browser.

La versione 0.1.0 non invia ancora comandi agli add-on collegati: il primo connettore viene usato
per verificare disponibilità e contratto dei dati prima di abilitare il controllo reale.
