from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest
import json
from pathlib import Path
from urllib.parse import urljoin

from app.main import artwork_media_type, create_app
from app.connectors.buspro import BusproConnector, normalize_snapshot
from app.connectors.etherm import normalize_thermostats
from app.connectors.ksenia import normalize_ksenia
from app.connectors.media import EkonexMediaConnector, EvoiceLocalMediaConnector, normalize_local_player, normalize_player
from app.connectors.local_media import normalize_local_snapshot
from app.connectors.local_media import HA_WEBSOCKET_MAX_BYTES
from app.connectors.control4_media import Control4MediaConnector, control4_icon_path, control4_queues, control4_remote_actions, normalize_control4_groups, normalize_control4_media
from app.connectors.supervisor import find_addon_url, find_host_url
from app.media_preferences import apply_preferences, load_preferences, save_preferences
from app.control4 import load_control4_config, public_control4_config, save_control4_config, summarize_ui_configuration
from app.source_icons import delete_source_icon, load_builtin_source_icon, load_builtin_source_icon_by_id, load_source_icon, save_source_icon
from app.backgrounds import load_background, load_background_image, load_backgrounds, save_background_image, save_card_theme, save_inherit, save_preset


def test_reconnect_warnings_are_rate_limited(monkeypatch) -> None:
    import app.main as main_module

    messages = []
    current = [100.0]
    main_module._reconnect_warning_at.clear()
    monkeypatch.setattr(main_module.time, "monotonic", lambda: current[0])
    monkeypatch.setattr(main_module.logging, "warning", lambda *args: messages.append(args))
    main_module.log_reconnect_warning("control4")
    main_module.log_reconnect_warning("control4")
    current[0] += 60
    main_module.log_reconnect_warning("control4")
    assert len(messages) == 2
    main_module._reconnect_warning_at.clear()


def test_release_changelog_matches_addon_version() -> None:
    root = Path(__file__).resolve().parents[1]
    version = next(line.split(":", 1)[1].strip() for line in (root / "config.yaml").read_text(encoding="utf-8").splitlines() if line.startswith("version:"))
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert changelog[0] == "# Changelog"
    assert changelog[2].startswith(f"## {version} — ")


def test_control4_octet_stream_artwork_uses_image_signature_only() -> None:
    assert artwork_media_type("application/octet-stream", b"\xff\xd8\xff\xe0jpeg") == "image/jpeg"
    assert artwork_media_type("application/octet-stream", b"\x89PNG\r\n\x1a\npng") == "image/png"
    assert artwork_media_type("application/octet-stream", b"GIF89aimage") == "image/gif"
    assert artwork_media_type("application/octet-stream", b"RIFFxxxxWEBPimage") == "image/webp"
    assert artwork_media_type("application/octet-stream", b"<html>not an image</html>") == ""


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["version"] == "2.21.87"


def test_installed_app_starts_at_dashboard() -> None:
    client = TestClient(create_app())
    manifest = client.get("/assets/manifest.webmanifest").json()
    for base, dashboard in (
        ("https://eface.example/assets/manifest.webmanifest", "https://eface.example/"),
        ("https://ha.example/ingress/token/assets/manifest.webmanifest", "https://ha.example/ingress/token/"),
    ):
        assert urljoin(base, manifest["start_url"]) == dashboard
        assert urljoin(base, manifest["scope"]) == dashboard
    old_install = client.get("/assets/", follow_redirects=False)
    assert old_install.status_code == 307
    assert old_install.headers["location"] == "../"


