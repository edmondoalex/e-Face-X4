import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import routines
from app import routine_nl
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


def test_visual_editor_exposes_time_window_fields():
    script = (Path(__file__).resolve().parents[1] / "app/static/assets/routine-tools.js").read_text(encoding="utf-8")
    assert 'value="time_window"' in script
    assert 'window-${key}-kind' in script
    assert "Intervallo da… a…" in script
    assert "'time_window'].includes(item.type)" in script


def test_visual_editor_exposes_choose_branches_without_dropping_advanced_routines():
    script = (Path(__file__).resolve().parents[1] / "app/static/assets/routine-tools.js").read_text(encoding="utf-8")
    for marker in ('data-routine-add="choose"', 'data-choose-add-choice', 'data-choose-add-step',
                   'data-choose-condition', 'function collectStepRow', 'function renderStepRow',
                   'const hasAdvancedFlow = spec => !canOpenVisual(spec)'):
        assert marker in script
    assert "if (!canOpenVisual(draft))" in script


def test_visual_editor_uses_drag_handles_and_duplicate_for_every_row():
    script = (Path(__file__).resolve().parents[1] / "app/static/assets/routine-tools.js").read_text(encoding="utf-8")
    for marker in ('data-routine-duplicate-row="trigger"', 'data-routine-duplicate-row="condition"',
                   'data-routine-duplicate-row="step"', 'data-branch-duplicate-step',
                   'data-choose-duplicate-choice', 'function dragCollection(container)',
                   'data-routine-drag aria-label="Trascina per riordinare il blocco"'):
        assert marker in script
    assert 'data-branch-move=' not in script


def test_sunrise_sunset_choose_routine_validates_and_round_trips():
    devices = catalog() + [{"id":"17", "kind":"cover", "name":"Finestra Cucina", "state":"closed"}]
    spec = {"name":"1°P TP Giorno/Notte", "mode":"single",
            "triggers":[{"type":"sun", "event":"sunrise"}, {"type":"sun", "event":"sunset"}],
            "conditions":[], "steps":[{"type":"choose", "choices":[
                {"condition":{"type":"time_window", "start":{"kind":"sunrise", "offset_minutes":0},
                              "end":{"kind":"sunset", "offset_minutes":0}},
                 "steps":[{"type":"delay", "seconds":900}, {"type":"action", "device_id":"17", "action":"open"}]},
                {"condition":{"type":"time_window", "start":{"kind":"sunset", "offset_minutes":0},
                              "end":{"kind":"sunrise", "offset_minutes":0}},
                 "steps":[{"type":"delay", "seconds":900}]}
            ], "default":[]}]}
    review = routines.validate(spec, devices)
    assert review["errors"] == []
    saved = routines.save("admin", "admin", None, review["spec"], False, None, shared=True)
    reopened = routines.validate(saved["spec"], devices)
    assert reopened["errors"] == []
    assert reopened["spec"]["steps"][0]["choices"][0]["steps"][1]["device_id"] == "17"
    assert reopened["spec"]["steps"][0]["choices"][1]["steps"] == [{"type":"wait", "seconds":900}]


def test_sunset_group_close_then_one_second_stop_is_preserved():
    devices = catalog() + [
        {"id":"17", "kind":"cover", "name":"Finestra Cucina", "state":"closed"},
        {"id":"21", "kind":"cover", "name":"Porta Sala CX", "state":"open"},
        {"id":"cover-group-no-pct:gruppo_tapparelle_1p", "kind":"cover", "name":"Gruppo Tapparelle 1°P · no %", "state":"open"},
    ]
    spec = {"name":"1°P TP Giorno/Notte", "mode":"single", "triggers":[{"type":"sun","event":"sunrise","offset_minutes":0}, {"type":"sun","event":"sunset","offset_minutes":0}], "conditions":[], "steps":[{"type":"choose", "choices":[
        {"condition":{"type":"time_window","start":{"kind":"sunrise","offset_minutes":0},"end":{"kind":"sunset","offset_minutes":0}},"steps":[{"type":"wait","seconds":900},{"type":"action","device_id":"17","action":"open","value":None},{"type":"action","device_id":"21","action":"open","value":None}]},
        {"condition":{"type":"time_window","start":{"kind":"sunset","offset_minutes":0},"end":{"kind":"sunrise","offset_minutes":0}},"steps":[{"type":"wait","seconds":900},{"type":"action","device_id":"cover-group-no-pct:gruppo_tapparelle_1p","action":"close","value":None},{"type":"wait","seconds":1},{"type":"action","device_id":"21","action":"stop","value":None}]}
    ], "default":[]}], "description":""}
    review = routines.validate(spec, devices)
    assert review["errors"] == []
    assert [step.get("action", step.get("seconds")) for step in review["spec"]["steps"][0]["choices"][1]["steps"]] == [900, "close", 1, "stop"]
    assert not any("editor JSON" in warning for warning in review["warnings"])


