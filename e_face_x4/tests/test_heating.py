import pytest
import httpx
from dataclasses import replace
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.heating import command_payload
from app.config import ProviderConfig
from app.main import create_app


def test_heating_commands_forward_only_user_controls():
    assert command_payload({"kind": "module", "key": "solare", "value": False}) == (
        "modules", {"key": "solare", "value": False, "pin": ""})
    assert command_payload({"kind": "setpoint", "section": "acs", "key": "setpoint_c", "value": 72}) == (
        "setpoints", {"acs": {"setpoint_c": 72.0}})
    assert command_payload({"kind": "setpoint", "section": "impianto", "key": "season_mode", "value": "summer"}) == (
        "setpoints", {"impianto": {"season_mode": "summer"}})
    assert command_payload({"kind": "setpoint", "section": "impianto", "key": "source_mode", "value": "AUTO"}) == (
        "setpoints", {"impianto": {"source_mode": "AUTO"}})
    assert command_payload({"kind": "setpoint", "section": "volano", "key": "evening_dump_trigger", "value": "time"}) == (
        "setpoints", {"volano": {"evening_dump_trigger": "time"}})
    assert command_payload({"kind": "force", "target": "volano", "active": False}) == (
        "volano/force_puffer/clear", {})
    assert command_payload({"kind": "force", "target": "acs", "active": True, "minutes": 30}) == (
        "acs/force_puffer", {"minutes": 30})


@pytest.mark.parametrize("payload", [
    {"kind": "actuate", "entity_id": "switch.boiler", "value": True},
    {"kind": "module", "key": "security", "value": True},
    {"kind": "module", "key": [], "value": True},
    {"kind": "module", "key": "solare", "value": "false"},
    {"kind": "setpoint", "section": "acs", "key": "max_c", "value": 100},
    {"kind": "setpoint", "section": "security", "key": "user_pin", "value": 1234},
    {"kind": "setpoint", "section": "impianto", "key": "season_mode", "value": []},
    {"kind": "setpoint", "section": "impianto", "key": "source_mode", "value": "gas"},
    {"kind": "setpoint", "section": "volano", "key": "evening_dump_run_entity", "value": "../../etc/passwd"},
    {"kind": "setpoint", "section": [], "key": "setpoint_c", "value": 40},
    {"kind": "force", "target": "acs", "active": True, "minutes": 241},
    {"kind": "force", "target": [], "active": False},
    {"kind": "zone", "entity_id": "switch.boiler", "temperature": 20},
    {"kind": "zone", "entity_id": "climate.office", "temperature": float("nan")},
])
def test_heating_rejects_unapproved_or_unsafe_commands(payload):
    with pytest.raises(HTTPException) as exc:
        command_payload(payload)
    assert exc.value.status_code == 400


def test_heating_api_sanitizes_config_and_sends_partial_updates(monkeypatch):
    import app.main as main_module
    original_settings = main_module.load_settings
    monkeypatch.setattr(main_module, "load_settings", lambda: replace(
        original_settings(), thermomind=ProviderConfig(True, "http://thermomind.test", "")))
    requests = []

    def upstream(request):
        requests.append((request.method, request.url.path, request.content))
        path = request.url.path
        data = {
            "/api/status": {"version": "0.8.59", "ha_connected": True, "token_source": "secret"},
            "/api/decision": {"computed": {}, "inputs": {}, "zones": []},
            "/api/modules": {"solare": True},
            "/api/setpoints": {"acs": {"setpoint_c": 72, "secret": "hidden"}, "security": {"user_pin": "1234"}},
            "/api/acs/force_puffer": {"active": False},
            "/api/volano/force_puffer": {"active": False},
            "/api/actuators": {"r22_resistenza": {"state": "off", "entity_id": "switch.test", "attributes": {"friendly_name": "Resistenza 1", "secret": "hidden"}}},
        }
        return httpx.Response(200, json=data.get(path, {"ok": True}))

    real_client = httpx.AsyncClient
    monkeypatch.setattr(main_module.httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(upstream), **kwargs))
    client = TestClient(create_app())
    snapshot = client.get("/api/user/heating")
    assert snapshot.status_code == 200
    assert "token_source" not in snapshot.json()["status"]
    assert "security" not in snapshot.json()["setpoints"]
    assert "secret" not in snapshot.json()["setpoints"]["acs"]
    assert snapshot.json()["actuators"]["r22_resistenza"] == {"state": "off", "name": "Resistenza 1"}
    response = client.post("/api/user/heating/command", json={"kind": "setpoint", "section": "acs", "key": "setpoint_c", "value": 73})
    assert response.status_code == 200
    assert requests[-1][0:2] == ("POST", "/api/setpoints")
    assert requests[-1][2] == b'{"acs":{"setpoint_c":73.0}}'
    assert client.post("/api/user/heating/command", json={"kind": "actuate"}).status_code == 400
