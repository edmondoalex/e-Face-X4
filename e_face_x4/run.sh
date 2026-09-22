#!/usr/bin/with-contenv bash
set -euo pipefail

component_target=/homeassistant/custom_components/eface_alexa
mkdir -p "$(dirname "$component_target")"
if ! diff -qr /app/custom_components/eface_alexa "$component_target" >/dev/null 2>&1; then
  mkdir -p "$component_target"
  cp -R /app/custom_components/eface_alexa/. "$component_target/"
  echo "[e-Face] Componente Alexa diretto installato/aggiornato. Riavviare Home Assistant Core una volta per caricarlo."
fi
ha_configuration=/homeassistant/configuration.yaml
if [[ -f "$ha_configuration" ]] && ! grep -Eq '^[[:space:]]*eface_alexa[[:space:]]*:' "$ha_configuration"; then
  printf '\n# Servizi Alexa diretti installati da e-Control\neface_alexa:\n' >> "$ha_configuration"
  echo "[e-Face] Servizi Alexa diretti attivati. Riavviare Home Assistant Core una volta."
fi

cd /app
exec /opt/venv/bin/python -m app.main
