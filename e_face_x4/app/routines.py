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
RUN_MODES = {"single", "restart", "queued", "parallel"}
MAX_QUEUED_RUNS = 5
MAX_PARALLEL_RUNS = 3
MAX_FLOW_NODES = 60
MAX_FLOW_DEPTH = 5
MAX_REPEAT = 10
SAFE_ACTIONS = {
    "light_scenario": {"on", "off", "run", "stop"},
    "light": {"on", "off", "brightness"},
    "switch": {"on", "off"},
    "media_player": {"media_play", "media_pause", "media_stop", "media_next", "media_previous", "turn_off", "set_volume", "volume_mute", "volume_unmute", "select_source", "remote_command", "dnd_on", "dnd_off", "tts"},
    "alexa_device": {"set_alarm", "set_timer", "set_reminder"},
    "climate": {"set_target"},
    "cover": {"open", "close", "stop", "set_position"},
    "lock": {"lock", "unlock"},
}
ACTION_STATES = {"on": "on", "off": "off", "open": "open", "close": "closed", "lock": "locked", "unlock": "unlocked", "media_play": "playing",
                 "media_pause": "paused", "media_stop": "idle", "turn_off": "off"}
ACTION_LABELS = {"on": "accendere", "off": "spegnere", "brightness": "regolare la luminosità", "open": "aprire",
                 "close": "chiudere", "stop": "fermare", "media_play": "avviare la riproduzione",
                 "media_pause": "mettere in pausa", "media_stop": "fermare la riproduzione",
                 "turn_off": "spegnere la stanza", "set_volume": "regolare il volume",
                 "volume_mute": "silenziare", "volume_unmute": "riattivare l'audio", "set_target": "impostare la temperatura",
                 "media_next": "passare al brano successivo", "media_previous": "tornare al brano precedente", "tts": "pronunciare un messaggio su",
                 "select_source": "selezionare una sorgente su", "remote_command": "premere un tasto telecomando su",
                 "dnd_on": "attivare Non disturbare su", "dnd_off": "disattivare Non disturbare su",
                 "set_alarm": "impostare una sveglia su", "set_timer": "impostare un timer su", "set_reminder": "impostare un promemoria su",
                 "lock": "bloccare", "unlock": "sbloccare", "set_position": "posizionare"}