def test_intercom_is_in_sidebar_with_embedded_view() -> None:
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    dashboard = (static / "index.html").read_text(encoding="utf-8")
    script = (static / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'data-view="intercom"' in dashboard
    assert 'id="intercom-frame"' in dashboard
    assert "intercom?embedded=1" in script
    assert (static / "assets" / "intercom-nav.svg").is_file()
    assert (static / "assets" / "intercom-ringing.svg").is_file()
    assert (static / "assets" / "intercom-speaking.svg").is_file()
    intercom = (static / "intercom.html").read_text(encoding="utf-8")
    assert 'class="intercom-station-list"' in intercom
    assert 'id="doorbird-expand"' in intercom
    assert 'id="call-ufficio" data-dial-extension="8291"' in intercom
    assert 'id="call-tavolo" data-dial-extension="8292"' in intercom
    assert 'id="intercom-call-panel" class="intercom-call-panel" hidden' in intercom
    assert 'class="intercom-station-row sip-station-row"' in intercom
    assert 'Chiama Ufficio e Tavolo Control4' not in intercom
    assert 'class="admin-intercom"' not in intercom
    client_script = (static / "assets" / "intercom.js").read_text(encoding="utf-8")
    intercom_page = (static / "intercom.html").read_text(encoding="utf-8")
    assert "Tablet Control4 · interno 8291" in intercom_page
    assert "const currentVersion = '2.21.87'" in client_script
    assert 'id="call-ufficio" data-dial-extension="8291" data-video-capable="true"' in intercom_page
    assert "Postazione esterna · interno 8201" in intercom_page
    assert "Postazione esterna · interno ${station.sip_extension}" in client_script
    assert "startRingtone" in client_script
    assert "current-device-controls" in client_script
    assert "signature === personalDevicesSignature" in client_script
    assert "requestId !== personalDevicesRequest" in client_script
    assert "eface-intercom-state" in client_script
    assert "api/intercom/groups" in client_script
    assert "if (!adminMode) $('#sip-connect').click()" in client_script
    assert "candidate?.type === 'relay'" in client_script
    assert "iceTransportPolicy: 'relay'" in client_script
    assert "iceReadySent = true" in client_script
    assert "Chiusura chiamata…" in client_script
    assert 'id="audio-status"' in intercom
    assert 'id="audio-retry"' in intercom
    assert 'id="remote-video"' in intercom
    assert 'id="local-video"' in intercom
    assert 'id="camera-switch"' in intercom
    assert "sessionOffersVideo" in client_script
    assert "const pushPromise = fetch" in client_script
    assert "Notifica urgente inviata" in client_script
    assert "const videoDestination = button.dataset.videoCapable === 'true'" in client_script
    assert client_script.count("$('#intercom-video-panel').scrollIntoView({behavior:'smooth', block:'start'})") == 3
    assert "prepareCameraPreview()" in client_script
    assert "Preparo il video prima della risposta…" in client_script
    assert "Chiamata a ${targetName} · squilla…" in client_script
    assert "In conversazione con ${targetName}" in client_script
    assert 'id="call-title"' in intercom
    assert "Chiamata a ${targetName}`" in client_script
    assert "video-call-active" in client_script
    assert "replaceTrack" in client_script
    assert "video:stream.getVideoTracks().length > 0" in client_script
    assert "peerconnection.getStats()" in client_script
    assert "Date.now() + 1500" in client_script
    assert "Date.now() + 60000" not in client_script
    assert "['closed', 'failed'].includes(peerconnection.connectionState)" in client_script
    assert "session.isEnded?.()" in client_script
    assert "createMediaElementSource" not in client_script
    assert "bindConnection(session.connection)" in client_script
    assert "peerconnection.getReceivers" in client_script
    assert "$('#intercom-frame').src = apiUrl('intercom?embedded=1')" in script
    assert "$('#intercom-frame').removeAttribute('src')" not in script


def test_admin_migration_guards_pages_apis_and_websocket(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    options = tmp_path / "options.json"
    options.write_text(json.dumps({"installer_password": "vecchia-password"}), encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    client = TestClient(create_app())
    assert client.get("/api/auth/status").json() == {"enabled": False, "user": None, "name": None, "role": None}
    assert client.get("/").status_code == 200
    assert client.post("/api/auth/setup", json={"password": "nuova-password-lunga"}).status_code == 401
    assert client.post("/api/installer/login", json={"password": "vecchia-password"}).status_code == 200
    assert client.post("/api/auth/setup", json={"password": "breve"}).status_code == 400
    assert client.post("/api/auth/setup", json={"password": "nuova-password-lunga"}).status_code == 200
    assert client.get("/api/auth/status").json() == {"enabled": True, "user": "admin", "name": "Admin", "role": "admin"}
    assert client.get("/api/user/appearance").status_code == 200
    assert client.post("/api/auth/setup", json={"password": "altra-password-lunga"}).status_code == 409
    client.post("/api/auth/logout")
    assert client.get("/api/user/appearance").status_code == 401
    assert client.get("/", follow_redirects=False).headers["location"] == "login"
    assert client.post("/api/auth/login", json={"username": "admin", "password": "errata"}).status_code == 401
    assert client.post("/api/auth/login", headers={"Origin": "https://evil.example"}, json={"username": "admin", "password": "nuova-password-lunga"}).status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/realtime"):
            pass
    login = client.post("/api/auth/login", headers={"X-Forwarded-Proto": "https"}, json={"username": "admin", "password": "nuova-password-lunga", "remember": True})
    assert login.status_code == 200
    assert "Max-Age=157680000" in login.headers["set-cookie"]
    assert "HttpOnly" in login.headers["set-cookie"] and "Secure" in login.headers["set-cookie"] and "SameSite=lax" in login.headers["set-cookie"]
    assert 'id="remember"' in client.get("/login").text
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nuova-password-lunga"}).status_code == 200
    options.write_text(json.dumps({"installer_password": ""}), encoding="utf-8")
    assert client.get("/api/installer/control4").status_code == 200


def test_admin_login_rate_limit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    from app.user_auth import create_admin
    create_admin("password-abbastanza-lunga")
    client = TestClient(create_app())
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "admin", "password": "errata"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-abbastanza-lunga"}).status_code == 429


def test_admin_accounts_are_isolated_and_sessions_can_be_revoked(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    from app.user_auth import create_admin
    create_admin("password-admin-lunga")
    admin = TestClient(create_app())
    person = TestClient(create_app())
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    created = admin.post("/api/admin/users", json={"username": "mario", "name": "Mario Rossi", "password": "password-mario-lunga"})
    assert created.status_code == 200
    assert created.json()["user"] | {"created_at": ""} == {"username": "mario", "name": "Mario Rossi", "role": "user", "active": True, "origin": "local", "sync_status": "local", "created_at": "", "provider": "", "trusted_access": False}
    assert created.json()["user"]["created_at"]
    assert admin.post("/api/admin/users", json={"username": "cloud", "name": "Cloud", "password": "password-cloud-lunga", "origin": "cloud"}).status_code == 400
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"}).status_code == 200
    assert person.get("/api/auth/status").json()["role"] == "user"
    assert person.get("/api/admin/users").status_code == 403
    assert person.get("/api/admin/intercom").status_code == 403
    assert person.get("/api/installer/control4").status_code == 403
    assert admin.patch("/api/admin/users/mario", json={"trusted_access": True}).json()["user"]["trusted_access"] is True
    trusted_login = person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga", "remember": False})
    assert trusted_login.status_code == 200
    assert "Max-Age=157680000" in trusted_login.headers["set-cookie"]
    assert admin.patch("/api/admin/users/mario", json={"trusted_access": False}).json()["user"]["trusted_access"] is False
    assert person.get("/api/user/appearance").status_code == 401
    regular_login = person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga", "remember": True})
    assert regular_login.status_code == 200
    assert "Max-Age=43200" in regular_login.headers["set-cookie"]
    assert admin.patch("/api/admin/users/mario", json={"password": "password-mario-nuova"}).status_code == 200
    assert person.get("/api/user/appearance").status_code == 401
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-nuova"}).status_code == 200
    assert admin.patch("/api/admin/users/mario", json={"active": False}).status_code == 200
    assert person.get("/api/user/appearance").status_code == 401
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-nuova"}).status_code == 401
    assert admin.patch("/api/admin/users/admin", json={"active": False}).status_code == 400


def test_admin_can_delete_clean_user_and_recreate_from_zero(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "sip.json"))
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    from app.user_auth import create_admin
    from app import sip_accounts
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"})
    payload = {"username": "mario", "name": "Mario", "password": "password-mario-lunga"}
    assert client.post("/api/admin/users", json=payload).status_code == 200
    assert sip_accounts.allocate("mario")["extension"] == "8302"
    assert client.delete("/api/admin/users/admin").status_code == 400
    assert client.delete("/api/admin/users/mario").json() == {"removed": True}
    assert "mario" not in sip_accounts.load()
    assert client.post("/api/admin/users", json=payload).status_code == 200


def test_admin_ami_probe_does_not_store_or_expose_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    from app.user_auth import create_admin
    from app import asterisk_ami
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/admin/intercom/ami/test", json={"secret": "private"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert client.post("/api/admin/intercom/ami/test", json={"secret": ""}).status_code == 400
    calls = []

    async def fake_probe(host, port, username, secret):
        calls.append((host, port, username, secret))
        return {"Response": "Success", "Line-000000": "username=8301"}

    async def fake_source(host, port):
        return "172.30.33.5"

    monkeypatch.setattr(asterisk_ami, "read_8301_auth", fake_probe)
    monkeypatch.setattr(asterisk_ami, "local_source_ip", fake_source)
    response = client.post("/api/admin/intercom/ami/test", json={"secret": " private\n"})
    assert response.status_code == 200
    assert response.json() == {"ami_connected": True, "auth_8301_found": True, "source_ip": "172.30.33.5"}
    assert response.headers["cache-control"] == "no-store, private"
    assert "private" not in response.text
    assert calls == [("192.168.3.24", 5038, "eface", "private")]

    async def rejected(host, port, username, secret):
        raise asterisk_ami.AMIAuthenticationError("denied")

    monkeypatch.setattr(asterisk_ami, "read_8301_auth", rejected)
    failure = client.post("/api/admin/intercom/ami/test", json={"secret": "private"})
    assert failure.status_code == 200
    assert failure.json() == {"ami_connected": False, "issue": "authentication", "source_ip": "172.30.33.5"}
    assert "private" not in failure.text

    async def config_missing(host, port, username, secret):
        raise asterisk_ami.AMIActionError("Category not found")

    monkeypatch.setattr(asterisk_ami, "read_8301_auth", config_missing)
    missing = client.post("/api/admin/intercom/ami/test", json={"secret": "private"})
    assert missing.json() == {"ami_connected": True, "issue": "config_read", "reason": "category", "source_ip": "172.30.33.5"}


def test_intercom_dashboard_stores_only_local_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    from app.user_auth import create_admin
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    default = client.get("/api/admin/intercom").json()
    assert default["settings"]["ring_extension"] == "8290"
    assert default["sip_ready"] is False
    assert default["turn"]["password_configured"] is False
    settings = {**default["settings"], "asterisk_host": "192.168.3.24", "doorbird_host": "192.168.2.30"}
    assert client.put("/api/admin/intercom", json=settings).status_code == 200
    assert (tmp_path / "intercom.json").is_file()
    assert client.put("/api/admin/intercom", json={**settings, "asterisk_host": "8.8.8.8"}).status_code == 400
    page = client.get("/tools").text
    assert 'id="tools-admin-nav"' in page
    assert 'id="intercom-tool"' in page
    assert 'id="users-tool"' in page
    assert 'id="logout"' in page
    assert page.index('id="logout"') < page.index('id="tools-user-section"')
    assert "tools-dashboard.js?v=2.21.87" in page
    home = client.get("/").text
    assert "backgrounds.css?v=2.21.43" in home
    assert "app.js?v=2.21.87" in home


def test_external_stations_api_requires_login_and_hides_secrets(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    monkeypatch.setenv("EFACE_EXTERNAL_STATIONS", str(tmp_path / "external.json"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    from app.user_auth import create_admin
    from app import provisioner_client, doorbird_api, credential_inventory
    credential_inventory.save("doorbird", "legacy-user", "legacy-secret")
    async def fake_provision(method, path, payload=None):
        assert path == "/v1/external-stations"
        if method == "PUT":
            assert payload == {"stations": [{"extension": "8202", "host": "192.168.2.31"}]}
        return {"provisioned": True}
    async def fake_doorbird(*args):
        assert args[1] in {"192.168.2.30", "192.168.2.31"}
        return None
    monkeypatch.setattr(provisioner_client, "request", fake_provision)
    monkeypatch.setattr(doorbird_api, "ensure_incoming_sip", fake_doorbird)
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.get("/api/intercom/external-stations").status_code == 401
    assert client.get("/api/admin/intercom/external-stations").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    stations = client.get("/api/admin/intercom/external-stations").json()["stations"]
    extra = {"id": "esterno-2", "name": "Cancello", "host": "192.168.2.31", "http_port": 80,
             "sip_extension": "8202", "ready": False, "username": "operator", "password": "secret"}
    first = {**stations[0], "username": "", "password": ""}
    first.pop("credential_configured")
    response = client.put("/api/admin/intercom/external-stations", json={"stations": [first, extra]})
    assert response.status_code == 200, response.text
    assert "secret" not in response.text
    public = client.get("/api/intercom/external-stations")
    assert public.status_code == 200
    assert "secret" not in public.text
    assert "192.168.2.31" not in public.text
    assert public.json()["stations"][1]["name"] == "Cancello"
    assert client.post("/api/intercom/external-stations/esterno-2/prepare-call").json() == {"ready": True, "extension": "8202"}
    assert client.post("/api/intercom/external-stations/ingresso/prepare-call").json() == {"ready": True, "extension": "8201"}


def test_composer_guide_is_admin_only_and_never_exposes_passwords(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CONTROL4_CONFIG", str(tmp_path / "control4.json"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    monkeypatch.setenv("EFACE_PROVISIONER_SETTINGS", str(tmp_path / "provisioner.json"))
    monkeypatch.setenv("EFACE_INTERNAL_STATIONS", str(tmp_path / "internal.json"))
    from app.user_auth import create_admin, create_account
    from app import credential_inventory, control4
    create_admin("password-admin-lunga")
    create_account("mario", "Mario", "password-mario-lunga")
    control4.save_control4_config({"host": "192.168.3.10", "username": "installer@example.com", "password": "director-secret"})
    credential_inventory.save("sip_eface", "8301", "eface-secret")
    credential_inventory.save("sip_control4", "8100", "proxy-secret")
    admin = TestClient(create_app())
    person = TestClient(create_app())
    path = "/api/admin/intercom/composer-guide"
    assert admin.get(path).status_code == 401
    person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"})
    assert person.get(path).status_code == 403
    admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"})
    response = admin.get(path)
    assert response.status_code == 200
    assert response.json()["eface_extension"] == "8301"
    assert response.json()["control4_sip_user"] == "8100"
    assert response.json()["eface_password_present"] is True
    assert response.json()["control4_sip_copy_present"] is True
    assert response.headers["cache-control"] == "no-store, private"
    for secret in ("director-secret", "eface-secret", "proxy-secret"):
        assert secret not in response.text
    page = admin.get("/tools").text
    assert 'id="composer-wizard"' in page
    assert "Configurazione guidata Intercom" in page


def test_intercom_uses_admin_verified_8301_copy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "sip_accounts.json"))
    from app.user_auth import create_admin, create_account
    from app import credential_inventory
    create_admin("password-admin-lunga")
    create_account("mario", "Mario", "password-mario-lunga")
    admin = TestClient(create_app())
    person = TestClient(create_app())
    assert admin.get("/api/intercom/sip/credential").status_code == 401
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"}).status_code == 200
    assert person.get("/api/intercom/sip/credential").status_code == 409
    assert admin.get("/api/intercom/sip/credential").status_code == 409
    credential_inventory.save("sip_eface", "8301", "real-sip-secret")
    response = admin.get("/api/intercom/sip/credential")
    assert response.status_code == 200
    assert response.json() == {"username": "8301", "password": "real-sip-secret"}
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["vary"] == "Cookie"
    assert "api/intercom/sip/credential" in admin.get("/assets/intercom.js").text
    script = admin.get("/assets/intercom.js").text
    assert "eface-intercom-fast-ice-v1" in script
    assert "if (icePreference === null) $('#fast-ice').checked = iceServers.length === 0" in script


def test_personal_sip_accounts_require_provisioning_and_keep_8301_private(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "sip_accounts.json"))
    from app.user_auth import create_admin, create_account
    create_admin("password-admin-lunga")
    create_account("mario", "Mario Rossi", "password-mario-lunga")
    admin = TestClient(create_app())
    person = TestClient(create_app())
    admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"})
    person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"})
    assert person.get("/api/admin/intercom/sip/accounts").status_code == 403
    assert person.get("/intercom").status_code == 200
    assert person.get("/intercom?admin=1").status_code == 403
    assert admin.get("/intercom?admin=1").status_code == 200
    assert person.get("/api/intercom/sip/credential").status_code == 409
    endpoint = "/api/admin/intercom/sip/accounts/mario"
    assert admin.post(endpoint, json={"admin_password": "wrong"}).status_code == 403
    created = admin.post(endpoint, json={"admin_password": "password-admin-lunga"})
    assert created.status_code == 200
    data = created.json()
    assert data["extension"] == "8302"
    assert data["provisioned"] is False
    assert "context=eface-test" in data["asterisk_config"]
    assert "[8301]" not in data["asterisk_config"]
    assert person.get("/api/intercom/sip/credential").status_code == 409
    listing = admin.get("/api/admin/intercom/sip/accounts")
    assert "password=" not in listing.text
    assert listing.json()["users"][0]["extension"] == "8302"
    assert admin.put(endpoint + "/provisioned", json={"provisioned": True}).status_code == 200
    credential = person.get("/api/intercom/sip/credential")
    assert credential.status_code == 200
    assert credential.json()["username"] == "8302"
    assert len(credential.json()["password"]) >= 40
    assert credential.headers["cache-control"] == "no-store, private"
    assert admin.post(endpoint, json={"admin_password": "password-admin-lunga"}).json()["asterisk_config"] == data["asterisk_config"]


def test_admin_doorbird_check_uses_stored_credential_without_exposing_it(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    from app.user_auth import create_admin
    from app import credential_inventory, doorbird_api
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/admin/intercom/doorbird/check").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert client.post("/api/admin/intercom/doorbird/check").status_code == 409
    credential_inventory.save("doorbird", "doorbird-admin", "doorbird-secret")
    calls = []

    async def fake_check(host, port, username, password):
        calls.append((host, port, username, password))
        return {"reachable": True, "authenticated": True, "reason": "ok"}

    monkeypatch.setattr(doorbird_api, "check_identity", fake_check)
    response = client.post("/api/admin/intercom/doorbird/check")
    assert response.json() == {"reachable": True, "authenticated": True, "reason": "ok"}
    assert response.headers["cache-control"] == "no-store, private"
    assert "doorbird-secret" not in response.text
    assert calls == [("192.168.2.30", 80, "doorbird-admin", "doorbird-secret")]


def test_doorbird_image_requires_login_and_keeps_credential_server_side(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    from app.user_auth import create_admin
    from app import credential_inventory, doorbird_api
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    endpoint = "/api/intercom/doorbird/image"
    assert client.get(endpoint).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert client.get(endpoint).status_code == 409
    credential_inventory.save("doorbird", "doorbird-admin", "doorbird-secret")
    calls = []

    async def fake_image(host, port, username, password):
        calls.append((host, port, username, password))
        return b"\xff\xd8\xffimage"

    monkeypatch.setattr(doorbird_api, "live_image", fake_image)
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.content == b"\xff\xd8\xffimage"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store, private"
    assert "doorbird-secret" not in str(response.headers)
    assert calls == [("192.168.2.30", 80, "doorbird-admin", "doorbird-secret")]

    async def no_permission(*_):
        return None

    monkeypatch.setattr(doorbird_api, "live_image", no_permission)
    assert client.get(endpoint).status_code == 204


def test_doorbird_video_proxy_requires_login_and_streams_without_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    from app.user_auth import create_admin
    from app import credential_inventory, doorbird_api
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    endpoint = "/api/intercom/doorbird/video"
    assert client.get(endpoint).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert client.get(endpoint).status_code == 409
    credential_inventory.save("doorbird", "doorbird-admin", "doorbird-secret")
    calls = []
    closed = []

    class FakeClient:
        async def aclose(self):
            closed.append("client")

    class FakeUpstream:
        async def aiter_raw(self):
            yield b"--my-boundary\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\xff"

        async def aclose(self):
            closed.append("upstream")

    async def fake_video(host, port, username, password):
        calls.append((host, port, username, password))
        return FakeClient(), FakeUpstream(), "multipart/x-mixed-replace; boundary=my-boundary"

    monkeypatch.setattr(doorbird_api, "live_video", fake_video)
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert response.headers["cache-control"] == "no-store, private"
    assert b"\xff\xd8\xff" in response.content
    assert "doorbird-secret" not in str(response.headers)
    assert calls == [("192.168.2.30", 80, "doorbird-admin", "doorbird-secret")]
    assert closed == ["upstream", "client"]


def test_intercom_test_phone_requires_admin_and_same_origin(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_INTERCOM_TURN_SETTINGS", str(tmp_path / "turn.json"))
    from app.user_auth import create_admin
    create_admin("password-admin-lunga")
    admin = TestClient(create_app())
    person = TestClient(create_app())
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert admin.post("/api/admin/users", json={"username": "mario", "name": "Mario", "password": "password-mario-lunga"}).status_code == 200
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"}).status_code == 200
    assert person.get("/intercom").status_code == 200
    assert "Postazione SIP" in admin.get("/intercom").text
    assert 'id="fast-ice"' in admin.get("/intercom").text
    assert 'id="speaker-gain"' in admin.get("/intercom").text
    assert 'id="microphone-gain"' in admin.get("/intercom").text
    assert admin.get("/assets/intercom.js").status_code == 200
    assert "pcConfig:peerConfig()" in admin.get("/assets/intercom.js").text
    assert admin.get("/api/intercom/ice").json() == {"iceServers": []}
    assert person.get("/api/intercom/ice").status_code == 200
    turn = {"turn_url": "turn:169.58.200.54:3478?transport=udp", "turn_username": "eface", "turn_password": "test-secret"}
    assert admin.put("/api/admin/intercom/turn", json=turn).status_code == 200
    assert "turn_password" not in admin.get("/api/admin/intercom").text
    assert admin.get("/api/intercom/ice").json()["iceServers"][0]["credential"] == "test-secret"
    assert admin.put("/api/admin/intercom/turn", json={**turn, "turn_url": "https://bad.example"}).status_code == 400
    assert "session.on('icecandidate'" in admin.get("/assets/intercom.js").text
    assert "createMediaStreamDestination" in admin.get("/assets/intercom.js").text
    assert admin.get("/assets/jssip-3.13.8.js").status_code == 200
    with pytest.raises(WebSocketDisconnect) as denied:
        with TestClient(create_app()).websocket_connect("/api/intercom/sip", headers={"origin": "http://testserver"}, subprotocols=["sip"]):
            pass
    assert denied.value.code == 1008
    with pytest.raises(WebSocketDisconnect) as denied:
        with admin.websocket_connect("/api/intercom/sip", headers={"origin": "https://evil.example"}, subprotocols=["sip"]):
            pass
    assert denied.value.code == 1008


def test_installation_preflight_is_admin_only_and_read_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_INTERCOM_TURN_SETTINGS", str(tmp_path / "turn.json"))
    from app import installation, intercom_settings
    from app.user_auth import create_admin

    create_admin("password-admin-lunga")
    intercom_settings.save_turn({"turn_url": "turn:169.58.200.54:3478?transport=udp", "turn_username": "eface", "turn_password": "test-secret"})

    async def reachable(_host, _port):
        return True

    monkeypatch.setattr(installation, "_tcp_reachable", reachable)
    monkeypatch.setattr(installation, "_stun_binding", lambda host, port: host == "169.58.200.54" and port == 3478)
    client = TestClient(create_app())
    assert client.get("/api/admin/installation/preflight").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    result = client.get("/api/admin/installation/preflight").json()
    assert result["asterisk_tcp"] is True
    assert result["doorbird_tcp"] is True
    assert result["turn_udp"] is True
    assert result["provisioning_available"] is False
    assert "test-secret" not in str(result)


def test_admin_credential_inventory_requires_reauth_to_reveal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CREDENTIAL_INVENTORY", str(tmp_path / "inventory.json"))
    monkeypatch.setenv("EFACE_INTERCOM_TURN_SETTINGS", str(tmp_path / "turn.json"))
    monkeypatch.setenv("EFACE_CONTROL4_CONFIG", str(tmp_path / "control4.json"))
    from app import intercom_settings
    from app.control4 import save_control4_config
    from app.user_auth import create_admin

    create_admin("password-admin-lunga")
    intercom_settings.save_turn({"turn_url": "turn:169.58.200.54:3478?transport=udp", "turn_username": "eface", "turn_password": "turn-secret"})
    save_control4_config({"host": "192.168.3.10", "username": "installer@example.test", "password": "c4-secret"})
    admin = TestClient(create_app())
    assert admin.get("/api/admin/credentials").status_code == 401
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200

    overview = admin.get("/api/admin/credentials")
    assert overview.status_code == 200
    assert overview.headers["cache-control"] == "no-store, private"
    assert "turn-secret" not in overview.text
    assert "c4-secret" not in overview.text
    assert "sip_eface" in overview.text
    assert admin.post("/api/admin/credentials/turn/reveal", json={"admin_password": "wrong"}).status_code == 403
    revealed = admin.post("/api/admin/credentials/turn/reveal", json={"admin_password": "password-admin-lunga"})
    assert revealed.json() == {"password": "turn-secret"}
    assert revealed.headers["cache-control"] == "no-store, private"
    assert admin.post("/api/admin/credentials/eface_admin/reveal", json={"admin_password": "password-admin-lunga"}).status_code == 400

    assert admin.put("/api/admin/credentials/sip_eface", json={"username": "8301", "password": "sip-secret"}).status_code == 400
    saved = admin.put("/api/admin/credentials/sip_eface", json={"username": "8301", "password": "sip-secret", "confirmed": True})
    assert saved.json() == {"configured": True, "synchronized": False}
    assert "sip-secret" not in admin.get("/api/admin/credentials").text
    assert admin.post("/api/admin/credentials/sip_eface/reveal", json={"admin_password": "password-admin-lunga"}).json() == {"password": "sip-secret"}
    assert admin.put("/api/admin/credentials/unknown", json={"username": "x", "password": "y", "confirmed": True}).status_code == 400
    assert admin.delete("/api/admin/credentials/sip_eface").json() == {"removed": True, "device_changed": False}
    assert admin.post("/api/admin/credentials/sip_eface/reveal", json={"admin_password": "password-admin-lunga"}).status_code == 404
    assert admin.post("/api/admin/users", json={"username": "mario", "name": "Mario", "password": "password-mario-lunga"}).status_code == 200
    person = TestClient(create_app())
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"}).status_code == 200
    assert person.get("/api/admin/credentials").status_code == 403
    assert person.post("/api/admin/credentials/turn/reveal", json={"admin_password": "password-admin-lunga"}).status_code == 403
    for _ in range(5):
        assert admin.post("/api/admin/credentials/control4/reveal", json={"admin_password": "wrong"}).status_code == 403
    assert admin.post("/api/admin/credentials/control4/reveal", json={"admin_password": "password-admin-lunga"}).status_code == 429


def test_install_brand_and_theme_are_consistent() -> None:
    from pathlib import Path
    import hashlib
    root = Path(__file__).parents[1]
    icon = root / "icon.png"
    brand = root / "app/static/assets/brand-icon.png"
    assert hashlib.sha256(icon.read_bytes()).digest() == hashlib.sha256(brand.read_bytes()).digest()
    assert hashlib.sha256((root / "logo.png").read_bytes()).digest() == hashlib.sha256(icon.read_bytes()).digest()
    client = TestClient(create_app())
    manifest = client.get("/assets/manifest.webmanifest").json()
    assert manifest["theme_color"] == "#000000"
    assert manifest["background_color"] == "#000000"
    assert manifest["icons"][0]["src"] == "eface-x4-app-icon.png"
    assert "eface-x4-app-icon.png" in client.get("/").text
    assert "manifest.webmanifest?v=2.21.59" in client.get("/").text
    assert client.get("/assets/eface-x4-app-icon.png").content == icon.read_bytes()
    assert 'rel="manifest"' in client.get("/login").text


def test_tools_page_starts_with_selected_background_and_card_theme(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_BACKGROUNDS", str(tmp_path / "backgrounds"))
    save_preset("midnight")
    save_card_theme("slate")
    page = TestClient(create_app()).get("/tools").text
    assert 'style="background:var(--tools-background,#181c1f);--tools-background:radial-gradient(circle at 70% 20%,#263f61,#08121e 65%)"' in page
    assert '<body class="tools-theme" data-background="midnight" data-card-theme="slate">' in page
    assert "__TOOLS_BACKGROUND__" not in page

    client = TestClient(create_app())
    home = client.get("/").text
    login = client.get("/login").text
    assert '<body class="app-theme" data-background="midnight" data-card-theme="slate">' in home
    assert 'ui-theme-contract.css?v=2.21.29' in home
    assert 'app.js?v=2.21.87' in home
    assert 'energy.css?v=2.21.30' in home
    assert 'home-comfort.css?v=2.21.31' in home
    assert '<body class="login-theme" data-background="midnight" data-card-theme="slate">' in login
    assert "__INITIAL_BACKGROUND__" not in home + login


def test_user_appearance_persists_room_order_and_glow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_BACKGROUNDS", str(tmp_path / "backgrounds"))
    client = TestClient(create_app())
    assert client.get("/api/user/appearance").json() == {"card_glow": True, "room_order": [], "security_order": ["scenarios", "areas", "zones", "locks"]}
    response = client.put("/api/user/appearance", json={"card_glow": False, "room_order": ["Sala", "Ufficio Alex"], "security_order": ["locks", "zones", "areas", "scenarios"]})
    assert response.status_code == 200
    assert client.get("/api/user/appearance").json() == {"card_glow": False, "room_order": ["Sala", "Ufficio Alex"], "security_order": ["locks", "zones", "areas", "scenarios"]}
    assert client.put("/api/user/appearance", json={"room_order": ["Sala", "sala"]}).status_code == 400
    assert client.put("/api/user/appearance", json={"card_glow": "false"}).status_code == 400
    assert client.put("/api/user/appearance", json={"security_order": ["locks", "zones", "zones", "scenarios"]}).status_code == 400
    assert client.put("/api/user/appearance", json={"security_order": [{}, "zones", "areas", "scenarios"]}).status_code == 400


def test_ksenia_normalizes_partitions_and_zones() -> None:
    items = normalize_ksenia({"entities": [
        {"type": "partitions", "id": 1, "name": "Casa", "realtime": {"ARM": "IA"}},
        {"type": "zones", "id": 7, "name": "Porta", "static": {"PRT": "1"}, "realtime": {"STA": "A", "BYP": "NO"}},
        {"type": "scenarios", "id": 2, "name": "Away", "static": {"CAT": "ARM", "PIN": "P"}, "realtime": {}},
        {"type": "systems", "id": 1, "static": {"ARM": {"D": "DISINSERITO", "S": "D"}}, "realtime": {"ARM": {"D": "SOLO ESTERNO", "S": "P"}}},
    ]})
    assert items[0]["id"] == "ksenia-partition:1"
    assert items[0]["state"] == "ARMED"
    assert items[1]["id"] == "ksenia-zone:7"
    assert items[1]["state"] == "ACTIVE"
    assert items[1]["sensor_type"] == "door"
    assert items[1]["room"] == ""
    assert items[2]["id"] == "ksenia-scenario:2"
    assert items[2]["category"] == "ARM"
    assert items[3]["arm_description"] == "SOLO ESTERNO"
    assert items[3]["arm_status"] == "P"


def test_ksenia_total_arms_unique_away_scenario_only() -> None:
    scenarios = [
        {"type": "scenarios", "id": 2, "name": "Away", "static": {"CAT": "ARM"}},
        {"type": "scenarios", "id": 3, "name": "A Fumare", "static": {"CAT": "PARTIAL"}},
    ]
    def active(description: str, status: str, entries: list[dict] = scenarios) -> str | None:
        items = normalize_ksenia({"entities": [*entries, {"type": "systems", "id": 1, "realtime": {"ARM": {"D": description, "S": status}}}]})
        return next(item for item in items if item["kind"] == "alarm_system")["active_scenario_id"]
    assert active("Inserito totale", "T") == "ksenia-scenario:2"
    assert active("Totale", "T_OUT") == "ksenia-scenario:2"
    assert active("A Fumare", "P") == "ksenia-scenario:3"
    assert active("Modalità personalizzata", "T") is None
    assert active("Inserito totale", "P") is None
    assert active("Inserito totale", "T", scenarios + [scenarios[0]]) is None


def test_alarm_and_room_media_navigation_are_present() -> None:
    script = TestClient(create_app()).get("/assets/app.js").text
    assert "renderSecurityDevices" in script
    assert "ksenia-partition" not in script
    assert "card?.classList.contains('media-player-card')" in script
    assert "event.type === 'ksenia_state'" in script
    assert "system?.arm_description" in script
    assert "security-lock-${stateClass}" in script


def test_ksenia_alarm_memory_is_not_an_active_alarm() -> None:
    items = normalize_ksenia({"entities": [
        {"type": "partitions", "id": 2, "name": "Centrale", "realtime": {"ARM": "D", "AST": "AM", "TST": "OK"}},
        {"type": "zones", "id": 56, "name": "Camera", "realtime": {"STA": "R", "T": "M", "BYP": "NO"}},
    ]})
    assert items[0]["state"] == "DISARMED"
    assert items[0]["alarm"] is False
    assert items[0]["alarm_memory"] is True
    assert items[1]["state"] == "CLOSED"
    assert items[1]["tamper"] is False
    assert items[1]["memory"] is True


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
    assert "status-strip" not in page.text
    assert "now-playing" not in page.text
    assert 'id="detail-view"' in page.text
    assert 'id="detail-back"' in page.text
    assert page.text.count('<dialog') == 7
    assert 'id="media-browser-dialog"' not in page.text
    assert 'id="security-area-dialog"' in page.text
    assert 'id="security-pin-dialog"' in page.text
    assert 'id="rgb-dialog"' in page.text
    assert 'id="show-all-devices"' in page.text
    assert 'id="scenario-panel"' in page.text
    assert 'id="scenario-list"' in page.text
    assert 'id="energy-view"' in page.text
    assert 'id="energy-picker"' in page.text
    assert 'id="energy-frame"' in page.text
    assert 'class="energy-frame"' in page.text
    assert 'scrolling="no"' in page.text
    assert 'energy-picker-intro' not in page.text
    assert 'data-view="energy"' in page.text
    assert 'card-themes.css' in page.text
    assert 'header-media-state.css' in page.text
    assert 'mobile-alignment.css' in page.text
    assert 'refresh-state.css' in page.text
    assert 'evoice.css' in page.text
    for label in ("Guarda", "Ascolta", "Luci", "Extra", "Scenari", "Oscuranti", "Comfort", "Sicurezza"):
        assert f'title="{label}"' in page.text
    assert 'src="assets/brand-horizontal.png?v=2.20.20"' in page.text
    assert 'id="startup-splash"' in page.text
    assert 'data-duration-ms="0"' in page.text
    assert 'style="display:none"' in page.text
    assert 'src="assets/startup-splash.png?v=2.20.20"' in page.text
    assert client.get("/assets/splash.css").status_code == 200
    assert "--splash-shift-x:1.6vw" in client.get("/assets/splash.css").text
    assert client.get("/assets/startup-splash.png").status_code == 200
    assert 'alt="e-Face X4"' in page.text
    assert 'class="header-wordmark"' not in page.text
    assert client.get("/assets/brand-horizontal.png").status_code == 200
    assert client.get("/assets/brand-icon.png").status_code == 200
    assert client.get("/assets/app.css").status_code == 200
    assert client.get("/assets/media.css").status_code == 200
    assert client.get("/assets/media-x4.css").status_code == 200
    assert client.get("/assets/media-remote-colors.css").status_code == 200
    refresh_css = client.get("/assets/refresh-state.css")
    assert refresh_css.status_code == 200
    assert ".app.loading" in refresh_css.text
    assert "body:not([data-background])" in refresh_css.text


    assert client.get("/assets/evoice.css").status_code == 200
    assert "grid-column:1/-1" in client.get("/assets/evoice.css").text
    assert "repeat(auto-fit,minmax(210px,1fr))" in client.get("/assets/evoice.css").text
    tools_page = client.get("/tools")
    assert "evoice-admin.css" in tools_page.text
    assert "e-Voice / Multimedia" in tools_page.text
    card_theme_css = client.get("/assets/card-themes.css")
    assert card_theme_css.status_code == 200
    assert ".security-pin-dialog" in card_theme_css.text
    assert ".media-zones-dialog" in card_theme_css.text
    assert ".video-remote-dialog" in card_theme_css.text
    assert ".home-overview-summary" in card_theme_css.text
    assert ".remote-volume-side" in card_theme_css.text
    assert "SESSIONE AUDIO/VIDEO" not in page.text
    assert client.get("/assets/borderless.css").status_code == 200
    assert client.get("/assets/tools-global-background.css").status_code == 200
    assert client.get("/assets/header-responsive.css").status_code == 200
    assert client.get("/assets/home-rooms.css").status_code == 200
    assert client.get("/assets/device-icons.css").status_code == 200
    assert client.get("/assets/home-status.css").status_code == 200
    assert client.get("/assets/home-live-media.css").status_code == 200
    assert client.get("/assets/media-session-power.css").status_code == 200
    assert client.get("/assets/home-comfort.css").status_code == 200
    assert client.get("/assets/control4-icons/thermostat.svg").status_code == 200
    app_js = client.get("/assets/app.js").text
    assert "let activeBackgroundRoom = ''" in app_js
    assert "function applyBackground(room = activeBackgroundRoom)" in app_js
    assert "function roomFeatureIcons(roomName)" in app_js
    assert "function mediaSourceMarkup(source, provider = '')" in app_js
    assert 'data-climate-season="WIN"' in app_js
    assert 'data-climate-mode="OFF"' in app_js
    assert "function renderHomeMediaSessions()" in app_js
    assert "function renderHomeStatusCounters()" in app_js
    assert "function renderHomeComfort()" in app_js
    assert "mdi:coolant-temperature" in app_js
    assert "comfort-heating" in app_js
    assert "comfort-cooling" in app_js
    assert "function updateEnergyMasterIcon(flows)" in app_js
    assert "linear-gradient(90deg," in app_js
    assert "{ kind: 'comfort', label: 'Comfort'" not in app_js
    assert "grid-template-columns:repeat(4" in client.get("/assets/home-status.css").text
    assert "event.target !== dialog" in app_js
    assert client.get("/tools").status_code == 200
    assert "Amministrazione" in client.get("/tools").text
    css = client.get("/assets/app.css").text
    assert ".layout>main,.detail-view,.scenario-panel,.scenario-list{min-width:0;max-width:100%}" in css
    assert ".scenario-list{display:grid" in css
    assert "@media(min-width:701px) and (max-width:1024px)" in css
    assert ".scenario-list{grid-template-columns:1fr}" in css


def test_startup_splash_is_admin_configurable_and_persistent(monkeypatch, tmp_path) -> None:
    from app import startup_settings
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_STARTUP_CONFIG", str(tmp_path / "startup.json"))
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    assert startup_settings.load() == {"enabled": False, "duration_ms": 5000}
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    response = client.put("/api/admin/startup", json={"enabled": True, "duration_ms": 3500})
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "duration_ms": 3500}
    page = client.get("/").text
    assert 'data-duration-ms="3500"' in page
    assert 'style=""' in page
    assert startup_settings.load() == {"enabled": True, "duration_ms": 3500}
    assert client.put("/api/admin/startup", json={"enabled": True, "duration_ms": 100}).status_code == 400


def test_startup_admin_controls_are_present() -> None:
    client = TestClient(create_app())
    page = client.get("/tools").text
    script = client.get("/assets/tools-dashboard.js").text
    assert 'id="startup-tool"' in page
    assert 'id="startup-enabled"' in page
    assert 'id="startup-duration"' in page
    assert "api/admin/startup" in script


def test_media_preferences_are_saved_and_applied(monkeypatch, tmp_path) -> None:
    path = tmp_path / "media_players.json"
    monkeypatch.setenv("EFACE_MEDIA_PREFERENCES", str(path))
    saved = save_preferences({"one": {"visible": True, "audio": True, "video": False, "tts": True, "name": "Echo Sala", "room": "Sala", "order": 1}, "two": {"visible": True, "audio": True, "order": 0}}, {"one", "two"})
    assert load_preferences() == saved
    filtered = apply_preferences({"items": [
        {"registry_id": "one", "room": "Sala", "experiences": ["watch"], "provider": "evoice", "tts_available": True},
        {"registry_id": "two", "room": "Studio", "experiences": ["listen"]},
        {"registry_id": "three", "room": "Altro", "experiences": ["listen"]},
    ], "groups": [], "rooms": []})
    assert [item["registry_id"] for item in filtered["items"]] == ["two", "one"]
    assert filtered["items"][1]["experiences"] == ["listen"]
    assert filtered["items"][1]["name"] == "Echo Sala"
    assert filtered["items"][1]["room"] == "Sala"
    assert filtered["items"][1]["tts_enabled"] is True
    assert filtered["rooms"] == ["Sala", "Studio"]


def test_player_without_enabled_functions_is_saved_as_hidden(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_MEDIA_PREFERENCES", str(tmp_path / "media_players.json"))
    saved = save_preferences({"one": {"visible": True, "audio": False, "video": False, "tts": False}}, {"one"})
    assert saved["one"]["visible"] is False


def test_installer_login_is_protected(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text('{"installer_password":"segreta"}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setenv("EFACE_INSTALLER_SECRET", str(tmp_path / "secret"))
    client = TestClient(create_app())
    assert client.get("/api/installer/media-players").status_code == 401
    assert client.get("/api/installer/media-source-icons").status_code == 401
    assert client.post("/api/installer/login", json={"password": "errata"}).status_code == 401
    response = client.post("/api/installer/login", json={"password": "segreta"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()


def test_custom_source_icon_is_persisted_and_removed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_SOURCE_ICONS", str(tmp_path / "source-icons"))
    content = b"\x89PNG\r\n\x1a\n" + b"persistent-icon"
    import base64
    save_source_icon(244, "image/png", base64.b64encode(content).decode())
    assert load_source_icon(244) == ("image/png", content)
    assert (tmp_path / "source-icons" / "244.png").is_file()
    assert delete_source_icon(244) is True
    assert load_source_icon(244) is None


def test_hidden_media_sources_survive_reload(monkeypatch, tmp_path) -> None:
    from app.source_icons import hidden_source_ids, set_source_hidden
    monkeypatch.setenv("EFACE_SOURCE_ICONS", str(tmp_path / "source-icons"))
    assert set_source_hidden(244, True) == {244}
    assert hidden_source_ids() == {244}
    assert (tmp_path / "source-icons" / "hidden.json").read_text(encoding="utf-8") == "[244]"
    assert set_source_hidden(244, False) == set()
    assert hidden_source_ids() == set()


def test_builtin_control4_source_icons_are_packaged() -> None:
    for label in ("Sonos", "Stations", "VIDAA", "Apps", "DLNA", "Spotify Connect", "Manage Music", "Digital Media", "AM/FM Tuner", "Wireless Music Bridge"):
        icon = load_builtin_source_icon(label)
        assert icon is not None
        assert icon[0] == "image/png"
        assert icon[1].startswith(b"\x89PNG\r\n\x1a\n")
    assert load_builtin_source_icon("Sorgente sconosciuta") is None
    assert load_builtin_source_icon("Sonos Rack Audio Sonos") is not None


def test_imported_control4_source_icons_are_packaged_by_id() -> None:
    expected_ids = {
        22, 24, 210, 586, 592, 593, 599, 605, 615, 791, 803, 809, 1319,
        1455, 1528, 1567, 1569, 1578, 1579, 1642, 1644, 1646, 1648, 1650,
        1652, 1654, 1658, 1660, 1662, 1667, 100002,
    }
    for source_id in expected_ids:
        icon = load_builtin_source_icon_by_id(source_id)
        assert icon is not None
        assert icon[0] == "image/png"
        assert icon[1].startswith(b"\x89PNG\r\n\x1a\n")
    assert load_builtin_source_icon_by_id(244) is None


def test_backgrounds_are_persistent_globally_and_per_room(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_BACKGROUNDS", str(tmp_path / "backgrounds"))
    save_preset("midnight")
    save_preset("warm", "Sala")
    assert load_background() == {"mode": "preset", "preset": "midnight"}
    assert load_background("Sala") == {"mode": "preset", "preset": "warm"}
    content = b"\x89PNG\r\n\x1a\n" + b"room-background"
    import base64
    save_background_image("image/png", base64.b64encode(content).decode(), "Ufficio Alex")
    assert load_background_image("Ufficio Alex") == ("image/png", content)
    assert load_backgrounds()["rooms"]["Ufficio Alex"]["mode"] == "custom"
    save_inherit("Sala")
    assert load_background("Sala")["mode"] == "inherit"


def test_control4_credentials_are_local_and_never_returned(monkeypatch, tmp_path) -> None:
    path = tmp_path / "control4.json"
    monkeypatch.setenv("EFACE_CONTROL4_CONFIG", str(path))
    save_control4_config({"host": "192.168.3.10", "username": "user@example.com", "password": "secret"})
    assert load_control4_config()["password"] == "secret"
    public = public_control4_config()
    assert public == {"host": "192.168.3.10", "username": "user@example.com", "artwork_hosts": "", "password_configured": True}
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
            {"key": "watch:809", "label": "Samsung TV", "experience": "watch", "type": "", "source_id": 809, "icon": "mdi:play-box", "remote_actions": []},
            {"key": "listen:100002", "label": "Spotify Connect", "experience": "listen", "type": "", "source_id": 100002, "icon": "mdi:play-box", "remote_actions": []},
    ]
    assert player["capabilities"]["turn_off"] is True
    assert player["active_experience"] == "listen"


def test_control4_native_icon_path_is_strictly_validated() -> None:
    item = {"capabilities": {"navigator_display_option": {"display_icons": {"Icon": [
        {"width": 300, "$t": "controller://driver/sky/icons/device/experience_300.png"},
        {"width": 140, "$t": "controller://driver/sky/icons/device/experience_140.png"},
    ]}}}}
    assert control4_icon_path(item) == "/driver/sky/icons/device/experience_140.png"
    assert control4_icon_path({"capabilities": {"navigator_display_option": {"display_icons": {"Icon": {"$t": "https://example.test/evil.png"}}}}}) is None
    assert control4_icon_path({"capabilities": {"navigator_display_option": {"display_icons": ""}}}) is None


def test_control4_remote_uses_only_commands_exposed_by_the_device() -> None:
    item = {"id": 244, "protocolId": 243, "protocolFilename": "driverworks_ip_uk_sky.c4z", "commands": {"command": [
        {"id": 2}, {"id": 9}, {"id": 10}, {"id": 14},
    ]}}
    actions = control4_remote_actions(item)
    assert {"play", "menu", "up", "enter", "custom:PROGRAM_A"}.issubset(actions)
    assert "guide" not in actions
    named = control4_remote_actions({"id": 807, "commands": {"command": [{"name": "PLAY"}, {"name": "LEFT"}]}})
    assert named == ["play", "left"]


def test_control4_empty_queue_payload_is_accepted() -> None:
    assert control4_queues({"queues": ""}) == []
    assert control4_queues({"queues": None}) == []


def test_control4_unknown_volume_disables_volume_control() -> None:
    players = normalize_control4_media(
        {"experiences": [{"type": "listen", "room_id": 7, "sources": {"source": []}}]},
        [{"id": 7, "name": "Esterno"}],
        [{"id": 7, "varName": "CURRENT_VOLUME", "value": -1}],
    )
    assert players[0]["volume"] is None
    assert players[0]["capabilities"]["set_volume"] is False


def test_control4_active_video_room_is_a_media_session() -> None:
    players = normalize_control4_media(
        {"experiences": [
            {"type": "watch", "room_id": 61, "sources": {"source": [{"id": 244, "name": "Sky Q"}]}},
            {"type": "listen", "room_id": 61, "sources": {"source": []}},
        ]},
        [{"id": 61, "name": "Sala"}],
        [
            {"id": 61, "varName": "POWER_STATE", "value": 1},
            {"id": 61, "varName": "CURRENT_SELECTED_DEVICE", "value": 244},
            {"id": 61, "varName": "CURRENT_AUDIO_DEVICE", "value": 244},
            {"id": 61, "varName": "CURRENT_VIDEO_DEVICE", "value": 0},
            {"id": 61, "varName": "PLAYING_AUDIO_DEVICE", "value": 1569},
            {"id": 61, "varName": "CURRENT MEDIA INFO", "value": {"mediainfo": {"mediatype": "BROADCAST_VIDEO"}}},
        ],
    )
    assert players[0]["state"] == "playing"
    assert players[0]["source"] == "Sky Q"
    assert players[0]["capabilities"]["grouping"] is True
    assert players[0]["active_experience"] == "watch"


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


@pytest.mark.asyncio
async def test_control4_cover_follows_only_trusted_image_redirects(monkeypatch) -> None:
    import httpx
    from app.connectors import control4_media

    url = "http://127.0.0.1/redirect-cover"
    fingerprint = "fingerprint-test"
    control4_media._artwork_urls["c4room:51"] = (fingerprint, url)
    # The initial host must be trusted too; a source outside the allowlist is rejected.
    assert (await Control4MediaConnector({}).artwork("c4room:51", fingerprint)).status_code == 415

    control4_media._artwork_urls["c4room:51"] = (fingerprint, "https://cdn-profiles.tunein.com/start")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://cdn-profiles.tunein.com/final.jpg"})
        return httpx.Response(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(control4_media.httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    response = await Control4MediaConnector({}).artwork("c4room:51", fingerprint)
    assert response.status_code == 200
    assert len(seen) == 2

    def unsafe(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://192.168.3.10/private"})

    transport = httpx.MockTransport(unsafe)
    assert (await Control4MediaConnector({}).artwork("c4room:51", fingerprint)).status_code == 415


@pytest.mark.asyncio
async def test_control4_cover_accepts_local_media_host_only_on_controller_subnet(monkeypatch) -> None:
    import httpx
    from app.connectors import control4_media

    fingerprint = "fingerprint-local"
    control4_media._artwork_urls["c4room:51"] = (fingerprint, "http://192.168.3.36/cover.jpg")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})

    original = httpx.AsyncClient
    monkeypatch.setattr(control4_media.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    connector = Control4MediaConnector({"host": "192.168.3.10"})
    assert (await connector.artwork("c4room:51", fingerprint)).status_code == 200
    assert seen == ["http://192.168.3.36/cover.jpg"]
    for url in ("http://192.168.4.36/cover.jpg", "http://192.168.3.10/private", "http://192.168.3.36:22/private", "http://127.0.0.1/cover.jpg"):
        control4_media._artwork_urls["c4room:51"] = (fingerprint, url)
        assert (await connector.artwork("c4room:51", fingerprint)).status_code == 415
    assert len(seen) == 1
    control4_media._artwork_urls["c4room:51"] = (fingerprint, "http://192.168.3.36:8080/cover.jpg")
    assert (await connector.artwork("c4room:51", fingerprint)).status_code == 200
    control4_media._artwork_urls["c4room:51"] = (fingerprint, "http://192.168.4.36/cover.jpg")
    extra_connector = Control4MediaConnector({"host": "192.168.3.10", "artwork_hosts": "192.168.4.36"})
    assert (await extra_connector.artwork("c4room:51", fingerprint)).status_code == 200


def test_control4_cover_accepts_any_public_image_host_but_not_private_dns(monkeypatch) -> None:
    import httpx
    from app.connectors import control4_media
    from app.connectors.control4_media import _trusted_artwork_url

    assert _trusted_artwork_url(httpx.URL("https://sonosradio.imgix.net/cover.jpg"), "192.168.3.10")
    monkeypatch.setattr(control4_media.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("1.1.1.1", 443))])
    assert _trusted_artwork_url(httpx.URL("https://other.imgix.net/cover.jpg"), "192.168.3.10")
    monkeypatch.setattr(control4_media.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("192.168.3.20", 443))])
    assert not _trusted_artwork_url(httpx.URL("https://other.imgix.net/cover.jpg"), "192.168.3.10")


@pytest.mark.asyncio
async def test_control4_cover_maps_director_alias_only_to_configured_controller(monkeypatch) -> None:
    import httpx
    from app.connectors import control4_media

    fingerprint = "fingerprint-director"
    control4_media._artwork_urls["c4room:51"] = (fingerprint, "http://director:80/album-art.jpg")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})

    original = httpx.AsyncClient
    monkeypatch.setattr(control4_media.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    connector = Control4MediaConnector({"host": "192.168.3.10"})
    assert (await connector.artwork("c4room:51", fingerprint)).status_code == 200
    assert seen == ["http://192.168.3.10/album-art.jpg"]
    control4_media._artwork_urls["c4room:51"] = (fingerprint, "http://director:8080/private")
    assert (await connector.artwork("c4room:51", fingerprint)).status_code == 415
    assert len(seen) == 1



def test_control4_cover_diagnostic_uses_saved_login_without_leaking_url(monkeypatch, tmp_path) -> None:
    import httpx
    import app.main as main_module

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    from app.user_auth import create_admin
    create_admin("password-admin-lunga")
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "private", "password": "private-secret"})

    async def snapshot(self):
        return {"items": [{"provider": "control4", "state": "playing", "registry_id": "c4room:51", "room": "Ufficio Alex", "title": "Brano", "source": "Radio RapTz", "content_fingerprint": "fingerprint-test"}]}

    async def artwork(self, registry_id, fingerprint, if_none_match=None):
        return httpx.Response(415)

    monkeypatch.setattr(main_module.Control4MediaConnector, "snapshot", snapshot)
    monkeypatch.setattr(main_module.Control4MediaConnector, "artwork", artwork)
    monkeypatch.setattr(main_module.Control4MediaConnector, "artwork_host", staticmethod(lambda *args: "images.example.test"))
    client = TestClient(main_module.create_app())
    assert client.get("/api/admin/control4/artwork-diagnostic").status_code == 401
    assert client.post("/api/admin/control4/artwork-support-link").status_code == 401
    client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"})
    response = client.get("/api/admin/control4/artwork-diagnostic")
    assert response.status_code == 200
    assert response.json()["players"][0]["artwork_status"] == 415
    assert "private-secret" not in response.text
    link_response = client.post("/api/admin/control4/artwork-support-link")
    assert link_response.status_code == 200
    link = link_response.json()["path"]
    assert client.get(link).json()["players"][0]["artwork_status"] == 415
    assert client.get(link).status_code == 404
    assert "private-secret" not in link_response.text


def test_amazon_auth_link_requires_session_and_returns_event_link(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    create_admin("password-admin-lunga")
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "private", "password": "director-secret"})

    class FakeSocket:
        instance = None

        def __init__(self, host):
            self.callbacks = {}
            FakeSocket.instance = self

        def add_item_callback(self, item_id, callback):
            self.callbacks[item_id] = callback

        async def sio_connect(self, token):
            assert token == "director-token"

        async def sio_disconnect(self):
            pass

    class Director:
        async def get_all_item_info(self):
            return [{"id": 1643, "name": "Amazon Music", "proxy": "media_service"}]

        async def send_post_request(self, uri, command, params, is_async):
            assert uri == "/api/v1/items/1643/commands"
            assert command == "LUA_ACTION" and params == {"ACTION": "GetLinkForAPIAuthentication"}
            await FakeSocket.instance.callbacks[1643](1643, {"data": {"devicecommand": {"command": "UPDATE_PROPERTY", "value": "https://link.ctrl4.co/private-code"}}})
            return '{"name":"LUA_ACTION","result":"ok","seq":1}'

    async def director(config):
        return Director(), "director-token"

    monkeypatch.setattr(main_module, "control4_director", director)
    monkeypatch.setattr(main_module, "C4Websocket", FakeSocket)
    client = TestClient(main_module.create_app())
    path = "/api/control4/music/amazon/auth-link"
    assert client.post(path).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    response = client.post(path)
    assert response.status_code == 200
    assert response.json() == {"url": "https://link.ctrl4.co/private-code"}
    assert response.headers["cache-control"] == "no-store, private"
    assert "director-secret" not in response.text and "director-token" not in response.text


def test_music_account_services_lists_installed_drivers_for_user(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    create_admin("password-admin-lunga")
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "private", "password": "director-secret"})

    class Director:
        async def get_all_item_info(self):
            return [
                {"id": 1643, "name": "Amazon Music", "proxy": "media_service"},
                {"id": 1644, "name": "Amazon Music", "proxy": "media_service", "deviceOrder": 1},
                {"id": 1648, "name": "TIDAL", "proxy": "media_service"},
                {"id": 614, "name": "TuneIn", "proxy": "media_service"},
                {"id": 615, "name": "TuneIn", "proxy": "media_service", "deviceOrder": 1},
                {"id": 1569, "name": "Spotify Connect", "proxy": "media_service"},
                {"id": 4, "name": "Unknown Device", "proxy": "light"},
            ]

    async def director(config):
        return Director(), "director-token"

    monkeypatch.setattr(main_module, "control4_director", director)
    client = TestClient(main_module.create_app())
    path = "/api/control4/music/account-services"
    assert client.get(path).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"services": [
        {"name": "Amazon Music", "proxy_id": 1644, "status": "ready"},
        {"name": "Spotify Connect", "proxy_id": 1569, "status": "ready"},
        {"name": "TIDAL", "proxy_id": 1648, "status": "test"},
        {"name": "TuneIn", "proxy_id": 615, "status": "ready"},
    ]}
    assert "director-secret" not in response.text


def test_tidal_auth_link_uses_tidal_driver(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    create_admin("password-admin-lunga")
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "private", "password": "director-secret"})

    class FakeSocket:
        instance = None

        def __init__(self, host):
            self.callbacks = {}
            FakeSocket.instance = self

        def add_item_callback(self, item_id, callback):
            self.callbacks[item_id] = callback

        async def sio_connect(self, token):
            pass

        async def sio_disconnect(self):
            pass

    class Director:
        async def get_all_item_info(self):
            return [{"id": 1648, "name": "TIDAL", "proxy": "media_service"}]

        async def send_post_request(self, uri, command, params, is_async):
            assert uri == "/api/v1/items/1648/commands"
            assert command == "LUA_ACTION" and params == {"ACTION": "GetLinkForAPIAuthentication"}
            await FakeSocket.instance.callbacks[1648](1648, {"data": {"url": "https://link.ctrl4.co/tidal-private"}})
            return '{"name":"LUA_ACTION","result":"ok","seq":1}'

    async def director(config):
        return Director(), "director-token"

    monkeypatch.setattr(main_module, "control4_director", director)
    monkeypatch.setattr(main_module, "C4Websocket", FakeSocket)
    client = TestClient(main_module.create_app())
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    response = client.post("/api/control4/music/tidal/auth-link")
    assert response.status_code == 200
    assert response.json() == {"url": "https://link.ctrl4.co/tidal-private"}


def test_tunein_auth_link_uses_tunein_driver(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    create_admin("password-admin-lunga")
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"host": "192.168.3.10", "username": "private", "password": "director-secret"})

    class FakeSocket:
        instance = None

        def __init__(self, host):
            self.callbacks = {}
            FakeSocket.instance = self

        def add_item_callback(self, item_id, callback):
            self.callbacks[item_id] = callback

        async def sio_connect(self, token):
            pass

        async def sio_disconnect(self):
            pass

    class Director:
        async def get_all_item_info(self):
            return [{"id": 614, "name": "TuneIn", "proxy": "media_service"}]

        async def send_post_request(self, uri, command, params, is_async):
            assert uri == "/api/v1/items/614/commands"
            assert command == "LUA_ACTION" and params == {"ACTION": "GetLinkForAPIAuthentication"}
            await FakeSocket.instance.callbacks[614](614, {"data": {"url": "https://link.ctrl4.co/tunein-private"}})
            return '{"name":"LUA_ACTION","result":"ok","seq":1}'

    async def director(config):
        return Director(), "director-token"

    monkeypatch.setattr(main_module, "control4_director", director)
    monkeypatch.setattr(main_module, "C4Websocket", FakeSocket)
    client = TestClient(main_module.create_app())
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    response = client.post("/api/control4/music/tunein/auth-link")
    assert response.status_code == 200
    assert response.json() == {"url": "https://link.ctrl4.co/tunein-private"}


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


def test_wiim_preset_selects_control4_source_in_current_room(monkeypatch) -> None:
    import app.main as main_module

    calls = []
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})

    async def play_preset(self, index):
        calls.append(("wiim", index))

    async def command(self, registry_id, operation, value=None):
        calls.append(("control4", registry_id, operation, value))
        return {"status": "success"}

    monkeypatch.setattr(main_module.WiiMClient, "play_preset", play_preset)
    monkeypatch.setattr(main_module.Control4MediaConnector, "command", command)
    response = TestClient(main_module.create_app()).post(
        "/api/control4/favorites/select", json={"id": "wiim:preset:3", "room_id": 51}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "target": "wiim", "preset_index": 3, "room_id": 51, "control4_source_id": 1667}
    assert calls == [("wiim", 3), ("control4", "c4room:51", "select_source", "listen:1667")]


