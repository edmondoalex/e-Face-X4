"""Personal SIP credentials; provisioning to Asterisk is an explicit step."""

from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path

_LOCK = threading.RLock()


def _path() -> Path:
    return Path(os.environ.get("EFACE_SIP_ACCOUNTS", "/data/sip_accounts.json"))


def load() -> dict[str, dict]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save(value: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"sip_accounts.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            os.chmod(temporary, 0o600)
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def allocate(username: str) -> dict:
    with _LOCK:
        accounts = load()
        if username in accounts:
            return accounts[username]
        used = {str(record.get("extension")) for record in accounts.values() if isinstance(record, dict)}
        # 8350-8399 are reserved for generic registered VoIP phones.
        extension = next((str(number) for number in range(8302, 8350) if str(number) not in used), None)
        if extension is None:
            raise ValueError("Nessun interno SIP disponibile")
        record = {"extension": extension, "password": secrets.token_urlsafe(36), "provisioned": False}
        accounts[username] = record
        _save(accounts)
        return record


def mark_provisioned(username: str, enabled: bool) -> dict:
    with _LOCK:
        accounts = load()
        if username not in accounts:
            raise ValueError("Interno SIP non assegnato")
        accounts[username]["provisioned"] = enabled
        _save(accounts)
        return accounts[username]


def asterisk_stanza(extension: str, password: str, display_name: str) -> str:
    if not extension.isdigit() or not 8302 <= int(extension) <= 8399:
        raise ValueError("Interno SIP non valido")
    if not password or any(char in password for char in "\r\n"):
        raise ValueError("Password SIP non valida")
    display_name = "".join(char for char in display_name if char.isalnum() or char in " -_").strip()[:64] or "e-Face"
    return (
        f"[{extension}](sipjs-phone-aor)\nmax_contacts=1\n"
        f"[{extension}](sipjs-phone-auth)\nusername={extension}\npassword={password}\n"
        f"[{extension}](sipjs-phone-endpoint)\naors={extension}\nauth={extension}\n"
        f'callerid="{display_name}" <{extension}>\ncontext=eface-test\nallow=opus,alaw,ulaw\n'
    )
