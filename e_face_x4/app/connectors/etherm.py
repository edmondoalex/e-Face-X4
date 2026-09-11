from __future__ import annotations

from typing import Any
import base64

import httpx

from ..config import ProviderConfig
from .base import Connector


def normalize_thermostats(payload: dict[str, Any]) -> list[dict[str, Any]]:
    config = ((payload.get("meta") or {}).get("vtherm_config") or {}) if isinstance(payload, dict) else {}
    configured = {str(item.get("id")): item for item in config.get("thermostats", []) if isinstance(item, dict)}
    result = []
    for entity in payload.get("entities", []) if isinstance(payload, dict) else []:
        if not isinstance(entity, dict) or str(entity.get("type") or "").lower() != "thermostats":
            continue
        source_id = str(entity.get("id") or "")
        static = entity.get("static") if isinstance(entity.get("static"), dict) else {}
        realtime = entity.get("realtime") if isinstance(entity.get("realtime"), dict) else {}
        therm = realtime.get("THERM") if isinstance(realtime.get("THERM"), dict) else {}
        threshold = therm.get("TEMP_THR") if isinstance(therm.get("TEMP_THR"), dict) else {}
        cfg = configured.get(source_id, {})
        season = str(therm.get("ACT_SEA") or "WIN").upper()
        demand = str(therm.get("DEMAND_ON") or therm.get("OUT_STATUS") or "OFF").upper() == "ON"
        mode = str(therm.get("ACT_MODEL") or therm.get("ACT_MODE") or "OFF").upper()
        state = ("COOLING" if season == "SUM" else "HEATING") if demand and mode != "OFF" else "OFF"
        result.append({
            "id": f"therm:{source_id}", "source_id": source_id, "provider": "etherm",
            "name": str(entity.get("name") or static.get("DES") or f"Termostato {source_id}"),
            "kind": "climate", "room": str(cfg.get("room") or cfg.get("group") or "Clima"),
            "state": state, "temperature": realtime.get("TEMP"), "value": realtime.get("TEMP"),
            "target_temperature": threshold.get("VAL"), "humidity": realtime.get("RH"),
            "season": season, "mode": mode, "pwm": therm.get("PWM"), "unit": "°C",
            "icon": "mdi:thermostat", "state_key": f"therm:{source_id}",
        })
    return result


class EThermConnector(Connector):
    id = "etherm"
    label = "e-Therm Plus KS"

    def __init__(self, config: ProviderConfig, timeout_s: float) -> None:
        self.config = config
        self.timeout_s = timeout_s

    def headers(self) -> dict[str, str]:
        if self.config.auth_mode == "basic" and self.config.username:
            encoded = base64.b64encode(f"{self.config.username}:{self.config.password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if self.config.auth_mode == "token" and self.config.token:
            return {"Authorization": f"Bearer {self.config.token}"}
        return {}

    async def snapshot(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"id": self.id, "label": self.label, "status": "disabled", "items": []}
        if not self.config.base_url:
            return {"id": self.id, "label": self.label, "status": "misconfigured", "items": []}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
                response = await client.get(f"{self.config.base_url}/api/entities?type=thermostats", headers=self.headers())
                response.raise_for_status()
                payload = response.json()
            items = normalize_thermostats(payload)
            return {"id": self.id, "label": self.label, "status": "online", "items": items}
        except httpx.HTTPStatusError as exc:
            reason = f"HTTP {exc.response.status_code}: autenticazione non valida" if exc.response.status_code == 401 else f"HTTP {exc.response.status_code} da e-Therm"
            return {"id": self.id, "label": self.label, "status": "offline", "reason": reason, "items": []}
        except httpx.ConnectError:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": "indirizzo non raggiungibile o connessione rifiutata sulla porta 8080", "items": []}
        except httpx.TimeoutException:
            return {"id": self.id, "label": self.label, "status": "offline", "reason": "timeout collegandosi a e-Therm", "items": []}
        except (httpx.HTTPError, ValueError):
            return {"id": self.id, "label": self.label, "status": "offline", "reason": "risposta e-Therm non valida", "items": []}

    async def command(self, source_id: str, action: str, value: Any) -> dict[str, Any]:
        if action not in {"set_target", "set_mode", "set_season"}:
            raise ValueError("comando termostato non valido")
        body = {"type": "thermostats", "id": int(source_id), "action": action, "value": value}
        async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False) as client:
            response = await client.post(f"{self.config.base_url}/api/cmd", headers=self.headers(), json=body)
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or not result.get("ok"):
            raise ValueError(str(result.get("error") if isinstance(result, dict) else "comando fallito"))
        return {"ok": True}