def test_guided_text_creates_reviewable_draft_without_actuation():
    devices = catalog() + [{"id": "light.corridor", "kind": "light", "name": "Luce Corridoio", "room": "Corridoio", "state": "off"}]
    spec = routine_nl.from_text("Quando Movimento rileva movimento, accendi Luce Corridoio poi aspetta 60 secondi poi spegni Luce Corridoio", devices)
    assert spec["triggers"] == [{"type": "state", "device_id": "sensor.motion", "to": "active"}]
    assert spec["steps"] == [{"type": "action", "device_id": "light.corridor", "action": "on"}, {"type": "wait", "seconds": 60}, {"type": "action", "device_id": "light.corridor", "action": "off"}]
    assert not routines.validate(spec, devices)["errors"]
    assert routines.list_routines() == []
    timed = routine_nl.from_text("Alle 18:30, accendi Luce Corridoio per 1 minuto poi spegni Luce Corridoio", devices)
    assert timed["steps"][1] == {"type": "wait", "seconds": 60}
    scenario = {"id": "light-scenario:film", "kind": "light_scenario", "name": "Sala Film", "room": "Sala", "state": "off", "capabilities": {"onoff": True}}
    scene_draft = routine_nl.from_text("Quando Sala Film si accende, accendi Luce Corridoio", devices + [scenario])
    assert scene_draft["triggers"][0]["to"] == "command_on"


def test_guided_text_rejects_ambiguous_or_unsupported_instructions():
    devices = catalog() + [{"id": "light.other", "kind": "light", "name": "Luce ingresso", "room": "Garage", "state": "off"}]
    with pytest.raises(ValueError, match="ambiguo"):
        routine_nl.from_text("Alle 18:30, accendi Luce ingresso", devices)
    with pytest.raises(ValueError, match="Azione non riconosciuta"):
        routine_nl.from_text("Alle 18:30, sblocca Porta ingresso", devices)
    with pytest.raises(ValueError, match="Attivazione non riconosciuta"):
        routine_nl.from_text("Quando piove, accendi Luce ingresso", devices)
    with pytest.raises(ValueError, match="Non capisco tutta"):
        routine_nl.from_text("Alle 18:30, accendi Luce Corridoio lentamente", devices + [{"id": "light.corridor", "kind": "light", "name": "Luce Corridoio", "room": "Corridoio", "state": "off"}])


