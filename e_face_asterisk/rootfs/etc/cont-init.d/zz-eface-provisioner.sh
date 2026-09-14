#!/usr/bin/with-contenv bashio
set -euo pipefail

# Runs after upstream asterisk.sh has restored /config/asterisk/custom.
# Even with provisioning disabled, do not start a second PBX on host ports.
if bashio::var.true "$(bashio::config 'eface_provisioner_enabled')"; then
    bind_ip="$(bashio::config 'eface_provisioner_bind_ip')"
    if [[ -z "${bind_ip}" ]]; then
        bashio::exit.nok "e-Face provisioner requires a private bind IP"
    fi
    EFACE_PROVISIONER_BIND_IP="${bind_ip}" PYTHONPATH=/opt/eface python3 -m asterisk_provisioner.startup
    rm -f /etc/services.d/eface_provisioner/down
else
    PYTHONPATH=/opt/eface python3 -m asterisk_provisioner.startup --check-only
fi
