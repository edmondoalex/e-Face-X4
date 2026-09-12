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

## Icone

Nella scheda **Configurazione**, la sezione **Icone navigazione** permette di impostare le icone
di Guarda, Ascolta, Luci, Oscuranti, Comfort e Sicurezza usando identificatori `mdi:...`.
Le icone dei singoli dispositivi vengono invece ereditate automaticamente dalla configurazione
di e-HDL BusPro MQTT.

## Collegamento e-HDL BusPro MQTT

Disattivare la modalitÃ  demo solo quando almeno un connettore reale Ã¨ stato configurato.
Per il primo connettore impostare:

- `buspro.enabled`: abilita il collegamento;
- `buspro.base_url`: indirizzo locale dell'add-on, normalmente `http://IP_HOME_ASSISTANT:8124`;
- `buspro.token`: valorizzare solo se e-HDL BusPro MQTT utilizza autenticazione token.

Il token resta nel file delle opzioni dell'add-on e non viene restituito al browser.

## Collegamento Ekonex Media

Per abilitare le pagine **Guarda** e **Ascolta** tramite e-Voice:

- aggiornare Ekonex Voice almeno alla versione `0.1.8-beta.37`;
- abilitare `evoice.enabled` nelle opzioni di e-Face.

e-Face usa automaticamente l'API locale autenticata tramite Home Assistant Supervisor. Espone soltanto i media player selezionati nel componente e-Voice e non legge direttamente il registro dei media player di Home Assistant.

`evoice.base_url`, `evoice.installation_id` ed `evoice.token` restano disponibili esclusivamente per usare l'API Media cloud come trasporto alternativo. Il browser comunica sempre soltanto con e-Face X4.