def test_professional_json_is_shared_persistent_and_admin_only(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    user_auth.create_admin("password-admin-lunga")
    user_auth.create_account("cliente", "Cliente", "password-cliente-lunga")
    spec = routines.validate(sample(), catalog())["spec"]
    saved = routines.save("cliente", "cliente", None, spec, False, None, shared=True)
    admin = TestClient(create_app())
    customer = TestClient(create_app())
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert customer.post("/api/auth/login", json={"username": "cliente", "password": "password-cliente-lunga"}).status_code == 200
    path = "/api/admin/routines/professional"
    assert customer.get(path).status_code == 403
    assert customer.post(path + "/validate", json={"spec": spec}).status_code == 403
    assert customer.post(path, json={"spec": spec, "enabled": False}).status_code == 403
    filters_path = "/api/admin/routines/catalog-filters"
    settings = {"block_sensitive_names": False, "hide_readonly_actions": False}
    assert customer.put(filters_path, json=settings).status_code == 403
    assert admin.put(filters_path, json=settings).json()["filters"] == settings
    assert routines.catalog_filters() == settings
    assert admin.get(path).json()["items"][0]["spec"] == spec
    assert admin.get(path).json()["items"][0]["id"] == saved["id"]
    assert customer.get("/api/user/routines").json()["items"][0]["id"] == saved["id"]
    updated = routines.save("cliente", "admin", saved["id"], {**spec, "name": "Luce ingresso evoluta"}, False, saved["revision"], shared=True)
    assert routines.get_routine(saved["id"])["spec"]["name"] == "Luce ingresso evoluta"
    assert updated["revision"] == saved["revision"] + 1
    with pytest.raises(RuntimeError, match="modificata"):
        routines.save("cliente", "admin", saved["id"], spec, False, saved["revision"], shared=True)


def test_solar_trigger_condition_and_location_guard():
    spec = sample()
    spec["triggers"] = [{"type": "sun", "event": "sunset", "offset_minutes": -15}]
    spec["conditions"] = [{"type": "sun", "event": "sunrise", "offset_minutes": 30, "relation": "after"}]
    review = routines.validate(spec, catalog())
    assert not review["errors"]
    assert review["spec"]["triggers"][0]["offset_minutes"] == -15
    assert not routines.validate(spec, catalog(), solar_available=False)["can_enable"]
    spec["triggers"][0]["offset_minutes"] = 181
    assert routines.validate(spec, catalog())["errors"]


def test_visual_time_window_validates_and_persists_without_losing_solar_boundaries():
    spec = sample()
    spec["conditions"] = [{"type": "time_window",
                           "start": {"kind": "sunset", "offset_minutes": -15},
                           "end": {"kind": "time", "at": "23:00"}}]
    review = routines.validate(spec, catalog())
    assert review["errors"] == []
    assert "tramonto" in review["description"]
    saved = routines.save("owner", "owner", None, review["spec"], False, None, shared=True)
    assert routines.get_routine(saved["id"])["spec"]["conditions"] == review["spec"]["conditions"]
    assert not routines.validate(spec, catalog(), solar_available=False)["can_enable"]
    bad = {**spec, "conditions": [{"type": "time_window", "start": {"kind": "time", "at": "23:00"},
                                  "end": {"kind": "sunrise", "offset_minutes": 181}}]}
    assert routines.validate(bad, catalog())["errors"]


@pytest.mark.asyncio
async def test_time_window_handles_midnight_and_sunset_to_sunrise(monkeypatch):
    from datetime import datetime as real_datetime

    current_hour = [22]
    class FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime(2026, 9, 20, current_hour[0], 0, tzinfo=tz)

    monkeypatch.setattr(routines, "datetime", FakeDateTime)
    async def solar_times():
        zone = ZoneInfo("Europe/Rome")
        return {"sunrise": real_datetime(2026, 9, 20, 7, tzinfo=zone),
                "sunset": real_datetime(2026, 9, 20, 19, tzinfo=zone)}

    async def snapshot():
        return []
    async def command(*_args):
        return None
    engine = routines.Engine(snapshot, command, solar_times=solar_times)
    condition = {"type": "time_window", "start": {"kind": "sunset", "offset_minutes": 0},
                 "end": {"kind": "sunrise", "offset_minutes": 0}}
    assert (await engine._evaluate_time_window(condition))[0]
    current_hour[0] = 1
    assert (await engine._evaluate_time_window(condition))[0]
    current_hour[0] = 12
    assert not (await engine._evaluate_time_window(condition))[0]
    fixed = {"type": "time_window", "start": {"kind": "time", "at": "21:00"},
             "end": {"kind": "time", "at": "23:00"}}
    assert not (await engine._evaluate_time_window(fixed))[0]
    current_hour[0] = 22
    assert (await engine._evaluate_time_window(fixed))[0]


def test_professional_or_can_include_visual_time_window():
    spec = sample()
    spec["description"] = "Finestra serale o sensore attivo"
    spec["conditions"] = {"or": [
        {"type": "time_window", "start": {"kind": "sunset", "offset_minutes": 0},
         "end": {"kind": "time", "at": "23:00"}},
        {"device_id": "sensor.motion", "operator": "is", "value": "on"},
    ]}
    review = routines.validate(spec, catalog())
    assert review["errors"] == []
    assert routines.uses_sun(review["spec"])
    assert not routines.validate(spec, catalog(), solar_available=False)["can_enable"]


def test_media_remote_commands_follow_source_capabilities():
    player = {"id": "c4media:1", "kind": "media_player", "name": "Sala", "state": "idle",
              "capabilities": {"play": True}, "source_options": [{"key": "watch:42", "label": "Sky Q", "source_id": 42,
              "experience": "watch", "remote_actions": ["menu", "enter"]}]}
    spec = sample()
    spec["triggers"] = [{"type": "remote", "device_id": "c4media:1", "source_id": 42, "command": "menu"}]
    spec["steps"] = [{"type": "action", "device_id": "c4media:1", "action": "remote_command",
                      "value": {"source_id": 42, "command": "enter"}}]
    assert not routines.validate(spec, catalog() + [player])["errors"]
    spec["steps"][0]["value"]["command"] = "record"
    assert routines.validate(spec, catalog() + [player])["errors"]
    spec["steps"] = [{"type": "action", "device_id": "light.hall", "action": "on"}]
    spec["triggers"] = [{"type": "remote", "device_id": "c4media:1", "source_id": 0, "command": "media_play"}]
    assert not routines.validate(spec, catalog() + [player])["errors"]
    spec["triggers"][0]["command"] = "media_next"
    assert routines.validate(spec, catalog() + [player])["errors"]


def test_professional_json_rejects_ignored_fields_and_remote_feedback_loop():
    spec = sample()
    spec["conditions"] = [{"type": "unsupported", "device_id": "light.hall", "operator": "is", "value": "off"}]
    assert not routines.validate(spec, catalog())["can_enable"]
    spec["conditions"] = []
    spec["steps"][0]["value"] = "off"
    assert not routines.validate(spec, catalog())["can_enable"]
    player = {"id": "c4media:1", "kind": "media_player", "name": "Sala", "state": "idle",
              "source_options": [{"key": "watch:42", "label": "Sky Q", "source_id": 42,
                                  "experience": "watch", "remote_actions": ["menu"]}]}
    spec["triggers"] = [{"type": "remote", "device_id": "c4media:1", "source_id": 42, "command": "menu"}]
    spec["steps"] = [{"type": "action", "device_id": "c4media:1", "action": "remote_command",
                      "value": {"source_id": 42, "command": "menu"}}]
    review = routines.validate(spec, catalog() + [player])
    assert any("loop" in error.lower() for error in review["errors"])


def test_advanced_flow_runs_boolean_conditions_branches_wait_repeat_parallel_and_stop():
    state = {"sensor.motion": "on", "light.hall": "off", "light.other": "off", "light.third": "off"}
    devices = catalog() + [
        {"id": "light.other", "kind": "light", "name": "Luce seconda", "room": "Sala", "state": "off"},
        {"id": "light.third", "kind": "light", "name": "Luce terza", "room": "Sala", "state": "off"},
    ]
    commands = []

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in devices]

    async def command(device_id, action, value):
        commands.append((device_id, action))
        state[device_id] = action

    spec = sample()
    spec["description"] = "Accendi e attendi che termini il movimento"
    spec["conditions"] = {"and": [
        {"type": "state", "device_id": "sensor.motion", "operator": "is", "value": "on"},
        {"not": {"type": "state", "device_id": "sensor.motion", "operator": "is", "value": "off"}},
    ]}
    spec["steps"] = [
        {"type": "variable", "name": "detected", "from_device_id": "sensor.motion"},
        {"type": "if", "condition": {"type": "variable", "name": "detected", "operator": "is", "value": "on"},
         "then": [{"type": "action", "device_id": "light.hall", "action": "on"}],
         "else": [{"type": "stop", "reason": "Nessun movimento"}]},
        {"type": "choose", "choices": [{"condition": {"device_id": "light.hall", "operator": "is", "value": "on"},
                                           "steps": [{"type": "repeat", "count": 2, "steps": [
                                               {"type": "action", "device_id": "light.other", "action": "on"}]}]}],
         "default": [{"type": "stop", "reason": "Luce spenta"}]},
        {"type": "parallel", "branches": [
            [{"type": "action", "device_id": "light.hall", "action": "off"}],
            [{"type": "action", "device_id": "light.third", "action": "on"}],
        ]},
        {"type": "wait_until", "condition": {"or": [
            {"device_id": "sensor.motion", "operator": "is", "value": "off"},
            {"device_id": "sensor.motion", "operator": "is", "value": "closed"},
        ]}, "timeout_seconds": 2},
        {"type": "stop", "reason": "Fine"},
    ]
    review = routines.validate(spec, devices)
    assert not review["errors"]
    assert review["spec"]["description"] == spec["description"]
    saved = routines.save("alice", "alice", None, review["spec"], True, None)
    assert routines.get_routine(saved["id"])["spec"]["description"] == spec["description"]
    engine = routines.Engine(snapshot, command)

    async def run():
        engine._start(saved, "movimento", "advanced:1", {item["id"]: item for item in await snapshot()})
        await asyncio.sleep(0.2)
        state["sensor.motion"] = "off"
        await asyncio.wait_for(engine.running[saved["id"]], 3)

    asyncio.run(run())
    assert commands == [("light.hall", "on"), ("light.other", "on"), ("light.other", "on"),
                        ("light.hall", "off"), ("light.third", "on")]
    assert routines.list_runs()[0]["status"] == "stopped"
    assert {"if", "choose", "repeat", "parallel", "wait_until", "stop"}.issubset(
        {event["stage"] for event in routines.list_runs()[0]["events"]})


