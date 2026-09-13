#!/usr/bin/env bash
set -euo pipefail

smoke_root="$(mktemp -d)"
mkdir -p "$smoke_root/asterisk" "$smoke_root/data"
cleanup() {
  docker rm -f eface-asterisk-ci >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_container() {
  docker run --detach --name eface-asterisk-ci \
    -e EFACE_PROVISION_BIND=0.0.0.0 \
    -v "$PWD/e_asterisk/tests/config.json:/config/config.json:ro" \
    -v "$smoke_root/asterisk:/config/asterisk" \
    -v "$smoke_root/data:/data" \
    -v "$PWD/e_asterisk/tests/container_flow.py:/tmp/container_flow.py:ro" \
    eface-asterisk-smoke >/dev/null
  for attempt in $(seq 1 60); do
    if docker exec eface-asterisk-ci python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8350/v1/health", timeout=2)' >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  docker logs eface-asterisk-ci
  return 1
}

start_container
if ! docker exec eface-asterisk-ci python3 /tmp/container_flow.py provision; then
  docker logs eface-asterisk-ci
  exit 1
fi
docker rm -f eface-asterisk-ci >/dev/null
start_container
if ! docker exec eface-asterisk-ci python3 /tmp/container_flow.py verify; then
  docker logs eface-asterisk-ci
  exit 1
fi
