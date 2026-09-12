from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


_snapshot_cache: dict[str, list[dict[str, Any]]] = {}


def _on(value: Any) -> bool:
    return str(value or "").strip().upper() in {"1", "ON", "YES", "TRUE", "AL", "ALARM", "AUTO"}


def _zone_sensor(name: str, category: str) -> tuple[str, str]:
    label = name.upper()
    if any(word in label for word in ("FUMO", "SMOKE")):
        return "smoke", "mdi:smoke-detector-variant"
    if any(word in label for word in ("ACQUA", "ALLAG", "WATER")):
        return "water", "mdi:water-alert-outline"
    if "TAPPARELLA" in label:
        return "shutter", "mdi:window-shutter"
    if any(word in label for word in ("PORTA", "PORTONE", "CANCELLO", "PORTONCINO")):
        return "door", "mdi:door-closed"
    if any(word in label for word in ("FIN", "FINESTRA")):
        return "window", "mdi:window-closed-variant"
    if category == "CMD" or any(word in label for word in ("SOCCORSO", "PANICO", "CMD")):
        return "button", "mdi:gesture-tap-button"
    if category == "EMOV" or any(word in label for word in ("SPY OUT", "WATCH OUT", "IPC ", "EXT ")):
        return "motion_outdoor", "mdi:cctv"
    if category == "IMOV" or any(word in label for word in ("IR ", "SPIDER", "BX80")):
        return "motion_indoor", "mdi:motion-sensor"
    return "contact", "mdi:access-point"


def normalize_ksenia(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entity in payload.get("entities", []) if isinstance(payload, dict) else []:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "").lower()
        if entity_type not in {"partitions", "zones", "scenarios", "systems"}:
            continue
        source_id = str(entity.get("id") or "")
        static = entity.get("static") if isinstance(entity.get("static"), dict) else {}
        realtime = entity.get("realtime") if isinstance(entity.get("realtime"), dict) else {}
        name = str(entity.get("name") or static.get("DES") or ("Area" if entity_type == "partitions" else "Zona") + f" {source_id}")
        if entity_type == "partitions":
            arm = str(realtime.get("ARM") or "D").upper()
            ast = str(realtime.get("AST") or "").strip().upper()
            tst = str(realtime.get("TST") or "").strip().upper()
            alarm = ast in {"AL", "ALARM"}
            alarm_memory = ast in {"AM", "MEM", "MEMORY"}
            tamper = tst in {"TAM", "TAMPER"}
            tamper_memory = tst in {"TM", "AM", "MEM", "MEMORY"}
            armed = arm not in {"", "D", "DISARMED", "OFF"}
            state = "ALARM" if alarm else "TAMPER" if tamper else "ARMED" if armed else "DISARMED"
            mode = "instant" if arm in {"IA", "I"} or arm.startswith("IA") else "delayed" if armed else "off"
            items.append({"id": f"ksenia-partition:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_partition", "name": name, "room": name, "state": state, "arm_state": arm, "arm_mode": mode, "alarm": alarm, "alarm_memory": alarm_memory, "tamper": tamper, "tamper_memory": tamper_memory, "countdown": realtime.get("T") or realtime.get("TIME"), "entry_delay": realtime.get("ENTRY_DELAY") or 0, "exit_delay": realtime.get("EXIT_DELAY") or 0, "test_state": tst, "icon": "mdi:shield-home-outline"})
        elif entity_type == "zones":
            category = str(static.get("CAT") or "").strip().upper()
            sensor_type, sensor_icon = _zone_sensor(name, category)
            zone_status = str(realtime.get("STA") or "").strip().upper()
            active = zone_status == "A"
            memory_raw = str(realtime.get("T") or "").strip().upper()
            zone_memory = bool(memory_raw and memory_raw not in {"0", "N", "NO", "OK"})
            tamper = zone_status in {"T", "TAM", "TAMPER"}
            bypass_raw = str(realtime.get("BYP") or "").strip().upper()
            bypassed = bypass_raw.startswith(("MAN", "AUTO"))
            mask_raw = str(realtime.get("VAS") or "").strip().upper()
            masked = zone_status == "FM" or bool(mask_raw and mask_raw not in {"0", "F", "N", "NO", "OK"})
            state = "TAMPER" if tamper else "ACTIVE" if active else "MASKED" if masked else "BYPASSED" if bypassed else "CLOSED"
            items.append({"id": f"ksenia-zone:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_zone", "name": name, "room": str(static.get("LOC") or ""), "state": state, "active": active, "alarm": False, "tamper": tamper, "memory": zone_memory, "masked": masked, "bypassed": bypassed, "partitions": static.get("PRT"), "sensor_type": sensor_type, "icon": sensor_icon})
        elif entity_type == "scenarios":
            category = str(static.get("CAT") or "").strip().upper()
            if category not in {"ARM", "DISARM", "PARTIAL"}:
                continue
            items.append({"id": f"ksenia-scenario:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_scenario", "name": name, "room": "Sicurezza", "state": category, "category": category, "pin_required": str(static.get("PIN") or "").upper() not in {"", "N", "NO"}, "icon": "mdi:shield-key-outline"})
        else:
            arm = realtime.get("ARM") if isinstance(realtime.get("ARM"), dict) else static.get("ARM") if isinstance(static.get("ARM"), dict) else {}
            description = str(arm.get("D") or "").strip()
            status = str(arm.get("S") or "").strip().upper()
            items.append({"id": f"ksenia-system:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_system", "name": "Sistema Ksenia", "room": "", "state": status, "arm_description": description, "arm_status": status, "icon": "mdi:shield-home-outline"})
    return items