def test_wiim_preset_reports_partial_control4_failure(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})

    async def play_preset(self, index):
        return None

    async def command(self, registry_id, operation, value=None):
        raise RuntimeError("director offline")

    monkeypatch.setattr(main_module.WiiMClient, "play_preset", play_preset)
    monkeypatch.setattr(main_module.Control4MediaConnector, "command", command)
    response = TestClient(main_module.create_app()).post(
        "/api/control4/favorites/select", json={"id": "wiim:preset:2", "room_id": 51}
    )

    assert response.status_code == 502
    assert "Preset avviato sul WiiM" in response.json()["detail"]


def test_wiim_track_favorite_restores_exact_queue_item(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    calls = []
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})

    async def snapshot(self):
        return {"track_id": "tracks/abc", "title": "Titolo", "artist": "Artista", "source": "YouTubeMusic", "artwork": ""}

    async def queue(self, **kwargs):
        return {"name": "Cover e remix", "total": 50, "tracks": [{"index": 7, "track_id": "tracks/abc", "title": "Titolo", "artist": "Artista", "album": "Album", "artwork": "", "source": "YouTubeMusic"}]}

    async def presets(self):
        return [{"index": 6, "name": "Cover e remix", "source": "YouTubeMusic", "artwork": ""}]

    async def play_preset(self, index):
        calls.append(("preset", index))

    async def play_queue_index(self, index):
        calls.append(("queue", index))

    async def command(self, registry_id, operation, value=None):
        calls.append(("control4", registry_id, operation, value))
        return {"status": "success"}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(main_module.WiiMClient, "snapshot", snapshot)
    monkeypatch.setattr(main_module.WiiMClient, "queue", queue)
    monkeypatch.setattr(main_module.WiiMClient, "presets", presets)
    monkeypatch.setattr(main_module.WiiMClient, "play_preset", play_preset)
    monkeypatch.setattr(main_module.WiiMClient, "play_queue_index", play_queue_index)
    monkeypatch.setattr(main_module.Control4MediaConnector, "command", command)
    monkeypatch.setattr(main_module.asyncio, "sleep", no_sleep)
    client = TestClient(main_module.create_app())

    saved = client.post("/api/control4/favorites/current-wiim-track")
    assert saved.status_code == 200
    favorite = next(item for item in saved.json()["items"] if item["kind"] == "wiim_track")
    assert favorite["preset_index"] == 6 and favorite["track_id"] == "tracks/abc"
    assert favorite["queue_total"] == 50

    restored = client.post("/api/control4/favorites/select", json={"id": favorite["id"], "room_id": 51})
    assert restored.status_code == 200
    assert restored.json()["queue_index"] == 7
    assert restored.json()["queue_total"] == 50
    assert calls == [("preset", 6), ("control4", "c4room:51", "select_source", "listen:1667"), ("queue", 7)]


