"""One-time, persistent PJSIP include migration for a controlled add-on.

Never invoked by the current e-Face/Asterisk add-ons. The future installer
must run this inside Asterisk before accepting provisioning requests.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Callable


def _write_exact(path: Path, data: bytes, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as output:
            os.chmod(temporary, mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
        if os.name == "posix":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class PjsipIncludeMigration:
    """Only touches custom/pjsip_custom.conf and its e-Face-owned backup."""

    def __init__(self, config_root: Path) -> None:
        self.root = config_root
        self.custom = config_root / "custom" / "pjsip_custom.conf"
        self.eface = config_root / "eface"
        self.managed = self.eface / "pjsip.conf"
        self.backup = self.eface / "pjsip_custom.before-eface.bak"
        self.line = f"#include {self.managed.as_posix()}".encode("ascii")

    def _preflight(self) -> None:
        if not self.root.is_dir() or self.root.is_symlink():
            raise RuntimeError("Volume Asterisk persistente non disponibile")
        if self.eface.is_symlink() or not self.eface.is_dir():
            raise RuntimeError("Directory e-Face persistente non disponibile")
        if self.custom.parent.is_symlink() or self.custom.is_symlink() or not self.custom.is_file():
            raise RuntimeError("File PJSIP custom persistente non disponibile")
        if self.managed.is_symlink() or not self.managed.is_file():
            raise RuntimeError("File PJSIP e-Face non disponibile")
        if self.backup.is_symlink():
            raise RuntimeError("Backup PJSIP non valido")

    def _with_include(self, original: bytes) -> bytes:
        separator = b"" if not original or original.endswith((b"\n", b"\r")) else b"\n"
        return original + separator + self.line + b"\n"

    def install(self, reload_pjsip: Callable[[], None]) -> bool:
        """Append exactly one include; restore original bytes if reload fails."""
        self._preflight()
        current = self.custom.read_bytes()
        lines = [line.strip() for line in current.splitlines()]
        if self.line in lines:
            if lines.count(self.line) != 1:
                raise RuntimeError("Include e-Face duplicato nel file PJSIP custom")
            # The include itself is the startup invariant. Existing installations
            # may contain later user/upstream additions or may predate the owned
            # backup. Never rewrite those files merely to recover provenance;
            # rollback remains fail-closed unless an exact backup is available.
            return False
        if self.backup.exists():
            original = self.backup.read_bytes()
            if current != original:
                raise RuntimeError("File PJSIP custom cambiato dopo il backup")
        else:
            original = current
            _write_exact(self.backup, original, 0o600)
        mode = self.custom.stat().st_mode & 0o777
        if self.custom.read_bytes() != original:
            raise RuntimeError("File PJSIP custom cambiato durante la migrazione")
        try:
            _write_exact(self.custom, self._with_include(original), mode)
            reload_pjsip()
        except Exception:
            _write_exact(self.custom, original, mode)
            try:
                reload_pjsip()
            except Exception:
                pass  # Preserve the backup; installer must halt and inspect.
            raise
        return True

    def rollback(self, reload_pjsip: Callable[[], None]) -> bool:
        """Restore exact pre-migration bytes; refuse to erase later changes."""
        self._preflight()
        if not self.backup.is_file():
            raise RuntimeError("Backup PJSIP mancante")
        original = self.backup.read_bytes()
        current = self.custom.read_bytes()
        if current == original:
            return False
        if current != self._with_include(original):
            raise RuntimeError("File PJSIP custom modificato dopo la migrazione")
        mode = self.custom.stat().st_mode & 0o777
        _write_exact(self.custom, original, mode)
        reload_pjsip()
        return True
