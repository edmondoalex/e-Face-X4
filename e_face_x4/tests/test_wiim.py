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