def test_wiim_track_favorite_waits_for_complete_preset_queue(monkeypatch, tmp_path) -> None:
    import app.main as main_module
    from app.media_favorites import add_favorite

    calls = []
    queue_reads = 0
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})
    add_favorite({"id": "wiim:track:6:tracks/abc", "kind": "wiim_track", "title": "Titolo", "track_id": "tracks/abc", "preset_index": 6, "preset_name": "Cover e remix", "queue_index": 1, "queue_total": 200})

    async def presets(self):
        return [{"index": 6, "name": "Cover e remix"}]

    async def play_preset(self, index):
        calls.append(("preset", index))

    async def queue(self, **kwargs):
        nonlocal queue_reads
        queue_reads += 1
        total = 1 if queue_reads == 1 else 200
        return {"name": "Cover e remix", "total": total, "tracks": [{"index": 1, "track_id": "tracks/abc"}]}

    async def play_queue_index(self, index):
        calls.append(("queue", index))

    async def command(self, registry_id, operation, value=None):
        calls.append(("control4", registry_id, operation, value))

    async def no_sleep(_):
        return None

    monkeypatch.setattr(main_module.WiiMClient, "presets", presets)
    monkeypatch.setattr(main_module.WiiMClient, "play_preset", play_preset)
    monkeypatch.setattr(main_module.WiiMClient, "queue", queue)
    monkeypatch.setattr(main_module.WiiMClient, "play_queue_index", play_queue_index)
    monkeypatch.setattr(main_module.Control4MediaConnector, "command", command)
    monkeypatch.setattr(main_module.asyncio, "sleep", no_sleep)

    response = TestClient(main_module.create_app()).post("/api/control4/favorites/select", json={"id": "wiim:track:6:tracks/abc", "room_id": 51})
    assert response.status_code == 200
    assert response.json()["queue_total"] == 200
    assert queue_reads == 2
    assert calls[-1] == ("queue", 1)


