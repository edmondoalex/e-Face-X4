from fastapi.testclient import TestClient

from app.main import create_app
from app.connectors.buspro import normalize_snapshot
from app.connectors.etherm import normalize_thermostats
from app.connectors.ksenia import normalize_ksenia
from app.connectors.media import normalize_player
from app.connectors.local_media import normalize_local_snapshot
from app.connectors.local_media import HA_WEBSOCKET_MAX_BYTES
from app.connectors.control4_media import Control4MediaConnector, control4_icon_path, control4_queues, control4_remote_actions, normalize_control4_groups, normalize_control4_media
from app.connectors.supervisor import find_addon_url
from app.media_preferences import apply_preferences, load_preferences, save_preferences
from app.control4 import load_control4_config, public_control4_config, save_control4_config, summarize_ui_configuration
from app.source_icons import delete_source_icon, load_builtin_source_icon, load_source_icon, save_source_icon
from app.backgrounds import load_background, load_background_image, load_backgrounds, save_background_image, save_inherit, save_preset


def test_health() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


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
    assert page.text.count('<dialog') == 6
    assert 'id="security-area-dialog"' in page.text
    assert 'id="security-pin-dialog"' in page.text
    assert 'id="rgb-dialog"' in page.text
    assert 'id="show-all-devices"' in page.text
    assert 'id="scenario-panel"' in page.text
    assert 'id="scenario-list"' in page.text
    assert '<iframe' not in page.text
    for label in ("Guarda", "Ascolta", "Luci", "Extra", "Scenari", "Oscuranti", "Comfort", "Sicurezza"):
        assert f'title="{label}"' in page.text
    assert 'src="assets/brand-horizontal.png?v=2.16.0"' in page.text
    assert 'alt="e-Face X4"' in page.text
    assert 'class="header-wordmark"' not in page.text
    assert client.get("/assets/brand-horizontal.png").status_code == 200
    assert client.get("/assets/brand-icon.png").status_code == 200
    assert client.get("/assets/app.css").status_code == 200
    assert client.get("/assets/media.css").status_code == 200
    assert client.get("/assets/media-x4.css").status_code == 200
    assert client.get("/assets/media-remote-colors.css").status_code == 200
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
    assert "event.target !== dialog" in app_js
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


def test_builtin_control4_source_icons_are_packaged() -> None:
    for label in ("Sonos", "Stations", "VIDAA", "Apps", "DLNA", "Spotify Connect", "Manage Music", "Digital Media", "AM/FM Tuner", "Wireless Music Bridge"):
        icon = load_builtin_source_icon(label)
        assert icon is not None
        assert icon[0] == "image/png"
        assert icon[1].startswith(b"\x89PNG\r\n\x1a\n")
    assert load_builtin_source_icon("Sorgente sconosciuta") is None


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
    assert "['listen', 'watch'].includes(experience)" in script
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
    assert "activeMediaRoom && selected.active_experience !== 'watch'" in script
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
