import asyncio

import pytest
from fastapi.testclient import TestClient

from app import routines
from app import user_auth
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_ROUTINES_DB", str(tmp_path / "routines.sqlite3"))


def catalog():
    return [
        {"id": "light.hall", "kind": "light", "name": "Luce ingresso", "room": "Ingresso", "state": "off"},
        {"id": "sensor.motion", "kind": "binary_sensor", "name": "Movimento", "room": "Ingresso", "state": "off"},
        {"id": "lock.door", "kind": "lock", "name": "Porta ingresso", "room": "Ingresso", "state": "locked"},
    ]


def sample():
    return {"name": "Luce ingresso", "triggers": [{"type": "state", "device_id": "sensor.motion", "to": "on"}],
            "conditions": [], "steps": [{"type": "action", "device_id": "light.hall", "action": "on"}]}


def test_validation_blocks_access_commands_and_cycles():
    unsafe = sample()
    unsafe["steps"] = [{"type": "action", "device_id": "lock.door", "action": "unlock"}]
    result = routines.validate(unsafe, catalog())
    assert result["can_enable"] is False
    assert "sicurezza" in " ".join(result["errors"])
    cycle = sample()
    cycle["triggers"] = [{"type": "state", "device_id": "light.hall", "to": "on"}]
    assert "riattivare" in " ".join(routines.validate(cycle, catalog())["errors"])


def test_validation_describes_timer_and_recheck():
    spec = sample()
    spec["steps"] += [{"type": "wait", "seconds": 120},
                      {"type": "check", "device_id": "sensor.motion", "operator": "is", "value": "off"},
                      {"type": "action", "device_id": "light.hall", "action": "off"}]
    result = routines.validate(spec, catalog())
    assert not result["errors"]
    assert "120 secondi" in result["description"]
    assert result["warnings"]


def test_validation_blocks_cross_routine_feedback():
    devices = catalog() + [{"id": "light.kitchen", "kind": "light", "name": "Luce cucina", "state": "off"}]
    first = {"id": "first", "enabled": True, "name": "Prima", "spec": {
        "triggers": [{"type": "state", "device_id": "light.kitchen", "to": "on"}],
        "steps": [{"type": "action", "device_id": "light.hall", "action": "on"}]}}
    second = sample()
    second["triggers"] = [{"type": "state", "device_id": "light.hall", "to": "on"}]
    second["steps"] = [{"type": "action", "device_id": "light.kitchen", "action": "on"}]
    assert "ciclo" in " ".join(routines.validate(second, devices, [first])["errors"])


def test_edit_review_does_not_warn_about_itself():
    spec = sample()
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    review = routines.validate({**spec, "id": saved["id"]}, catalog(), routines.list_routines())
    assert not review["errors"]
    assert not any("Interazione possibile" in warning for warning in review["warnings"])


def test_revision_and_ownership_preserve_attribution():
    spec = routines.validate(sample(), catalog())["spec"]
    first = routines.save("alice", "alice", None, spec, False, None)
    assert first["revision"] == 1
    with pytest.raises(PermissionError):
        routines.save("bob", "bob", first["id"], spec, True, 1)
    with pytest.raises(RuntimeError):
        routines.save("alice", "alice", first["id"], spec, True, 0)
    second = routines.save("alice", "alice", first["id"], spec, True, 1)
    assert second["revision"] == 2
    assert second["enabled"]


