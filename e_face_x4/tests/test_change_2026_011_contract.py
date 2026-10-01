from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import ProviderConfig
from app.connectors.buspro import BusproConnector, normalize_snapshot


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "change_2026_011_smart_home_snapshot.json"
PROTECTED_SECURITY_TERMS = {
    "alarm",
    "alarm_system",
    "arm",
    "bypass",
    "disarm",
    "partition",
    "security_scenario",
    "zone",
}


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_change_2026_011_fixture_has_versioned_complete_contract() -> None:
    smart_home = load_fixture()["smart_home"]
    assert smart_home["schema_version"] == "1.0"
    assert smart_home["organization_schema_version"] == 1
    assert all(isinstance(smart_home[key], list) for key in ("floors", "rooms", "groups", "devices"))

    required = {
        "source",
        "device_id",
        "name",
        "device_class",
        "native_type",
        "native_id",
        "capabilities",
        "commands",
        "features",
        "read_only",
        "available",
        "stale",
        "state",
        "floor_id",
        "floor_name",
        "room_id",
        "room_name",
        "group_ids",
        "group_names",
        "icon_auto",
        "icon_override",
        "icon",
        "orphaned",
        "categories",
        "orders",
        "visible",
        "favorite",
        "shortcut",
        "visual_category",
    }
    assert smart_home["devices"]
    assert all(required <= set(device) for device in smart_home["devices"])
    assert all(device["source"] in {"hdl", "ksenia"} for device in smart_home["devices"])


def test_change_2026_011_fixture_keeps_source_identity_and_organization() -> None:
    devices = load_fixture()["smart_home"]["devices"]
    identities = {(device["source"], device["device_id"]) for device in devices}
    assert len(identities) == len(devices)

    same_native = [device for device in devices if device["native_id"] == "shared-native-id"]
    assert {device["source"] for device in same_native} == {"hdl", "ksenia"}
    assert len({f'{device["source"]}:{device["device_id"]}' for device in same_native}) == 2

    organized = next(device for device in devices if device["source"] == "hdl")
    assert organized["floor_id"] == "floor-ground"
    assert organized["room_id"] == "room-office"
    assert organized["group_ids"] == ["group-work"]
    assert organized["icon"] == organized["icon_override"]

    orphan = next(device for device in devices if device["orphaned"])
    assert orphan["floor_id"] == ""
    assert orphan["room_id"] == ""


def test_change_2026_011_fixture_excludes_protected_ksenia_security() -> None:
    devices = load_fixture()["smart_home"]["devices"]
    for device in devices:
        assert str(device["device_class"]).casefold() not in PROTECTED_SECURITY_TERMS
        assert str(device["native_type"]).casefold() not in PROTECTED_SECURITY_TERMS
        assert not (set(map(str.casefold, device["capabilities"])) & PROTECTED_SECURITY_TERMS)


def test_change_2026_011_legacy_fixture_remains_usable_before_producer_approval() -> None:
    payload = load_fixture()
    payload.pop("smart_home")
    normalized = normalize_snapshot(payload)
    assert [device["name"] for device in normalized["devices"]] == ["Legacy light"]
    assert normalized["devices"][0]["state"] == "ON"


def test_change_2026_011_consumer_prefers_smart_home_and_tolerates_unknown_fields() -> None:
    normalized = normalize_snapshot(load_fixture())
    devices = normalized["devices"]
    assert {device["id"] for device in devices} == {
        "hdl:1.2.3",
        "ksenia:ksn_light_demo",
        "ksenia:ksn_temperature_demo",
    }
    assert all(device["source"] in {"hdl", "ksenia"} for device in devices)
    hdl = next(device for device in devices if device["id"] == "hdl:1.2.3")
    assert hdl["room"] == "Office"
    assert hdl["categories"] == ["lights"]
    assert hdl["orders"] == {"lights": 1}
    assert hdl["favorite"] is True
    assert hdl["allowed_actions"] == ["on", "off", "brightness"]
    assert hdl["organization_authority"] == "e-control-hub"


@pytest.mark.asyncio
async def test_change_2026_011_command_uses_only_canonical_hub_endpoint(monkeypatch) -> None:
    fixture = load_fixture()
    observed: list[tuple[str, str, dict[str, Any] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        observed.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(200, json=fixture)
        return httpx.Response(
            200,
            json={
                "ok": True,
                "status": "confirmed",
                "command_id": "fixture-command",
                "correlation_id": "fixture-correlation",
                "error": None,
            },
        )

    from app.connectors import buspro as buspro_module

    original = httpx.AsyncClient
    monkeypatch.setattr(
        buspro_module.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    connector = BusproConnector(ProviderConfig(enabled=True, base_url="http://hub.test", token=""), 4)

    result = await connector.command("ksenia:ksn_light_demo", "on")

    assert result["ok"] is True
    posts = [entry for entry in observed if entry[0] == "POST"]
    assert posts == [
        (
            "POST",
            "/api/user/smart-home/ksenia/ksn_light_demo/command",
            {"action": "on", "value": None},
        )
    ]


@pytest.mark.asyncio
async def test_change_2026_011_brightness_is_translated_to_hub_level(monkeypatch) -> None:
    fixture = load_fixture()
    observed: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=fixture)
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "status": "confirmed"})

    from app.connectors import buspro as buspro_module

    original = httpx.AsyncClient
    monkeypatch.setattr(buspro_module.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    connector = BusproConnector(ProviderConfig(enabled=True, base_url="http://hub.test", token=""), 4)

    await connector.command("hdl:1.2.3", "brightness", 128)

    assert observed == [{"action": "level", "value": 50}]


def test_change_2026_011_frontend_respects_hub_authority_and_capabilities() -> None:
    root = Path(__file__).resolve().parents[1]
    app_js = (root / "app" / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    tools_js = (root / "app" / "static" / "assets" / "organization-tools.js").read_text(encoding="utf-8")
    assert "device.allowed_actions" in app_js
    assert "device.categories" in app_js
    assert "device.orders" in app_js
    assert "device.visible !== false" in app_js
    assert "device.organization_authority==='e-control-hub'" in tools_js
    assert "gestito da e-Control Hub" in tools_js
