"""Pre-Asterisk startup reconciliation for a future controlled add-on.

Call only after TECH7Fox has restored persistent custom config symlinks and
before the Asterisk service starts. The current live add-on does not call it.
"""

from __future__ import annotations

import subprocess
import socket
import sys
import ipaddress
import os
from pathlib import Path

from .include_migration import PjsipIncludeMigration
from .managed_config import ManagedConfig


def assert_asterisk_ports_free(ports: tuple[tuple[int, int], ...] | None = None) -> None:
    """Fail before migration if another PBX occupies standard host ports."""
    if ports is None:
        ports = ((socket.SOCK_DGRAM, 5060), (socket.SOCK_STREAM, 8088), (socket.SOCK_STREAM, 8089))
    for kind, port in ports:
        if kind == socket.SOCK_STREAM:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check:
                check.settimeout(0.3)
                if check.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Porta Asterisk {port} occupata: altro PBX attivo")
        with socket.socket(socket.AF_INET, kind) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(("0.0.0.0", port))
            except OSError as error:
                raise RuntimeError(f"Porta Asterisk {port} occupata: altro PBX attivo") from error


def assert_private_bind_host(host: str) -> None:
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as error:
        raise ValueError("Indirizzo provisioner non valido") from error
    if address.is_unspecified or address.is_multicast or not address.is_private or address.is_loopback:
        raise ValueError("Indirizzo provisioner deve essere IPv4 privato non loopback")


def asterisk_is_running() -> bool:
    try:
        result = subprocess.run(
            ["asterisk", "-rx", "core show uptime"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def prepare_before_asterisk(config_root: Path = Path("/config/asterisk")) -> bool:
    """Recover e-Face state, then install one persistent include if needed.

    Returns True only when this boot adds the include. No CLI reload is used:
    this function must run in cont-init, before Asterisk starts.
    """
    if asterisk_is_running():
        raise RuntimeError("Asterisk è già avviato: migrazione pre-avvio rifiutata")
    assert_asterisk_ports_free()
    managed = ManagedConfig(config_root / "eface")
    managed.reconcile_file()
    migration = PjsipIncludeMigration(config_root)
    installed = migration.install(lambda: None)
    if not migration.managed.is_file() or migration.line not in [
        line.strip() for line in migration.custom.read_bytes().splitlines()
    ]:
        raise RuntimeError("Include PJSIP e-Face non confermato")
    return installed


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-only"]:
        assert_asterisk_ports_free()
    elif len(sys.argv) == 1:
        assert_private_bind_host(os.environ.get("EFACE_PROVISIONER_BIND_IP", ""))
        prepare_before_asterisk()
    else:
        raise SystemExit("Argomenti bootstrap non validi")
