"""Attach the managed PJSIP file after upstream restores custom configs."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

INCLUDE = "#include /config/asterisk/eface/pjsip.conf"


def ensure_include(active: Path, custom_root: Path) -> bool:
    """Return true if already present, else back up and update a custom file."""
    root = custom_root.resolve(strict=True)
    target = active.resolve(strict=True)
    content = target.read_text(encoding="utf-8")
    if INCLUDE in content.splitlines():
        return False
    if not active.is_symlink() or target.parent != root or target.name != "pjsip.conf":
        raise RuntimeError("Include e-Face assente da un pjsip.conf non gestibile")
    backup = root / "pjsip.conf.before-eface.bak"
    if not backup.exists():
        shutil.copy2(target, backup)
        os.chmod(backup, 0o600)
    with target.open("a", encoding="utf-8", newline="\n") as file:
        file.write(f"\n; Managed e-Face endpoints\n{INCLUDE}\n")
        file.flush()
        os.fsync(file.fileno())
    return True


if __name__ == "__main__":
    ensure_include(Path("/etc/asterisk/pjsip.conf"), Path("/config/asterisk/custom"))
