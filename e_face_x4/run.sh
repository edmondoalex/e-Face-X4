#!/usr/bin/with-contenv bash
set -euo pipefail

if [[ -f /homeassistant/configuration.yaml ]]; then
  ha_config_root=/homeassistant
elif [[ -f /config/configuration.yaml ]]; then
  ha_config_root=/config
else
  echo "[e-Face] Configurazione Home Assistant non montata; componente Alexa non installabile."
  ha_config_root=/homeassistant
fi
export EFACE_HA_CONFIG_ROOT="$ha_config_root"
component_target="$ha_config_root/custom_components/eface_alexa"
mkdir -p "$(dirname "$component_target")"
if ! diff -qr /app/custom_components/eface_alexa "$component_target" >/dev/null 2>&1; then
  mkdir -p "$component_target"
  cp -R /app/custom_components/eface_alexa/. "$component_target/"
  echo "[e-Face] Componente Alexa diretto installato/aggiornato. Riavviare Home Assistant Core una volta per caricarlo."
fi
ha_configuration="$ha_config_root/configuration.yaml"
if [[ -f "$ha_configuration" ]] && ! grep -Eq '^[[:space:]]*eface_alexa[[:space:]]*:' "$ha_configuration"; then
  printf '\n# Servizi Alexa diretti installati da e-Control\neface_alexa:\n' >> "$ha_configuration"
  echo "[e-Face] Servizi Alexa diretti attivati. Riavviare Home Assistant Core una volta."
fi

# A fresh Python integration cannot be loaded into an already running Core.
# The helper restarts Core once only when its services are still absent.
/opt/venv/bin/python -m app.component_bootstrap &

cd /app
exec /opt/venv/bin/python -m app.main
