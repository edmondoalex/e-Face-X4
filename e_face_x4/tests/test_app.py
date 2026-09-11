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
            {"type": "temperature", "name": "Temperatura", "group": "Sala"},
        ],
        "mqtt": {"connected": True},
    })
    assert normalized["counts"] == {"lights": 1, "covers": 1, "locks": 1, "sensors": 1}
    assert normalized["rooms"] == [
        {"id": "room-0", "name": "Ingresso", "devices": 1},
        {"id": "room-1", "name": "Sala", "devices": 3},
    ]
    assert normalized["mqtt_connected"] is True


def test_supervisor_addon_slug_becomes_internal_dns_name() -> None:
    payload = {"data": {"addons": [{"slug": "a59e0dbb_e_hdl_buspro_mqtt"}]}}
    assert find_addon_url(payload, "e_hdl_buspro_mqtt", 8124) == "http://a59e0dbb-e-hdl-buspro-mqtt:8124"
