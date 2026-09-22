from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import installation_profile
from app.config import load_settings
from app.connectors.buspro import normalize_snapshot
from app.main import create_app


def test_admin_connector_override_is_persistent_and_preserves_secret(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    profile = tmp_path / "installation.json"
    options.write_text(json.dumps({"buspro": {"enabled": False, "base_url": "http://old", "token": "initial"}}), encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setenv("EFACE_INSTALLATION_PROFILE", str(profile))

    installation_profile.save_connector("buspro", {
        "enabled": True, "base_url": "http://buspro.local:8124", "auth_mode": "token", "token": "new-secret",
    }, {"token": "initial", "password": "", "auth_mode": "token"})
    installation_profile.save_connector("buspro", {
        "enabled": True, "base_url": "http://buspro.local:8125", "auth_mode": "token", "token": "",
    }, vars(load_settings().buspro))

    configured = load_settings().buspro
    assert configured.enabled is True
    assert configured.base_url == "http://buspro.local:8125"
    assert configured.token == "new-secret"
    assert "new-secret" in profile.read_text(encoding="utf-8")


def test_access_profile_changes_presentation_without_losing_cover_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_INSTALLATION_PROFILE", str(tmp_path / "installation.json"))
    installation_profile.save_access_profiles({"items": [{
        "device_id": "garage", "enabled": True, "behavior": "cover_open_unlock",
        "name": "Porta garage", "confirm": True,
    }]})
    result = normalize_snapshot({
        "devices": [{"id": "garage", "type": "cover", "group": "Esterno", "subnet_id": 1, "device_id": 2, "channel": 3}],
        "cover_states": {"1.2.3": {"state": "OPEN", "position": 60}},
    })
    item = result["devices"][0]
    assert item["kind"] == "lock"
    assert item["name"] == "Porta garage"
    assert item["state"] == "OPEN"
    assert item["position"] == 60
    assert item["confirm_action"] is True
    assert result["counts"]["locks"] == 1
    assert result["counts"]["covers"] == 0


def test_access_action_translation_is_explicit() -> None:
    assert installation_profile.translate_access_action({"behavior": "relay_on_unlock"}, "unlock") == "on"
    assert installation_profile.translate_access_action({"behavior": "relay_on_unlock"}, "lock") == "off"
    assert installation_profile.translate_access_action({"behavior": "relay_off_unlock"}, "open") == "off"
    assert installation_profile.translate_access_action({"behavior": "cover_close_unlock"}, "open") == "close"
    assert installation_profile.translate_access_action({"behavior": "auto"}, "open") == "open"


def test_tools_exposes_portable_connector_and_access_sections() -> None:
    script = (Path(__file__).parents[1] / "app/static/assets/tools-dashboard.js").read_text(encoding="utf-8")
    assert "Connettori esterni" in script
    assert "Serrature e accessi" in script
    assert "api/admin/connectors" in script
    assert "api/admin/access-devices" in script
    assert 'id="access-devices-search"' in script
    assert "function filterAccessDevices()" in script
    assert "row.dataset.search" in script


def test_connector_admin_api_is_protected_and_never_returns_secrets(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_OPTIONS", str(tmp_path / "options.json"))
    monkeypatch.setenv("EFACE_INSTALLATION_PROFILE", str(tmp_path / "installation.json"))
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    from app.user_auth import create_admin
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.get("/api/admin/connectors").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    saved = client.put("/api/admin/connectors/buspro", json={
        "enabled": True, "base_url": "http://buspro.local:8124", "auth_mode": "token", "token": "secret-token",
    })
    assert saved.status_code == 200
    payload = client.get("/api/admin/connectors").json()
    buspro = next(item for item in payload["connectors"] if item["id"] == "buspro")
    evoice = next(item for item in payload["connectors"] if item["id"] == "evoice")
    assert buspro["token_configured"] is True
    assert "token" not in buspro
    assert "password" not in buspro
    assert "secret-token" not in json.dumps(payload)
    assert evoice["effective_url"] == "e-Control locale · API eVoice"
    assert evoice["source"] == "Integrazione e-Control"


def test_user_interface_never_uses_home_assistant_branding() -> None:
    static = Path(__file__).parents[1] / "app/static"
    for path in static.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".css"}:
            assert "Home Assistant" not in path.read_text(encoding="utf-8"), path
