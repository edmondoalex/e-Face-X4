"""Persistent dialplan include for e-Face managed registered VoIP phones."""

from __future__ import annotations

from pathlib import Path

from .external_routes import reload_dialplan
from .managed_config import _atomic_write

_INCLUDE = "#include /config/asterisk/eface/voip_routes.conf"
_CONTENT = (
    "; Telefoni VoIP gestiti da e-Face.\n"
    "exten => 8301,1,Dial(PJSIP/8301,40)\n"
    "exten => _830[2-9],1,Dial(PJSIP/${EXTEN},40)\n"
    "exten => _83[1-4]X,1,Dial(PJSIP/${EXTEN},40)\n"
    "exten => _83[5-9]X,1,Dial(PJSIP/${EXTEN},40)\n"
)


class VoipRoutes:
    def __init__(self, config_root: Path):
        self.directory = config_root / "eface"
        self.source = config_root / "custom" / "extensions.conf"
        self.generated = self.directory / "voip_routes.conf"
        self.backup = self.directory / "extensions.before-voip-routes.bak"

    def ensure(self, reload=reload_dialplan) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        previous_generated = self.generated.read_text(encoding="utf-8") if self.generated.exists() else None
        changed = previous_generated != _CONTENT
        if changed:
            _atomic_write(self.generated, _CONTENT)
        current = self.source.read_text(encoding="utf-8")
        if _INCLUDE in current.splitlines():
            if changed:
                try:
                    reload()
                except Exception:
                    if previous_generated is not None:
                        _atomic_write(self.generated, previous_generated)
                    raise
            return
        if self.backup.exists():
            raise RuntimeError("Include telefoni VoIP rimosso dopo installazione")
        lines = current.splitlines(keepends=True)
        start = next((i for i, line in enumerate(lines) if line.strip() == "[eface-test]"), -1)
        if start < 0:
            raise RuntimeError("Contesto eface-test non trovato")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        _atomic_write(self.backup, current)
        lines.insert(end, _INCLUDE + "\n")
        try:
            _atomic_write(self.source, "".join(lines))
            reload()
        except Exception:
            _atomic_write(self.source, current)
            self.backup.unlink(missing_ok=True)
            raise
