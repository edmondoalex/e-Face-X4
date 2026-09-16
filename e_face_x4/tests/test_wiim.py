import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors.wiim import WiiMClient, decode_linkplay_text, public_artwork, validate_host
from app.main import native_wiim_media_item, overlay_wiim_on_control4


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


def test_wiim_snapshot_overlays_linked_control4_room() -> None:
    providers = [{"id": "control4", "items": [{"id": "c4media:51", "registry_id": "c4room:51", "kind": "media_player", "active_source_id": 1667, "state": "idle", "title": "Vecchio", "volume": 40, "muted": True, "capabilities": {}}]}]
    snapshot = {"state": "playing", "title": "Titolo WiiM", "artist": "Artista", "album": "Album", "track_id": "track-1", "artwork": "https://example.com/cover.jpg", "volume": 37, "muted": False}
    assert overlay_wiim_on_control4(providers, snapshot, 1667) is True
    player = providers[0]["items"][0]
    assert player["transport_provider"] == "wiim"
    assert player["title"] == "Titolo WiiM" and player["state"] == "playing"
    assert player["volume"] == 40 and player["muted"] is True and player["wiim_artwork"] is True
    assert player["content_fingerprint"].startswith("wiim-")


def test_wiim_is_standalone_media_provider_without_control4_room() -> None:
    item = native_wiim_media_item({"id": "uuid-1", "name": "WiiM Pro", "state": "playing", "source": "SoundCloud", "title": "Track", "track_id": "t1", "volume": 45, "muted": False})
    assert item["id"] == "wiim:uuid-1"
    assert item["provider"] == item["transport_provider"] == "wiim"
    assert item["capabilities"]["next"] is True
    assert item["capabilities"]["select_source"] is False


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


@pytest.mark.asyncio
async def test_native_wiim_queue_browse_and_exact_play() -> None:
    actions = []
    context = """<?xml version="1.0"?><PlayList><ListName>Cover e remix_#~2026-09-15</ListName><ListInfo><TotalNumber>2</TotalNumber></ListInfo><Tracks><Track1><Id>tracks/abc</Id><Metadata>&lt;DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"&gt;&lt;dc:title&gt;Titolo&lt;/dc:title&gt;&lt;upnp:artist&gt;Artista&lt;/upnp:artist&gt;&lt;upnp:album&gt;Album&lt;/upnp:album&gt;&lt;upnp:albumArtURI&gt;https://example.com/cover.jpg&lt;/upnp:albumArtURI&gt;&lt;/DIDL-Lite&gt;</Metadata><Source>YouTubeMusic</Source></Track1></Tracks></PlayList>"""

    def handler(request: httpx.Request) -> httpx.Response:
        action = request.headers["soapaction"].split("#")[-1].strip('"')
        actions.append((action, request.content.decode()))
        if action == "BrowseQueueEx":
            escaped = context.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return httpx.Response(200, text=f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:BrowseQueueExResponse xmlns:u="urn:schemas-wiimu-com:service:PlayQueue:1"><QueueContext>{escaped}</QueueContext></u:BrowseQueueExResponse></s:Body></s:Envelope>')
        return httpx.Response(200, text='<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>')

    client = WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler))
    queue = await client.queue(limit=10)
    assert queue["name"] == "Cover e remix"
    assert queue["queue_name"] == "Cover e remix_#~2026-09-15"
    assert queue["total"] == 2
    assert queue["tracks"][0] == {"index": 1, "track_id": "tracks/abc", "url": "", "title": "Titolo", "artist": "Artista", "album": "Album", "artwork": "https://example.com/cover.jpg", "source": "YouTubeMusic"}
    await client.play_queue_index(1, "Playlist_#~token")
    assert [action for action, _ in actions] == ["BrowseQueueEx", "PlayQueueWithIndex"]
    assert "<QueueName>Playlist_#~token</QueueName>" in actions[-1][1]
    assert "<Index>1</Index>" in actions[-1][1]
    assert all("schemas-wiimu-com:service:PlayQueue:1" in body for _, body in actions)


@pytest.mark.asyncio
async def test_native_wiim_create_queue_then_plays_first_track() -> None:
    actions = []
    def handler(request: httpx.Request) -> httpx.Response:
        action = request.headers.get("soapaction", "").split("#")[-1].strip('"') or str(request.url.params.get("command") or "")
        actions.append((action, request.content.decode()))
        return httpx.Response(200, text='<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>')
    client = WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler))
    context = '<?xml version="1.0"?><PlayList><ListName>e-Face SoundCloud - Test</ListName></PlayList>'
    await client.create_queue(context, "e-Face SoundCloud - Test")
    assert [item[0] for item in actions] == ["CreateQueue", "PlayQueueWithIndex", "setPlayerCmd:play"]
    assert "&lt;PlayList&gt;" in actions[0][1]
    assert "<QueueName>e-Face SoundCloud - Test</QueueName>" in actions[1][1]


