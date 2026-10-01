from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import backgrounds
from app.connectors.buspro import normalize_snapshot


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "change_2026_011_multibus_parity.json"
PROTECTED_ACTIONS = {"arm", "disarm", "bypass", "partition", "reset_panel"}


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_multibus_parity_matrix_is_driver_neutral() -> None:
    fixture = load_fixture()
    devices = fixture["equivalent_devices"]
    assert {device["source"] for device in devices} == {"hdl", "ksenia", "futurebus"}

    reference = {
        key: devices[0][key]
        for key in (
            "device_class",
            "capabilities",
            "expected_categories",
            "expected_actions",
            "routine_trigger",
            "routine_condition",
            "routine_action",
        )
    }
    for device in devices[1:]:
        assert {key: device[key] for key in reference} == reference
    assert len({f'{device["source"]}:{device["device_id"]}' for device in devices}) == 3


def test_multibus_default_categories_cover_historical_pages() -> None:
    fixture = load_fixture()
    cases = fixture["classification_cases"]
    expected = {
        "switch": "extra",
        "shutter": "covers",
        "gate": "security",
        "thermostat": "comfort",
        "temperature": "sensors",
        "scene": "scenarios",
    }
    for case in cases:
        assert case["expected_categories"] == [expected[case["device_class"]]]
        assert set(case["expected_categories"]) <= set(fixture["canonical_categories"])


def test_multibus_visual_category_never_expands_capabilities() -> None:
    gate = next(case for case in load_fixture()["classification_cases"] if case["device_class"] == "gate")
    assert gate["expected_categories"] == ["security"]
    assert set(gate["expected_actions"]) == set(gate["capabilities"])
    assert not (set(gate["expected_actions"]) & PROTECTED_ACTIONS)
    assert not (set(gate["forbidden_actions"]) & set(gate["expected_actions"]))


def test_multibus_missing_capabilities_produce_no_actions() -> None:
    sensor = next(case for case in load_fixture()["classification_cases"] if case.get("read_only"))
    assert sensor["capabilities"] == []
    assert sensor["expected_actions"] == []


def test_multibus_preferences_use_canonical_identity_and_survive_catalog_changes() -> None:
    lifecycle = load_fixture()["preference_lifecycle"]
    assert lifecycle["canonical_id"].count(":") == 1
    assert lifecycle["initial"]["name"] != lifecycle["updated_catalog"]["name"]
    assert lifecycle["initial"]["available"] is True
    assert lifecycle["updated_catalog"]["available"] is False
    assert lifecycle["persisted_preferences"]["categories"] == ["lights", "extra"]
    assert set(lifecycle["must_survive"]) == {
        "restart",
        "update",
        "rename",
        "catalog_refresh",
        "offline",
        "backup_restore",
    }


def test_existing_appearance_store_accepts_canonical_multibus_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EFACE_BACKGROUNDS", str(tmp_path))
    canonical_id = "futurebus:future-light-parity"
    expected = {
        "visible": False,
        "categories": ["lights", "extra"],
        "orders": {"devices": 4, "lights": 2, "extra": 0},
        "name": "Preferred name",
        "room": "Preferred room",
        "icon": "mdi:wall-sconce-flat",
    }

    backgrounds.save_device_organization({canonical_id: expected})

    assert backgrounds.load_device_organization() == {canonical_id: expected}


@pytest.mark.parametrize("source", ["hdl", "ksenia", "futurebus"])
def test_multibus_equivalent_devices_normalize_with_equal_features(source: str) -> None:
    candidate = next(device for device in load_fixture()["equivalent_devices"] if device["source"] == source)
    payload = {
        "smart_home": {
            "schema_version": "1.0",
            "capability_model_version": "1.0",
            "organization_schema_version": 1,
            "command_endpoint_template": "/api/user/smart-home/{source}/{device_id}/command",
            "realtime": {"mode": "snapshot", "supports_refresh": True},
            "features": {"organization": True, "commands": True, "scenarios": True, "routines": True},
            "floors": [],
            "rooms": [],
            "groups": [],
            "devices": [
                    {
                        **candidate,
                        "id": f'{source}:{candidate["device_id"]}',
                        "name": f"{source} parity light",
                    "native_type": "fixture",
                    "native_id": "parity-light",
                    "read_only": False,
                    "available": True,
                    "stale": False,
                    "state": "on",
                    "floor_id": None,
                    "floor_name": None,
                    "room_id": None,
                    "room_name": None,
                    "group_ids": [],
                        "group_names": [],
                        "categories": candidate["expected_categories"],
                        "orders": {"lights": 0},
                        "visible": True,
                        "favorite": False,
                        "shortcut": False,
                        "visual_category": "lights",
                        "commands": [{"action": action, "value_type": "number" if action == "level" else "none"} for action in candidate["capabilities"]],
                        "features": {"controllable": True, "realtime": True, "scenario": False, "routine_trigger": True, "routine_action": True},
                    "icon_auto": "mdi:lightbulb",
                    "icon_override": "",
                    "icon": "mdi:lightbulb",
                    "orphaned": False,
                }
            ],
        }
    }

    normalized = normalize_snapshot(payload)["devices"]

    assert len(normalized) == 1
    assert normalized[0]["id"] == f'{source}:{candidate["device_id"]}'
    assert normalized[0]["kind"] == "light"
    assert normalized[0]["capabilities"] == ["on", "off", "level"]
    assert normalized[0]["default_categories"] == ["lights"]
