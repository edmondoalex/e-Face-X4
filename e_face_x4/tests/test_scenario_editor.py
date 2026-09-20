from dataclasses import replace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import ProviderConfig
from app.main import create_app
from app.scenario_editor import fingerprint, validate


DEVICES = [
    {"type": "light", "subnet_id": 1, "device_id": 20, "channel": 2, "name": "Faretti"},
    {"type": "light", "entity_id": "light.sala", "name": "Lampada Sala"},
    {"type": "cover", "subnet_id": 1, "device_id": 30, "channel": 1, "name": "Tapparella"},
    {"type": "cover", "entity_id": "cover.sala", "name": "Tenda"},
]
GROUPS = [{"id": "gruppo_pt", "name": "Gruppo PT"}]
TRIGGERS = [{"id": "ha-1", "name": "Sveglia"}]
SPEC = {
    "name": "Film", "run_enabled": True, "onoff_enabled": True,
    "items": [{"subnet_id": 1, "device_id": 20, "channel": 2, "state": "ON", "brightness": 128},
              {"entity_id": "light.sala", "domain": "light", "state": "OFF", "brightness": None}],
    "covers": [{"kind": "single", "subnet_id": 1, "device_id": 30, "channel": 1,
                "command": "SET_POSITION", "position": 45, "ramp_minutes": 3, "step_seconds": 5,
                "two_phase_open": True, "phase1_pct": 25, "phase2_delay_minutes": 4},
               {"kind": "group", "group_id": "gruppo_pt", "command": "OPEN", "position": None,
                "ramp_minutes": 0, "step_seconds": 5, "two_phase_open": False,
                "phase1_pct": 25, "phase2_delay_minutes": 4}],
    "combination_targets": [{"subnet_id": 1, "device_id": 44, "switch_number": 3}],
    "trigger": {"enabled": True, "type": "sunset", "time": "", "offset_min": -20},
    "ha_trigger_enabled": True, "ha_trigger_id": "ha-1",
}


def test_full_hdl_scenario_contract_is_preserved():
    result = validate(SPEC, DEVICES, GROUPS, TRIGGERS)
    assert result == SPEC
    assert fingerprint(result) == fingerprint(dict(reversed(list(result.items()))))


@pytest.mark.parametrize("change", [
    {"name": ""},
    {"run_enabled": False, "onoff_enabled": False},
    {"items": [{"entity_id": "lock.front", "state": "ON"}]},
    {"items": [{"entity_id": "light.unknown", "state": "ON"}]},
    {"covers": [{"kind": "group", "group_id": "missing", "command": "OPEN"}]},
    {"trigger": {"enabled": True, "type": "time", "time": "25:00", "offset_min": 0}},
    {"ha_trigger_enabled": True, "ha_trigger_id": "unknown"},
])
def test_invalid_scenario_is_rejected_without_silent_drops(change):
    with pytest.raises(HTTPException) as exc:
        validate({**SPEC, **change}, DEVICES, GROUPS, TRIGGERS)
    assert exc.value.status_code == 400


def test_editor_api_reads_hdl_and_rejects_stale_write(monkeypatch):
    import app.main as main_module
    settings = main_module.load_settings
    monkeypatch.setattr(main_module, "load_settings", lambda: replace(
        settings(), buspro=ProviderConfig(True, "http://hdl.test", "")))
    saved = {"id": "scene-1", **SPEC}
    calls = []

    def upstream(request):
        calls.append((request.method, request.url.path))
        data = {
            "/api/user/light_scenarios": {"items": [saved]},
            "/api/user/devices": DEVICES,
            "/api/cover_groups": {"groups": GROUPS},
            "/api/user/scenario_ha_triggers": {"items": TRIGGERS},
            "/api/user/light_scenarios_status": {"states": {"scene-1": "ON"}, "running": {}},
        }
        if request.method == "GET":
            return httpx.Response(200, json=data[request.url.path])
        return httpx.Response(200, json=saved)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(main_module.httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(upstream), **kwargs))
    client = TestClient(create_app())
    response = client.get("/api/user/scenarios/editor")
    assert response.status_code == 200
    assert response.json()["items"][0]["revision"] == fingerprint(saved)
    assert response.json()["items"][0]["state"] == "ON"
    stale = client.put("/api/user/scenarios/editor/scene-1", json={"revision": "old", "spec": SPEC})
    assert stale.status_code == 409
    assert not any(method == "PUT" for method, _ in calls)
    updated = client.put("/api/user/scenarios/editor/scene-1", json={"revision": fingerprint(saved), "spec": SPEC})
    assert updated.status_code == 200
    assert calls[-1] == ("PUT", "/api/user/light_scenarios/scene-1")
