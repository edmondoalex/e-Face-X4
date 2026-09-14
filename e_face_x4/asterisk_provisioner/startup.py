"""Pre-Asterisk startup reconciliation for a future controlled add-on.

Call only after TECH7Fox has restored persistent custom config symlinks and
before the Asterisk service starts. The current live add-on does not call it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .include_migration import PjsipIncludeMigration
from .managed_config import ManagedConfig


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
    managed = ManagedConfig(config_root / "eface")
    managed.reconcile_file()
    migration = PjsipIncludeMigration(config_root)
    installed = migration.install(lambda: None)
    if not migration.managed.is_file() or migration.line not in [
        line.strip() for line in migration.custom.read_bytes().splitlines()
    ]:
        raise RuntimeError("Include PJSIP e-Face non confermato")
    return installed
