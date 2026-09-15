import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors.wiim import WiiMClient, decode_linkplay_text, public_artwork, validate_host


def test_wiim_host_is_lan_only() -> None:
    assert validate_host("192.168.3.52") == "192.168.3.52"
    for value in ("example.com", "127.0.0.1", "224.0.0.1", "8.8.8.8"):
        with pytest.raises(ValueError):
            validate_host(value)


def test_wiim_metadata_helpers() -> None:
    assert decode_linkplay_text("5A4F5941") == "ZOYA"
    assert decode_linkplay_text("Titolo") == "Titolo"
    assert public_artwork("https://i.scdn.co/image/example") == "https://i.scdn.co/image/example"
    assert public_artwork("file:///etc/passwd") == ""
    assert public_artwork("https://user:pass@example.com/image") == ""


@pytest.mark.asyncio
async def test_native_wiim_snapshot() -> None:
    responses = {
        "getStatusEx": {"uuid": "device-1", "DeviceName": "WiiM Pro", "project": "WiiM_Pro", "firmware": "1.2.3"},
        "getPlayerStatus": {"status": "play", "Title": "5469746F6C6F", "Artist": "41727469737461", "Album": "416C62756D", "curpos": "12000", "totlen": "180000", "vol": "78", "mute": "0", "loop": "4", "mode": "31"},
        "getMetaInfo": {"metaData": {"title": "Titolo", "artist": "Artista", "album": "Album", "albumArtURI": "https://example.com/cover.jpg", "trackId": "track-1", "sampleRate": "44100", "bitDepth": "16", "bitRate": "320"}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=responses[request.url.params["command"]])

    data = await WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler)).snapshot()
    assert data["state"] == "playing"
    assert data["title"] == "Titolo"
    assert data["artwork"] == "https://example.com/cover.jpg"
    assert data["duration"] == 180
    assert data["position"] == 12
    assert data["volume"] == 78


@pytest.mark.asyncio
async def test_native_wiim_actions_and_presets() -> None:
    commands = []

    def handler(request: httpx.Request) -> httpx.Response:
        command = request.url.params["command"]
        commands.append(command)
        if command == "getPresetInfo":
            return httpx.Response(200, json={"preset_list": [{"number": "1", "name": "526164696F"}]})
        return httpx.Response(200, text="OK")

    client = WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler))
    await client.player_action("volume", 42)
    await client.player_action("seek", 73)
    await client.player_action("loop", 5)
    await client.player_action("next")
    assert await client.presets() == [{"index": 1, "name": "Radio", "source": "", "artwork": ""}]
    await client.play_preset(1)
    assert commands == ["setPlayerCmd:vol:42", "setPlayerCmd:seek:73", "setPlayerCmd:loopmode:5", "setPlayerCmd:next", "getPresetInfo", "MCUKeyShortClick:1"]
    with pytest.raises(ValueError):
        await client.player_action("volume", 101)


@pytest.mark.asyncio
async def test_native_wiim_multiroom_foundation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["command"] == "getStatusEx":
            return httpx.Response(200, json={"group": "0", "GroupName": "WiiM Studio"})
        return httpx.Response(200, json={"slaves": 0, "wmrm_version": "4.3", "group_type": -1})

    data = await WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler)).multiroom()
    assert data["grouped"] is False
    assert data["role"] == "standalone"
    assert data["protocol_version"] == "4.3"


