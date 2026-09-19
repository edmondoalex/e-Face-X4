"""Constrained customer routines with an attributable, bounded audit trail."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

MAX_STEPS = 20
MAX_WAIT_SECONDS = 3600
LOG_DAYS = 15
MAX_LOG_ROWS = 20_000
MAX_DB_BYTES = 50 * 1024 * 1024
SAFE_ACTIONS = {
    "light": {"on", "off", "brightness"},
    "switch": {"on", "off"},
    "media_player": {"media_play", "media_pause", "media_stop", "turn_off", "set_volume", "volume_mute", "volume_unmute"},
    "climate": {"set_target"},
    "cover": {"open", "close", "stop"},
}
ACTION_STATES = {"on": "on", "off": "off", "open": "open", "close": "closed", "media_play": "playing",
                 "media_pause": "paused", "media_stop": "idle", "turn_off": "off"}
ACTION_LABELS = {"on": "accendere", "off": "spegnere", "brightness": "regolare la luminosità", "open": "aprire",
                 "close": "chiudere", "stop": "fermare", "media_play": "avviare la riproduzione",
                 "media_pause": "mettere in pausa", "media_stop": "fermare la riproduzione",
                 "turn_off": "spegnere la stanza", "set_volume": "regolare il volume",
                 "volume_mute": "silenziare", "volume_unmute": "riattivare l'audio", "set_target": "impostare la temperatura"}
SENSITIVE_WORDS = re.compile(r"porta|portone|cancello|garage|serratura|allarme|alarm|gate|door|lock", re.I)
SECRET_TEXT = re.compile(r"(?i)(password|token|secret|authorization)\s*[:=]\s*\S+|https?://\S+")


def _path() -> Path:
    return Path(os.environ.get("EFACE_ROUTINES_DB", "/data/routines.sqlite3"))


class _Connection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def _connect() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, factory=_Connection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS routines (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
            spec TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL,
            last_trigger_key TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS routine_runs (
            id TEXT PRIMARY KEY, routine_id TEXT NOT NULL, owner TEXT NOT NULL,
            name TEXT NOT NULL, revision INTEGER NOT NULL, trigger_detail TEXT NOT NULL,
            started_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS routine_revisions (
            routine_id TEXT NOT NULL, revision INTEGER NOT NULL, actor TEXT NOT NULL,
            at TEXT NOT NULL, spec TEXT NOT NULL, PRIMARY KEY(routine_id, revision)
        );
        CREATE TABLE IF NOT EXISTS routine_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            at TEXT NOT NULL, stage TEXT NOT NULL, device_id TEXT NOT NULL DEFAULT '',
            device_name TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '', before_state TEXT NOT NULL DEFAULT '',
            after_state TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS routine_runs_recent ON routine_runs(started_at DESC);
        CREATE INDEX IF NOT EXISTS routine_events_device ON routine_events(device_id, at DESC);
        CREATE INDEX IF NOT EXISTS routine_events_run ON routine_events(run_id, id);
    """)
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state(device: dict | None) -> str:
    value = (device or {}).get("state")
    return str(value).casefold() if value is not None else ""


def _row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["enabled"] = bool(data["enabled"])
    data["spec"] = json.loads(data["spec"])
    return data


def list_routines(owner: str | None = None, enabled_only: bool = False) -> list[dict]:
    with _connect() as db:
        clauses, args = [], []
        if owner is not None:
            clauses.append("owner = ?")
            args.append(owner)
        if enabled_only:
            clauses.append("enabled = 1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return [_row(row) for row in db.execute("SELECT * FROM routines" + where + " ORDER BY updated_at DESC", args)]


def get_routine(routine_id: str, owner: str | None = None) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM routines WHERE id = ?" + (" AND owner = ?" if owner is not None else ""),
                         (routine_id, owner) if owner is not None else (routine_id,)).fetchone()
        return _row(row) if row else None


def _condition(raw: object, devices: dict[str, dict], errors: list[str]) -> dict | None:
    if not isinstance(raw, dict):
        errors.append("Condizione non valida")
        return None
    device_id = str(raw.get("device_id") or "")
    operator = str(raw.get("operator") or "is")
    value = str(raw.get("value") or "").strip().casefold()[:80]
    if device_id not in devices or operator not in {"is", "is_not"} or not value:
        errors.append(f"Condizione non valida per {device_id or 'dispositivo mancante'}")
        return None
    return {"device_id": device_id, "operator": operator, "value": value}


