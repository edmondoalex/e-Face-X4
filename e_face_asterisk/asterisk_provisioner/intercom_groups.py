"""Persistent e-Face intercom ring groups."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from .external_routes import reload_dialplan
from .managed_config import _atomic_write

_LOCK = threading.RLock()
_GROUP = re.compile(r"(?:828[0-9]|8290)\Z")
_MEMBER = re.compile(r"(?:829[1-9]|83[0-9]{2})\Z")
_INCLUDE = "#include /config/asterisk/eface/intercom_groups.conf"
_DEFAULT = [{"extension": "8290", "name": "Tutti", "members": ["8291", "8292"]}]


def validate(groups: object) -> list[dict]:
    if not isinstance(groups, list) or len(groups) > 11:
        raise ValueError("Massimo undici gruppi Intercom")
    result, used = [], set()
    for item in groups:
        if not isinstance(item, dict) or set(item) != {"extension", "name", "members"}:
            raise ValueError("Dati gruppo incompleti")
        extension, name, members = item["extension"], item["name"], item["members"]
        if not isinstance(extension, str) or not _GROUP.fullmatch(extension) or extension in used:
            raise ValueError("Numero gruppo non valido o duplicato")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 48:
            raise ValueError("Nome gruppo non valido")
        if not isinstance(members, list) or len(members) > 48 or any(not isinstance(x, str) or not _MEMBER.fullmatch(x) for x in members):
            raise ValueError("Interni del gruppo non validi")
        used.add(extension)
        result.append({"extension": extension, "name": name.strip(), "members": sorted(set(members))})
    return sorted(result, key=lambda x: x["extension"])


def render(groups: object) -> str:
    lines = ["; Gruppi Intercom gestiti da e-Face.\n"]
    values = validate(groups)
    for group in values:
        if group["extension"] != "8290":
            lines.append(f"exten => {group['extension']},1,Goto(eface-groups,{group['extension']},1)\n")
    lines.append("\n[eface-groups]\n")
    for group in values:
        targets = "&".join(f"Local/{member}@eface-test/n" for member in group["members"])
        lines.append(f"exten => {group['extension']},1,Dial({targets},40)\n" if targets else f"exten => {group['extension']},1,Hangup()\n")
    return "".join(lines)


class IntercomGroups:
    def __init__(self, root: Path):
        self.directory = root / "eface"
        self.source = root / "custom" / "extensions.conf"
        self.state = self.directory / "intercom_groups.json"
        self.generated = self.directory / "intercom_groups.conf"
        self.backup = self.directory / "extensions.before-intercom-groups.bak"

    def load(self) -> list[dict]:
        try: return validate(json.loads(self.state.read_text(encoding="utf-8")))
        except FileNotFoundError: return validate(_DEFAULT)

    def ensure(self, reload=reload_dialplan) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.state.exists(): _atomic_write(self.state, json.dumps(_DEFAULT, ensure_ascii=False))
        expected = render(self.load())
        previous_generated = self.generated.read_text(encoding="utf-8") if self.generated.exists() else None
        generated_changed = previous_generated != expected
        if generated_changed: _atomic_write(self.generated, expected)
        current = self.source.read_text(encoding="utf-8")
        include_present = _INCLUDE in current.splitlines()
        legacy = re.compile(r"^exten\s*=>\s*8290,1,Dial\([^\r\n]*\)\s*$", re.MULTILINE)
        goto = "exten => 8290,1,Goto(eface-groups,8290,1)"
        migrated = goto in current.splitlines()
        if not migrated and not legacy.search(current):
            raise RuntimeError("Rotta legacy 8290 non riconosciuta")
        updated = legacy.sub(goto, current, count=1) if not migrated else current
        if not include_present:
            lines = updated.splitlines(keepends=True)
            start = next((i for i,x in enumerate(lines) if x.strip() == "[eface-test]"), -1)
            if start < 0: raise RuntimeError("Contesto eface-test non trovato")
            end = next((i for i in range(start+1,len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
            lines.insert(end, _INCLUDE + "\n"); updated = "".join(lines)
        source_changed = updated != current
        if source_changed:
            if not self.backup.exists(): _atomic_write(self.backup, current)
            _atomic_write(self.source, updated)
        if source_changed or generated_changed:
            try: reload()
            except Exception:
                if source_changed: _atomic_write(self.source, current)
                if previous_generated is None: self.generated.unlink(missing_ok=True)
                else: _atomic_write(self.generated, previous_generated)
                reload(); raise

    def replace(self, groups: object, reload=reload_dialplan) -> list[dict]:
        updated = validate(groups)
        with _LOCK:
            self.ensure(reload); previous = self.load()
            try:
                _atomic_write(self.state, json.dumps(updated, ensure_ascii=False))
                _atomic_write(self.generated, render(updated)); reload()
            except Exception:
                _atomic_write(self.state, json.dumps(previous, ensure_ascii=False)); _atomic_write(self.generated, render(previous)); reload(); raise
        return updated