def test_linked_control4_wiim_commands_use_native_wiim_api(monkeypatch) -> None:
    import app.main as main_module

    calls = []
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"username": "configured", "password": "configured"})
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})

    async def c4_snapshot(self):
        return {"id": "control4", "status": "online", "items": [{"registry_id": "c4room:51", "active_source_id": 1667}]}

    async def player_action(self, action, value=None):
        calls.append((action, value))

    async def snapshot(self):
        return {"id": "wiim", "state": "playing", "volume": 42}

    monkeypatch.setattr(main_module.Control4MediaConnector, "snapshot", c4_snapshot)
    monkeypatch.setattr(main_module.WiiMClient, "player_action", player_action)
    monkeypatch.setattr(main_module.WiiMClient, "snapshot", snapshot)
    response = TestClient(main_module.create_app()).post("/api/devices/c4media:51/command", json={"action": "media_next"})
    assert response.status_code == 200
    assert response.json()["provider"] == "wiim"
    assert calls == [("next", None)]


def test_linked_control4_wiim_volume_stays_on_control4(monkeypatch) -> None:
    import app.main as main_module

    c4_calls = []
    wiim_calls = []
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"username": "configured", "password": "configured"})
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667})

    async def c4_command(self, device_id, operation, value=None):
        c4_calls.append((device_id, operation, value))
        return {"ok": True}

    async def player_action(self, action, value=None):
        wiim_calls.append((action, value))

    monkeypatch.setattr(main_module.Control4MediaConnector, "command", c4_command)
    monkeypatch.setattr(main_module.WiiMClient, "player_action", player_action)
    response = TestClient(main_module.create_app()).post("/api/devices/c4media:51/command", json={"action": "set_volume", "value": 55})
    assert response.status_code == 200
    assert c4_calls == [("c4room:51", "set_volume", 55)]
    assert wiim_calls == []


