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

Disattivare la modalità demo solo quando almeno un connettore reale è stato configurato.
Per il primo connettore impostare:

- `buspro.enabled`: abilita il collegamento;
- `buspro.base_url`: indirizzo locale dell'add-on, normalmente `http://IP_HOME_ASSISTANT:8124`;
- `buspro.token`: valorizzare solo se e-HDL BusPro MQTT utilizza autenticazione token.

Il token resta nel file delle opzioni dell'add-on e non viene restituito al browser.

## Collegamento Ekonex Media

Per abilitare le pagine **Guarda** e **Ascolta** in locale configurare soltanto:

- `evoice.enabled`: abilita il collegamento;

Lasciare vuoti `evoice.base_url`, `evoice.installation_id` ed `evoice.token`. e-Face usa
automaticamente il collegamento interno protetto di Home Assistant/Supervisor; non servono IP,
porte o credenziali manuali.

I tre campi opzionali permettono in futuro di usare il backend cloud Ekonex Media. In quel caso
`base_url` è l'indirizzo del backend senza il suffisso `/api/media/v1`.

Le credenziali restano nell'add-on. Il browser comunica esclusivamente con e-Face X4. Gli
aggiornamenti arrivano dallo stream realtime; lo snapshot periodico viene usato come recupero.

La versione 0.1.0 non invia ancora comandi agli add-on collegati: il primo connettore viene usato
per verificare disponibilità e contratto dei dati prima di abilitare il controllo reale.