REMOTE_PLAYER_COMMANDS = {"media_play": "play", "media_pause": "pause", "media_stop": "stop", "media_next": "next", "media_previous": "previous", "turn_off": "turn_off", "volume_mute": "mute", "volume_unmute": "mute"}
SENSITIVE_WORDS = re.compile(r"portone|cancello|garage|serratura|allarme|alarm|gate|door|lock", re.I)
SECRET_TEXT = re.compile(r"(?i)(password|token|secret|authorization)\s*[:=]\s*\S+|https?://\S+")
BYPASS_ID = re.compile(r"switch\.e_safe_zone_[0-9]{1,3}_bypass_ctrl\Z")
HA_COVER_ID = re.compile(r"cover\.buspro_cover_[a-z0-9_]+\Z")
ALEXA_SCHEDULE_ID = re.compile(r"sensor\.[a-z0-9_]+_(?:next_alarm|next_timer|next_reminder)\Z")


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
        CREATE TABLE IF NOT EXISTS routine_settings (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS routine_bypass_recovery (
            run_id TEXT PRIMARY KEY, routine_id TEXT NOT NULL, switch_ids TEXT NOT NULL,
            started_at TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS routine_runs_recent ON routine_runs(started_at DESC);
        CREATE INDEX IF NOT EXISTS routine_events_device ON routine_events(device_id, at DESC);
        CREATE INDEX IF NOT EXISTS routine_events_run ON routine_events(run_id, id);
    """)
    return connection


def catalog_filters() -> dict[str, bool]:
    defaults = {"block_sensitive_names": True, "hide_readonly_actions": True}
    with _connect() as db:
        saved = {row["key"]: bool(row["value"]) for row in db.execute("SELECT key, value FROM routine_settings")}
    return {key: saved.get(key, value) for key, value in defaults.items()}


def save_catalog_filters(values: dict) -> dict[str, bool]:
    if not isinstance(values, dict) or set(values) != {"block_sensitive_names", "hide_readonly_actions"} or any(type(value) is not bool for value in values.values()):
        raise ValueError("Filtri catalogo non validi")
    with _connect() as db:
        db.executemany("INSERT INTO routine_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [(key, int(value)) for key, value in values.items()])
        db.commit()
    return catalog_filters()


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


def _solar_rule(raw: dict, errors: list[str], *, condition: bool = False) -> dict | None:
    event = str(raw.get("event") or "")
    offset = raw.get("offset_minutes", 0)
    relation = str(raw.get("relation") or "after")
    if event not in {"sunrise", "sunset"} or isinstance(offset, bool) or not isinstance(offset, int) or not -180 <= offset <= 180 or (condition and relation not in {"before", "after"}):
        errors.append("Alba/tramonto: scegli evento e anticipo/ritardo tra -180 e +180 minuti")
        return None
    rule = {"type": "sun", "event": event, "offset_minutes": offset}
    if condition:
        rule["relation"] = relation
    return rule


def _window_boundary(raw: object, errors: list[str], label: str) -> dict | None:
    if not isinstance(raw, dict):
        errors.append(f"{label}: indica orario, alba o tramonto")
        return None
    kind = raw.get("kind")
    if kind == "time" and set(raw) == {"kind", "at"}:
        at = raw.get("at")
        if isinstance(at, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", at):
            return {"kind": "time", "at": at}
    elif isinstance(kind, str) and kind in {"sunrise", "sunset"} and set(raw) == {"kind", "offset_minutes"}:
        offset = raw.get("offset_minutes")
        if type(offset) is int and -180 <= offset <= 180:
            return {"kind": kind, "offset_minutes": offset}
    errors.append(f"{label}: orario non valido oppure offset fuori da -180/+180 minuti")
    return None


def _time_window(raw: object, errors: list[str]) -> dict | None:
    if not isinstance(raw, dict) or set(raw) != {"type", "start", "end"} or raw.get("type") != "time_window":
        errors.append("Intervallo orario non valido")
        return None
    start = _window_boundary(raw["start"], errors, "Inizio intervallo")
    end = _window_boundary(raw["end"], errors, "Fine intervallo")
    if not start or not end:
        return None
    if start == end:
        errors.append("Inizio e fine dell'intervallo coincidono")
        return None
    return {"type": "time_window", "start": start, "end": end}


def _window_label(boundary: dict) -> str:
    if boundary["kind"] == "time":
        return boundary["at"]
    return f"{'alba' if boundary['kind'] == 'sunrise' else 'tramonto'} {boundary['offset_minutes']:+d} min"


def _remote_allowed(device: dict | None, source_id: int, command: str) -> bool:
    if not device or device.get("kind") != "media_player":
        return False
    if source_id == 0:
        cap = REMOTE_PLAYER_COMMANDS.get(command)
        return bool(cap and (device.get("capabilities") or {}).get(cap))
    return any(isinstance(source, dict) and source.get("experience") == "watch" and str(source.get("source_id")) == str(source_id) and command in (source.get("remote_actions") or [])
               for source in (device.get("source_options") or []))


def _flow_items(value: object):
    """Yield nested dictionaries without assuming a specific flow shape."""
    pending = [value]
    inspected = 0
    while pending and inspected <= 1000:
        current = pending.pop()
        inspected += 1
        if isinstance(current, dict):
            yield current
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def referenced_devices(spec: dict) -> set[str]:
    return {str(item["device_id"]) for item in _flow_items(spec) if item.get("device_id") is not None}


def uses_sun(spec: dict) -> bool:
    return any(item.get("type") == "sun" or (isinstance(item.get("kind"), str) and item.get("kind") in {"sunrise", "sunset"})
               for item in _flow_items(spec))


def _action_steps(steps: object) -> list[dict]:
    return [item for item in _flow_items(steps) if item.get("type") == "action"]


def has_bypass(spec: dict) -> bool:
    return any(item.get("type") == "protected_cover" for item in _flow_items(spec))


def pending_bypass_recovery() -> list[dict]:
    with _connect() as db:
        return [{"run_id": row["run_id"], "routine_id": row["routine_id"],
                 "switch_ids": json.loads(row["switch_ids"])} for row in db.execute("SELECT * FROM routine_bypass_recovery")]


def begin_bypass_recovery(run_id: str, routine_id: str, switch_ids: list[str]) -> None:
    with _connect() as db:
        db.execute("INSERT INTO routine_bypass_recovery(run_id,routine_id,switch_ids,started_at) VALUES(?,?,?,?)",
                   (run_id, routine_id, json.dumps(switch_ids), _now()))


def finish_bypass_recovery(run_id: str) -> None:
    with _connect() as db:
        db.execute("DELETE FROM routine_bypass_recovery WHERE run_id = ?", (run_id,))


def fail_bypass_recovery(run_id: str, error: str) -> None:
    with _connect() as db:
        db.execute("UPDATE routine_bypass_recovery SET last_error = ? WHERE run_id = ?", (error[:300], run_id))


def _record_bypass_event(run_id: str, stage: str, **fields: str) -> None:
    # An audit write must never prevent the remaining alarm zones being restored.
    try:
        record_event(run_id, stage, **fields)
    except (sqlite3.Error, OSError):
        pass


def _compile_condition(raw: object, catalog: dict[str, dict], errors: list[str], depth: int = 0) -> dict | None:
    if depth > MAX_FLOW_DEPTH or not isinstance(raw, dict):
        errors.append("Condizione annidata non valida o troppo profonda")
        return None
    groups = set(raw) & {"and", "or", "not"}
    if groups:
        if len(groups) != 1 or len(raw) != 1:
            errors.append("Condizione logica: usa soltanto AND, OR oppure NOT")
            return None
        key = next(iter(groups))
        if key == "not":
            item = _compile_condition(raw[key], catalog, errors, depth + 1)
            return {"not": item} if item else None
        children = raw[key]
        if not isinstance(children, list) or not 2 <= len(children) <= 8:
            errors.append(f"{key.upper()} richiede da 2 a 8 condizioni")
            return None
        result = [_compile_condition(child, catalog, errors, depth + 1) for child in children]
        return {key: result} if all(result) else None
    kind = raw.get("type", "state")
    if kind == "sun":
        extra = set(raw) - {"type", "event", "offset_minutes", "relation"}
        if extra:
            errors.append("Campi condizione solare non supportati: " + ", ".join(sorted(extra)))
        return _solar_rule(raw, errors, condition=True)
    if kind == "time_window":
        return _time_window(raw, errors)
    if kind == "variable":
        if set(raw) - {"type", "name", "operator", "value"}:
            errors.append("Campi condizione variabile non supportati")
        name = raw.get("name")
        operator = raw.get("operator", "is")
        value = raw.get("value")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or operator not in {"is", "is_not"} or not isinstance(value, (str, int, float, bool)) or len(str(value)) > 80:
            errors.append("Condizione variabile non valida")
            return None
        return {"type": "variable", "name": name, "operator": operator, "value": value}
    if kind != "state" or set(raw) - {"type", "device_id", "operator", "value"}:
        errors.append("Condizione non supportata o con campi sconosciuti")
        return None
    return _condition(raw, catalog, errors)


def _compile_flow(steps: object, catalog: dict[str, dict], errors: list[str], budget: dict, depth: int = 0) -> list[dict]:
    if depth > MAX_FLOW_DEPTH or not isinstance(steps, list) or len(steps) > MAX_STEPS:
        errors.append("Azioni: lista non valida, troppo lunga o troppo annidata")
        return []
    result = []
    for raw in steps:
        budget["nodes"] += 1
        if budget["nodes"] > MAX_FLOW_NODES or not isinstance(raw, dict):
            errors.append("Massimo 60 blocchi validi nell'automazione")
            continue
        kind = raw.get("type")
        if kind in {"action", "wait", "check"}:
            if kind == "action":
                # The ordinary validator remains the sole authority for actuator permissions.
                leaf = validate({"name": "Verifica comando", "triggers": [{"type": "time", "at": "00:00"}], "conditions": [], "steps": [raw]}, list(catalog.values()))
                errors.extend(leaf["errors"])
                if not leaf["errors"]:
                    result.append(leaf["spec"]["steps"][0])
            elif kind == "wait":
                if set(raw) - {"type", "seconds"} or isinstance(raw.get("seconds"), bool) or not isinstance(raw.get("seconds"), int) or not 1 <= raw["seconds"] <= MAX_WAIT_SECONDS:
                    errors.append("Timer non valido (1–3600 secondi)")
                else:
                    result.append(dict(raw))
            else:
                if set(raw) - {"type", "device_id", "operator", "value"}:
                    errors.append("Verifica: campi non supportati")
                condition = _compile_condition({"type": "state", **{k: v for k, v in raw.items() if k != "type"}}, catalog, errors)
                if condition:
                    result.append({"type": "check", **condition})
            continue
        if kind == "delay":
            if set(raw) - {"type", "seconds"} or isinstance(raw.get("seconds"), bool) or not isinstance(raw.get("seconds"), int) or not 1 <= raw["seconds"] <= MAX_WAIT_SECONDS:
                errors.append("Delay non valido (1–3600 secondi)")
            else:
                result.append({"type": "wait", "seconds": raw["seconds"]})
        elif kind == "wait_until":
            timeout = raw.get("timeout_seconds")
            condition = _compile_condition(raw.get("condition"), catalog, errors)
            if set(raw) - {"type", "condition", "timeout_seconds"} or isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_WAIT_SECONDS:
                errors.append("Wait until richiede timeout_seconds tra 1 e 3600")
            elif condition:
                result.append({"type": kind, "condition": condition, "timeout_seconds": timeout})
        elif kind == "if":
            condition = _compile_condition(raw.get("condition"), catalog, errors)
            then = _compile_flow(raw.get("then"), catalog, errors, budget, depth + 1)
            otherwise = _compile_flow(raw.get("else", []), catalog, errors, budget, depth + 1)
            if set(raw) - {"type", "condition", "then", "else"} or not then:
                errors.append("If richiede un ramo then non vuoto e solo campi previsti")
            if condition:
                result.append({"type": kind, "condition": condition, "then": then, "else": otherwise})
        elif kind == "choose":
            choices = raw.get("choices")
            if set(raw) - {"type", "choices", "default"} or not isinstance(choices, list) or not 1 <= len(choices) <= 8:
                errors.append("Choose richiede da 1 a 8 scelte")
                continue
            compiled = []
            for choice in choices:
                if not isinstance(choice, dict) or set(choice) != {"condition", "steps"}:
                    errors.append("Scelta non valida")
                    continue
                condition = _compile_condition(choice["condition"], catalog, errors)
                branch = _compile_flow(choice["steps"], catalog, errors, budget, depth + 1)
                if condition and branch:
                    compiled.append({"condition": condition, "steps": branch})
            default = _compile_flow(raw.get("default", []), catalog, errors, budget, depth + 1)
            if compiled:
                result.append({"type": kind, "choices": compiled, "default": default})
        elif kind == "repeat":
            count = raw.get("count")
            branch = _compile_flow(raw.get("steps"), catalog, errors, budget, depth + 1)
            if set(raw) - {"type", "count", "steps"} or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_REPEAT or not branch:
                errors.append("Repeat richiede 1–10 iterazioni e azioni valide")
            else:
                result.append({"type": kind, "count": count, "steps": branch})
        elif kind == "parallel":
            branches = raw.get("branches")
            if set(raw) - {"type", "branches"} or not isinstance(branches, list) or not 2 <= len(branches) <= MAX_PARALLEL_RUNS:
                errors.append("Parallel richiede 2–3 rami")
                continue
            compiled = [_compile_flow(branch, catalog, errors, budget, depth + 1) for branch in branches]
            targets = [set(step["device_id"] for step in _action_steps(branch)) for branch in compiled]
            if any(not branch for branch in compiled) or any(targets[i] & targets[j] for i in range(len(targets)) for j in range(i + 1, len(targets))):
                errors.append("Rami paralleli vuoti o con comandi allo stesso dispositivo")
            if any(item.get("type") == "variable" for branch in compiled for item in _flow_items(branch)):
                errors.append("Variabili non consentite nei rami paralleli")
            result.append({"type": kind, "branches": compiled})
        elif kind == "protected_cover":
            switch_ids = raw.get("bypass_switches")
            delay = raw.get("enable_delay_seconds", 3)
            move = raw.get("move_seconds", 40)
            if (set(raw) - {"type", "bypass_switches", "enable_delay_seconds", "move_seconds", "steps"}
                    or not isinstance(switch_ids, list) or not 1 <= len(switch_ids) <= 16
                    or len(switch_ids) != len(set(str(item) for item in switch_ids))
                    or any(not isinstance(item, str) or not BYPASS_ID.fullmatch(item)
                           or catalog.get(item, {}).get("kind") != "safety_bypass" for item in switch_ids)
                    or isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 30
                    or isinstance(move, bool) or not isinstance(move, int) or not 1 <= move <= 180):
                errors.append("Bypass protetto: switch e-Safe presenti nel catalogo, ritardo 0–30 s e movimento 1–180 s obbligatori")
                continue
            branch = _compile_flow(raw.get("steps"), catalog, errors, budget, depth + 1)
            if not branch or any(item.get("type") != "action" or catalog.get(item.get("device_id"), {}).get("kind") not in {"cover", "light"}
                                 for item in _flow_items(branch) if "type" in item):
                errors.append("Bypass protetto: ammesse soltanto azioni dirette su cover e luci")
                continue
            if not any(catalog.get(item["device_id"], {}).get("kind") == "cover" for item in _action_steps(branch)):
                errors.append("Bypass protetto: aggiungi almeno una cover")
                continue
            result.append({"type": kind, "bypass_switches": switch_ids,
                           "enable_delay_seconds": delay, "move_seconds": move, "steps": branch})
        elif kind == "variable":
            name, value, source = raw.get("name"), raw.get("value"), raw.get("from_device_id")
            if set(raw) - {"type", "name", "value", "from_device_id"} or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or (source is None) == (value is None) or (source is not None and str(source) not in catalog) or (value is not None and (not isinstance(value, (str, int, float, bool)) or len(str(value)) > 80)):
                errors.append("Variable: indica nome e un solo valore o from_device_id valido")
            else:
                result.append({"type": kind, "name": name, **({"from_device_id": str(source)} if source is not None else {"value": value})})
        elif kind == "stop":
            reason = raw.get("reason", "Arresto richiesto dalla routine")
            if set(raw) - {"type", "reason"} or not isinstance(reason, str) or len(reason) > 120:
                errors.append("Stop: motivo non valido")
            else:
                result.append({"type": kind, "reason": reason})
        else:
            errors.append("Tipo di blocco non supportato")
    return result


def _flow_max_wait(steps: list[dict]) -> int:
    total = 0
    for step in steps:
        kind = step["type"]
        if kind == "wait":
            total += step["seconds"]
        elif kind == "wait_until":
            total += step["timeout_seconds"]
        elif kind == "if":
            total += max(_flow_max_wait(step["then"]), _flow_max_wait(step["else"]))
        elif kind == "choose":
            total += max([_flow_max_wait(choice["steps"]) for choice in step["choices"]] + [_flow_max_wait(step["default"])])
        elif kind == "repeat":
            total += step["count"] * _flow_max_wait(step["steps"])
        elif kind == "parallel":
            total += max(_flow_max_wait(branch) for branch in step["branches"])
        elif kind == "protected_cover":
            total += step["enable_delay_seconds"] + step["move_seconds"] + _flow_max_wait(step["steps"])
    return total


def _flow_max_commands(steps: list[dict]) -> int:
    total = 0
    for step in steps:
        kind = step["type"]
        if kind == "action":
            total += 1
        elif kind == "if":
            total += max(_flow_max_commands(step["then"]), _flow_max_commands(step["else"]))
        elif kind == "choose":
            total += max([_flow_max_commands(choice["steps"]) for choice in step["choices"]] + [_flow_max_commands(step["default"])])
        elif kind == "repeat":
            total += step["count"] * _flow_max_commands(step["steps"])
        elif kind == "parallel":
            total += sum(_flow_max_commands(branch) for branch in step["branches"])
        elif kind == "protected_cover":
            total += 2 * len(step["bypass_switches"]) + _flow_max_commands(step["steps"])
    return total


def _flow_validate_variables(steps: list[dict], known: set[str], errors: list[str]) -> set[str]:
    available = set(known)
    for step in steps:
        kind = step["type"]
        if kind in {"if", "wait_until"}:
            missing = {item["name"] for item in _flow_items(step["condition"]) if item.get("type") == "variable"} - available
            if missing:
                errors.append("Variabili usate prima della definizione: " + ", ".join(sorted(missing)))
        if kind == "variable":
            available.add(step["name"])
        elif kind == "if":
            then_known = _flow_validate_variables(step["then"], available, errors)
            else_known = _flow_validate_variables(step["else"], available, errors)
            available = then_known & else_known
        elif kind == "choose":
            outcomes = []
            for choice in step["choices"]:
                missing = {item["name"] for item in _flow_items(choice["condition"]) if item.get("type") == "variable"} - available
                if missing:
                    errors.append("Variabili usate prima della definizione: " + ", ".join(sorted(missing)))
                outcomes.append(_flow_validate_variables(choice["steps"], available, errors))
            outcomes.append(_flow_validate_variables(step["default"], available, errors))
            available = set.intersection(*outcomes)
        elif kind == "repeat":
            available = _flow_validate_variables(step["steps"], available, errors)
        elif kind == "parallel":
            for branch in step["branches"]:
                _flow_validate_variables(branch, available, errors)
    return available


def _validate_advanced(payload: dict, devices: list[dict], others: list[dict], solar_available: bool) -> dict:
    errors: list[str] = []
    stack = [payload]
    seen = 0
    while stack:
        value = stack.pop()
        seen += 1
        if seen > 400:
            return {"spec": {}, "errors": ["JSON troppo complesso: massimo 400 elementi"], "warnings": [], "risks": [], "description": "", "can_enable": False}
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    catalog = {str(item.get("id")): item for item in devices if isinstance(item, dict) and item.get("id") is not None}
    description = payload.get("description", "")
    if not isinstance(description, str) or len(description) > 1000:
        errors.append("Descrizione non valida (massimo 1000 caratteri)")
        description = ""
    conditions = payload.get("conditions", [])
    if isinstance(conditions, list):
        if len(conditions) > 8:
            errors.append("Massimo 8 condizioni iniziali")
        compiled_conditions = [_compile_condition(item, catalog, errors) for item in conditions]
        compiled_conditions = [item for item in compiled_conditions if item]
    else:
        compiled_conditions = _compile_condition(conditions, catalog, errors)
    if any(item.get("type") == "variable" for item in _flow_items(compiled_conditions)):
        errors.append("Le condizioni iniziali non possono usare variabili: non sono ancora definite")
    flow = _compile_flow(payload.get("steps"), catalog, errors, {"nodes": 0})
    protected = [item for item in _flow_items(flow) if item.get("type") == "protected_cover"]
    if protected and (len(protected) > 4 or payload.get("mode", "single") != "single"
                      or any(item.get("type") in {"repeat", "parallel"} for item in _flow_items(flow))):
        errors.append("Bypass protetto: massimo 4 blocchi sequenziali, modalità single, senza repeat o parallel")
    _flow_validate_variables(flow, set(), errors)
    if not flow or _flow_max_wait(flow) > MAX_WAIT_SECONDS:
        errors.append("Azioni mancanti o durata massima superiore a 60 minuti")
    if _flow_max_commands(flow) > 40:
        errors.append("Massimo 40 comandi possibili per esecuzione, inclusi repeat e rami paralleli")
    if not solar_available and (uses_sun({"conditions": compiled_conditions, "steps": flow}) or uses_sun({"triggers": payload.get("triggers", [])})):
        errors.append("Alba/tramonto non disponibili nell'impianto")
    base = validate({key: value for key, value in payload.items() if key in {"id", "name", "mode", "triggers"}} | {"conditions": [], "steps": _action_steps(flow)}, devices, others, solar_available=solar_available)
    errors.extend(base["errors"])
    unknown = set(payload) - {"id", "name", "description", "mode", "triggers", "conditions", "steps"}
    if unknown:
        errors.append("Campi JSON non supportati: " + ", ".join(sorted(str(item) for item in unknown)))
    base["spec"]["description"] = description.strip()
    base["spec"]["conditions"] = compiled_conditions
    base["spec"]["steps"] = flow
    base["errors"] = list(dict.fromkeys(errors))
    base["can_enable"] = not base["errors"]
    possible = ", ".join(dict.fromkeys(
        f"{ACTION_LABELS.get(step['action'], step['action'])} {catalog[step['device_id']].get('name') or step['device_id']}"
        for step in _action_steps(flow) if step["device_id"] in catalog))
    base["description"] = (f"Alla prima attivazione compatibile, la routine {base['spec']['name']} verifica le condizioni. "
                           f"In base ai rami potrebbe: {possible or 'non eseguire comandi'}. "
                           "Le verifiche e i timeout possono fermare le azioni successive; le azioni già inviate non vengono annullate.")
    extra_risks = []
    kinds = {item.get("type") for item in _flow_items(flow)}
    if "repeat" in kinds:
        extra_risks.append("Repeat può inviare più volte lo stesso comando: verifica che il dispositivo tolleri ripetizioni e che non generi nuovi trigger.")
    if "parallel" in kinds:
        extra_risks.append("Nei rami paralleli un ramo può completare comandi anche se un altro si ferma; non esiste annullamento fisico dei comandi già inviati.")
    if "wait_until" in kinds:
        extra_risks.append("Se wait_until raggiunge il timeout, le azioni successive vengono interrotte; i comandi precedenti restano applicati.")
    if protected:
        extra_risks.append("Bypass allarme: e-Face verifica che le zone siano disattivate prima, registra il ripristino e tenta lo spegnimento anche dopo errori o interruzioni. Se e-Control è irraggiungibile il ripristino resta pendente e viene ritentato: verificare comunque l'allarme fisico.")
    if any(item.get("type") == "action" and item.get("action") == "off" for item in _flow_items(flow)) and kinds & {"wait", "wait_until"}:
        extra_risks.append("Uno spegnimento dopo un'attesa può sovrascrivere un'accensione manuale fatta nel frattempo.")
    base["risks"] = list(dict.fromkeys([*base["risks"], *extra_risks]))
    base["warnings"] = list(dict.fromkeys([*base["warnings"], *extra_risks]))
    return base


def _action_targets(device: dict | None, action: str) -> set[str]:
    targets = {ACTION_STATES[action]} if action in ACTION_STATES else set()
    if device and device.get("kind") == "light_scenario" and action in {"on", "off", "run", "stop"}:
        targets.add(f"command_{action}")
        if action in {"on", "off", "run"}:
            targets.add("running")
    return targets


def validate(payload: dict, devices: list[dict], others: list[dict] = (), *, solar_available: bool = True) -> dict:
    """Validate against the live installation; never trust client-provided capabilities."""
    if isinstance(payload, dict) and ("description" in payload or isinstance(payload.get("conditions"), dict) or any(
        isinstance(item, dict) and (set(item) & {"and", "or", "not"} or item.get("type") == "variable")
        for item in (payload.get("conditions") if isinstance(payload.get("conditions"), list) else [])) or any(
        isinstance(item, dict) and item.get("type") not in {"action", "wait", "check"}
        for item in (payload.get("steps") if isinstance(payload.get("steps"), list) else []))):
        return _validate_advanced(payload, devices, list(others), solar_available)
    errors: list[str] = []
    warnings: list[str] = []
    mode = payload.get("mode", "single")
    if not isinstance(mode, str) or mode not in RUN_MODES:
        errors.append("Modalità routine non valida: usa single, restart, queued o parallel")
        mode = "single"
    unsupported = set(payload) - {"id", "name", "mode", "triggers", "conditions", "steps"}
    if unsupported:
        errors.append("Campi JSON non supportati: " + ", ".join(sorted(str(key) for key in unsupported)))
    catalog = {str(item.get("id")): item for item in devices if isinstance(item, dict) and item.get("id")}
    active_filters = catalog_filters()
    name = str(payload.get("name") or "").strip()[:80]
    if not 1 <= len(name) <= 80:
        errors.append("Assegna un nome alla routine")
    raw_triggers = payload.get("triggers")
    if not isinstance(raw_triggers, list) or not 1 <= len(raw_triggers) <= 12:
        errors.append("Servono da 1 a 12 attivazioni")
        raw_triggers = []
    triggers = []
    for raw in raw_triggers:
        if not isinstance(raw, dict):
            errors.append("Attivazione non valida")
            continue
        trigger_fields = {"time": {"type", "at"}, "doorbird": {"type", "event"}, "sun": {"type", "event", "offset_minutes"},
                          "alexa_schedule": {"type", "device_id", "offset_minutes"},
                          "remote": {"type", "device_id", "source_id", "command"}, "state": {"type", "device_id", "to"}}
        trigger_kind = raw.get("type") if isinstance(raw.get("type"), str) else ""
        extra = set(raw) - trigger_fields.get(trigger_kind, set(raw))
        if extra:
            errors.append("Campi attivazione non supportati: " + ", ".join(sorted(str(key) for key in extra)))
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
        elif raw.get("type") == "sun":
            rule = _solar_rule(raw, errors)
            if rule:
                triggers.append(rule)
        elif raw.get("type") == "alexa_schedule":
            device_id = str(raw.get("device_id") or "")
            offset = raw.get("offset_minutes", 0)
            if (device_id not in catalog or catalog.get(device_id, {}).get("kind") != "alexa_schedule" or
                    isinstance(offset, bool) or not isinstance(offset, int) or not -180 <= offset <= 180):
                errors.append("Evento Alexa non valido")
            else:
                triggers.append({"type": "alexa_schedule", "device_id": device_id, "offset_minutes": offset})
        elif raw.get("type") == "remote":
            device_id = str(raw.get("device_id") or "")
            source_id = raw.get("source_id", 0)
            command = str(raw.get("command") or "")
            if isinstance(source_id, bool) or not isinstance(source_id, int) or source_id < 0 or not _remote_allowed(catalog.get(device_id), source_id, command):
                errors.append(f"Telecomando: tasto non disponibile per {device_id or 'player mancante'}")
            else:
                triggers.append({"type": "remote", "device_id": device_id, "source_id": source_id, "command": command})
        elif raw.get("type") == "state":
            device_id = str(raw.get("device_id") or "")
            target = str(raw.get("to") or "").strip().casefold()[:80]
            if device_id not in catalog or not target or catalog.get(device_id, {}).get("kind") == "safety_bypass":
                errors.append(f"Attivazione non valida per {device_id or 'dispositivo mancante'}")
            else:
                triggers.append({"type": "state", "device_id": device_id, "to": target})
        else:
            errors.append("Tipo di attivazione non supportato")
    raw_conditions = payload.get("conditions", [])
    if not isinstance(raw_conditions, list) or len(raw_conditions) > 8:
        errors.append("Massimo 8 condizioni iniziali")
        raw_conditions = []
    for raw in raw_conditions:
        if isinstance(raw, dict):
            if raw.get("type") not in (None, "state", "sun", "time_window"):
                errors.append("Tipo di condizione non supportato")
            allowed = ({"type", "event", "offset_minutes", "relation"} if raw.get("type") == "sun" else
                       {"type", "start", "end"} if raw.get("type") == "time_window" else
                       {"type", "device_id", "operator", "value"})
            extra = set(raw) - allowed
            if extra:
                errors.append("Campi condizione non supportati: " + ", ".join(sorted(str(key) for key in extra)))
    conditions = [item for raw in raw_conditions if (item := _solar_rule(raw, errors, condition=True) if isinstance(raw, dict) and raw.get("type") == "sun" else
                  _time_window(raw, errors) if isinstance(raw, dict) and raw.get("type") == "time_window" else _condition(raw, catalog, errors))]
    if not solar_available and uses_sun({"triggers": triggers, "conditions": conditions}):
        errors.append("Alba/tramonto non disponibili: controlla posizione e fuso orario di e-Control")
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
        step_fields = {"wait": {"type", "seconds"}, "check": {"type", "device_id", "operator", "value"},
                       "action": {"type", "device_id", "action", "value"}}
        extra = set(raw) - step_fields.get(kind if isinstance(kind, str) else "", set(raw))
        if extra:
            errors.append("Campi blocco non supportati: " + ", ".join(sorted(str(key) for key in extra)))
        if kind == "wait":
            seconds = raw.get("seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= MAX_WAIT_SECONDS:
                errors.append("Il timer deve durare da 1 secondo a 60 minuti")
                continue
            total_wait += seconds
            steps.append({"type": "wait", "seconds": seconds})
        elif kind == "check":
            if raw.get("type") != "check":
                errors.append("Tipo di verifica non supportato")
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
            blocked_name = device_kind not in {"cover", "lock"} and (SENSITIVE_WORDS.search(identity) or re.search(r"porta", identity, re.I))
            if device_kind in {"alarm_system", "alarm_partition", "alarm_scenario", "alarm_zone"} or (active_filters["block_sensitive_names"] and blocked_name):
                errors.append(f"{device.get('name')}: accessi e sicurezza non sono automatizzabili dal cliente")
                continue
            if action not in SAFE_ACTIONS.get(device_kind, set()):
                errors.append(f"{device.get('name')}: comando {action or 'mancante'} non consentito")
                continue
            caps = device.get("capabilities") or {}
            if device_kind == "light_scenario" and not caps.get("onoff" if action in {"on", "off"} else "run"):
                errors.append(f"{device.get('name')}: comando {action} non esposto dallo scenario")
                continue
            required_cap = {"media_play": "play", "media_pause": "pause", "media_stop": "stop", "turn_off": "turn_off", "set_volume": "set_volume", "volume_mute": "mute", "volume_unmute": "mute"}.get(action)
            if action in {"media_next", "media_previous"}:
                required_cap = "next" if action == "media_next" else "previous"
            if action == "tts" and not device.get("tts_enabled"):
                errors.append(f"{device.get('name')}: TTS non abilitato per questo player")
                continue
            if action in {"dnd_on", "dnd_off"} and not device.get("dnd_available"):
                errors.append(f"{device.get('name')}: Non disturbare non disponibile")
                continue
            if required_cap and not caps.get(required_cap):
                errors.append(f"{device.get('name')}: comando {action} non esposto dal dispositivo")
                continue
            value = raw.get("value")
            if action in {"brightness", "set_volume", "set_position"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                    errors.append(f"{device.get('name')}: valore percentuale non valido")
                    continue
                value = round(float(value))
                if action == "set_position" and not device.get("position_supported"):
                    errors.append(f"{device.get('name')}: posizionamento percentuale non disponibile")
                    continue
            elif action == "set_target":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 5 <= value <= 35:
                    errors.append(f"{device.get('name')}: temperatura fuori dai limiti 5–35 °C")
                    continue
                value = round(float(value), 1)
            elif action in {"tts", "set_alarm", "set_timer", "set_reminder"}:
                value = str(value or "").strip()
                if not value or len(value) > 300:
                    errors.append(f"{device.get('name')}: testo del comando Alexa mancante o troppo lungo")
                    continue
            elif action == "select_source":
                value = str(value or "").strip()
                if device.get("provider") == "control4":
                    legacy_matches = [str(source.get("key")) for source in (device.get("source_options") or [])
                                      if isinstance(source, dict) and str(source.get("label") or "").casefold() == value.casefold()]
                    if len(legacy_matches) == 1 and ":" not in value:
                        value = legacy_matches[0]
                sources = ([str(source.get("key")) for source in (device.get("source_options") or []) if isinstance(source, dict)]
                           if device.get("provider") == "control4" else device.get("source_list") or [])
                if not caps.get("select_source") or value not in sources:
                    errors.append(f"{device.get('name')}: sorgente non disponibile")
                    continue
            elif action == "remote_command":
                if not isinstance(value, dict):
                    errors.append(f"{device.get('name')}: tasto telecomando non valido")
                    continue
                if set(value) - {"source_id", "command"}:
                    errors.append(f"{device.get('name')}: campi telecomando non supportati")
                    continue
                source_id = value.get("source_id")
                command = str(value.get("command") or "")
                if isinstance(source_id, bool) or not isinstance(source_id, int) or source_id <= 0 or not _remote_allowed(device, source_id, command):
                    errors.append(f"{device.get('name')}: tasto telecomando non disponibile sulla sorgente")
                    continue
                value = {"source_id": source_id, "command": command}
            else:
                if value is not None:
                    errors.append(f"{device.get('name')}: il comando {action} non accetta un valore")
                    continue
                value = None
            actions.append((device_id, action))
            steps.append({"type": "action", "device_id": device_id, "action": action, "value": value})
            if device_kind == "cover" and action in {"open", "close", "set_position"}:
                warnings.append(f"{device.get('name')}: il movimento fisico della tenda/tapparella può sorprendere chi è vicino")
            if device_kind == "switch":
                warnings.append(f"{device.get('name')}: verifica che lo switch non alimenti un dispositivo critico")
            if action == "set_volume" and value is not None and value > 70:
                warnings.append(f"{device.get('name')}: volume elevato ({value}%) percepibile dalle persone presenti")
            if action in {"tts", "set_alarm", "set_timer", "set_reminder"}:
                warnings.append(f"{device.get('name')}: il messaggio vocale potrebbe essere sentito dalle persone presenti")
            if action == "remote_command":
                warnings.append(f"{device.get('name')}: il telecomando richiede che la sorgente video selezionata sia attiva al momento dell'esecuzione")
        else:
            errors.append("Tipo di blocco non supportato")
    if total_wait > MAX_WAIT_SECONDS:
        errors.append("La somma dei timer supera 60 minuti")
    if not actions:
        errors.append("Aggiungi almeno un'azione")
    for trigger in triggers:
        if trigger["type"] == "state" and any(device_id == trigger["device_id"] and trigger["to"] in _action_targets(catalog.get(device_id), action) for device_id, action in actions):
            errors.append("La routine potrebbe riattivare sé stessa sullo stesso dispositivo")
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for other in [*others, {"spec": {"triggers": triggers, "steps": steps}, "enabled": True, "id": payload.get("id"), "candidate": True}]:
        if not other.get("enabled") or (other.get("id") == payload.get("id") and not other.get("candidate")):
            continue
        state_sources = [(item.get("device_id"), item.get("to")) for item in other.get("spec", {}).get("triggers", []) if item.get("type") == "state"]
        action_targets = [(item.get("device_id"), state) for item in _action_steps(other.get("spec", {}).get("steps", []))
                          for state in _action_targets(catalog.get(item.get("device_id")), item.get("action"))]
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
    # A remote command can itself emit a remote trigger: include it in the
    # dependency graph rather than treating only physical state changes.
    event_edges: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    for other in [*others, {"spec": {"triggers": triggers, "steps": steps}, "enabled": True, "id": payload.get("id"), "candidate": True}]:
        if not other.get("enabled") or (other.get("id") == payload.get("id") and not other.get("candidate")):
            continue
        spec = other.get("spec") or {}
        sources: list[tuple[str, ...]] = []
        targets: set[tuple[str, ...]] = set()
        for trigger in spec.get("triggers", []):
            if trigger.get("type") == "state":
                sources.append(("state", str(trigger.get("device_id")), str(trigger.get("to"))))
            elif trigger.get("type") == "remote":
                sources.append(("remote", str(trigger.get("device_id")), str(trigger.get("source_id")), str(trigger.get("command"))))
        for step in _action_steps(spec.get("steps", [])):
            if step.get("type") != "action":
                continue
            target_id = str(step.get("device_id"))
            for state in _action_targets(catalog.get(target_id), str(step.get("action"))):
                targets.add(("state", target_id, state))
            if step.get("action") == "remote_command" and isinstance(step.get("value"), dict):
                value = step["value"]
                targets.add(("remote", target_id, str(value.get("source_id")), str(value.get("command"))))
        for source in sources:
            event_edges.setdefault(source, set()).update(targets)
    for source in event_edges:
        stack = [(source, frozenset())]
        while stack:
            node, visited = stack.pop()
            if node in visited:
                errors.append("Possibile loop tra routine: un comando puo riattivare se stesso o un'altra routine")
                stack.clear()
                break
            stack.extend((target, visited | {node}) for target in event_edges.get(node, ()) if target in event_edges)
        if any("Possibile loop tra routine" in error for error in errors):
            break
    for index, (device_id, action) in enumerate(actions[1:], 1):
        if device_id == actions[index - 1][0] and action != actions[index - 1][1]:
            warnings.append(f"{catalog[device_id].get('name')}: comandi diversi nella stessa routine; verifica i timer")
    for other in others:
        if not other.get("enabled") or other.get("id") == payload.get("id"):
            continue
        other_targets = {step.get("device_id") for step in _action_steps(other.get("spec", {}).get("steps", []))}
        if other_targets.intersection(device_id for device_id, _ in actions):
            warnings.append(f"Interazione possibile con la routine «{other['name']}» sugli stessi dispositivi")
    if any(step["type"] == "check" for step in steps):
        warnings.append("Se una verifica intermedia non è soddisfatta, le azioni successive non verranno eseguite")
    risks: list[str] = []
    if mode == "restart":
        risks.append("Un nuovo evento interrompe il timer e riparte dall'inizio; le azioni gia eseguite non vengono annullate. Dopo 20 avvii in un'ora nuovi eventi sono bloccati e l'esecuzione in corso termina normalmente.")
    elif mode == "queued":
        risks.append("Gli eventi si mettono in coda (massimo 5): un comando puo avvenire molto dopo l'evento che lo ha richiesto. La coda in corso non sopravvive al riavvio dell'add-on.")
    elif mode == "parallel":
        risks.append("Fino a 3 esecuzioni possono operare contemporaneamente: comandi sullo stesso dispositivo potrebbero sovrapporsi.")
    if any(step["type"] == "wait" for step in steps) and any(action == "off" for _, action in actions):
        risks.append("Uno spegnimento dopo un timer puo sovrascrivere un'accensione manuale avvenuta durante l'attesa.")
    if any(catalog[device_id].get("kind") == "cover" and action in {"open", "close", "set_position"} for device_id, action in actions):
        risks.append("Oscuranti in movimento: e-Face non puo accertare la presenza di persone o ostacoli; verifica le protezioni fisiche dell'impianto.")
    if any(catalog[device_id].get("kind") == "lock" and action == "unlock" for device_id, action in actions):
        risks.append("La routine può sbloccare un accesso fisico automaticamente: verifica trigger, condizioni e protezioni prima di attivarla.")
    if any(catalog[device_id].get("kind") == "switch" for device_id, _ in actions):
        risks.append("Gli switch possono alimentare carichi reali: verifica che un comando automatico non interrompa apparecchiature importanti.")
    if mode == "parallel" and len({device_id for device_id, _ in actions}) < len(actions):
        errors.append("Parallel non consentito: la stessa routine comanda piu volte lo stesso dispositivo e le esecuzioni potrebbero sovrapporsi")
    warnings.extend(risks)
    normalized = {"name": name, "mode": mode, "triggers": triggers, "conditions": conditions, "steps": steps}
    descriptions = []
    for trigger in triggers:
        if trigger["type"] == "time":
            descriptions.append(f"alle {trigger['at']}")
        elif trigger["type"] == "doorbird":
            descriptions.append("quando suona DoorBird" if trigger["event"] == "doorbell" else "quando DoorBird rileva movimento")
        elif trigger["type"] == "sun":
            descriptions.append(f"a {'alba' if trigger['event'] == 'sunrise' else 'tramonto'} {trigger['offset_minutes']:+d} minuti")
        elif trigger["type"] == "remote":
            descriptions.append(f"quando e-Face invia il tasto {trigger['command']} a {catalog[trigger['device_id']].get('name')}")
        elif trigger["type"] == "alexa_schedule":
            descriptions.append(f"all'evento {catalog[trigger['device_id']].get('name')} {trigger['offset_minutes']:+d} minuti")
        else:
            descriptions.append(f"quando {catalog[trigger['device_id']].get('name')} diventa {trigger['to']}")
    narrative = "La casa avvierà la routine " + (" oppure ".join(descriptions) if descriptions else "solo dopo una configurazione valida") + ". "
    if conditions:
        narrative += "Prima controllerà " + ", ".join(
            f"se è tra {_window_label(item['start'])} e {_window_label(item['end'])}"
            if item.get("type") == "time_window" else
            f"se è {'prima' if item['relation'] == 'before' else 'dopo'} di {'alba' if item['event'] == 'sunrise' else 'tramonto'} {item['offset_minutes']:+d} minuti"
            if item.get("type") == "sun" else
            f"{catalog[item['device_id']].get('name')} {item['operator'].replace('is_not', 'non è').replace('is', 'è')} {item['value']}"
            for item in conditions) + ". "
    for step in steps:
        if step["type"] == "wait":
            narrative += f"Poi attenderà {step['seconds']} secondi. "
        elif step["type"] == "check":
            narrative += f"Ricontrollerà {catalog[step['device_id']].get('name')}: se non è {step['value']}, interromperà il resto. "
        else:
            amount = (" con un messaggio vocale" if step["action"] == "tts" else
                      f" ({step['value']['command']})" if step["action"] == "remote_command" else
                      f" ({step['value']})" if step["action"] == "select_source" else
                      f" a {step['value']}{' °C' if step['action'] == 'set_target' else '%'}" if step.get("value") is not None else "")
            narrative += f"Farà {ACTION_LABELS.get(step['action'], step['action'])} {catalog[step['device_id']].get('name')}{amount}. "
            device_kind = catalog[step["device_id"]].get("kind")
            if device_kind == "light" and step["action"] == "on":
                narrative += "Chi è nella stanza vedrà accendersi la luce. "
            elif device_kind == "media_player" and step["action"] in {"media_play", "set_volume", "volume_unmute", "tts"}:
                narrative += "Chi è nella stanza potrebbe sentire l'audio. "
            elif device_kind == "cover" and step["action"] in {"open", "close"}:
                narrative += "La tenda/tapparella si muoverà fisicamente. "
            elif device_kind == "climate":
                narrative += "La temperatura percepita cambierà gradualmente. "
    for device_id, action in actions:
        if action == "on" and not any(other_id == device_id and other_action == "off" for other_id, other_action in actions):
            narrative += f"{catalog[device_id].get('name')} resterà acceso finché non interviene un altro comando. "
    return {"spec": normalized, "errors": list(dict.fromkeys(errors)), "warnings": list(dict.fromkeys(warnings)), "risks": risks, "description": narrative.strip(), "can_enable": not errors}


def save(owner: str, actor: str, routine_id: str | None, spec: dict, enabled: bool, expected_revision: int | None,
         *, shared: bool = False) -> dict:
    with _connect() as db:
        old = db.execute("SELECT owner, revision, enabled FROM routines WHERE id = ?", (routine_id,)).fetchone() if routine_id else None
        if old and old["owner"] != owner and not shared:
            raise PermissionError("Routine di un altro utente")
        if old and expected_revision != old["revision"]:
            raise RuntimeError("Routine modificata da un'altra sessione: ricarica prima di salvare")
        if routine_id and not old:
            raise LookupError("Routine non trovata")
        if not old and db.execute("SELECT COUNT(*) FROM routines" if shared else "SELECT COUNT(*) FROM routines WHERE owner = ?",
                                  () if shared else (owner,)).fetchone()[0] >= 100:
            raise ValueError("Massimo 100 routine per impianto" if shared else "Massimo 100 routine per utente")
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
    return get_routine(identifier, None if shared else owner)


def delete(owner: str, routine_id: str, *, shared: bool = False) -> bool:
    with _connect() as db:
        return bool(db.execute("DELETE FROM routines WHERE id = ?" if shared else "DELETE FROM routines WHERE id = ? AND owner = ?",
                               (routine_id,) if shared else (routine_id, owner)).rowcount)


def record_event(run_id: str, stage: str, *, device_id: str = "", device_name: str = "", action: str = "", detail: str = "", before_state: str = "", after_state: str = "", result: str = "", at: str | None = None) -> None:
    with _connect() as db:
        db.execute("INSERT INTO routine_events(run_id,at,stage,device_id,device_name,action,detail,before_state,after_state,result) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (run_id, at or _now(), stage, device_id, device_name, action, SECRET_TEXT.sub("[dato nascosto]", detail)[:400], before_state[:100], after_state[:100], result[:100]))


def list_runs(*, device_id: str = "", routine_id: str = "", routine_name: str = "", limit: int = 100) -> list[dict]:
    clauses, args = [], []
    if routine_id:
        clauses.append("r.routine_id = ?")
        args.append(routine_id)
    if routine_name:
        clauses.append("lower(r.name) LIKE lower(?) ESCAPE '\\'")
        args.append("%" + routine_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
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
    def __init__(self, snapshot: Callable[[], Awaitable[list[dict]]], command: Callable[[str, str, object], Awaitable[object]],
                 snapshot_selected: Callable[[set[str]], Awaitable[list[dict]]] | None = None,
                 activity_changed: Callable[[set[str]], Awaitable[None]] | None = None,
                 solar_times: Callable[[], Awaitable[dict[str, datetime]]] | None = None,
                 bypass_state: Callable[[str], Awaitable[str]] | None = None):
        self.snapshot = snapshot
        self.snapshot_selected = snapshot_selected
        self.command = command
        self.activity_changed = activity_changed
        self.solar_times = solar_times
        self.bypass_state = bypass_state
        self.active_bypass_runs: set[str] = set()
        self.bypass_lock = asyncio.Lock()
        self.active_targets: dict[str, set[str]] = {}
        self.previous: dict[str, str] = {}
        self.running: dict[str, asyncio.Task] = {}
        self.running_tasks: dict[str, set[asyncio.Task]] = {}
        self.pending: dict[str, list[tuple[dict, str, dict[str, dict], str | None]]] = {}
        self.cancel_reasons: dict[asyncio.Task, str] = {}
        self.recent_starts: dict[str, list[datetime]] = {}
        self.external_cooldowns: dict[tuple[str, str], float] = {}
        self.last_prune = 0.0
        self.buspro_by_state_key: dict[str, str] = {}
        self.scenario_running_only: set[str] = set()
        self.buspro_live = False
        self.ksenia_live = False

    @staticmethod
    def _references(routine: dict) -> set[str]:
        return referenced_devices(routine["spec"])

    async def _snapshot_for(self, matching: list[dict]) -> dict[str, dict]:
        references = set().union(*(self._references(routine) for routine in matching))
        items = await self.snapshot_selected(references) if self.snapshot_selected else await self.snapshot()
        return {str(item["id"]): item for item in items if item.get("id") is not None}

    async def _wait_bypass_state(self, device_id: str, wanted: str) -> bool:
        if self.bypass_state is None:
            return False
        for attempt in range(7):
            if await self.bypass_state(device_id) == wanted:
                return True
            if attempt < 6:
                await asyncio.sleep(0.5)
        return False

    async def _restore_bypasses(self, run_id: str, switch_ids: list[str]) -> bool:
        errors = []
        for device_id in switch_ids:
            try:
                await self.command(device_id, "off", None)
                if not await self._wait_bypass_state(device_id, "off"):
                    raise RuntimeError("spegnimento non confermato")
                _record_bypass_event(run_id, "bypass_restore", device_id=device_id, action="off", result="confirmed")
            except Exception as exc:
                errors.append(f"{device_id}: {exc}")
                _record_bypass_event(run_id, "bypass_restore", device_id=device_id, action="off", detail=str(exc), result="pending")
        if errors:
            try:
                fail_bypass_recovery(run_id, "; ".join(errors))
            except (sqlite3.Error, OSError):
                pass  # The previously committed recovery row remains pending.
            return False
        finish_bypass_recovery(run_id)
        return True

    async def recover_bypasses(self) -> None:
        for item in pending_bypass_recovery():
            if item["run_id"] not in self.active_bypass_runs:
                await self._restore_bypasses(item["run_id"], item["switch_ids"])

    async def ksenia_event(self, items: list[dict]) -> None:
        received_at = _now()
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
        devices = await self._snapshot_for([routine for routine, _, _ in matching])
        devices.update(by_id)
        for routine, identifier, state in matching:
            self._start(routine, f"{by_id[identifier].get('name') or identifier} → {state}",
                        f"ksenia:{identifier}:{uuid.uuid4()}", devices, received_at)

    def configure_buspro(self, devices: list[dict]) -> None:
        self.buspro_by_state_key = {str(item["state_key"]).casefold(): str(item["id"])
                                     for item in devices if item.get("state_key") and item.get("id") is not None}
        self.scenario_running_only = {str(item["id"]) for item in devices if item.get("kind") == "light_scenario" and not (item.get("capabilities") or {}).get("onoff")}
        for item in devices:
            if str(item.get("id")) in self.buspro_by_state_key.values():
                self.previous[str(item["id"])] = _state(item)

    def active_device_ids(self) -> set[str]:
        return set().union(*self.active_targets.values()) if self.active_targets else set()

    async def _notify_activity(self) -> None:
        if self.activity_changed:
            await self.activity_changed(self.active_device_ids())

    async def buspro_event(self, event: dict) -> None:
        received_at = _now()
        data = event.get("data")
        if not isinstance(data, dict):
            return
        scenario_event = event.get("type") in {"light_scenario_state", "light_scenario_running", "light_scenario_command"}
        key = f"scenario:{data.get('id')}" if scenario_event else str(data.get("entity_id") or "").casefold() or ".".join(
            str(data.get(part)) for part in ("subnet_id", "device_id", "channel"))
        identifier = self.buspro_by_state_key.get(key)
        if scenario_event and event.get("type") == "light_scenario_command":
            action = str(data.get("action") or "").casefold()
            if not identifier or action not in {"on", "off", "run", "stop"}:
                return
            state = f"command_{action}"
            matching = [routine for routine in list_routines(enabled_only=True) if any(
                trigger["type"] == "state" and trigger["device_id"] == identifier and trigger["to"] == state
                for trigger in routine["spec"]["triggers"])]
            if matching:
                devices = await self._snapshot_for(matching)
                for routine in matching:
                    self._start(routine, f"{devices.get(identifier, {}).get('name') or identifier} → comando {action}",
                                f"scenario-command:{identifier}:{uuid.uuid4()}", devices, received_at)
            return
        if scenario_event and event.get("type") == "light_scenario_running" and identifier not in self.scenario_running_only:
            if not identifier or not data.get("running"):
                return
            matching = [routine for routine in list_routines(enabled_only=True) if any(
                trigger["type"] == "state" and trigger["device_id"] == identifier and trigger["to"] == "running"
                for trigger in routine["spec"]["triggers"])]
            if matching:
                devices = await self._snapshot_for(matching)
                for routine in matching:
                    self._start(routine, f"{devices.get(identifier, {}).get('name') or identifier} → avvio scenario",
                                f"scenario-run:{identifier}:{uuid.uuid4()}", devices, received_at)
            return
        if scenario_event and event.get("type") == "light_scenario_state" and identifier in self.scenario_running_only:
            return
        value = ("running" if data.get("running") else "idle") if event.get("type") == "light_scenario_running" else data.get("state", data.get("value"))
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
        devices = await self._snapshot_for(matching)
        if identifier in devices:
            devices[identifier] = {**devices[identifier], "state": state}
        for routine in matching:
            self._start(routine, f"{devices.get(identifier, {}).get('name') or identifier} → {state}",
                        f"state:{identifier}:{uuid.uuid4()}", devices, received_at)

    async def tick(self) -> None:
        if time.monotonic() - self.last_prune > 3600:
            prune()
            self.last_prune = time.monotonic()
        routines = list_routines(enabled_only=True)
        if not routines:
            self.previous = {}
            return
        devices = {str(item.get("id")): item for item in await self.snapshot() if item.get("id") is not None}
        current = {identifier: _state(item) for identifier, item in devices.items()}
        local = datetime.now(ZoneInfo("Europe/Rome"))
        sun = {}
        if self.solar_times and any(trigger.get("type") == "sun" for routine in routines for trigger in routine["spec"]["triggers"]):
            try:
                sun = await self.solar_times()
            except (OSError, RuntimeError, ValueError):
                pass
        for routine in routines:
            identifier = routine["id"]
            if routine["spec"].get("mode", "single") == "single" and identifier in self.running and not self.running[identifier].done():
                continue
            matched = ""
            matched_type = ""
            matched_key = ""
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
                elif trigger["type"] == "sun" and trigger["event"] in sun:
                    target = sun[trigger["event"]] + timedelta(minutes=trigger["offset_minutes"])
                    now = datetime.now(target.tzinfo)
                    if target <= now < target + timedelta(minutes=1):
                        matched = f"{'Alba' if trigger['event'] == 'sunrise' else 'Tramonto'} {trigger['offset_minutes']:+d} minuti"
                        matched_type = "sun"
                elif trigger["type"] == "alexa_schedule":
                    device_id = trigger["device_id"]
                    raw_state = current.get(device_id)
                    try:
                        target = datetime.fromisoformat(str(raw_state).replace("Z", "+00:00")) + timedelta(minutes=trigger["offset_minutes"])
                        now = datetime.now(target.tzinfo) if target.tzinfo else local.replace(tzinfo=None)
                        if target <= now < target + timedelta(minutes=1):
                            matched = f"{devices[device_id].get('name')} {trigger['offset_minutes']:+d} minuti"
                            matched_type = "alexa_schedule"
                            matched_key = f"alexa:{device_id}:{raw_state}:{trigger['offset_minutes']}"
                    except (TypeError, ValueError):
                        pass
            if not matched:
                continue
            trigger_key = matched_key or (local.strftime("%Y-%m-%d") + ":" + matched if matched_type == "sun" else local.strftime("%Y-%m-%d %H:%M") + ":" + matched if matched_type == "time" else f"state:{uuid.uuid4()}")
            self._start(routine, matched, trigger_key, devices)
        self.previous = current

    async def doorbird_event(self, event: str) -> None:
        if event not in {"doorbell", "motionsensor"}:
            return
        matching = [routine for routine in list_routines(enabled_only=True) if any(
            trigger["type"] == "doorbird" and trigger["event"] == event for trigger in routine["spec"]["triggers"])]
        if not matching:
            return
        devices = await self._snapshot_for(matching)
        now = time.monotonic()
        for routine in matching:
            key = (routine["id"], event)
            if now - self.external_cooldowns.get(key, 0) < 5:
                continue
            self.external_cooldowns[key] = now
            self._start(routine, "DoorBird: chiamata" if event == "doorbell" else "DoorBird: movimento",
                        f"doorbird:{event}:{_now()}", devices)

    async def remote_event(self, device_id: str, source_id: int, command: str) -> None:
        matching = [routine for routine in list_routines(enabled_only=True) if any(
            trigger.get("type") == "remote" and trigger["device_id"] == device_id and trigger["source_id"] == source_id and trigger["command"] == command
            for trigger in routine["spec"]["triggers"])]
        if not matching:
            return
        devices = await self._snapshot_for(matching)
        name = devices.get(device_id, {}).get("name") or device_id
        for routine in matching:
            self._start(routine, f"Telecomando e-Face: {name} · {command}", f"remote:{uuid.uuid4()}", devices)

    def _start(self, routine: dict, matched: str, trigger_key: str, devices: dict[str, dict], received_at: str | None = None) -> None:
        identifier = routine["id"]
        mode = routine["spec"].get("mode", "single")
        active = {task for task in self.running_tasks.get(identifier, set()) if not task.done()}
        if active and mode == "single":
            return
        if active and mode == "parallel" and len(active) >= MAX_PARALLEL_RUNS:
            return
        if active and mode == "queued" and len(self.pending.get(identifier, [])) >= MAX_QUEUED_RUNS:
            return
        if routine["last_trigger_key"] == trigger_key:
            return
        with _connect() as db:
            changed = db.execute("UPDATE routines SET last_trigger_key = ? WHERE id = ? AND last_trigger_key != ? AND enabled = 1",
                                 (trigger_key, identifier, trigger_key)).rowcount
        if not changed:
            return
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        if identifier not in self.recent_starts:
            with _connect() as db:
                rows = db.execute("SELECT started_at FROM routine_runs WHERE routine_id = ? AND started_at >= ?", (identifier, cutoff.isoformat())).fetchall()
            self.recent_starts[identifier] = [datetime.fromisoformat(row[0]) for row in rows]
        recent = self.recent_starts[identifier]
        recent[:] = [started for started in recent if started >= cutoff]
        if len(recent) >= 20:
            run_id = str(uuid.uuid4())
            with _connect() as db:
                db.execute("INSERT INTO routine_runs(id,routine_id,owner,name,revision,trigger_detail,started_at,ended_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
                           (run_id, identifier, routine["owner"], routine["name"], routine["revision"], matched, _now(), _now(), "blocked"))
            record_event(run_id, "rate_limit", detail="Più di 20 attivazioni in un'ora: blocco di sicurezza")
        else:
            recent.append(now)
            if active and mode == "restart":
                for task in active:
                    self.cancel_reasons[task] = "Nuovo evento: timer riavviato (mode restart)"
                    task.cancel()
                self.pending.pop(identifier, None)
            if active and mode == "queued":
                self.pending.setdefault(identifier, []).append((routine, matched, devices, received_at))
                return
            self._launch(routine, matched, devices, received_at)

    def _launch(self, routine: dict, matched: str, devices: dict[str, dict], received_at: str | None) -> None:
        identifier = routine["id"]
        task = asyncio.create_task(self._run(routine, matched, devices, received_at))
        self.running[identifier] = task
        self.running_tasks.setdefault(identifier, set()).add(task)
        task.add_done_callback(lambda done: self._finished(identifier, done))

    def _finished(self, identifier: str, task: asyncio.Task) -> None:
        active = self.running_tasks.get(identifier)
        if active is None:
            return
        active.discard(task)
        self.cancel_reasons.pop(task, None)
        if active:
            if self.running.get(identifier) is task:
                self.running[identifier] = next(iter(active))
            return
        self.running_tasks.pop(identifier, None)
        if self.running.get(identifier) is task:
            self.running.pop(identifier, None)
        waiting = self.pending.get(identifier)
        while waiting:
            routine, matched, devices, received_at = waiting.pop(0)
            latest = get_routine(identifier)
            if latest and latest["enabled"] and latest["revision"] == routine["revision"]:
                self._launch(routine, matched, devices, received_at)
                break
        if not waiting:
            self.pending.pop(identifier, None)

    def cancel_routine(self, identifier: str) -> None:
        self.pending.pop(identifier, None)
        for task in self.running_tasks.get(identifier, set()):
            if not task.done():
                self.cancel_reasons[task] = "Routine modificata o disattivata"
                task.cancel()

    async def _evaluate_time_window(self, condition: dict) -> tuple[bool, str]:
        start, end = condition["start"], condition["end"]
        solar = any(boundary["kind"] != "time" for boundary in (start, end))
        if solar and not self.solar_times:
            raise RuntimeError("Orari di alba/tramonto non disponibili")
        schedule = await self.solar_times() if solar else {}
        zone = next(iter(schedule.values())).tzinfo if schedule else ZoneInfo("Europe/Rome")
        now = datetime.now(zone)

        def minute(boundary: dict) -> int:
            if boundary["kind"] == "time":
                hour, minute_part = map(int, boundary["at"].split(":"))
                return hour * 60 + minute_part
            moment = schedule[boundary["kind"]] + timedelta(minutes=boundary["offset_minutes"])
            return moment.hour * 60 + moment.minute

        first, last = minute(start), minute(end)
        current = now.hour * 60 + now.minute
        if first < last:
            passed = first <= current < last
        elif first > last:
            passed = current >= first or current < last
        else:
            passed = False
        detail = (f"Intervallo {_window_label(start)} → {_window_label(end)}; "
                  f"soglie {first // 60:02d}:{first % 60:02d}–{last // 60:02d}:{last % 60:02d}; ora {now:%H:%M}")
        return passed, detail

    async def _evaluate_condition(self, condition: dict, devices: dict[str, dict], variables: dict) -> bool:
        if "and" in condition:
            for item in condition["and"]:
                if not await self._evaluate_condition(item, devices, variables):
                    return False
            return True
        if "or" in condition:
            for item in condition["or"]:
                if await self._evaluate_condition(item, devices, variables):
                    return True
            return False
        if "not" in condition:
            return not await self._evaluate_condition(condition["not"], devices, variables)
        if condition.get("type") == "time_window":
            return (await self._evaluate_time_window(condition))[0]
        if condition.get("type") == "sun":
            if not self.solar_times:
                raise RuntimeError("Orari di alba/tramonto non disponibili")
            schedule = await self.solar_times()
            boundary = schedule[condition["event"]] + timedelta(minutes=condition["offset_minutes"])
            current = datetime.now(boundary.tzinfo)
            return current < boundary if condition["relation"] == "before" else current >= boundary
        if condition.get("type") == "variable" and condition["name"] not in variables:
            raise RuntimeError(f"Variabile {condition['name']} non definita")
        actual = variables[condition["name"]] if condition.get("type") == "variable" else _state(devices.get(condition["device_id"]))
        equal = str(actual).casefold() == str(condition["value"]).casefold()
        return equal if condition["operator"] == "is" else not equal

    async def _run_flow(self, routine: dict, run_id: str, starting_devices: dict[str, dict]) -> str:
        variables: dict = {}
        conditions = routine["spec"].get("conditions", [])
        initial = conditions if isinstance(conditions, list) else [conditions]
        devices = starting_devices
        for condition in initial:
            if condition.get("type") == "time_window":
                passed, detail = await self._evaluate_time_window(condition)
            else:
                passed = await self._evaluate_condition(condition, devices, variables)
                detail = ""
            device_id = str(condition.get("device_id") or "")
            device = devices.get(device_id, {})
            actual = _state(device) if device_id else ""
            record_event(run_id, "condition", device_id=device_id, device_name=str(device.get("name") or ""),
                         detail=detail or f"Regola {json.dumps(condition, ensure_ascii=False)}; stato letto: {actual or 'non applicabile'}",
                         before_state=actual, result="pass" if passed else "skip")
            if not passed:
                return "skipped"

        async def execute(steps: list[dict], current: dict[str, dict], values: dict) -> tuple[str, dict[str, dict]]:
            for step in steps:
                latest = get_routine(routine["id"])
                if not latest or not latest["enabled"] or latest["revision"] != routine["revision"]:
                    record_event(run_id, "cancel", detail="Routine modificata o disattivata durante l'esecuzione")
                    return "cancelled", current
                kind = step["type"]
                if kind == "wait":
                    record_event(run_id, "timer", detail=f"Attesa {step['seconds']} secondi")
                    await asyncio.sleep(step["seconds"])
                    current = await self._snapshot_for([routine])
                elif kind == "wait_until":
                    deadline = time.monotonic() + step["timeout_seconds"]
                    record_event(run_id, "wait_until", detail=f"Attesa condizione, massimo {step['timeout_seconds']} secondi")
                    while True:
                        current = await self._snapshot_for([routine])
                        if await self._evaluate_condition(step["condition"], current, values):
                            record_event(run_id, "wait_until", detail="Condizione soddisfatta", result="pass")
                            break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            record_event(run_id, "wait_until", detail="Timeout: azioni successive non eseguite", result="stop")
                            return "stopped", current
                        await asyncio.sleep(min(1.0, remaining))
                elif kind == "check":
                    current = await self._snapshot_for([routine])
                    passed = await self._evaluate_condition(step, current, values)
                    actual = _state(current.get(step["device_id"]))
                    record_event(run_id, "check", device_id=step["device_id"], device_name=str(current.get(step["device_id"], {}).get("name") or ""),
                                 detail=f"Stato letto: {actual}; richiesto {step['operator']} {step['value']}", before_state=actual,
                                 result="pass" if passed else "stop")
                    if not passed:
                        return "stopped", current
                elif kind == "variable":
                    if "from_device_id" in step:
                        current = await self._snapshot_for([routine])
                        values[step["name"]] = _state(current.get(step["from_device_id"]))
                    else:
                        values[step["name"]] = step["value"]
                    record_event(run_id, "variable", detail=f"{step['name']} = {values[step['name']]}")
                elif kind == "stop":
                    record_event(run_id, "stop", detail=step["reason"], result="stop")
                    return "stopped", current
                elif kind == "if":
                    current = await self._snapshot_for([routine])
                    passed = await self._evaluate_condition(step["condition"], current, values)
                    record_event(run_id, "if", detail="Ramo then" if passed else "Ramo else", result="pass" if passed else "skip")
                    status, current = await execute(step["then"] if passed else step["else"], current, values)
                    if status != "completed":
                        return status, current
                elif kind == "choose":
                    current = await self._snapshot_for([routine])
                    chosen = step["default"]
                    label = "default"
                    for index, choice in enumerate(step["choices"]):
                        if await self._evaluate_condition(choice["condition"], current, values):
                            chosen, label = choice["steps"], str(index + 1)
                            break
                    record_event(run_id, "choose", detail=f"Ramo {label}")
                    status, current = await execute(chosen, current, values)
                    if status != "completed":
                        return status, current
                elif kind == "repeat":
                    for number in range(step["count"]):
                        record_event(run_id, "repeat", detail=f"Iterazione {number + 1}/{step['count']}")
                        status, current = await execute(step["steps"], current, values)
                        if status != "completed":
                            return status, current
                elif kind == "parallel":
                    tasks = []
                    async with asyncio.TaskGroup() as group:
                        for branch in step["branches"]:
                            tasks.append(group.create_task(execute(branch, dict(current), dict(values))))
                    results = [task.result() for task in tasks]
                    if any(status != "completed" for status, _ in results):
                        return next(status for status, _ in results if status != "completed"), current
                    current = await self._snapshot_for([routine])
                    record_event(run_id, "parallel", detail=f"Completati {len(tasks)} rami")
                elif kind == "protected_cover":
                    async with self.bypass_lock:
                        switch_ids = step["bypass_switches"]
                        if self.bypass_state is None:
                            raise RuntimeError("Verifica bypass e-Control non disponibile")
                        if pending_bypass_recovery():
                            raise RuntimeError("Un ripristino bypass precedente è ancora pendente: movimento annullato")
                        for device_id in switch_ids:
                            state = await self.bypass_state(device_id)
                            if state != "off":
                                raise RuntimeError(f"Bypass {device_id} non spento: movimento annullato")
                        begin_bypass_recovery(run_id, routine["id"], switch_ids)
                        self.active_bypass_runs.add(run_id)
                        try:
                            for device_id in switch_ids:
                                await self.command(device_id, "on", None)
                                if not await self._wait_bypass_state(device_id, "on"):
                                    raise RuntimeError(f"Bypass {device_id} non confermato")
                                _record_bypass_event(run_id, "bypass", device_id=device_id, action="on", result="confirmed")
                            if step["enable_delay_seconds"]:
                                await asyncio.sleep(step["enable_delay_seconds"])
                            status, current = await execute(step["steps"], current, values)
                            if status != "completed":
                                return status, current
                            await asyncio.sleep(step["move_seconds"])
                        finally:
                            try:
                                restored = await self._restore_bypasses(run_id, switch_ids)
                                if not restored:
                                    raise RuntimeError("Bypass non ripristinato: intervento richiesto; recupero automatico pendente")
                            finally:
                                self.active_bypass_runs.discard(run_id)
                elif kind == "action":
                    device_id = step["device_id"]
                    device = current.get(device_id)
                    if not device:
                        raise RuntimeError(f"Dispositivo {device_id} non disponibile")
                    fresh = validate({"name": routine["name"], "triggers": [{"type": "time", "at": "00:00"}], "steps": [step]}, list(current.values()))
                    if fresh["errors"]:
                        raise RuntimeError("Comando non più sicuro: " + fresh["errors"][0])
                    before = _state(device)
                    record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail="Comando richiesto", before_state=before, result="sent")
                    try:
                        await self.command(device_id, step["action"], fresh["spec"]["steps"][0].get("value"))
                    except Exception as exc:
                        record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail=str(exc), before_state=before, result="failed")
                        raise
                    record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail="Confermato dal connettore; stato da verificare", before_state=before, result="accepted")
                    current = await self._snapshot_for([routine])
                    after = _state(current.get(device_id))
                    record_event(run_id, "observed", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], before_state=before, after_state=after, result="changed" if after != before else "unchanged")
                else:
                    raise RuntimeError(f"Blocco non eseguibile: {kind}")
            return "completed", current

        result, _ = await execute(routine["spec"]["steps"], devices, variables)
        return result

    async def _run(self, routine: dict, trigger_detail: str, starting_devices: dict[str, dict], received_at: str | None = None) -> None:
        run_id = str(uuid.uuid4())
        with _connect() as db:
            db.execute("INSERT INTO routine_runs(id,routine_id,owner,name,revision,trigger_detail,started_at,status) VALUES(?,?,?,?,?,?,?,?)",
                       (run_id, routine["id"], routine["owner"], routine["name"], routine["revision"], trigger_detail, _now(), "running"))
        if received_at:
            record_event(run_id, "received", detail="Evento ricevuto dal connettore", at=received_at)
        record_event(run_id, "trigger", detail=trigger_detail)
        status = "completed"
        try:
            self.active_targets[run_id] = {str(step["device_id"]) for step in _action_steps(routine["spec"]["steps"])}
            await self._notify_activity()
            if "description" in routine["spec"] or isinstance(routine["spec"].get("conditions"), dict) or any(
                step.get("type") not in {"action", "wait", "check"} for step in routine["spec"]["steps"]):
                status = await self._run_flow(routine, run_id, starting_devices)
                return
            devices = starting_devices
            for condition in routine["spec"]["conditions"]:
                if condition.get("type") == "time_window":
                    passed, detail = await self._evaluate_time_window(condition)
                    record_event(run_id, "condition", detail=detail, result="pass" if passed else "skip")
                    if not passed:
                        status = "skipped"
                        return
                    continue
                if condition.get("type") == "sun":
                    if not self.solar_times:
                        raise RuntimeError("Orari di alba/tramonto non disponibili")
                    schedule = await self.solar_times()
                    boundary = schedule[condition["event"]] + timedelta(minutes=condition["offset_minutes"])
                    checked_at = datetime.now(boundary.tzinfo)
                    passed = (checked_at < boundary) if condition["relation"] == "before" else (checked_at >= boundary)
                    record_event(run_id, "condition", detail=f"{'Prima' if condition['relation'] == 'before' else 'Dopo'} {'alba' if condition['event'] == 'sunrise' else 'tramonto'} {condition['offset_minutes']:+d} minuti; soglia {boundary:%H:%M}, ora {checked_at:%H:%M}", result="pass" if passed else "skip")
                    if not passed:
                        status = "skipped"
                        return
                    continue
                device = devices.get(condition["device_id"])
                actual = _state(device)
                passed = (actual == condition["value"]) == (condition["operator"] == "is")
                comparison = "uguale a" if condition["operator"] == "is" else "diverso da"
                record_event(run_id, "condition", device_id=condition["device_id"], device_name=str((device or {}).get("name") or ""),
                             detail=f"Stato letto: {actual or 'non disponibile'}; richiesto: {comparison} {condition['value']}",
                             before_state=actual, result="pass" if passed else "skip")
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
                    devices = await self._snapshot_for([routine])
                elif step["type"] == "check":
                    devices = await self._snapshot_for([routine])
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
                        await self.command(device_id, step["action"], fresh["spec"]["steps"][0].get("value"))
                    except Exception as exc:
                        record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail=str(exc), before_state=before, result="failed")
                        raise
                    record_event(run_id, "command", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], detail="Confermato dal connettore; stato da verificare", before_state=before, result="accepted")
                    devices = await self._snapshot_for([routine])
                    after = _state(devices.get(device_id))
                    record_event(run_id, "observed", device_id=device_id, device_name=str(device.get("name") or ""), action=step["action"], before_state=before, after_state=after, result="changed" if after != before else "unchanged")
        except asyncio.CancelledError:
            status = "cancelled"
            record_event(run_id, "cancel", detail=self.cancel_reasons.get(asyncio.current_task(), "Add-on arrestato"))
            raise
        except Exception as exc:
            status = "failed"
            record_event(run_id, "error", detail=str(exc))
        finally:
            self.active_targets.pop(run_id, None)
            await self._notify_activity()
            with _connect() as db:
                db.execute("UPDATE routine_runs SET ended_at = ?, status = ? WHERE id = ?", (_now(), status, run_id))
