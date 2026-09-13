#!/usr/bin/with-contenv bash
set -euo pipefail
PYTHONPATH=/opt/eface-provisioner python3 -c 'from pathlib import Path; from managed_config import ManagedConfig; ManagedConfig(Path("/config/asterisk/eface")).reconcile_file()'