def test_media_master_volume_contract_is_relative_and_room_label_is_not_duplicated() -> None:
    script = (Path(__file__).resolve().parents[1] / "app" / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    assert "40/50 + 10 => 50/60" in script
    assert "postDeviceCommand(player.id, 'set_volume', level)" in script
    assert 'class="media-session-room"' not in script
    assert 'media-track media-room-name' in script
    assert "item.registry_id === group?.owner_registry_id" in script
    assert "openDevices(room, devices.length ? devices : [master]" in script


def test_wiim_preset_delete_endpoint_clears_cache(monkeypatch) -> None:
    import app.main as main_module

    calls = []
    monkeypatch.setattr(main_module.wiim_settings, "load", lambda: {"enabled": True, "host": "192.168.3.52"})

    async def delete_preset(self, index):
        calls.append(index)

    monkeypatch.setattr(main_module.WiiMClient, "delete_preset", delete_preset)
    response = TestClient(main_module.create_app()).delete("/api/wiim/presets/4")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "index": 4}
    assert calls == [4]


def test_control4_rejects_evoice_only_commands(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"demo_mode":false,"evoice":{"enabled":true}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"username": "configured", "password": "configured"})

    response = TestClient(main_module.create_app()).post("/api/devices/c4media:51/command", json={"action": "tts", "value": "Ciao"})
    assert response.status_code == 400
    assert "soltanto sui player e-Voice" in response.json()["detail"]