@pytest.mark.asyncio
async def test_native_wiim_delete_preset_clears_key_mapping() -> None:
    requests = []
    mapping = "<?xml version=\"1.0\"?><KeyList><Key1><Name>Radio</Name><RoutineId>Empty</RoutineId></Key1><Key2><RoutineId>Empty</RoutineId></Key2></KeyList>"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((str(request.url), request.content.decode() if request.content else ""))
        if request.method == "POST" and "GetKeyMapping" in request.headers.get("soapaction", ""):
            escaped = mapping.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return httpx.Response(200, text=f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><QueueContext>{escaped}</QueueContext></s:Body></s:Envelope>')
        if request.method == "POST":
            return httpx.Response(200, text='<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>')
        return httpx.Response(200, json={"preset_list": []})

    await WiiMClient("192.168.3.52", transport=httpx.MockTransport(handler)).delete_preset(1)
    set_body = requests[1][1]
    assert "SetKeyMapping" in set_body
    assert "&lt;Key1&gt;&lt;RoutineId&gt;Empty&lt;/RoutineId&gt;&lt;/Key1&gt;" in set_body
    assert "Radio" not in set_body


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


def test_soundcloud_favorite_removal_creates_backup(monkeypatch, tmp_path) -> None:
    from app import soundcloud_library
    path = tmp_path / "soundcloud.json"
    monkeypatch.setenv("EFACE_SOUNDCLOUD_LIBRARY", str(path))
    track = {"urn": "soundcloud:tracks:42", "title": "Track", "artist": "Artist"}
    soundcloud_library.toggle(track)
    assert soundcloud_library.remove_favorite(track["urn"])["favorites"] == []
    assert path.with_suffix(".json.bak").is_file()


def test_wiim_presets_are_rendered_as_eface_favorites() -> None:
    script = __import__("app.main", fromlist=["STATIC"]).STATIC.joinpath("assets", "app.js").read_text(encoding="utf-8")
    styles = __import__("app.main", fromlist=["STATIC"]).STATIC.joinpath("assets", "recent-visibility.css").read_text(encoding="utf-8")
    assert "wiim_preset" in script
    assert "speaker-wireless" in script
    assert "Preferito creato da e-Face" in script
    assert ".media-favorite-eface{display:block;object-fit:contain;background:transparent}" in styles


def test_soundcloud_local_playlists_create_and_append(monkeypatch, tmp_path) -> None:
    from app import soundcloud_library
    monkeypatch.setenv("EFACE_SOUNDCLOUD_LIBRARY", str(tmp_path / "soundcloud.json"))
    first = {"urn":"soundcloud:tracks:1","title":"Uno","artist":"Artista","artwork":"","duration":120}
    second = {"urn":"soundcloud:tracks:2","title":"Due","artist":"Artista","artwork":"","duration":140}
    data = soundcloud_library.save_to_playlist("La mia lista", first)
    playlist_id = data["playlists"][0]["id"]
    data = soundcloud_library.save_to_playlist("", second, playlist_id)
    assert data["playlists"][0]["name"] == "La mia lista"
    assert [item["urn"] for item in data["playlists"][0]["tracks"]] == ["soundcloud:tracks:1", "soundcloud:tracks:2"]


def test_comfort_navigation_icon_follows_heat_and_cool_state() -> None:
    static = __import__("app.main", fromlist=["STATIC"]).STATIC
    script = static.joinpath("assets", "app.js").read_text(encoding="utf-8")
    styles = static.joinpath("assets", "app.css").read_text(encoding="utf-8")
    assert "comfortHeating && comfortCooling ? 'status-comfort-mixed' : comfortHeating ? 'status-amber' : 'status-cyan'" in script
    assert ".rail button.status-amber .nav-icon" in styles
    assert ".rail button.status-comfort-mixed .nav-icon" in styles
    assert "linear-gradient(90deg,#ffa643 0 50%,#61d8f2 50% 100%)" in styles


def test_wiim_controls_are_integrated_in_main_player() -> None:
    script = __import__("app.main", fromlist=["STATIC"]).STATIC.joinpath("assets", "app.js").read_text(encoding="utf-8")
    assert "data-wiim-timeline" in script
    assert "c4wiimroute:" in script
    assert "every room must retain its own volume control" in script
    assert "data-wiim-seek" in script
    assert 'data-wiim-action="${action}"' in script
    assert "shuffle-variant" in script and "Ripetizione WiiM" in script
    assert "current-wiim-track" in script
