from fastapi.testclient import TestClient

from app.main import create_app
from app.connectors.buspro import normalize_snapshot
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
    assert '<dialog' not in page.text
    assert 'id="show-all-devices"' in page.text
    for label in ("Guarda", "Ascolta", "Luci", "Oscuranti", "Comfort", "Sicurezza"):
        assert f'title="{label}"' in page.text
    assert 'src="assets/brand-horizontal.png"' in page.text
    assert 'class="header-wordmark"' not in page.text
    assert client.get("/assets/brand-horizontal.png").status_code == 200
    assert client.get("/assets/brand-icon.png").status_code == 200
    assert client.get("/assets/app.css").status_code == 200


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
            {"type": "light", "name": "Lampada", "group": "Sala"},
            {"type": "cover", "name": "Tenda", "group": "Sala"},
            {"type": "lock", "name": "Porta", "group": "Ingresso"},
            {"type": "temperature", "name": "Temperatura", "group": "Sala", "subnet_id": 1, "device_id": 61, "channel": 1},
            {"type": "switch", "name": "Presa", "group": "sala"},
        ],
        "mqtt": {"connected": True},
        "temp_states": {"1.61.1": {"value": 28.0, "ts": 123}},
    })
    assert normalized["counts"] == {"lights": 2, "covers": 1, "locks": 1, "sensors": 1}
    assert normalized["rooms"] == [
        {"id": "room-0", "name": "Ingresso", "devices": 1},
        {"id": "room-1", "name": "Sala", "devices": 4},
    ]
    assert normalized["mqtt_connected"] is True
    assert normalized["devices"][0]["icon"] == ""
    temperature = next(device for device in normalized["devices"] if device["kind"] == "temperature")
    assert temperature["state"] == 28.0
    assert temperature["unit"] == "°C"


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
    assert 'data-action="on"' in script
    assert 'data-action="open"' in script
    assert "api/devices/${encodeURIComponent(deviceId)}/command" in script


def test_device_command_requires_enabled_connector(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text('{"buspro":{"enabled":false,"base_url":"","token":""}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(create_app()).post("/api/devices/1/command", json={"action": "on"})
    assert response.status_code == 503