def validate(payload: dict, devices: list[dict], others: list[dict] = ()) -> dict:
    """Validate against the live installation; never trust client-provided capabilities."""
    errors: list[str] = []
    warnings: list[str] = []
    catalog = {str(item.get("id")): item for item in devices if isinstance(item, dict) and item.get("id")}
    name = str(payload.get("name") or "").strip()[:80]
    if not 1 <= len(name) <= 80:
        errors.append("Assegna un nome alla routine")
    raw_triggers = payload.get("triggers")
    if not isinstance(raw_triggers, list) or not 1 <= len(raw_triggers) <= 4:
        errors.append("Servono da 1 a 4 attivazioni")
        raw_triggers = []
    triggers = []
    for raw in raw_triggers:
        if not isinstance(raw, dict):
            errors.append("Attivazione non valida")
            continue
        if raw.get("type") == "time":
            at = str(raw.get("at") or "")
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", at):
                errors.append("Orario di attivazione non valido")
            else:
                triggers.append({"type": "time", "at": at})
        elif raw.get("type") == "doorbird":
            event = str(raw.get("event") or "")
            if event not in {"doorbell", "motionsensor"}:
                errors.append("Evento DoorBird non valido")
            else:
                triggers.append({"type": "doorbird", "event": event})
        elif raw.get("type") == "state":
            device_id = str(raw.get("device_id") or "")
            target = str(raw.get("to") or "").strip().casefold()[:80]
            if device_id not in catalog or not target:
                errors.append(f"Attivazione non valida per {device_id or 'dispositivo mancante'}")
            else:
                triggers.append({"type": "state", "device_id": device_id, "to": target})
        else:
            errors.append("Tipo di attivazione non supportato")
    raw_conditions = payload.get("conditions", [])
    if not isinstance(raw_conditions, list) or len(raw_conditions) > 8:
        errors.append("Massimo 8 condizioni iniziali")
        raw_conditions = []
    conditions = [item for raw in raw_conditions if (item := _condition(raw, catalog, errors))]
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
        errors.append(f"Servono da 1 a {MAX_STEPS} blocchi in Allora")
        raw_steps = []
    steps = []
    total_wait = 0
    actions: list[tuple[str, str]] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            errors.append("Blocco non valido")
            continue
        kind = raw.get("type")
        if kind == "wait":
            seconds = raw.get("seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= MAX_WAIT_SECONDS:
                errors.append("Il timer deve durare da 1 secondo a 60 minuti")
                continue
            total_wait += seconds
            steps.append({"type": "wait", "seconds": seconds})
        elif kind == "check":
            condition = _condition(raw, catalog, errors)
            if condition:
                steps.append({"type": "check", **condition})
        elif kind == "action":
            device_id = str(raw.get("device_id") or "")
            action = str(raw.get("action") or "")
            device = catalog.get(device_id)
            if not device:
                errors.append(f"Dispositivo {device_id or 'mancante'} non presente nell'impianto")
                continue
            device_kind = str(device.get("kind") or "")
            identity = " ".join(str(device.get(key) or "") for key in ("id", "entity_id", "name", "room"))
            if device_kind in {"lock", "alarm_system", "alarm_partition", "alarm_scenario", "alarm_zone"} or SENSITIVE_WORDS.search(identity):
                errors.append(f"{device.get('name')}: accessi e sicurezza non sono automatizzabili dal cliente")
                continue
            if action not in SAFE_ACTIONS.get(device_kind, set()):
                errors.append(f"{device.get('name')}: comando {action or 'mancante'} non consentito")
                continue
            caps = device.get("capabilities") or {}
            required_cap = {"media_play": "play", "media_pause": "pause", "media_stop": "stop", "turn_off": "turn_off", "set_volume": "set_volume", "volume_mute": "mute", "volume_unmute": "mute"}.get(action)
            if required_cap and not caps.get(required_cap):
                errors.append(f"{device.get('name')}: comando {action} non esposto dal dispositivo")
                continue
            value = raw.get("value")
            if action in {"brightness", "set_volume"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                    errors.append(f"{device.get('name')}: valore percentuale non valido")
                    continue
                value = round(float(value))
            elif action == "set_target":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 5 <= value <= 35:
                    errors.append(f"{device.get('name')}: temperatura fuori dai limiti 5–35 °C")
                    continue
                value = round(float(value), 1)
            else:
                value = None
            actions.append((device_id, action))
            steps.append({"type": "action", "device_id": device_id, "action": action, "value": value})
            if device_kind == "cover" and action in {"open", "close"}:
                warnings.append(f"{device.get('name')}: il movimento fisico della tenda/tapparella può sorprendere chi è vicino")
            if device_kind == "switch":
                warnings.append(f"{device.get('name')}: verifica che lo switch non alimenti un dispositivo critico")
            if action == "set_volume" and value is not None and value > 70:
                warnings.append(f"{device.get('name')}: volume elevato ({value}%) percepibile dalle persone presenti")
        else:
            errors.append("Tipo di blocco non supportato")
    if total_wait > MAX_WAIT_SECONDS:
        errors.append("La somma dei timer supera 60 minuti")
    if not actions:
        errors.append("Aggiungi almeno un'azione")
    for trigger in triggers:
        if trigger["type"] == "state" and any(device_id == trigger["device_id"] and ACTION_STATES.get(action) == trigger["to"] for device_id, action in actions):
            errors.append("La routine potrebbe riattivare sé stessa sullo stesso dispositivo")
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for other in [*others, {"spec": {"triggers": triggers, "steps": steps}, "enabled": True, "id": payload.get("id"), "candidate": True}]:
        if not other.get("enabled") or (other.get("id") == payload.get("id") and not other.get("candidate")):
            continue
        state_sources = [(item.get("device_id"), item.get("to")) for item in other.get("spec", {}).get("triggers", []) if item.get("type") == "state"]
        action_targets = [(item.get("device_id"), ACTION_STATES[item["action"]]) for item in other.get("spec", {}).get("steps", []) if item.get("type") == "action" and item.get("action") in ACTION_STATES]
        for source in state_sources:
            edges.setdefault(source, set()).update(action_targets)
    for source in edges:
        stack = [(source, set())]
        while stack:
            node, visited = stack.pop()
            if node in visited:
                errors.append("Possibile ciclo tra routine: un'azione può riattivare un'altra routine")
                stack.clear()
                break
            stack.extend((target, visited | {node}) for target in edges.get(node, ()) if target in edges)
        if any("ciclo tra routine" in error for error in errors):
            break
    for index, (device_id, action) in enumerate(actions[1:], 1):
        if device_id == actions[index - 1][0] and action != actions[index - 1][1]:
            warnings.append(f"{catalog[device_id].get('name')}: comandi diversi nella stessa routine; verifica i timer")
    for other in others:
        if not other.get("enabled") or other.get("id") == payload.get("id"):
            continue
        other_targets = {step.get("device_id") for step in other.get("spec", {}).get("steps", []) if step.get("type") == "action"}
        if other_targets.intersection(device_id for device_id, _ in actions):
            warnings.append(f"Interazione possibile con la routine «{other['name']}» sugli stessi dispositivi")
    if any(step["type"] == "check" for step in steps):
        warnings.append("Se una verifica intermedia non è soddisfatta, le azioni successive non verranno eseguite")
    normalized = {"name": name, "triggers": triggers, "conditions": conditions, "steps": steps}
    descriptions = []
    for trigger in triggers:
        if trigger["type"] == "time":
            descriptions.append(f"alle {trigger['at']}")
        elif trigger["type"] == "doorbird":
            descriptions.append("quando suona DoorBird" if trigger["event"] == "doorbell" else "quando DoorBird rileva movimento")
        else:
            descriptions.append(f"quando {catalog[trigger['device_id']].get('name')} diventa {trigger['to']}")
    narrative = "La casa avvierà la routine " + (" oppure ".join(descriptions) if descriptions else "solo dopo una configurazione valida") + ". "
    if conditions:
        narrative += "Prima controllerà " + ", ".join(f"{catalog[item['device_id']].get('name')} {item['operator'].replace('is_not', 'non è').replace('is', 'è')} {item['value']}" for item in conditions) + ". "
    for step in steps:
        if step["type"] == "wait":
            narrative += f"Poi attenderà {step['seconds']} secondi. "
        elif step["type"] == "check":
            narrative += f"Ricontrollerà {catalog[step['device_id']].get('name')}: se non è {step['value']}, interromperà il resto. "
        else:
            amount = f" a {step['value']}{' °C' if step['action'] == 'set_target' else '%'}" if step.get("value") is not None else ""
            narrative += f"Farà {ACTION_LABELS.get(step['action'], step['action'])} {catalog[step['device_id']].get('name')}{amount}. "
            device_kind = catalog[step["device_id"]].get("kind")
            if device_kind == "light" and step["action"] == "on":
                narrative += "Chi è nella stanza vedrà accendersi la luce. "
            elif device_kind == "media_player" and step["action"] in {"media_play", "set_volume", "volume_unmute"}:
                narrative += "Chi è nella stanza potrebbe sentire l'audio. "
            elif device_kind == "cover" and step["action"] in {"open", "close"}:
                narrative += "La tenda/tapparella si muoverà fisicamente. "
            elif device_kind == "climate":
                narrative += "La temperatura percepita cambierà gradualmente. "
    for device_id, action in actions:
        if action == "on" and not any(other_id == device_id and other_action == "off" for other_id, other_action in actions):
            narrative += f"{catalog[device_id].get('name')} resterà acceso finché non interviene un altro comando. "
    return {"spec": normalized, "errors": list(dict.fromkeys(errors)), "warnings": list(dict.fromkeys(warnings)), "description": narrative.strip(), "can_enable": not errors}


def save(owner: str, actor: str, routine_id: str | None, spec: dict, enabled: bool, expected_revision: int | None) -> dict:
    with _connect() as db:
        old = db.execute("SELECT owner, revision, enabled FROM routines WHERE id = ?", (routine_id,)).fetchone() if routine_id else None
        if old and old["owner"] != owner:
            raise PermissionError("Routine di un altro utente")
        if old and expected_revision != old["revision"]:
            raise RuntimeError("Routine modificata da un'altra sessione: ricarica prima di salvare")
        if routine_id and not old:
            raise LookupError("Routine non trovata")
        if not old and db.execute("SELECT COUNT(*) FROM routines WHERE owner = ?", (owner,)).fetchone()[0] >= 100:
            raise ValueError("Massimo 100 routine per utente")
        identifier = routine_id or str(uuid.uuid4())
        revision = old["revision"] + 1 if old else 1
        db.execute("""INSERT INTO routines(id, owner, name, enabled, revision, spec, updated_by, updated_at)
                      VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                      enabled=excluded.enabled, revision=excluded.revision, spec=excluded.spec,
                      updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                   (identifier, owner, spec["name"], int(enabled), revision, json.dumps(spec, ensure_ascii=False), actor, _now()))
        db.execute("INSERT INTO routine_revisions(routine_id, revision, actor, at, spec) VALUES(?,?,?,?,?)",
                   (identifier, revision, actor, _now(), json.dumps(spec, ensure_ascii=False)))
        if enabled and (not old or not old["enabled"]):
            local = datetime.now(ZoneInfo("Europe/Rome"))
            for trigger in spec["triggers"]:
                if trigger["type"] == "time" and trigger["at"] == local.strftime("%H:%M"):
                    db.execute("UPDATE routines SET last_trigger_key = ? WHERE id = ?",
                               (local.strftime("%Y-%m-%d %H:%M") + f":Orario {trigger['at']}", identifier))
                    break
    return get_routine(identifier, owner)


def delete(owner: str, routine_id: str) -> bool:
    with _connect() as db:
        return bool(db.execute("DELETE FROM routines WHERE id = ? AND owner = ?", (routine_id, owner)).rowcount)


def record_event(run_id: str, stage: str, *, device_id: str = "", device_name: str = "", action: str = "", detail: str = "", before_state: str = "", after_state: str = "", result: str = "") -> None:
    with _connect() as db:
        db.execute("INSERT INTO routine_events(run_id,at,stage,device_id,device_name,action,detail,before_state,after_state,result) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (run_id, _now(), stage, device_id, device_name, action, SECRET_TEXT.sub("[dato nascosto]", detail)[:400], before_state[:100], after_state[:100], result[:100]))


def list_runs(*, device_id: str = "", routine_id: str = "", limit: int = 100) -> list[dict]:
    clauses, args = [], []
    if routine_id:
        clauses.append("r.routine_id = ?")
        args.append(routine_id)
    if device_id:
        clauses.append("EXISTS (SELECT 1 FROM routine_events e WHERE e.run_id = r.id AND (e.device_id = ? OR lower(e.device_name) LIKE lower(?) ESCAPE '\\'))")
        args.extend((device_id, "%" + device_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connect() as db:
        runs = [dict(row) for row in db.execute("SELECT r.*, v.actor AS modified_by, v.at AS modified_at FROM routine_runs r LEFT JOIN routine_revisions v ON v.routine_id = r.routine_id AND v.revision = r.revision" + where + " ORDER BY r.started_at DESC LIMIT ?", (*args, min(max(limit, 1), 200)))]
        for run in runs:
            run["events"] = [dict(row) for row in db.execute("SELECT * FROM routine_events WHERE run_id = ? ORDER BY id", (run["id"],))]
        return runs


def prune() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOG_DAYS)).isoformat()
    with _connect() as db:
        db.execute("DELETE FROM routine_events WHERE run_id IN (SELECT id FROM routine_runs WHERE started_at < ?)", (cutoff,))
        db.execute("DELETE FROM routine_runs WHERE started_at < ?", (cutoff,))
        db.execute("""DELETE FROM routine_revisions WHERE at < ?
                      AND NOT EXISTS (SELECT 1 FROM routines r WHERE r.id = routine_revisions.routine_id AND r.revision = routine_revisions.revision)
                      AND NOT EXISTS (SELECT 1 FROM routine_runs x WHERE x.routine_id = routine_revisions.routine_id AND x.revision = routine_revisions.revision)""", (cutoff,))
        row = db.execute("SELECT id FROM routine_events ORDER BY id DESC LIMIT 1 OFFSET ?", (MAX_LOG_ROWS,)).fetchone()
        if row:
            db.execute("DELETE FROM routine_events WHERE id <= ?", (row["id"],))
            db.execute("DELETE FROM routine_runs WHERE id NOT IN (SELECT DISTINCT run_id FROM routine_events)")
    for _ in range(20):
        if not _path().exists() or _path().stat().st_size <= MAX_DB_BYTES:
            break
        with _connect() as db:
            oldest = db.execute("SELECT id FROM routine_runs ORDER BY started_at LIMIT 100").fetchall()
            if not oldest:
                break
            ids = [row["id"] for row in oldest]
            db.executemany("DELETE FROM routine_events WHERE run_id = ?", ((identifier,) for identifier in ids))
            db.executemany("DELETE FROM routine_runs WHERE id = ?", ((identifier,) for identifier in ids))
        with _connect() as db:
            db.execute("VACUUM")


class Engine:
    def __init__(self, snapshot: Callable[[], Awaitable[list[dict]]], command: Callable[[str, str, object], Awaitable[object]]):
        self.snapshot = snapshot
        self.command = command
        self.previous: dict[str, str] = {}
        self.running: dict[str, asyncio.Task] = {}
        self.external_cooldowns: dict[tuple[str, str], float] = {}
        self.last_prune = 0.0
        self.buspro_by_state_key: dict[str, str] = {}
        self.buspro_live = False
        self.ksenia_live = False

    async def ksenia_event(self, items: list[dict]) -> None:
        changed: list[tuple[str, str]] = []
        by_id = {str(item["id"]): item for item in items if item.get("id") is not None}
        for identifier, item in by_id.items():
            state = _state(item)
            prior = self.previous.get(identifier)
            self.previous[identifier] = state
            if prior is not None and prior != state:
                changed.append((identifier, state))
        if not changed:
            return
        matching = [(routine, identifier, state) for routine in list_routines(enabled_only=True)
                    for identifier, state in changed if any(
                        trigger["type"] == "state" and trigger["device_id"] == identifier and trigger["to"] == state
                        for trigger in routine["spec"]["triggers"])]
        if not matching:
            return
        devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id") is not None}
        devices.update(by_id)
        for routine, identifier, state in matching:
            self._start(routine, f"{by_id[identifier].get('name') or identifier} → {state}",
                        f"ksenia:{identifier}:{uuid.uuid4()}", devices)

    def configure_buspro(self, devices: list[dict]) -> None:
        self.buspro_by_state_key = {str(item["state_key"]).casefold(): str(item["id"])
                                     for item in devices if item.get("state_key") and item.get("id") is not None}
        for item in devices:
            if str(item.get("id")) in self.buspro_by_state_key.values():
                self.previous[str(item["id"])] = _state(item)

    async def buspro_event(self, event: dict) -> None:
        data = event.get("data")
        if not isinstance(data, dict):
            return
        key = str(data.get("entity_id") or "").casefold() or ".".join(
            str(data.get(part)) for part in ("subnet_id", "device_id", "channel"))
        identifier = self.buspro_by_state_key.get(key)
        value = data.get("state", data.get("value"))
        if not identifier or value is None:
            return
        state = str(value).casefold()
        prior = self.previous.get(identifier)
        self.previous[identifier] = state
        if prior is None or prior == state:
            return
        matching = [routine for routine in list_routines(enabled_only=True) if any(
            trigger["type"] == "state" and trigger["device_id"] == identifier and trigger["to"] == state
            for trigger in routine["spec"]["triggers"])]
        if not matching:
            return
        devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id") is not None}
        if identifier in devices:
            devices[identifier] = {**devices[identifier], "state": state}
        for routine in matching:
            self._start(routine, f"{devices.get(identifier, {}).get('name') or identifier} → {state}",
                        f"state:{identifier}:{uuid.uuid4()}", devices)

    async def tick(self) -> None:
        if time.monotonic() - self.last_prune > 3600:
            prune()
            self.last_prune = time.monotonic()
        routines = list_routines(enabled_only=True)
        if not routines:
            self.previous = {}
            return
        devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id")}
        current = {identifier: _state(item) for identifier, item in devices.items()}
        local = datetime.now(ZoneInfo("Europe/Rome"))
        for routine in routines:
            identifier = routine["id"]
            if identifier in self.running and not self.running[identifier].done():
                continue
            matched = ""
            matched_type = ""
            for trigger in routine["spec"]["triggers"]:
                if trigger["type"] == "state":
                    device_id = trigger["device_id"]
                    if self.buspro_live and device_id in self.buspro_by_state_key.values():
                        continue
                    if self.ksenia_live and device_id.startswith("ksenia-"):
                        continue
                    if device_id in self.previous and self.previous[device_id] != current.get(device_id) and current.get(device_id) == trigger["to"]:
                        matched = f"{devices[device_id].get('name')} → {trigger['to']}"
                        matched_type = "state"
                elif trigger["type"] == "time" and local.strftime("%H:%M") == trigger["at"]:
                    matched = f"Orario {trigger['at']}"
                    matched_type = "time"
            if not matched:
                continue
            trigger_key = local.strftime("%Y-%m-%d %H:%M") + ":" + matched if matched_type == "time" else f"state:{uuid.uuid4()}"
            self._start(routine, matched, trigger_key, devices)
        self.previous = current

    async def doorbird_event(self, event: str) -> None:
        if event not in {"doorbell", "motionsensor"}:
            return
        matching = [routine for routine in list_routines(enabled_only=True) if any(
            trigger["type"] == "doorbird" and trigger["event"] == event for trigger in routine["spec"]["triggers"])]
        if not matching:
            return
        devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id")}
        now = time.monotonic()
        for routine in matching:
            key = (routine["id"], event)
            if now - self.external_cooldowns.get(key, 0) < 5:
                continue
            self.external_cooldowns[key] = now
            self._start(routine, "DoorBird: chiamata" if event == "doorbell" else "DoorBird: movimento",
                        f"doorbird:{event}:{_now()}", devices)

    def _start(self, routine: dict, matched: str, trigger_key: str, devices: dict[str, dict]) -> None:
        identifier = routine["id"]
        if identifier in self.running and not self.running[identifier].done():
            return
        if routine["last_trigger_key"] == trigger_key:
            return
        with _connect() as db:
            changed = db.execute("UPDATE routines SET last_trigger_key = ? WHERE id = ? AND last_trigger_key != ? AND enabled = 1",
                                 (trigger_key, identifier, trigger_key)).rowcount
        if not changed:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with _connect() as db:
            count = db.execute("SELECT COUNT(*) FROM routine_runs WHERE routine_id = ? AND started_at >= ?", (identifier, cutoff)).fetchone()[0]
        if count >= 20:
            run_id = str(uuid.uuid4())
            with _connect() as db:
                db.execute("INSERT INTO routine_runs(id,routine_id,owner,name,revision,trigger_detail,started_at,ended_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
                           (run_id, identifier, routine["owner"], routine["name"], routine["revision"], matched, _now(), _now(), "blocked"))
            record_event(run_id, "rate_limit", detail="Più di 20 attivazioni in un'ora: blocco di sicurezza")
        else:
            self.running[identifier] = asyncio.create_task(self._run(routine, matched, devices))

    async def _run(self, routine: dict, trigger_detail: str, starting_devices: dict[str, dict]) -> None:
        run_id = str(uuid.uuid4())
        with _connect() as db:
            db.execute("INSERT INTO routine_runs(id,routine_id,owner,name,revision,trigger_detail,started_at,status) VALUES(?,?,?,?,?,?,?,?)",
                       (run_id, routine["id"], routine["owner"], routine["name"], routine["revision"], trigger_detail, _now(), "running"))
        record_event(run_id, "trigger", detail=trigger_detail)
        status = "completed"
        try:
            devices = starting_devices
            for condition in routine["spec"]["conditions"]:
                device = devices.get(condition["device_id"])
                actual = _state(device)
                passed = (actual == condition["value"]) == (condition["operator"] == "is")
                record_event(run_id, "condition", device_id=condition["device_id"], device_name=str((device or {}).get("name") or ""), detail=f"{actual} {condition['operator']} {condition['value']}", result="pass" if passed else "skip")
                if not passed:
                    status = "skipped"
                    return
            for step in routine["spec"]["steps"]:
                latest = get_routine(routine["id"])
                if not latest or not latest["enabled"] or latest["revision"] != routine["revision"]:
                    status = "cancelled"
                    record_event(run_id, "cancel", detail="Routine modificata o disattivata durante l'esecuzione")
                    return
                if step["type"] == "wait":
                    record_event(run_id, "timer", detail=f"Attesa {step['seconds']} secondi")
                    await asyncio.sleep(step["seconds"])
                    devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id")}
                elif step["type"] == "check":
                    devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id")}
                    device = devices.get(step["device_id"])
                    actual = _state(device)
                    passed = (actual == step["value"]) == (step["operator"] == "is")
                    record_event(run_id, "check", device_id=step["device_id"], device_name=str((device or {}).get("name") or ""), detail=f"{actual} {step['operator']} {step['value']}", result="pass" if passed else "stop")
                    if not passed:
                        status = "stopped"
                        return
                else:
                    device_id = step["device_id"]
                    device = devices.get(device_id)
                    if not device:
                        raise RuntimeError(f"Dispositivo {device_id} non disponibile")
                    fresh = validate({"name": routine["name"], "triggers": [{"type":"time","at":"00:00"}], "steps": [step]}, list(devices.values()))
                    if fresh["errors"]:
                        raise RuntimeError("Comando non più sicuro: " + fresh["errors"][0])
                    before = _state(device)
                    record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail="Comando richiesto", before_state=before, result="sent")
                    try:
                        await self.command(device_id, step["action"], step.get("value"))
                    except Exception as exc:
                        record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail=str(exc), before_state=before, result="failed")
                        raise
                    record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail="Confermato dal connettore; stato da verificare", before_state=before, result="accepted")
                    devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id")}
                    after = _state(devices.get(device_id))
                    record_event(run_id, "observed", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], before_state=before, after_state=after, result="changed" if after != before else "unchanged")
        except asyncio.CancelledError:
            status = "cancelled"
            record_event(run_id, "cancel", detail="Add-on arrestato")
            raise
        except Exception as exc:
            status = "failed"
            record_event(run_id, "error", detail=str(exc))
        finally:
            with _connect() as db:
                db.execute("UPDATE routine_runs SET ended_at = ?, status = ? WHERE id = ?", (_now(), status, run_id))