def test_advanced_flow_rejects_self_loop_parallel_collisions_and_excessive_repeat():
    spec = sample()
    spec["steps"] = [{"type": "if", "condition": {"device_id": "sensor.motion", "value": "on"},
                      "then": [{"type": "action", "device_id": "sensor.motion", "action": "on"}], "else": []}]
    assert not routines.validate(spec, catalog())["can_enable"]
    spec["steps"] = [{"type": "parallel", "branches": [
        [{"type": "action", "device_id": "light.hall", "action": "on"}],
        [{"type": "action", "device_id": "light.hall", "action": "off"}],
    ]}]
    assert any("paralleli" in error.lower() for error in routines.validate(spec, catalog())["errors"])
    spec["steps"] = [{"type": "repeat", "count": 10, "steps": [
        {"type": "action", "device_id": "light.hall", "action": "on"} for _ in range(5)]}]
    assert any("40 comandi" in error for error in routines.validate(spec, catalog())["errors"])


def test_advanced_nested_action_is_included_in_cross_routine_loop_check():
    devices = catalog() + [{"id": "light.other", "kind": "light", "name": "Seconda luce", "state": "off"}]
    first = {"name": "Prima", "triggers": [{"type": "state", "device_id": "light.hall", "to": "on"}],
             "conditions": [], "steps": [{"type": "action", "device_id": "light.other", "action": "on"}]}
    stored = routines.save("alice", "alice", None, routines.validate(first, devices)["spec"], True, None)
    second = {"name": "Seconda", "triggers": [{"type": "state", "device_id": "light.other", "to": "on"}],
              "conditions": [], "steps": [{"type": "if", "condition": {"device_id": "sensor.motion", "value": "off"},
                                          "then": [{"type": "action", "device_id": "light.hall", "action": "on"}], "else": []}]}
    review = routines.validate(second, devices, [stored])
    assert any("ciclo" in error.lower() or "loop" in error.lower() for error in review["errors"])


