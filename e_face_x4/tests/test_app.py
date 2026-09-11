from fastapi.testclient import TestClient

from app.main import create_app
from app.connectors.buspro import normalize_snapshot
from app.connectors.etherm import normalize_thermostats
from app.connectors.media import normalize_player
from app.connectors.local_media import normalize_local_snapshot
from app.connectors.local_media import HA_WEBSOCKET_MAX_BYTES
from app.connectors.control4_media import normalize_control4_groups, normalize_control4_media
from app.connectors.supervisor import find_addon_url
from app.media_preferences import apply_preferences, load_preferences, save_preferences
from app.control4 import load_control4_config, public_control4_config, save_control4_config, summarize_ui_configuration


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_bootstrap_never_exposes_tokens(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        '{"demo_mode":true,"buspro":{"enabled":false,"base_url":"http://localhost","token":"top-secret"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).get("/api/bootstrap")
    assert response.status_code == 200
    assert "top-secret" not in response.text


def test_starts_with_empty_options(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).get("/api/bootstrap")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


def test_starts_with_empty_connector_urls(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        '{"demo_mode":true,"buspro":{"enabled":false,"base_url":"","token":""},'
        '"evoice":{"enabled":false,"base_url":"","token":""}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).get("/api/bootstrap")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


def test_x4_shell_and_brand_assets_are_served() -> None:
    client = TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200
    assert "status-strip" in page.text
    assert "now-playing" in page.text
    assert 'id="detail-view"' in page.text
    assert 'id="detail-back"' in page.text
    assert page.text.count('<dialog') == 2
    assert 'id="rgb-dialog"' in page.text
    assert 'id="show-all-devices"' in page.text
    assert 'id="scenario-panel"' in page.text
    assert 'id="scenario-list"' in page.text
    assert '<iframe' not in page.text
    for label in ("Guarda", "Ascolta", "Luci", "Extra", "Scenari", "Oscuranti", "Comfort", "Sicurezza"):
        assert f'title="{label}"' in page.text
    assert 'src="assets/brand-horizontal.png?v=0.7.5"' in page.text
    assert 'alt="EKONEX e-Face X4"' in page.text
    assert 'class="header-wordmark"' not in page.text
    assert client.get("/assets/brand-horizontal.png").status_code == 200
    assert client.get("/assets/brand-icon.png").status_code == 200
    assert client.get("/assets/app.css").status_code == 200
    assert client.get("/assets/media.css").status_code == 200
    assert client.get("/assets/media-x4.css").status_code == 200
    assert client.get("/tools").status_code == 200
    assert "Admin / Installatore" in client.get("/tools").text
    css = client.get("/assets/app.css").text
    assert ".layout>main,.detail-view,.scenario-panel,.scenario-list{min-width:0;max-width:100%}" in css
    assert ".scenario-list{display:grid" in css
    assert "@media(min-width:701px) and (max-width:1024px)" in css
    assert ".scenario-list{grid-template-columns:1fr}" in css


def test_media_preferences_are_saved_and_applied(monkeypatch, tmp_path) -> None:
    path = tmp_path / "media_players.json"
    monkeypatch.setenv("EFACE_MEDIA_PREFERENCES", str(path))
    saved = save_preferences({"one": {"visible": True, "audio": True, "video": False, "order": 1}, "two": {"visible": True, "audio": True, "order": 0}}, {"one", "two"})
    assert load_preferences() == saved
    filtered = apply_preferences({"items": [
        {"registry_id": "one", "room": "Sala", "experiences": ["watch"]},
        {"registry_id": "two", "room": "Studio", "experiences": ["listen"]},
        {"registry_id": "three", "room": "Altro", "experiences": ["listen"]},
    ], "groups": [], "rooms": []})
    assert [item["registry_id"] for item in filtered["items"]] == ["two", "one"]
    assert filtered["items"][1]["experiences"] == ["listen"]
    assert filtered["rooms"] == ["Sala", "Studio"]


def test_installer_login_is_protected(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text('{"installer_password":"segreta"}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setenv("EFACE_INSTALLER_SECRET", str(tmp_path / "secret"))
    client = TestClient(create_app())
    assert client.get("/api/installer/media-players").status_code == 401
    assert client.post("/api/installer/login", json={"password": "errata"}).status_code == 401
    response = client.post("/api/installer/login", json={"password": "segreta"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()


def test_control4_credentials_are_local_and_never_returned(monkeypatch, tmp_path) -> None:
    path = tmp_path / "control4.json"
    monkeypatch.setenv("EFACE_CONTROL4_CONFIG", str(path))
    save_control4_config({"host": "192.168.3.10", "username": "user@example.com", "password": "secret"})
    assert load_control4_config()["password"] == "secret"
    public = public_control4_config()
    assert public == {"host": "192.168.3.10", "username": "user@example.com", "password_configured": True}
    assert "secret" not in str(public)
    save_control4_config({"host": "192.168.3.10", "username": "user@example.com", "password": ""})
    assert load_control4_config()["password"] == "secret"


def test_control4_ui_configuration_provides_rooms_and_sources() -> None:
    result = summarize_ui_configuration({"experiences": [
        {"type": "watch", "room_id": 9, "sources": {"source": [{"id": 1}, {"id": 2}]}},
        {"type": "listen", "room_id": 9, "sources": {"source": [{"id": 3}]}},
        {"type": "listen", "room_id": 12, "sources": {"source": []}},
    ]}, [{"id": 9, "name": "Sala"}, {"id": 12, "name": "Studio"}])
    assert result == {"rooms": 2, "room_names": ["Studio", "Sala"], "experiences": ["listen", "watch"], "sources": 3}


def test_control4_media_uses_only_listen_watch_rooms_and_native_sources() -> None:
    ui = {"experiences": [
        {"type": "watch", "room_id": 51, "sources": {"source": [{"id": 809, "name": "Samsung TV"}]}},
        {"type": "listen", "room_id": 51, "sources": {"source": [{"id": 100002, "name": "Spotify Connect"}]}},
        {"type": "lights", "room_id": 54, "sources": {"source": [{"id": 1, "name": "Luce"}]}},
    ]}
    variables = [
        {"id": 51, "varName": "POWER_STATE", "value": 1},
        {"id": 51, "varName": "CURRENT_VOLUME", "value": 64},
        {"id": 51, "varName": "IS_MUTED", "value": 0},
        {"id": 51, "varName": "CURRENT_AUDIO_DEVICE", "value": 100002},
    ]
    players = normalize_control4_media(ui, [{"id": 51, "name": "Ufficio Alex"}, {"id": 54, "name": "Bagno PT"}], variables)
    assert len(players) == 1
    player = players[0]
    assert player["name"] == "Ufficio Alex"
    assert player["experiences"] == ["watch", "listen"]
    assert player["state"] == "playing"
    assert player["volume"] == 64
    assert player["source"] == "Spotify Connect"
    assert player["source_options"] == [
        {"key": "watch:809", "label": "Samsung TV", "experience": "watch", "type": ""},
        {"key": "listen:100002", "label": "Spotify Connect", "experience": "listen", "type": ""},
    ]
    assert player["capabilities"]["turn_off"] is True


def test_control4_unknown_volume_disables_volume_control() -> None:
    players = normalize_control4_media(
        {"experiences": [{"type": "listen", "room_id": 7, "sources": {"source": []}}]},
        [{"id": 7, "name": "Esterno"}],
        [{"id": 7, "varName": "CURRENT_VOLUME", "value": -1}],
    )
    assert players[0]["volume"] is None
    assert players[0]["capabilities"]["set_volume"] is False


def test_control4_current_media_info_exposes_metadata_and_safe_artwork_fingerprint() -> None:
    import base64

    cover = "https://i.scdn.co/image/example"
    players = normalize_control4_media(
        {"experiences": [{"type": "listen", "room_id": 51, "sources": {"source": []}}]},
        [{"id": 51, "name": "Ufficio Alex"}],
        [{"id": 51, "varName": "POWER_STATE", "value": 1},
         {"id": 51, "varName": "CURRENT MEDIA INFO", "value": {"mediainfo": {
            "title": "Brano", "artist": "Artista", "album": "Album",
            "meta": {"audioFormat": "Spotify Connect"},
            "streamStatus": "status=OK_paused",
            "img": base64.b64encode(cover.encode()).decode(),
        }}}],
    )
    assert players[0]["title"] == "Brano"
    assert players[0]["artist"] == "Artista"
    assert players[0]["album"] == "Album"
    assert players[0]["source"] == "Spotify Connect"
    assert players[0]["state"] == "paused"
    assert len(players[0]["content_fingerprint"]) == 64
    assert players[0]["capabilities"]["artwork"] is True
    assert players[0]["capabilities"]["previous"] is True
    assert players[0]["capabilities"]["next"] is True
    assert players[0]["capabilities"]["grouping"] is False


def test_control4_command_does_not_require_evoice_enabled(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"evoice":{"enabled":false,"base_url":"","token":"","installation_id":""}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "configured", "password": "configured"})

    async def command(self, registry_id, operation, value=None):
        return {"status": "success", "registry_id": registry_id, "operation": operation}

    monkeypatch.setattr(main_module.Control4MediaConnector, "command", command)
    response = TestClient(main_module.create_app()).post("/api/devices/c4media:51/command", json={"action": "turn_off"})
    assert response.status_code == 200
    assert response.json() == {"status": "success", "registry_id": "c4room:51", "operation": "turn_off"}


def test_configured_home_name_is_shown_in_bootstrap(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text('{"home_name":"Villa Aurora","demo_mode":true}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).get("/api/bootstrap")
    assert response.status_code == 200
    assert response.json()["dashboard"]["home"]["name"] == "Villa Aurora"


def test_buspro_snapshot_is_normalized_by_room_and_kind() -> None:
    normalized = normalize_snapshot({
        "devices": [
            {"type": "light", "name": "Lampada", "group": "Sala", "dimmable": True, "rgb_group": "RGB Sala", "rgb_channel": "red"},
            {"type": "cover", "name": "Tenda", "group": "Sala"},
            {"type": "lock", "name": "Porta", "group": "Ingresso"},
            {"type": "temperature", "name": "Temperatura", "group": "Sala", "subnet_id": 1, "device_id": 61, "channel": 1},
            {"type": "light", "category": "Switch", "name": "Presa", "group": "sala"},
            {"name": "Luce legacy", "group": "Sala", "subnet_id": 1, "device_id": 2, "channel": 3},
        ],
        "mqtt": {"connected": True},
        "temp_states": {"1.61.1": {"value": 28.0, "ts": 123}},
    })
    assert normalized["counts"] == {"lights": 2, "switches": 1, "covers": 1, "locks": 1, "sensors": 1}
    assert normalized["rooms"] == [
        {"id": "room-0", "name": "Ingresso", "devices": 1},
        {"id": "room-1", "name": "Sala", "devices": 5},
    ]
    assert normalized["mqtt_connected"] is True
    assert normalized["devices"][0]["icon"] == ""
    assert normalized["devices"][0]["dimmable"] is True
    assert normalized["devices"][0]["rgb_group"] == "RGB Sala"
    assert normalized["devices"][0]["rgb_channel"] == "red"
    temperature = next(device for device in normalized["devices"] if device["kind"] == "temperature")
    assert temperature["state"] == 28.0
    assert temperature["unit"] == "°C"
    assert temperature["state_key"] == "1.61.1"
    assert normalized["devices"][-1]["kind"] == "light"
    assert next(device for device in normalized["devices"] if device["name"] == "Presa")["kind"] == "switch"


def test_supervisor_addon_slug_becomes_internal_dns_name() -> None:
    payload = {"data": {"addons": [{"slug": "a59e0dbb_e_hdl_buspro_mqtt"}]}}
    assert find_addon_url(payload, "e_hdl_buspro_mqtt", 8124) == "http://a59e0dbb-e-hdl-buspro-mqtt:8124"


def test_navigation_icons_have_defaults(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    data = TestClient(create_app()).get("/api/bootstrap").json()
    assert data["nav_icons"]["watch"] == "mdi:television-play"
    assert data["nav_icons"]["security"] == "mdi:shield-home"
    assert data["nav_icons"]["extra"] == "mdi:shape"
    assert data["nav_icons"]["scenarios"] == "mdi:creation"


def test_invalid_mdi_icon_name_returns_safe_fallback() -> None:
    response = TestClient(create_app()).get("/api/icons/mdi/not!valid.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "M12 2 22 12 12 22 2 12Z" in response.text


def test_icon_urls_are_invalidated_by_addon_version() -> None:
    script = TestClient(create_app()).get("/assets/app.js")
    assert script.status_code == 200
    assert "encodeURIComponent(appVersion)" in script.text


def test_device_commands_are_present_in_frontend() -> None:
    script = TestClient(create_app()).get("/assets/app.js").text
    assert 'data-device-toggle tabindex="0"' in script
    assert "active ? 'off' : 'on'" in script
    assert 'data-action="open"' in script
    assert "api/devices/${encodeURIComponent(deviceId)}/command" in script
    assert "deviceVisualClass(device)" in script
    assert "device-switch-on" in script
    assert "device-cover-open" in script
    assert "device-lock-closed" in script
    assert "deviceCardStyle(device)" in script
    assert "--cover-color:rgb" in script
    assert "new WebSocket(realtimeUrl())" in script
    assert "applyRealtimeEvent(JSON.parse(message.data))" in script
    assert "realtimeSocket.readyState !== WebSocket.OPEN" in script
    assert "updateNavigationStates()" in script
    assert "status-yellow" in script
    assert "data-rgb-color" in script
    assert "data-rgb-brightness" in script
    assert "data-brightness" in script
    assert "data.brightness" in script
    assert "--light-glow:" in script
    assert "brightness255(device) / 255" in script
    assert "openRgbDialog" in script
    assert "rgb-channel-controls" in script
    assert "'skip-previous'" in script
    assert "'skip-next'" in script
    assert "'volume-high'" in script
    assert "mediaSourceIcon" in script
    assert "enabled = false" in script


def test_device_command_requires_enabled_connector(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text('{"buspro":{"enabled":false,"base_url":"","token":""}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).post("/api/devices/1/command", json={"action": "on"})
    assert response.status_code == 503


def test_scenario_command_rejects_unknown_action_before_connector() -> None:
    response = TestClient(create_app()).post("/api/scenarios/example/command", json={"action": "delete"})
    assert response.status_code == 400


def test_etherm_thermostat_is_normalized() -> None:
    items = normalize_thermostats({"entities": [{"type": "thermostats", "id": 7, "name": "Sala", "realtime": {"TEMP": 21.4, "RH": 48, "THERM": {"ACT_SEA": "WIN", "ACT_MODEL": "MAN", "DEMAND_ON": "ON", "TEMP_THR": {"VAL": 22.5}, "PWM": 35}}}], "meta": {"vtherm_config": {"thermostats": [{"id": 7, "floor": "Piano terra"}]}}})
    assert items[0]["id"] == "therm:7"
    assert items[0]["state"] == "HEATING"
    assert items[0]["temperature"] == 21.4
    assert items[0]["target_temperature"] == 22.5
    assert items[0]["room"] == "Piano terra"


def test_etherm_basic_auth_header() -> None:
    from app.config import ProviderConfig
    from app.connectors.etherm import EThermConnector
    config = ProviderConfig(True, "http://etherm:8080", "", "basic", "alex", "secret")
    assert EThermConnector(config, 4).headers()["Authorization"].startswith("Basic ")


def test_provider_url_without_protocol_is_normalized(monkeypatch, tmp_path) -> None:
    from app.config import load_settings
    options = tmp_path / "options.json"
    options.write_text('{"etherm":{"enabled":true,"base_url":"192.168.3.24:8080"}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    assert load_settings().etherm.base_url == "http://192.168.3.24:8080"


def test_media_player_is_normalized_without_exposing_credentials() -> None:
    item = normalize_player({
        "registry_id": "abc123", "entity_id": "media_player.sala", "name": "Sala",
        "area": {"id": "sala", "name": "SALA"}, "state": "playing",
        "availability": "available", "connection_status": "online",
        "media": {"title": "Brano", "artist": "Artista", "content_fingerprint": "sha256:track"},
        "volume_percent": 42, "muted": False, "source": "Spotify",
        "source_list": ["Spotify", "Radio"], "capabilities": {"play": True, "set_volume": True},
        "resource_revision": 9, "access_token": "never-share",
    })
    assert item["id"] == "media:abc123"
    assert item["title"] == "Brano"
    assert item["volume"] == 42
    assert "access_token" not in item


def test_media_configuration_includes_installation(monkeypatch, tmp_path) -> None:
    from app.config import load_settings
    options = tmp_path / "options.json"
    options.write_text('{"evoice":{"enabled":true,"base_url":"media.local","token":"secret","installation_id":"plant-1"}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    settings = load_settings()
    assert settings.evoice.base_url == "http://media.local"
    assert settings.evoice.installation_id == "plant-1"


def test_media_ui_has_room_selection_and_typed_controls() -> None:
    client = TestClient(create_app())
    page = client.get("/").text
    script = client.get("/assets/app.js").text
    assert 'id="av-room-toggle"' in page
    assert "data-media-action" in script
    assert "data-media-volume" in script
    assert "data-media-source" in script
    assert "media_changed" in script
    assert "renderMediaExperience" in script
    assert 'id="media-zones-dialog"' in page
    assert "[...currentRooms" not in script
    assert "device.experiences?.includes('watch')" in script
    assert "['listen', 'watch'].includes(experience)" in script
    assert "data-zone-volume" in script
    assert "postDeviceCommand(player.id, 'media_unjoin'" in script


def test_control4_digital_media_queue_becomes_canonical_group() -> None:
    players = [
        {"registry_id": "c4room:50", "name": "Ufficio Contabilità"},
        {"registry_id": "c4room:51", "name": "Ufficio Alex"},
    ]
    variables = [{
        "varName": "QUEUE_STATUS_V2",
        "value": {"queues": {"queue": {"id": 10015, "owner": 51, "rooms": {"id": [50, 51]}}}},
    }]
    groups = normalize_control4_groups(players, variables)
    assert groups == [{
        "group_id": "c4queue:10015",
        "name": "Sessione audio",
        "owner_registry_id": "c4room:51",
        "member_registry_ids": ["c4room:50", "c4room:51"],
        "completeness": "complete",
        "resource_revision": 10015,
    }]
    assert players[0]["group"] == groups[0]


def test_local_home_assistant_media_snapshot_is_normalized() -> None:
    players, groups = normalize_local_snapshot({
        "areas": [{"area_id": "living", "name": "Soggiorno"}],
        "devices": [{"id": "device-1", "area_id": "living"}],
        "entities": [{"id": "registry-1", "entity_id": "media_player.sala", "device_id": "device-1", "device_class": "tv", "disabled_by": None}],
        "states": [{"entity_id": "media_player.sala", "state": "playing", "last_updated": "2026-09-11T10:00:00Z", "attributes": {"friendly_name": "Sala", "volume_level": 0.4, "supported_features": 16397, "source_list": ["Spotify"]}}],
    })
    assert groups == []
    assert players[0]["id"] == "media:registry-1"
    assert players[0]["room"] == "Sala"
    assert players[0]["volume"] == 40
    assert players[0]["capabilities"]["play"] is True
    assert players[0]["experiences"] == ["watch"]
    assert HA_WEBSOCKET_MAX_BYTES == 16 * 1024 * 1024


def test_media_player_without_area_uses_its_name_as_room() -> None:
    players, _ = normalize_local_snapshot({
        "areas": [], "devices": [], "entities": [],
        "states": [{"entity_id": "media_player.ufficio_alex", "state": "playing", "last_updated": "2026-09-11T10:00:00Z", "attributes": {"friendly_name": "Ufficio Alex", "supported_features": 16384}}],
    })
    assert players[0]["room"] == "Ufficio Alex"
