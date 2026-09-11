#!/usr/bin/with-contenv bash
set -euo pipefail

cd /app
exec /opt/venv/bin/python -m app.main