def test_engine_runs_only_on_state_transition_and_logs_device():
    state = {"sensor.motion": "off", "light.hall": "off"}
    commands = []

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]

    async def command(device_id, action, value):
        commands.append((device_id, action, value))
        state[device_id] = action

    spec = routines.validate(sample(), catalog())["spec"]
    routine = routines.save("alice", "alice", None, spec, True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        await engine.tick()  # Baseline must not run an old state.
        state["sensor.motion"] = "on"
        await engine.tick()
        await engine.running[routine["id"]]
        await engine.tick()

    asyncio.run(run())
    assert commands == [("light.hall", "on", None)]
    runs = routines.list_runs(device_id="light.hall")
    assert len(routines.list_runs(device_id="ingresso")) == 1
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert any(event["result"] == "accepted" for event in runs[0]["events"])
    assert any(event["result"] == "changed" for event in runs[0]["events"])
    assert runs[0]["modified_by"] == "alice"


def test_state_trigger_can_run_twice_in_same_minute():
    state = {"sensor.motion": "off", "light.hall": "off"}
    commands = []

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]

    async def command(device_id, action, value):
        commands.append((device_id, action))

    spec = routines.validate(sample(), catalog())["spec"]
    saved = routines.save("alice", "alice", None, spec, True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        await engine.tick()
        for _ in range(2):
            state["sensor.motion"] = "on"
            await engine.tick()
            await engine.running[saved["id"]]
            state["sensor.motion"] = "off"
            await engine.tick()

    asyncio.run(run())
    assert len(commands) == 2
    assert len(routines.list_runs()) == 2


def test_buspro_events_catch_short_on_off_on_sequence():
    devices = [{**item, "state_key": "1.2.3" if item["id"] == "sensor.motion" else "1.2.4"} for item in catalog()]
    commands = []

    async def snapshot():
        return devices

    async def command(device_id, action, value):
        commands.append((device_id, action))

    saved = routines.save("alice", "alice", None, routines.validate(sample(), devices)["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    engine.configure_buspro(devices)
    engine.buspro_live = True

    async def run():
        for value in ("ON", "OFF", "ON"):
            await engine.buspro_event({"type": "light_state", "data": {"subnet_id": 1, "device_id": 2, "channel": 3, "state": value}})
            if saved["id"] in engine.running:
                await engine.running[saved["id"]]

    asyncio.run(run())
    assert commands == [("light.hall", "on"), ("light.hall", "on")]


def test_engine_rechecks_after_timer_before_action():
    state = {"sensor.motion": "off", "light.hall": "off"}
    commands = []

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]

    async def command(device_id, action, value):
        commands.append(action)
        state[device_id] = action

    spec = sample()
    spec["steps"] = [{"type": "wait", "seconds": 1},
                     {"type": "check", "device_id": "sensor.motion", "operator": "is", "value": "off"},
                     {"type": "action", "device_id": "light.hall", "action": "on"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        await engine.tick()
        state["sensor.motion"] = "on"
        await engine.tick()
        await engine.running[saved["id"]]

    asyncio.run(run())
    assert commands == []
    assert routines.list_runs()[0]["status"] == "stopped"


def test_doorbird_event_starts_once_and_is_attributed():
    state = {"light.hall": "off"}
    commands = []

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]

    async def command(device_id, action, value):
        commands.append((device_id, action))
        state[device_id] = action

    spec = sample()
    spec["triggers"] = [{"type": "doorbird", "event": "doorbell"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        await engine.doorbird_event("doorbell")
        await engine.running[saved["id"]]
        await engine.doorbird_event("doorbell")  # Duplicate monitor/callback event.

    asyncio.run(run())
    assert commands == [("light.hall", "on")]
    assert routines.list_runs()[0]["trigger_detail"] == "DoorBird: chiamata"


def test_user_routes_and_admin_log_are_separated(monkeypatch):
    monkeypatch.setattr(user_auth, "enabled", lambda: False)
    with TestClient(create_app()) as client:
        assert client.get("/api/user/routines").json() == {"items": []}
        assert client.get("/api/admin/routines/log").status_code == 401
        assert client.get("/assets/routine-tools.js").status_code == 200
        assert "routine-tools.js" in client.get("/tools").text
        script = client.get("/assets/routine-tools.js").text
        assert 'data-device-search' in script
        assert 'binary_sensor:[\'on\',\'off\']' in script
        assert 'matches.slice(0, 80)' in script
        invalid = client.post("/api/user/routines", json={"spec": sample(), "enabled": False})
        assert invalid.status_code == 400  # Devices missing from the live catalog.
