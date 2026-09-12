from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from .base import Connector


def _on(value: Any) -> bool:
    return str(value or "").strip().upper() in {"1", "ON", "YES", "TRUE", "AL", "ALARM", "AUTO"}


def normalize_ksenia(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entity in payload.get("entities", []) if isinstance(payload, dict) else []:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "").lower()
        if entity_type not in {"partitions", "zones"}:
            continue
        source_id = str(entity.get("id") or "")
        static = entity.get("static") if isinstance(entity.get("static"), dict) else {}
        realtime = entity.get("realtime") if isinstance(entity.get("realtime"), dict) else {}
        name = str(entity.get("name") or static.get("DES") or ("Area" if entity_type == "partitions" else "Zona") + f" {source_id}")
        if entity_type == "partitions":
            arm = str(realtime.get("ARM") or "D").upper()
            ast = str(realtime.get("AST") or "").strip().upper()
            alarm = bool(ast and ast != "OK")
            armed = arm not in {"", "D", "DISARMED", "OFF"}
            state = "ALARM" if alarm else "ARMED" if armed else "DISARMED"
            items.append({"id": f"ksenia-partition:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_partition", "name": name, "room": name, "state": state, "arm_state": arm, "alarm": alarm, "countdown": realtime.get("T") or realtime.get("TIME"), "icon": "mdi:shield-home-outline"})
        else:
            alarm = str(realtime.get("STA") or "").strip().upper() == "A"
            tamper_raw = str(realtime.get("T") or realtime.get("TMP") or "").strip().upper()
            tamper = bool(tamper_raw and tamper_raw not in {"0", "N", "NO", "OK"})
            bypass_raw = str(realtime.get("BYP") or "").strip().upper()
            bypassed = bypass_raw.startswith(("MAN", "AUTO"))
            mask_raw = str(realtime.get("VAS") or "").strip().upper()
            masked = bool(mask_raw and mask_raw not in {"0", "F", "N", "NO", "OK"})
            state = "ALARM" if alarm else "TAMPER" if tamper else "MASKED" if masked else "BYPASSED" if bypassed else "CLOSED"
            items.append({"id": f"ksenia-zone:{source_id}", "source_id": source_id, "provider": "ksenia", "kind": "alarm_zone", "name": name, "room": str(static.get("LOC") or "Sicurezza"), "state": state, "alarm": alarm, "tamper": tamper, "masked": masked, "bypassed": bypassed, "partitions": static.get("PRT"), "icon": "mdi:shield-outline"})
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
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
                response = await client.get(f"{self.config.base_url}/api/entities")
                response.raise_for_status()
                items = normalize_ksenia(response.json())
            return {"id": self.id, "label": self.label, "status": "online", "items": items}
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": f"Ksenia non raggiungibile ({type(exc).__name__})", "items": []}

    async def command(self, kind: str, source_id: str, action: str) -> dict[str, Any]:
        allowed = {"partition": {"arm_delay", "arm_instant", "disarm"}, "zone": {"bypass_on", "bypass_off"}}
        if action not in allowed.get(kind, set()):
            raise ValueError("comando Ksenia non valido")
        body = {"type": "partitions" if kind == "partition" else "zones", "id": int(source_id), "action": action}
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
            response = await client.post(f"{self.config.base_url}/api/cmd", json=body)
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or not result.get("ok"):
            error = str(result.get("error") if isinstance(result, dict) else "comando fallito")
            if error == "pin_session_required":
                raise ValueError("Il pannello Ksenia richiede una sessione PIN")
            raise ValueError(error)
        return {"ok": True}