class KseniaConnector(Connector):
    id = "ksenia"
    label = "Ksenia lares"

    def __init__(self, config: ProviderConfig, timeout_s: float) -> None:
        self.config = config
        self.timeout_s = timeout_s

    async def snapshot(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"id": self.id, "label": self.label, "status": "disabled", "items": []}
        try:
            async with httpx.AsyncClient(timeout=max(12.0, self.timeout_s), follow_redirects=False) as client:
                response = await client.get(f"{self.config.base_url}/api/entities")
                response.raise_for_status()
                items = normalize_ksenia(response.json())
            if not items:
                raise ValueError("nessuna area o zona ricevuta")
            _snapshot_cache[self.config.base_url] = items
            return {"id": self.id, "label": self.label, "status": "online", "items": items}
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            cached = _snapshot_cache.get(self.config.base_url)
            if cached:
                return {"id": self.id, "label": self.label, "status": "stale", "reason": "ultimo stato Ksenia disponibile", "items": cached}
            return {"id": self.id, "label": self.label, "status": "offline", "reason": f"Ksenia non raggiungibile ({type(exc).__name__})", "items": []}

    @staticmethod
    def _parse(response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Risposta non valida dalla centrale Ksenia")
        return result

    @staticmethod
    def _command_error(error: Any) -> str:
        raw = str(error or "").strip()
        lowered = raw.lower()
        if any(word in lowered for word in ("pin", "login", "credential", "auth", "denied")):
            return "Codice Ksenia errato o non autorizzato"
        if "timeout" in lowered:
            return "La centrale Ksenia non risponde"
        return raw or "Comando rifiutato dalla centrale Ksenia"

    async def command(self, kind: str, source_id: str, action: str, pin: str) -> dict[str, Any]:
        allowed = {"partition": {"arm_delay", "arm_instant", "disarm"}, "zone": {"bypass_on", "bypass_off"}, "scenario": {"execute"}}
        if action not in allowed.get(kind, set()):
            raise ValueError("comando Ksenia non valido")
        pin = str(pin or "").strip()
        if not pin:
            raise ValueError("Inserisci il codice Ksenia")
        entity_type = {"partition": "partitions", "zone": "zones", "scenario": "scenarios"}[kind]
        async with httpx.AsyncClient(timeout=max(12.0, self.timeout_s), follow_redirects=False) as client:
            session = self._parse(await client.post(f"{self.config.base_url}/api/cmd", json={"type": "session", "action": "start", "value": {"pin": pin, "minutes": 1}}))
            if not session.get("ok") or not session.get("token"):
                raise ValueError(self._command_error(session.get("error")))
            token = str(session["token"])
            try:
                body = {"type": entity_type, "id": int(source_id), "action": action, "token": token}
                result = self._parse(await client.post(f"{self.config.base_url}/api/cmd", json=body))
                if not result.get("ok"):
                    raise ValueError(self._command_error(result.get("error")))
            finally:
                try:
                    await client.post(f"{self.config.base_url}/api/cmd", json={"type": "session", "action": "end", "token": token})
                except httpx.HTTPError:
                    pass
        return {"ok": True}
