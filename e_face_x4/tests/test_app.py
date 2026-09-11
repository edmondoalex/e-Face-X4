from fastapi.testclient import TestClient

from app.main import create_app
from app.connectors.buspro import normalize_snapshot
from app.connectors.etherm import normalize_thermostats
from app.connectors.media import normalize_player
from app.connectors.local_media import normalize_local_snapshot
from app.connectors.supervisor import find_addon_url


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
    css = client.get("/assets/app.css").text
    assert ".layout>main,.detail-view,.scenario-panel,.scenario-list{min-width:0;max-width:100%}" in css
    assert ".scenario-list{display:grid" in css
    assert "@media(min-width:701px) and (max-width:1024px)" in css
    assert ".scenario-list{grid-template-columns:1fr}" in css


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
    assert 'id="media-zones-dialog"' in page


def test_local_home_assistant_media_snapshot_is_normalized() -> None:
    players, groups = normalize_local_snapshot({
        "areas": [{"area_id": "living", "name": "Soggiorno"}],
        "devices": [{"id": "device-1", "area_id": "living"}],
        "entities": [{"id": "registry-1", "entity_id": "media_player.sala", "device_id": "device-1", "disabled_by": None}],
        "states": [{"entity_id": "media_player.sala", "state": "playing", "last_updated": "2026-09-11T10:00:00Z", "attributes": {"friendly_name": "Sala", "volume_level": 0.4, "supported_features": 16397, "source_list": ["Spotify"]}}],
    })
    assert groups == []
    assert players[0]["id"] == "media:registry-1"
    assert players[0]["room"] == "Soggiorno"
    assert players[0]["volume"] == 40
    assert players[0]["capabilities"]["play"] is True
