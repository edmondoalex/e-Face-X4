from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    enabled: bool
    base_url: str
    token: str
    auth_mode: str = "none"
    username: str = ""
    password: str = ""
    installation_id: str = ""


@dataclass(frozen=True)
class Settings:
    home_name: str
    installer_password: str
    demo_mode: bool
    request_timeout_s: float
    nav_icons: dict[str, str]
    buspro: ProviderConfig
    evoice: ProviderConfig
    etherm: ProviderConfig
    ksenia: ProviderConfig


def _provider(value: Any) -> ProviderConfig:
    raw = value if isinstance(value, dict) else {}
    base_url = str(raw.get("base_url") or "").strip().strip("'\"").rstrip("/")
    if base_url:
        match = re.match(r"^(https?)\s*:?\s*/?\s*/?\s*(.+)$", base_url, re.IGNORECASE)
        if match:
            base_url = f"{match.group(1).lower()}://{match.group(2)}"
        elif not re.match(r"^[a-z][a-z0-9+.-]*://", base_url, re.IGNORECASE):
            base_url = f"http://{base_url.lstrip('/')}"
    return ProviderConfig(
        enabled=bool(raw.get("enabled", False)),
        base_url=base_url,
        token=str(raw.get("token") or "").strip(),
        auth_mode=str(raw.get("auth_mode") or ("token" if raw.get("token") else "none")).strip().lower(),
        username=str(raw.get("username") or "").strip(),
        password=str(raw.get("password") or ""),
        installation_id=str(raw.get("installation_id") or "").strip(),
    )


def load_settings() -> Settings:
    path = Path(os.environ.get("EFACE_OPTIONS", "/data/options.json"))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    timeout = min(15.0, max(1.0, float(raw.get("request_timeout_s", 4))))
    icon_defaults = {
        "watch": "mdi:television-play", "listen": "mdi:music", "lights": "mdi:lightbulb-group",
        "extra": "mdi:shape", "scenarios": "mdi:creation", "covers": "mdi:blinds-horizontal", "comfort": "mdi:home-thermometer", "security": "mdi:shield-home",
    }
    raw_icons = raw.get("nav_icons") if isinstance(raw.get("nav_icons"), dict) else {}
    nav_icons = {key: str(raw_icons.get(key) or value).strip() for key, value in icon_defaults.items()}
    return Settings(
        home_name=str(raw.get("home_name") or "Casa").strip() or "Casa",
        installer_password=str(raw.get("installer_password") or ""),
        demo_mode=bool(raw.get("demo_mode", True)),
        request_timeout_s=timeout,
        nav_icons=nav_icons,
        buspro=_provider(raw.get("buspro")),
        evoice=_provider(raw.get("evoice")),
        etherm=_provider(raw.get("etherm")),
        ksenia=_provider(raw.get("ksenia")),
    )
