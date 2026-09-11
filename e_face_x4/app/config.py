from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    enabled: bool
    base_url: str
    token: str


@dataclass(frozen=True)
class Settings:
    demo_mode: bool
    request_timeout_s: float
    buspro: ProviderConfig
    evoice: ProviderConfig


def _provider(value: Any) -> ProviderConfig:
    raw = value if isinstance(value, dict) else {}
    return ProviderConfig(
        enabled=bool(raw.get("enabled", False)),
        base_url=str(raw.get("base_url") or "").strip().rstrip("/"),
        token=str(raw.get("token") or "").strip(),
    )


def load_settings() -> Settings:
    path = Path(os.environ.get("EFACE_OPTIONS", "/data/options.json"))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    timeout = min(15.0, max(1.0, float(raw.get("request_timeout_s", 4))))
    return Settings(
        demo_mode=bool(raw.get("demo_mode", True)),
        request_timeout_s=timeout,
        buspro=_provider(raw.get("buspro")),
        evoice=_provider(raw.get("evoice")),
    )

