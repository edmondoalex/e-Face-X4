"""Narrow, user-facing e-ThermoMind API contract.

Never forward arbitrary paths or whole configuration documents: the upstream API
also contains installer and direct-actuator controls.
"""
from __future__ import annotations

import math
import re
from fastapi import HTTPException

MODULES = {
    "resistenze_volano", "volano_to_acs", "volano_to_puffer", "puffer_to_acs",
    "impianto", "gas_emergenza", "caldaia_legna", "solare", "miscelatrice",
    "curva_climatica", "pdc",
}
SETPOINTS = {
    "acs": {"setpoint_c": (40, 85), "max_c": (50, 85)},
    "volano": {"max_c": (40, 95), "min_to_acs_c": (35, 75), "evening_dump_after_h": (0, 23.99)},
    "puffer": {"max_c": (50, 90), "setpoint_c": (40, 90), "min_to_acs_c": (40, 80)},
    "impianto": {"volano_min_c": (35, 80), "puffer_min_c": (35, 80)},
    "resistance": {"export_on_min_w": (0, 6000)},
}


def command_payload(payload: dict) -> tuple[str, dict]:
    kind = payload.get("kind")
    if kind == "module":
        key = payload.get("key")
        if not isinstance(key, str) or key not in MODULES or type(payload.get("value")) is not bool:
            raise HTTPException(400, "Modulo o valore non valido")
        pin = str(payload.get("pin") or "")
        if len(pin) > 32:
            raise HTTPException(400, "PIN non valido")
        return "modules", {"key": key, "value": payload["value"], "pin": pin}
    if kind == "setpoint":
        section, key = payload.get("section"), payload.get("key")
        if section == "impianto" and key in {"pdc_ready", "puffer_ready"}:
            if type(payload.get("value")) is not bool:
                raise HTTPException(400, "Consenso non valido")
            return "setpoints", {"impianto": {key: payload["value"]}}
        if section == "impianto" and key == "source_mode":
            if not isinstance(payload.get("value"), str) or payload["value"] not in {"AUTO", "PDC", "PUFFER"}:
                raise HTTPException(400, "Sorgente non valida")
            return "setpoints", {"impianto": {key: payload["value"]}}
        if section == "volano" and key == "evening_dump_trigger":
            if not isinstance(payload.get("value"), str) or payload["value"] not in {"time", "entity"}:
                raise HTTPException(400, "Trigger scarico non valido")
            return "setpoints", {"volano": {key: payload["value"]}}
        if section == "volano" and key == "evening_dump_run_entity":
            value = payload.get("value")
            if not isinstance(value, str) or not re.fullmatch(r"(?:switch|input_boolean)\.[a-z0-9_]{1,100}", value):
                raise HTTPException(400, "Entità RUN non valida")
            return "setpoints", {"volano": {key: value}}
        if section == "impianto" and key == "season_mode":
            if not isinstance(payload.get("value"), str) or payload["value"] not in {"winter", "summer"}:
                raise HTTPException(400, "Stagione non valida")
            return "setpoints", {"impianto": {"season_mode": payload["value"]}}
        bounds = SETPOINTS.get(section, {}).get(key) if isinstance(section, str) and isinstance(key, str) else None
        try:
            value = float(payload.get("value"))
        except (TypeError, ValueError):
            raise HTTPException(400, "Valore non numerico")
        if not bounds or not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise HTTPException(400, "Setpoint fuori intervallo")
        return "setpoints", {section: {key: value}}
    if kind == "force":
        target = payload.get("target")
        if not isinstance(target, str) or target not in {"acs", "volano"}:
            raise HTTPException(400, "Forzatura non valida")
        if payload.get("active") is False:
            return f"{target}/force_puffer/clear", {}
        minutes = payload.get("minutes")
        if type(minutes) is not int or not 1 <= minutes <= 240:
            raise HTTPException(400, "Durata non valida")
        return f"{target}/force_puffer", {"minutes": minutes}
    if kind == "zone":
        entity = str(payload.get("entity_id") or "")
        if not entity.startswith("climate.") or len(entity) > 120:
            raise HTTPException(400, "Zona non valida")
        try:
            temperature = float(payload.get("temperature"))
        except (TypeError, ValueError):
            raise HTTPException(400, "Temperatura non valida")
        if not math.isfinite(temperature) or not 5 <= temperature <= 35:
            raise HTTPException(400, "Temperatura fuori intervallo")
        return "climate_setpoint", {"entity_id": entity, "temperature": temperature}
    raise HTTPException(400, "Comando non supportato")
