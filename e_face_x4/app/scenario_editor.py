"""Validate the complete e-HDL light-scenario editing contract."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from fastapi import HTTPException


def fingerprint(item: dict[str, Any]) -> str:
    encoded = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _fail(message: str) -> None:
    raise HTTPException(400, message)


def _integer(value: Any, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool):
        _fail(f"{label}: numero non valido")
    try:
        number = int(value)
        if str(value).strip() not in {str(number), f"{number}.0"}:
            _fail(f"{label}: numero intero richiesto")
    except (TypeError, ValueError):
        _fail(f"{label}: numero non valido")
    if not minimum <= number <= maximum:
        _fail(f"{label}: valore fuori intervallo ({minimum}–{maximum})")
    return number


def _address(item: dict, label: str) -> dict[str, int]:
    return {key: _integer(item.get(key), 0 if key != "channel" else 1, 255, label)
            for key in ("subnet_id", "device_id", "channel")}


def _known(item: dict, catalog: list[dict], *, kind: str) -> bool:
    entity = str(item.get("entity_id") or "").lower()
    for device in catalog:
        if str(device.get("type") or "light").lower() != kind:
            continue
        if entity and str(device.get("entity_id") or "").lower() == entity:
            return True
        if not entity and not device.get("entity_id") and all(
            item.get(key) == device.get(key) for key in ("subnet_id", "device_id", "channel")):
            return True
    return False


def validate(payload: dict, catalog: list[dict], groups: list[dict], triggers: list[dict],
             existing: dict | None = None) -> dict:
    if not isinstance(payload, dict):
        _fail("Scenario non valido")
    name = payload.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        _fail("Nome scenario obbligatorio (massimo 80 caratteri)")
    run_enabled, onoff_enabled = payload.get("run_enabled"), payload.get("onoff_enabled")
    if type(run_enabled) is not bool or type(onoff_enabled) is not bool or not (run_enabled or onoff_enabled):
        _fail("Abilita RUN oppure ON/OFF")
    out = {"name": name.strip(), "run_enabled": run_enabled, "onoff_enabled": onoff_enabled}
    old_items = existing.get("items", []) if existing else []
    old_covers = existing.get("covers", []) if existing else []
    old_item_ids = {_target_id(it) for it in old_items if isinstance(it, dict)}
    old_cover_ids = {_target_id(it) for it in old_covers if isinstance(it, dict)}
    items = payload.get("items", [])
    covers = payload.get("covers", [])
    combos = payload.get("combination_targets", [])
    if not all(isinstance(value, list) and len(value) <= 300 for value in (items, covers, combos)):
        _fail("Troppi elementi o elenco non valido")
    clean_items, seen_items = [], set()
    for item in items:
        if not isinstance(item, dict) or item.get("state") not in {"ON", "OFF"}:
            _fail("Stato luce non valido")
        if item.get("entity_id"):
            entity = str(item["entity_id"]).strip().lower()
            if not re.fullmatch(r"(?:light|switch)\.[a-z0-9_]+", entity):
                _fail("Entità luce non valida")
            clean = {"entity_id": entity, "domain": entity.split(".", 1)[0]}
        else:
            clean = _address(item, "Indirizzo luce")
        clean["state"] = item["state"]
        brightness = item.get("brightness")
        clean["brightness"] = None if brightness is None or item["state"] == "OFF" else _integer(brightness, 0, 255, "Luminosità")
        if clean.get("domain") == "switch" and clean["brightness"] is not None:
            _fail("Uno switch non ha luminosità")
        key = _target_id(clean)
        if key in seen_items or (not _known(clean, catalog, kind="light") and key not in old_item_ids):
            _fail("Luce duplicata o non presente nel catalogo HDL")
        seen_items.add(key)
        clean_items.append(clean)
    clean_covers, seen_covers = [], set()
    group_ids = {str(group.get("id")) for group in groups if isinstance(group, dict)}
    for item in covers:
        if not isinstance(item, dict) or item.get("kind", "single") not in {"single", "group", "ha"}:
            _fail("Tapparella non valida")
        kind = item.get("kind", "single")
        command = item.get("command")
        if command not in {"OPEN", "CLOSE", "STOP", "SET_POSITION"}:
            _fail("Comando tapparella non valido")
        clean = {"kind": kind, "command": command,
                 "position": _integer(item.get("position"), 0, 100, "Posizione") if command == "SET_POSITION" else None,
                 "ramp_minutes": _integer(item.get("ramp_minutes", 0), 0, 240, "Durata rampa"),
                 "step_seconds": _integer(item.get("step_seconds", 5), 1, 120, "Passo rampa"),
                 "two_phase_open": item.get("two_phase_open", False),
                 "phase1_pct": _integer(item.get("phase1_pct", 25), 1, 99, "Prima fase"),
                 "phase2_delay_minutes": _integer(item.get("phase2_delay_minutes", 4), 0, 240, "Attesa seconda fase")}
        if type(clean["two_phase_open"]) is not bool:
            _fail("Apertura in due fasi non valida")
        if kind == "group":
            group_id = item.get("group_id")
            if not isinstance(group_id, str) or not group_id or (group_id not in group_ids and _target_id(item) not in old_cover_ids):
                _fail("Gruppo tapparelle non presente")
            clean["group_id"] = group_id
        elif kind == "ha":
            entity = str(item.get("entity_id") or "").strip().lower()
            if not re.fullmatch(r"cover\.[a-z0-9_]+", entity):
                _fail("Entità tapparella non valida")
            clean["entity_id"] = entity
        else:
            clean.update(_address(item, "Indirizzo tapparella"))
        key = _target_id(clean)
        if key in seen_covers or (kind != "group" and not _known(clean, catalog, kind="cover") and key not in old_cover_ids):
            _fail("Tapparella duplicata o non presente nel catalogo HDL")
        seen_covers.add(key)
        clean_covers.append(clean)
    clean_combos, seen_combos = [], set()
    for item in combos:
        if not isinstance(item, dict):
            _fail("Combinazione non valida")
        clean = {key: _integer(item.get(key), 1 if key == "switch_number" else 0, 255, "Combinazione")
                 for key in ("subnet_id", "device_id", "switch_number")}
        key = tuple(clean.values())
        if key in seen_combos:
            _fail("Combinazione duplicata")
        seen_combos.add(key)
        clean_combos.append(clean)
    if not (clean_items or clean_covers or clean_combos):
        _fail("Aggiungi almeno una luce, tapparella o combinazione")
    out.update(items=clean_items, covers=clean_covers, combination_targets=clean_combos)
    trigger = payload.get("trigger") or {"enabled": False, "type": "none", "time": "", "offset_min": 0}
    if not isinstance(trigger, dict) or type(trigger.get("enabled")) is not bool:
        _fail("Trigger non valido")
    trigger_type = trigger.get("type", "none")
    if trigger_type not in {"none", "time", "sunrise", "sunset", "sveglia"}:
        _fail("Tipo trigger non valido")
    clock = str(trigger.get("time") or "").strip()
    if clock and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
        _fail("Orario non valido")
    if trigger["enabled"] and trigger_type == "time" and not clock:
        _fail("Scegli l'orario di avvio")
    out["trigger"] = {"enabled": trigger["enabled"], "type": trigger_type, "time": clock,
                      "offset_min": _integer(trigger.get("offset_min", 0), -1440, 1440, "Scostamento trigger")}
    ha_enabled = payload.get("ha_trigger_enabled", False)
    ha_id = str(payload.get("ha_trigger_id") or "").strip()
    if type(ha_enabled) is not bool or len(ha_id) > 80:
        _fail("Trigger e-Control non valido")
    known_trigger_ids = {str(item.get("id")) for item in triggers if isinstance(item, dict)}
    if ha_enabled and (not ha_id or ha_id not in known_trigger_ids):
        _fail("Seleziona un trigger e-Control esistente")
    out["ha_trigger_enabled"] = ha_enabled
    out["ha_trigger_id"] = ha_id if ha_enabled else ""
    return out


def _target_id(item: dict) -> tuple:
    if item.get("group_id"):
        return ("group", str(item["group_id"]))
    if item.get("entity_id"):
        return ("ha", str(item["entity_id"]).lower())
    return ("buspro", item.get("subnet_id"), item.get("device_id"), item.get("channel"))