def test_wait_until_timeout_stops_following_actions():
    commands = []

    async def snapshot():
        return catalog()

    async def command(device_id, action, value):
        commands.append(action)

    spec = sample()
    spec["steps"] = [{"type": "wait_until", "condition": {"device_id": "sensor.motion", "value": "on"}, "timeout_seconds": 1},
                     {"type": "action", "device_id": "light.hall", "action": "on"}]
    review = routines.validate(spec, catalog())
    assert not review["errors"]
    saved = routines.save("alice", "alice", None, review["spec"], True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        engine._start(saved, "timeout", "timeout:1", {item["id"]: item for item in catalog()})
        await asyncio.wait_for(engine.running[saved["id"]], 2)

    asyncio.run(run())
    assert not commands
    assert routines.list_runs()[0]["status"] == "stopped"


def test_legacy_control4_source_label_is_normalized_to_key():
    player = {"id": "c4media:1", "kind": "media_player", "name": "Sala", "state": "off", "provider": "control4",
              "capabilities": {"select_source": True}, "source_options": [{"key": "watch:42", "label": "Sky Q", "source_id": 42,
              "experience": "watch", "remote_actions": ["menu"]}]}
    spec = sample()
    spec["steps"] = [{"type": "action", "device_id": "c4media:1", "action": "select_source", "value": "Sky Q"}]
    review = routines.validate(spec, catalog() + [player])
    assert not review["errors"]
    assert review["spec"]["steps"][0]["value"] == "watch:42"


def test_scenario_start_event_triggers_running_even_with_onoff_state():
    scenario = {"id": "light-scenario:film", "state_key": "scenario:film", "kind": "light_scenario",
                "name": "Sala Film", "state": "off", "capabilities": {"onoff": True, "run": True}}
    devices = catalog() + [scenario]
    commands = []

    async def snapshot():
        return devices

    async def command(device_id, action, value):
        commands.append((device_id, action))

    spec = sample()
    spec["triggers"] = [{"type": "state", "device_id": scenario["id"], "to": "running"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, devices)["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    engine.configure_buspro(devices)

    async def run():
        await engine.buspro_event({"type": "light_scenario_running", "data": {"id": "film", "running": True}})
        await engine.running[saved["id"]]

    asyncio.run(run())
    assert commands == [("light.hall", "on")]


def test_scenario_command_trigger_distinguishes_on_from_off_and_blocks_feedback():
    scenario = {"id": "light-scenario:film", "state_key": "scenario:film", "kind": "light_scenario",
                "name": "Sala Film", "state": "off", "capabilities": {"onoff": True, "run": True}}
    devices = catalog() + [scenario]
    spec = sample()
    spec["triggers"] = [{"type": "state", "device_id": scenario["id"], "to": "command_on"}]
    assert not routines.validate(spec, devices)["errors"]
    recursive = {**spec, "steps": [{"type": "action", "device_id": scenario["id"], "action": "on"}]}
    assert "riattivare" in " ".join(routines.validate(recursive, devices)["errors"])
    calls = []

    async def snapshot():
        return devices

    async def command(device_id, action, value):
        calls.append(action)

    saved = routines.save("alice", "alice", None, routines.validate(spec, devices)["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    engine.configure_buspro(devices)

    async def run():
        await engine.buspro_event({"type": "light_scenario_command", "data": {"id": "film", "action": "off"}})
        assert saved["id"] not in engine.running
        await engine.buspro_event({"type": "light_scenario_command", "data": {"id": "film", "action": "on"}})
        await engine.running[saved["id"]]

    asyncio.run(run())
    assert calls == ["on"]


def test_validation_blocks_access_commands_and_cycles():
    unsafe = sample()
    unsafe["steps"] = [{"type": "action", "device_id": "lock.door", "action": "unlock"}]
    result = routines.validate(unsafe, catalog())
    assert result["can_enable"] is True
    assert "accesso fisico" in " ".join(result["risks"])
    cycle = sample()
    cycle["triggers"] = [{"type": "state", "device_id": "light.hall", "to": "on"}]
    assert "riattivare" in " ".join(routines.validate(cycle, catalog())["errors"])


def test_cover_named_porta_available_and_catalog_filters_persist():
    devices = catalog() + [{"id": "cover.scala", "kind": "cover", "name": "Porta Scala", "room": "Scala", "state": "closed"}]
    spec = sample()
    spec["triggers"] = [{"type": "state", "device_id": "sensor.motion", "to": "on"}]
    spec["conditions"] = [{"device_id": "cover.scala", "operator": "is", "value": "closed"}]
    spec["steps"] = [{"type": "action", "device_id": "cover.scala", "action": "open"}]
    assert not routines.validate(spec, devices)["errors"]
    spec["triggers"] = [{"type": "state", "device_id": "cover.scala", "to": "open"}]
    spec["steps"] = [{"type": "action", "device_id": "light.hall", "action": "on"}]
    assert not routines.validate(spec, devices)["errors"]
    assert routines.catalog_filters() == {"block_sensitive_names": True, "hide_readonly_actions": True}
    assert routines.save_catalog_filters({"block_sensitive_names": False, "hide_readonly_actions": False}) == {"block_sensitive_names": False, "hide_readonly_actions": False}
    assert routines.catalog_filters()["block_sensitive_names"] is False
    with pytest.raises(ValueError):
        routines.save_catalog_filters({"block_sensitive_names": "false", "hide_readonly_actions": False})


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


def test_installation_shared_routines_keep_original_owner_and_record_editor():
    spec = routines.validate(sample(), catalog())["spec"]
    first = routines.save("nuc", "nuc", None, spec, False, None)
    assert [item["name"] for item in routines.list_routines()] == ["Luce ingresso"]
    changed = routines.save("alex", "alex", first["id"], {**spec, "name": "Luce condivisa"}, False,
                            first["revision"], shared=True)
    assert changed["owner"] == "nuc"
    assert changed["updated_by"] == "alex"
    assert changed["name"] == "Luce condivisa"
    assert routines.delete("alex", first["id"], shared=True)


def test_scenarios_and_echo_commands_follow_real_capabilities():
    devices = catalog() + [
        {"id": "light-scenario:film", "kind": "light_scenario", "name": "Sala Film", "room": "Soggiorno",
         "state": "off", "capabilities": {"onoff": True, "run": False}},
        {"id": "media:echo", "kind": "media_player", "name": "Echo Ufficio", "room": "Ufficio",
         "state": "idle", "tts_enabled": True, "dnd_available": True, "source_list": ["Radio", "Spotify"],
         "capabilities": {"play": True, "next": True, "previous": True, "select_source": True}},
    ]
    spec = {"name": "Cinema", "triggers": [{"type": "state", "device_id": "light-scenario:film", "to": "on"}],
            "steps": [{"type": "action", "device_id": "media:echo", "action": "tts", "value": "Benvenuti"}]}
    review = routines.validate(spec, devices)
    assert not review["errors"]
    assert review["spec"]["steps"][0]["value"] == "Benvenuti"
    assert "messaggio vocale" in review["description"]
    spec["steps"] = [{"type": "action", "device_id": "media:echo", "action": "select_source", "value": "Spotify"}]
    assert not routines.validate(spec, devices)["errors"]
    spec["steps"][0]["value"] = "sorgente inesistente"
    assert "sorgente" in " ".join(routines.validate(spec, devices)["errors"])
    spec["steps"] = [{"type": "action", "device_id": "media:echo", "action": "dnd_on"}]
    assert not routines.validate(spec, devices)["errors"]
    spec["steps"] = [{"type": "action", "device_id": "light-scenario:film", "action": "run"}]
    assert "non esposto" in " ".join(routines.validate(spec, devices)["errors"])
    spec["steps"] = [{"type": "action", "device_id": "light-scenario:film", "action": "on"}]
    spec["triggers"] = [{"type": "state", "device_id": "sensor.motion", "to": "on"}]
    assert not routines.validate(spec, devices)["errors"]


def test_activity_indicator_covers_timer_and_clears_after_last_action():
    state = {"sensor.motion": "off", "light.hall": "off"}
    activity = []
    first_action = asyncio.Event()

    async def snapshot():
        return [{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]

    async def command(device_id, action, value):
        state[device_id] = action
        if action == "on":
            first_action.set()

    async def changed(device_ids):
        activity.append(set(device_ids))

    spec = sample()
    spec["steps"] += [{"type": "wait", "seconds": 1}, {"type": "action", "device_id": "light.hall", "action": "off"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command, activity_changed=changed)

    async def run():
        await engine.tick()
        state["sensor.motion"] = "on"
        await engine.tick()
        await first_action.wait()
        assert engine.active_device_ids() == {"light.hall"}
        await engine.running[saved["id"]]

    asyncio.run(run())
    assert activity[0] == {"light.hall"}
    assert activity[-1] == set()
    assert engine.active_device_ids() == set()
    assert state["light.hall"] == "off"


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
    assert len(routines.list_runs(routine_name="LUCE INGRESSO")) == 1
    assert len(routines.list_runs(routine_name="Luce")) == 1
    assert routines.list_runs(routine_name="Non esiste") == []
    assert routines.list_runs(routine_name="Luce%") == []
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
    for item in routines.list_runs():
        stages = [event["stage"] for event in item["events"]]
        assert stages.index("received") < stages.index("trigger") < stages.index("command")


def test_ksenia_zone_closed_active_closed_active_triggers_twice():
    zone = {"id": "ksenia-zone:5", "kind": "alarm_zone", "name": "IR Ufficio", "state": "CLOSED"}
    commands = []

    async def snapshot():
        return [zone, *catalog()]

    async def command(device_id, action, value):
        commands.append((device_id, action))

    spec = sample()
    spec["triggers"] = [{"type": "state", "device_id": zone["id"], "to": "active"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, [zone, *catalog()])["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    engine.ksenia_live = True

    async def run():
        for state in ("CLOSED", "ACTIVE", "CLOSED", "ACTIVE"):
            await engine.ksenia_event([{**zone, "state": state}])
            if saved["id"] in engine.running:
                await engine.running[saved["id"]]

    asyncio.run(run())
    assert commands == [("light.hall", "on"), ("light.hall", "on")]


def test_restart_mode_resets_motion_timer_and_does_not_send_old_off():
    zone = {"id": "ksenia-zone:5", "kind": "alarm_zone", "name": "IR Ufficio", "state": "closed"}
    state = {"light.hall": "off"}
    commands = []

    async def snapshot():
        return [zone, *[{**item, "state": state.get(item["id"], item["state"])} for item in catalog()]]

    async def command(device_id, action, value):
        commands.append(action)
        state[device_id] = action

    spec = sample()
    spec["mode"] = "restart"
    spec["triggers"] = [{"type": "state", "device_id": zone["id"], "to": "active"}]
    spec["steps"] += [{"type": "wait", "seconds": 1}, {"type": "action", "device_id": "light.hall", "action": "off"}]
    review = routines.validate(spec, [zone, *catalog()])
    assert not review["errors"]
    assert review["spec"]["mode"] == "restart"
    saved = routines.save("alice", "alice", None, review["spec"], True, None)
    engine = routines.Engine(snapshot, command)

    async def run():
        await engine.ksenia_event([{**zone, "state": "closed"}])
        await engine.ksenia_event([{**zone, "state": "active"}])
        await asyncio.sleep(0.2)
        await engine.ksenia_event([{**zone, "state": "closed"}])
        await engine.ksenia_event([{**zone, "state": "active"}])
        await asyncio.sleep(0.1)
        assert commands == ["on", "on"]
        assert state["light.hall"] == "on"
        await engine.running[saved["id"]]
        await asyncio.sleep(0)

    asyncio.run(run())
    assert commands == ["on", "on", "off"]
    assert sorted(item["status"] for item in routines.list_runs()) == ["cancelled", "completed"]


def test_unknown_professional_fields_and_modes_are_blocked():
    spec = sample()
    spec["mode"] = "restart"
    assert not routines.validate(spec, catalog())["errors"]
    assert routines.validate({**spec, "mode": "unknown"}, catalog())["errors"]
    assert routines.validate({**spec, "unsupported": True}, catalog())["errors"]
    assert routines.validate({**spec, "steps": [{**spec["steps"][0], "service": "dangerous"}]}, catalog())["errors"]


def test_queued_mode_runs_events_in_order_with_bounded_backlog():
    commands = []

    async def snapshot():
        return catalog()

    async def command(device_id, action, value):
        commands.append(action)

    spec = sample()
    spec["mode"] = "queued"
    spec["steps"] = [{"type": "action", "device_id": "light.hall", "action": "on"}, {"type": "wait", "seconds": 1}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    devices = {item["id"]: item for item in catalog()}

    async def run():
        for index in range(3):
            engine._start(saved, f"event {index}", f"queue:{index}", devices)
        assert len(engine.pending[saved["id"]]) == 2
        await asyncio.wait_for(_wait_for_runs(3), 5)

    async def _wait_for_runs(count):
        while len([item for item in routines.list_runs() if item["status"] == "completed"]) < count:
            await asyncio.sleep(0.05)

    asyncio.run(run())
    assert commands == ["on", "on", "on"]


def test_restart_rate_limit_counts_events_before_tasks_write_logs():
    async def snapshot():
        return catalog()

    async def command(device_id, action, value):
        pass

    spec = sample()
    spec["mode"] = "restart"
    spec["steps"].append({"type": "wait", "seconds": 1})
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command)
    devices = {item["id"]: item for item in catalog()}

    async def run():
        for index in range(22):
            engine._start(saved, f"event {index}", f"restart:{index}", devices)
        assert len(engine.recent_starts[saved["id"]]) == 20
        assert len([item for item in routines.list_runs() if item["status"] == "blocked"]) == 2
        engine.cancel_routine(saved["id"])
        await asyncio.gather(*engine.running_tasks[saved["id"]], return_exceptions=True)

    asyncio.run(run())


def test_parallel_mode_keeps_activity_until_last_run_finishes():
    activity = []

    async def snapshot():
        return catalog()

    async def command(device_id, action, value):
        pass

    async def changed(device_ids):
        activity.append(set(device_ids))

    spec = sample()
    spec["mode"] = "parallel"
    spec["steps"].append({"type": "wait", "seconds": 1})
    saved = routines.save("alice", "alice", None, routines.validate(spec, catalog())["spec"], True, None)
    engine = routines.Engine(snapshot, command, activity_changed=changed)
    devices = {item["id"]: item for item in catalog()}

    async def run():
        engine._start(saved, "first", "parallel:1", devices)
        await asyncio.sleep(0.2)
        engine._start(saved, "second", "parallel:2", devices)
        await asyncio.sleep(0.1)
        assert len(engine.running_tasks[saved["id"]]) == 2
        assert engine.active_device_ids() == {"light.hall"}
        await asyncio.sleep(0.8)
        assert engine.active_device_ids() == {"light.hall"}
        await asyncio.gather(*engine.running_tasks[saved["id"]], return_exceptions=True)

    asyncio.run(run())
    assert activity[-1] == set()
    assert len([item for item in routines.list_runs() if item["status"] == "completed"]) == 2


def test_ksenia_event_fetches_only_referenced_devices():
    zone = {"id": "ksenia-zone:5", "kind": "alarm_zone", "name": "IR Ufficio", "state": "CLOSED"}
    selected_calls = []
    commands = []

    async def full_snapshot():
        raise AssertionError("Lo snapshot completo non deve essere letto per questo evento")

    async def selected_snapshot(references):
        selected_calls.append(references)
        return [zone, catalog()[0]]

    async def command(device_id, action, value):
        commands.append((device_id, action))

    spec = sample()
    spec["triggers"] = [{"type": "state", "device_id": zone["id"], "to": "active"}]
    saved = routines.save("alice", "alice", None, routines.validate(spec, [zone, *catalog()])["spec"], True, None)
    engine = routines.Engine(full_snapshot, command, selected_snapshot)
    engine.ksenia_live = True

    async def run():
        await engine.ksenia_event([zone])
        await engine.ksenia_event([{**zone, "state": "ACTIVE"}])
        await engine.running[saved["id"]]

    asyncio.run(run())
    assert commands == [("light.hall", "on")]
    assert selected_calls
    assert all(call == {"ksenia-zone:5", "light.hall"} for call in selected_calls)


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
        assert 'data-routine-description' in script
        assert 'api/user/routines/from-text' in script
        assert 'data-routine-generate-status' in script
        assert 'placeholder="Nome routine"' in script
        assert "routine_name:logPanel.querySelector" in script
        assert 'placeholder="ID routine"' not in script
        assert 'data-device-search' in script
        assert 'binary_sensor:[\'on\',\'off\']' in script
        assert "alarm_zone:['closed','active','tamper','masked','bypassed']" in script
        assert 'matches.slice(0, 80)' not in script
        invalid = client.post("/api/user/routines", json={"spec": sample(), "enabled": False})
        assert invalid.status_code == 400  # Devices missing from the live catalog.
