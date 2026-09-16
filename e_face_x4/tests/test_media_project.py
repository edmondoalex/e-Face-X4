from app import media_project


def test_discovery_builds_provider_neutral_project(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_PROJECT", str(tmp_path / "project.json"))
    control4 = {"status": "online", "items": [{"registry_id": "c4room:51", "name": "Sala", "room": "Sala", "experiences": ["listen", "watch"]}]}
    wiim = {"id": "uuid-amp", "name": "Terrazzo", "model": "WiiM Amp"}
    project = media_project.discovered(control4, wiim, {"host": "192.168.3.60"})
    assert {device["provider"] for device in project["devices"]} == {"control4", "wiim"}
    assert len(project["zones"]) == 2
    assert any(device["kind"] == "network_amplifier" for device in project["devices"])
    assert project["revision"] == 1


def test_project_rejects_cross_room_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_PROJECT", str(tmp_path / "project.json"))
    raw = media_project.empty()
    raw["zones"] = [{"id": "zone:a", "name": "A"}, {"id": "zone:b", "name": "B"}]
    raw["devices"] = [{"id": "device:one", "name": "Player", "zone_id": "zone:a", "capabilities": ["audio"]}]
    raw["endpoints"] = {"zone:b": {"audio": "device:one"}}
    assert media_project.validate(raw)["endpoints"]["zone:b"] == {}


def test_project_save_creates_backup(monkeypatch, tmp_path):
    path = tmp_path / "project.json"
    monkeypatch.setenv("EFACE_MEDIA_PROJECT", str(path))
    media_project.save(media_project.empty())
    media_project.save(media_project.empty())
    assert path.with_suffix(".json.bak").is_file()
