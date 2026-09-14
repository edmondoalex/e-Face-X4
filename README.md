# e-Face X4

Add-on Home Assistant che concentra in un'unica interfaccia i servizi e gli add-on e-Konex.

e-Face X4 non incorpora i motori degli add-on collegati: ogni integrazione rimane responsabile
dei propri dati e comandi. Il concentratore usa connettori isolati e presenta un modello uniforme
alla dashboard.

## Prima fondazione

- add-on Home Assistant con Ingress;
- interfaccia responsive per desktop, tablet e telefono;
- modalità demo esplicita, disattivabile dalle opzioni;
- connettore HTTP iniziale per e-HDL BusPro MQTT;
- endpoint di salute e diagnostica senza esposizione di credenziali;
- timeout, validazione delle risposte e degradazione controllata quando un add-on è offline.

La cartella `Progettazione UI` contiene esclusivamente i riferimenti originali di progetto.

Per riprendere lo sviluppo Control4/HA senza ripetere la diagnosi iniziale, seguire la [procedura operativa audio, video e accesso al controller](docs/PROCEDURA_CONTROL4_HASSIO_SVILUPPO.md). Il videocitofono SIP/DoorBird è un percorso separato, documentato nella stessa procedura e nel [task di installazione](docs/TASK_INSTALLAZIONE_PLUG_AND_PLAY.md).

## Sviluppo locale

```powershell
cd e_face_x4
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:EFACE_OPTIONS = (Resolve-Path .\dev-options.json)
.venv\Scripts\python -m app.main
```

Aprire `http://127.0.0.1:8099`.