def test_control4_and_evoice_are_loaded_together(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"demo_mode":false,"evoice":{"enabled":true,"base_url":"http://evoice.local","installation_id":"home"}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    preferences = tmp_path / "media_players.json"
    preferences.write_text('{"echo-1":{"visible":true,"audio":true,"video":false,"tts":true,"name":"Echo Cucina","room":"Cucina nuova","order":0}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_MEDIA_PREFERENCES", str(preferences))
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {"username": "configured", "password": "configured"})

    async def c4_snapshot(self):
        return {"id": "control4", "status": "online", "items": [{"id": "c4media:1", "registry_id": "c4room:1", "provider": "control4", "kind": "media_player", "name": "Sala", "room": "Sala"}], "groups": [], "rooms": ["Sala"]}

    async def evoice_snapshot(self):
        return {"id": "evoice", "status": "online", "items": [{"id": "media:echo-1", "registry_id": "echo-1", "kind": "media_player", "name": "Echo", "room": "Cucina", "tts_available": True}], "groups": [], "rooms": ["Cucina"]}

    async def ksenia_snapshot(self):
        return {"id": "ksenia", "status": "online", "items": [{"id": "ksenia-zone:1", "kind": "alarm_zone", "name": "Sensore senza stanza", "room": ""}]}

    monkeypatch.setattr(main_module.Control4MediaConnector, "snapshot", c4_snapshot)
    monkeypatch.setattr(main_module.EkonexMediaConnector, "snapshot", evoice_snapshot)
    monkeypatch.setattr(main_module.KseniaConnector, "snapshot", ksenia_snapshot)
    payload = TestClient(main_module.create_app()).get("/api/bootstrap").json()
    assert {provider["id"] for provider in payload["providers"]} >= {"control4", "evoice"}
    assert {item["id"] for item in payload["dashboard"]["devices"]} >= {"c4media:1", "media:echo-1"}
    assert "Cucina" not in {room["name"] for room in payload["dashboard"]["rooms"]}
    assert "Sala" in {room["name"] for room in payload["dashboard"]["rooms"]}
    assert "Cucina nuova" in {room["name"] for room in payload["dashboard"]["rooms"]}
    assert "Clima" not in {room["name"] for room in payload["dashboard"]["rooms"]}


def test_evoice_local_api_requires_supervisor_token(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"demo_mode":false,"evoice":{"enabled":true,"base_url":"","token":"","installation_id":""}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {})

    payload = TestClient(main_module.create_app()).get("/api/bootstrap").json()
    provider = next(item for item in payload["providers"] if item["id"] == "evoice")
    assert provider["status"] == "misconfigured"
    assert provider["items"] == []


def test_evoice_local_api_uses_supervisor_proxy(monkeypatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    connector = EvoiceLocalMediaConnector(4)
    assert connector.timeout == 15.0
    assert connector._url("/snapshot") == "http://supervisor/core/api/evoice/media/snapshot"
    assert connector.headers() == {"Authorization": "Bearer supervisor-secret"}


def test_evoice_local_snapshot_uses_recent_cache_after_transient_timeout(monkeypatch) -> None:
    import asyncio
    import httpx
    from app.connectors import media as media_module

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"players": [{"registry_id": "echo-1", "name": "Echo", "is_echo": True}]}

    class Client:
        calls = 0

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            Client.calls += 1
            if Client.calls > 1:
                raise httpx.ReadTimeout("temporaneo")
            return Response()

    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.setattr(media_module.httpx, "AsyncClient", Client)
    media_module._LOCAL_SNAPSHOT_CACHE = None
    media_module._LOCAL_SNAPSHOT_CACHED_AT = 0.0
    connector = EvoiceLocalMediaConnector(4)
    assert asyncio.run(connector.snapshot())["status"] == "online"
    cached = asyncio.run(connector.snapshot())
    assert cached["status"] == "stale"
    assert cached["reason"] == "ReadTimeout"
    assert cached["items"][0]["registry_id"] == "echo-1"


def test_bootstrap_keeps_stale_evoice_players(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"demo_mode":false,"evoice":{"enabled":true}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    monkeypatch.setattr(main_module, "load_control4_config", lambda: {})

    async def stale_snapshot(self):
        return {"id": "evoice", "label": "Ekonex Voice locale", "status": "stale", "items": [{
            "id": "media:echo-1", "registry_id": "echo-1", "provider": "evoice",
            "kind": "media_player", "name": "Echo", "room": "Studio",
        }]}

    monkeypatch.setattr(main_module.EvoiceLocalMediaConnector, "snapshot", stale_snapshot)
    payload = TestClient(main_module.create_app()).get("/api/bootstrap").json()
    assert any(item["id"] == "media:echo-1" for item in payload["dashboard"]["devices"])


def test_ksenia_security_command_requires_central_pin(monkeypatch, tmp_path) -> None:
    import app.main as main_module

    options = tmp_path / "options.json"
    options.write_text('{"ksenia":{"enabled":true,"base_url":"http://127.0.0.1:18888","token":""}}', encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    response = TestClient(main_module.create_app()).post(
        "/api/devices/ksenia-partition:1/command", json={"action": "arm_delay"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Inserisci il codice di sicurezza"


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


def test_buspro_lock_battery_comes_from_hdl_metrics() -> None:
    normalized = normalize_snapshot({
        "devices": [{"type": "lock", "entity_id": "lock.porta_ufficio", "name": "Porta Ufficio", "group": "Ufficio"}],
        "ha_states": {"lock.porta_ufficio": {"state": "locked", "metrics": {"battery_level": 76, "battery_low": False}}},
    })
    assert normalized["devices"][0]["battery_percent"] == 76


@pytest.mark.asyncio
async def test_buspro_garage_locks_use_cover_commands(monkeypatch) -> None:
    import httpx
    from app.config import ProviderConfig
    from app.connectors import buspro as buspro_module

    devices = [
        {"name": "Portone Alex", "type": "lock", "domain": "cover", "entity_id": "cover.e_safe_out_50"},
        {"name": "Portone Luca", "type": "lock", "domain": "cover", "entity_id": "cover.e_safe_out_51"},
    ]
    normalized = normalize_snapshot({"devices": devices})
    assert [item["kind"] for item in normalized["devices"]] == ["cover", "cover"]
    assert normalized["counts"]["covers"] == 2
    commands = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"devices": devices})
        commands.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True})

    original = httpx.AsyncClient
    monkeypatch.setattr(buspro_module.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    connector = BusproConnector(ProviderConfig(enabled=True, base_url="http://hdl", token=""), 4)
    await connector.command("cover.e_safe_out_50", "open")
    await connector.command("cover.e_safe_out_51", "close")
    assert commands == [
        ("/api/control/ha/cover/cover.e_safe_out_50", {"command": "OPEN"}),
        ("/api/control/ha/cover/cover.e_safe_out_51", {"command": "CLOSE"}),
    ]


def test_supervisor_addon_slug_becomes_internal_dns_name() -> None:
    payload = {"data": {"addons": [{"slug": "a59e0dbb_e_hdl_buspro_mqtt"}]}}
    assert find_addon_url(payload, "e_hdl_buspro_mqtt", 8124) == "http://a59e0dbb-e-hdl-buspro-mqtt:8124"


def test_supervisor_network_info_becomes_host_network_url() -> None:
    payload = {"data": {"interfaces": [
        {"enabled": True, "ipv4": {"address": ["192.168.3.24/24"]}},
    ]}}
    assert find_host_url(payload, 1980) == "http://192.168.3.24:1980"


def test_navigation_icons_have_defaults(monkeypatch, tmp_path) -> None:
    options = tmp_path / "options.json"
    options.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("EFACE_OPTIONS", str(options))
    data = TestClient(create_app()).get("/api/bootstrap").json()
    assert data["nav_icons"]["watch"] == "mdi:television-play"
    assert data["nav_icons"]["security"] == "mdi:shield-home"
    assert data["nav_icons"]["energy"] == "mdi:solar-power-variant"
    assert data["nav_icons"]["extra"] == "mdi:shape"
    assert data["nav_icons"]["scenarios"] == "mdi:creation"


def test_energy_cards_expose_dynamic_flow_states() -> None:
    script = TestClient(create_app()).get("/assets/app.js").text
    assert "transmission-tower-import" in script
    assert "transmission-tower-export" in script
    assert "batteryFlow" in script
    assert "gridFlow" in script
    assert "PRELIEVO" in script
    assert "IMMISSIONE" in script
    assert "loadEnergyDashboards(false)" in script
    assert "energyRefreshRunning" in script


def test_user_can_select_persistent_card_theme(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_BACKGROUNDS", str(tmp_path))
    client = TestClient(create_app())
    assert client.get("/api/user/card-theme").json()["theme"] == "graphite"
    response = client.put("/api/user/card-theme", json={"theme": "midnight"})
    assert response.status_code == 200
    assert client.get("/api/user/card-theme").json()["theme"] == "midnight"
    assert client.put("/api/user/card-theme", json={"theme": "rainbow"}).status_code == 400


def test_tools_page_has_card_theme_picker_and_brand() -> None:
    page = TestClient(create_app()).get("/tools").text
    assert 'id="card-theme-tool"' in page
    assert 'id="card-theme-config"' in page
    assert 'class="tools-brand"' in page


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
    assert items[0]["icon"] == "mdi:home-thermometer-outline"


def test_etherm_external_temperature_is_read_only() -> None:
    items = normalize_thermostats({"entities": [{"type": "thermostats", "id": 8, "name": "Temperatura Esterna", "realtime": {"TEMP": 17.6, "THERM": {"ACT_SEA": "WIN", "ACT_MODEL": "MAN", "DEMAND_ON": "ON", "TEMP_THR": {"VAL": 21}}}}]})
    assert items[0]["read_only"] is True
    assert items[0]["state"] == "OFF"
    assert items[0]["icon"] == "mdi:thermometer"


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


def test_echo_is_recognized_with_tts_and_dnd() -> None:
    item = normalize_player({
        "registry_id": "echo-1", "entity_id": "media_player.echo_sala", "name": "Echo Sala",
        "manufacturer": "Amazon", "capabilities": {"tts": True, "do_not_disturb": True},
    })
    assert item["device_type"] == "echo"
    assert item["tts_available"] is True
    assert item["dnd_available"] is True


def test_echo_without_evoice_tts_capability_does_not_offer_tts() -> None:
    item = normalize_player({"registry_id": "echo-2", "entity_id": "media_player.echo_sala", "name": "Echo Sala", "manufacturer": "Amazon", "capabilities": {"tts": False}})
    assert item["device_type"] == "echo"
    assert item["tts_available"] is False


def test_local_evoice_player_gets_stable_artwork_fingerprint() -> None:
    raw = {"registry_id": "echo-1", "entity_id": "media_player.echo", "name": "Echo", "supported_features": 256, "media": {"title": "Happier", "artist": "Artist", "album": "Album"}}
    first = normalize_local_player(raw)
    second = normalize_local_player(raw)
    assert len(first["content_fingerprint"]) == 64
    assert first["content_fingerprint"] == second["content_fingerprint"]
    assert first["capabilities"]["artwork"] is True
    assert first["capabilities"]["turn_off"] is True


def test_local_echo_stop_capability_also_offers_power_button() -> None:
    item = normalize_local_player({
        "registry_id": "echo-2", "entity_id": "media_player.echo_2", "name": "Echo Spot",
        "is_echo": True, "capabilities": {"stop": True},
    })
    assert item["capabilities"]["turn_off"] is True


def test_local_echo_power_button_uses_media_stop(monkeypatch) -> None:
    import asyncio

    async def capture(self, registry_id, payload):
        return {"registry_id": registry_id, "operation": payload["operation"]}

    monkeypatch.setattr(EkonexMediaConnector, "command", capture)
    result = asyncio.run(EvoiceLocalMediaConnector(4).command("echo-2", {"operation": "turn_off"}))
    assert result == {"registry_id": "echo-2", "operation": "media_stop"}


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
    assert 'id="media-zones-power-all"' not in page
    assert "[...currentRooms" not in script
    assert "device.experiences?.includes('watch')" in script
    assert "device.experiences?.includes('listen') || device.tts_enabled" in script
    assert "data-tts-send" in script
    assert "data-tts-select-all" in script
    assert "}, duration)" in script
    assert "data-tts-volume" in script
    assert "await postDeviceCommand(deviceId, 'set_volume', volume)" in script
    assert "localStorage.setItem('eface-tts-volume'" in script
    assert "const ttsVolumeRestores = new Map()" in script
    assert "postDeviceCommand(deviceId, 'set_volume', pending.volume)" in script
    assert "data-dnd-device" in script
    assert "selected.provider === 'evoice' && selected.tts_enabled && ttsPlayers.length" in script
    assert "selectedMediaId = String(device.id)" in script
    assert "item.provider === selected.provider" in script
    assert "item.provider === player.provider" in script
    assert "['playing','buffering'].includes(state)" in script
    assert "consumedPlayback.has(playbackKey)" in script
    assert "player.provider === 'evoice'" in script
    assert "device.active_experience || (['playing', 'buffering'].includes(state) ? 'listen' : '')" in script
    assert 'data-base-volume="${volume}"' in script
    assert "Number(slider.dataset.baseVolume || 0) + delta" in script
    assert "Number(player.volume) + delta" in script
    assert "`${player.provider}|${playbackIdentity}`" in script
    assert "!['alarm_partition', 'alarm_scenario', 'alarm_system'].includes(device.kind)" in script
    assert "data-zone-volume" in script
    assert "postDeviceCommand(player.id, 'media_unjoin'" in script
    assert "updateGlobalMediaSession()" in script
    assert 'id="global-media-session"' in page
    assert 'id="media-sessions-dialog"' in page
    assert "activeMediaSessions()" in script
    assert "data-session-device" in script
    assert "['custom:PROGRAM_A','red','Rosso']" in script
    assert 'class="remote-color remote-${color}"' in script
    assert "media-session-row-watch" in script
    assert "device.source ? `<small>${esc(device.source)}</small>` : ''" in script
    assert "event.clientX < thumbX ? -2 : 2" in script
    assert "device.active_experience === 'watch' && stateIsActive(device)" in script
    assert "device.active_experience === 'listen' && stateIsActive(device)" in script
    assert "signature === lastDetailSignature" in script
    media_css = client.get("/assets/media-x4.css").text
    assert ".media-session.media-session-listen .media-volume input{accent-color:#20df6b}" in media_css
    assert ".media-session.media-session-watch .media-volume input{accent-color:#61d8f2}" in media_css
    assert "Ascoltati di recente" in script
    assert "api/control4/recently-played" in script
    assert "const recentCache = new Map()" in script
    assert "const recentPending = new Map()" in script
    assert "strip.setPointerCapture(event.pointerId)" in script
    assert "recentDrag.strip.scrollLeft = recentDrag.left - delta" in script
    assert "addEventListener('wheel'" not in script


def test_control4_recently_played_decodes_native_payload(monkeypatch) -> None:
    import asyncio
    import base64
    import json
    from app.connectors import control4_media

    history = [{"key":"abc", "driverId":615, "roomIds":"51,54", "timestamp":123,
                "info":{"container":{"title":"Radio Deejay", "subtitle":"On air", "itemType":"Station",
                                      "image":"http://cdn-radiotime-logos.tunein.com/s1g.png"}}}]
    class Director:
        async def send_post_request(self, uri, command, params, is_async):
            assert command == "GetHistoryItemsByRooms"
            assert params == {"rooms":"51,54", "limit":20}
            return json.dumps({"b64json":base64.b64encode(json.dumps(history).encode()).decode()})
    async def fake_director(config):
        return Director(), "token"
    monkeypatch.setattr(control4_media, "control4_director", fake_director)
    items = asyncio.run(Control4MediaConnector({}).recently_played([51,54]))
    assert items[0]["title"] == "Radio Deejay"
    assert items[0]["room_ids"] == [51,54]
    assert items[0]["content_fingerprint"]


def test_control4_digital_media_queue_becomes_canonical_group() -> None:
    players = [
        {"registry_id": "c4room:50", "name": "Ufficio Contabilità"},
        {"registry_id": "c4room:51", "name": "Ufficio Alex"},
    ]
    variables = [{"varName": "QUEUE_STATUS_V2", "value": {"queues": ""}}, {
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


def test_control4_shared_audio_route_becomes_one_session_without_queue() -> None:
    players = [
        {"registry_id": "c4room:51", "active_experience": "listen", "active_source_id": 210, "title": "Neon Ocean", "artist": "Neon Pulse", "album": "Neon Pulse", "content_fingerprint": None},
        {"registry_id": "c4room:50", "active_experience": "listen", "active_source_id": 210, "title": "Neon Ocean", "artist": "Neon Pulse", "album": "Neon Pulse", "content_fingerprint": None},
        {"registry_id": "c4room:61", "active_experience": "listen", "active_source_id": 100002, "title": "Other", "artist": "Artist", "album": "Album", "content_fingerprint": "other-track"},
    ]
    groups = normalize_control4_groups(players, [])
    assert len(groups) == 1
    assert groups[0]["group_id"].startswith("c4route:210:")
    assert groups[0]["member_registry_ids"] == ["c4room:51", "c4room:50"]
    assert groups[0]["inferred_from_route"] is True
    assert players[2].get("group") is None


def test_control4_digital_media_uses_actual_tunein_service_and_shared_stream() -> None:
    ui = {"experiences": [
        {"type": "listen", "room_id": room, "sources": {"source": [
            {"id": 100002, "name": "Digital Media"}, {"id": 615, "name": "TuneIn"},
        ]}} for room in (51, 61)
    ]}
    rooms = [{"id": 51, "name": "Ufficio Alex"}, {"id": 61, "name": "Sala"}]
    variables = [
        {"id": 51, "varName": "POWER_STATE", "value": 1},
        {"id": 51, "varName": "CURRENT_AUDIO_DEVICE", "value": 100002},
        {"id": 51, "varName": "PLAYING_AUDIO_DEVICE", "value": 615},
        {"id": 51, "varName": "CURRENT MEDIA INFO", "value": {"mediainfo": {"title": "Track", "album": "Energy Hits", "img": "https://img.example/station.jpg", "meta": {"audioFormat": "MPEG-1 Layer 3 (MP3)"}}}},
        {"id": 61, "varName": "POWER_STATE", "value": 1},
        {"id": 61, "varName": "CURRENT_AUDIO_DEVICE", "value": 615},
        {"id": 61, "varName": "PLAYING_AUDIO_DEVICE", "value": 615},
        {"id": 61, "varName": "CURRENT MEDIA INFO", "value": {"mediainfo": {"title": "Energy Hits", "album": "Energy Hits", "img": "https://img.example/station.jpg"}}},
    ]
    players = normalize_control4_media(ui, rooms, variables)
    office = next(player for player in players if player["room"] == "Ufficio Alex")
    assert office["selected_source_id"] == 100002
    assert office["playing_source_id"] == 615
    assert office["active_source_id"] == 615
    assert office["source"] == "TuneIn"
    groups = normalize_control4_groups(players, variables)
    assert len(groups) == 1
    assert groups[0]["member_registry_ids"] == ["c4room:51", "c4room:61"]
    assert groups[0]["owner_registry_id"] == "c4room:61"
    assert groups[0]["inferred_from_stream"] is True


def test_control4_group_volume_uses_owner_as_reference(monkeypatch) -> None:
    import asyncio
    from app.connectors import control4_media

    levels = {}

    class Room:
        def __init__(self, director, room_id):
            self.room_id = room_id

        async def set_volume(self, level):
            levels[self.room_id] = level

    async def director(config):
        return object(), "token"

    connector = Control4MediaConnector({})

    async def snapshot():
        group = {"group_id": "c4route:210:test", "owner_registry_id": "c4room:50", "member_registry_ids": ["c4room:50", "c4room:51"]}
        return {"groups": [group], "items": [
            {"registry_id": "c4room:50", "volume": 41},
            {"registry_id": "c4room:51", "volume": 37},
        ]}

    connector.snapshot = snapshot
    monkeypatch.setattr(control4_media, "control4_director", director)
    monkeypatch.setattr(control4_media, "C4Room", Room)
    result = asyncio.run(connector.group_volume("c4route:210:test", 50))
    assert levels == {50: 50, 51: 46}
    assert [item["volume"] for item in result["members"]] == [50, 46]


def test_local_home_assistant_media_snapshot_is_normalized() -> None:
    players, groups = normalize_local_snapshot({
        "areas": [{"area_id": "living", "name": "Soggiorno"}],
        "devices": [{"id": "device-1", "area_id": "living"}],
        "entities": [{"id": "registry-1", "entity_id": "media_player.sala", "device_id": "device-1", "device_class": "tv", "disabled_by": None}],
        "states": [{"entity_id": "media_player.sala", "state": "playing", "last_updated": "2026-09-11T10:00:00Z", "attributes": {"friendly_name": "Sala", "volume_level": 0.4, "supported_features": 16397, "source_list": ["Spotify"]}}],
    })
    assert groups == []
    assert players[0]["id"] == "media:registry-1"
    assert players[0]["room"] == "Soggiorno"
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
