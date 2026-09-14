"""Fail-closed runtime entrypoint for a future controlled Asterisk add-on."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .asterisk_adapter import endpoint_exists, reload_pjsip
from .identity import SiteIdentity
from .include_migration import PjsipIncludeMigration
from .managed_config import ManagedConfig, render
from .service import make_https_server
from .external_routes import ExternalRoutes, reload_dialplan
from .control4_routes import Control4Routes


def assert_ready(config_root: Path) -> ManagedConfig:
    """Read-only check that persisted config and running Asterisk agree."""
    config = ManagedConfig(config_root / "eface")
    migration = PjsipIncludeMigration(config_root)
    if config.pending.exists() or not migration.backup.is_file() or not migration.custom.is_file():
        raise RuntimeError("Provisioner non preparato o transazione incompleta")
    if migration.custom.read_bytes() != migration._with_include(migration.backup.read_bytes()):
        raise RuntimeError("Include PJSIP persistente non valido")
    if not config.pjsip.is_file() or config.pjsip.read_text(encoding="utf-8") != render(config.load()):
        raise RuntimeError("Configurazione PJSIP e-Face non riconciliata")
    result = subprocess.run(
        ["asterisk", "-rx", "core waitfullybooted"],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Asterisk non pronto")
    for record in config.load().values():
        if not endpoint_exists(str(record["extension"])):
            raise RuntimeError("Interno persistente assente in Asterisk")
    return config


def serve(config_root: Path, bind_host: str, port: int) -> None:
    config = assert_ready(config_root)
    external_routes = ExternalRoutes(config_root)
    external_routes.ensure(reload_dialplan)
    control4_routes = Control4Routes(config_root)
    control4_routes.ensure(reload_dialplan)
    identity = SiteIdentity(config_root / "eface").ensure()
    with make_https_server(
        config, identity.token, reload_pjsip, endpoint_exists,
        bind_host, port, identity.certificate, identity.private_key, external_routes, control4_routes,
    ) as server:
        server.serve_forever()


if __name__ == "__main__":
    host = os.environ.get("EFACE_PROVISIONER_BIND_IP", "")
    port = int(os.environ.get("EFACE_PROVISIONER_PORT", "9443"))
    serve(Path("/config/asterisk"), host, port)