def test_admin_wiim_configuration_is_protected_and_verified(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_WIIM_CONFIG", str(tmp_path / "wiim.json"))
    from app.user_auth import create_admin
    from app import main as main_module

    class FakeWiiM:
        def __init__(self, host: str):
            self.host = validate_host(host)
            assert self.host == "192.168.3.52"

        async def snapshot(self):
            return {"name": "WiiM Pro", "model": "WiiM_Pro", "firmware": "1.2.3", "state": "playing", "volume": 35}

    monkeypatch.setattr(main_module, "WiiMClient", FakeWiiM)
    create_admin("password-admin-lunga")
    client = TestClient(main_module.create_app())
    assert client.get("/api/admin/wiim").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    payload = {"enabled": True, "host": "192.168.3.52", "control4_source_id": 1667, "control4_protocol_id": 1666}
    response = client.put("/api/admin/wiim", json=payload)
    assert response.status_code == 200
    assert response.json()["device"]["name"] == "WiiM Pro"
    assert (tmp_path / "wiim.json").is_file()
    assert client.post("/api/admin/wiim/test", json={"host": "8.8.8.8"}).status_code == 400


def test_wiim_admin_ui_is_present() -> None:
    from app.main import create_app

    page = TestClient(create_app()).get("/tools").text
    assert 'id="wiim-tool"' in page
    assert 'id="wiim-config"' in page
    assert "Collegamento diretto e-Face → WiiM" in page
    assert "Home Assistant non è nel percorso funzionale" in page
    home = TestClient(create_app()).get("/").text
    assert 'data-view="wiim"' not in home
    assert 'id="wiim-frame"' not in home
    assert 'href="wiim">APRI CONSOLE DEBUG' in page


def test_wiim_service_registry_starts_with_soundcloud() -> None:
    from app.wiim_services import catalog

    services = catalog()
    assert services[0]["id"] == "soundcloud"
    assert services[0]["status"] == "configuration_required"
    assert "search" in services[0]["features"]


@pytest.mark.asyncio
async def test_soundcloud_official_search_normalization() -> None:
    from app.connectors.soundcloud import SoundCloudClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "secure.soundcloud.com":
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        assert request.headers["authorization"] == "OAuth token"
        return httpx.Response(200, json={"collection": [{"urn": "soundcloud:tracks:42", "title": "Track", "duration": 123000, "access": "playable", "user": {"username": "Artist"}}]})

    items = await SoundCloudClient("client-id", "client-secret", transport=httpx.MockTransport(handler)).search_tracks("house")
    assert items == [{"type": "track", "urn": "soundcloud:tracks:42", "title": "Track", "artist": "Artist", "artwork": "", "duration": 123, "permalink_url": "", "playable": True}]


@pytest.mark.asyncio
async def test_soundcloud_catalog_stream_and_wiim_play_url() -> None:
    from app.connectors.soundcloud import SoundCloudClient

    def soundcloud_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "secure.soundcloud.com":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        if request.url.path.endswith("/streams"):
            return httpx.Response(200, json={"hls_aac_160_url": "https://media.example/playlist.m3u8?sig=abc"})
        return httpx.Response(200, json={"collection": [{"urn": "soundcloud:playlists:7", "title": "Set", "track_count": 4, "user": {"username": "DJ"}}]})

    client = SoundCloudClient("catalog-client", "catalog-secret", transport=httpx.MockTransport(soundcloud_handler))
    assert (await client.search("house", "playlists"))[0]["type"] == "playlist"
    assert await client.stream("soundcloud:tracks:42") == {"url": "https://media.example/playlist.m3u8?sig=abc", "quality": "hls_aac_160_url"}

    commands = []
    def wiim_handler(request: httpx.Request) -> httpx.Response:
        commands.append(request.url.params["command"]); return httpx.Response(200, text="OK")
    await WiiMClient("192.168.3.52", transport=httpx.MockTransport(wiim_handler)).play_url("https://media.example/playlist.m3u8?sig=abc")
    assert commands == ["setPlayerCmd:play:https://media.example/playlist.m3u8?sig=abc"]


def test_soundcloud_admin_experience_assets_present() -> None:
    from app.main import create_app
    app = create_app()
    assert (app_module := __import__("app.main", fromlist=["STATIC"])).STATIC.joinpath("soundcloud.html").is_file()
    page = app_module.STATIC.joinpath("soundcloud.html").read_text(encoding="utf-8")
    script = app_module.STATIC.joinpath("assets", "soundcloud.js").read_text(encoding="utf-8")
    assert "Cerca su SoundCloud" in page
    assert 'data-kind="playlists"' in page and "related" in script


def test_soundcloud_local_library_is_persistent(monkeypatch, tmp_path) -> None:
    from app import soundcloud_library
    monkeypatch.setenv("EFACE_SOUNDCLOUD_LIBRARY", str(tmp_path / "library.json"))
    track = {"urn": "soundcloud:tracks:42", "title": "Track", "artist": "Artist", "artwork": "https://example.com/a.jpg", "duration": 123}
    assert soundcloud_library.remember(track)["recent"][0]["title"] == "Track"
    assert soundcloud_library.toggle(track)["favorites"][0]["urn"] == track["urn"]
    assert soundcloud_library.toggle(track)["favorites"] == []


def test_wiim_presets_are_rendered_as_eface_favorites() -> None:
    script = __import__("app.main", fromlist=["STATIC"]).STATIC.joinpath("assets", "app.js").read_text(encoding="utf-8")
    assert "wiim_preset" in script
    assert "speaker-wireless" in script


def test_wiim_controls_are_integrated_in_main_player() -> None:
    script = __import__("app.main", fromlist=["STATIC"]).STATIC.joinpath("assets", "app.js").read_text(encoding="utf-8")
    assert "data-wiim-timeline" in script
    assert "data-wiim-seek" in script
    assert 'data-wiim-action="${action}"' in script
    assert "shuffle-variant" in script and "Ripetizione WiiM" in script
