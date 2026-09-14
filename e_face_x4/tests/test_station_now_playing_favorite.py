from fastapi.testclient import TestClient

from app import control4_stations
from app.main import create_app


def test_current_stations_star_toggles_catalog_favorite(monkeypatch, tmp_path):
    import app.main as main

    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    monkeypatch.setitem(control4_stations._STATION_METADATA, 24, ("GOA-BASE", 1665, "/images/broadcast/aa/test.jpg"))

    class Director:
        async def get_item_info(self, item_id):
            assert item_id == 24
            return {"name": "Stations", "proxy": "media_service"}

        async def get_item_variable_value(self, room_id, name):
            assert (room_id, name) == (51, "CURRENT MEDIA INFO")
            return {"mediainfo": {"mediaid": 24, "channel": "GOA-BASE", "mediatypeV2": "INTERNET_MEDIA"}}

    async def director(_config):
        return Director(), "token"

    monkeypatch.setattr(main, "control4_director", director)
    client = TestClient(create_app())
    payload = {"room_id": 51, "proxy_id": 24}
    first = client.post("/api/control4/favorites/current-station", json=payload)
    assert first.status_code == 200
    assert first.json()["items"][0]["id"] == "station:24:24"
    second = client.post("/api/control4/favorites/current-station", json=payload)
    assert second.status_code == 200
    assert second.json()["items"] == []


def test_current_spotify_star_saves_playlist_not_track(monkeypatch, tmp_path):
    import app.main as main

    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))

    class Director:
        async def get_item_info(self, item_id):
            assert item_id == 1569
            return {"name": "Spotify Connect", "proxy": "media_service"}

        async def get_item_variable_value(self, room_id, name):
            assert (room_id, name) == (51, "CURRENT MEDIA INFO")
            return {"mediainfo": {"title": "Danza Kuduro", "medSrcDev": 1569}}

    async def director(_config):
        return Director(), "token"

    async def history(_self, room_ids, limit):
        assert room_ids == [51]
        return [{"key": "playlist-1", "title": "Big Boom In The Room", "subtitle": "",
                 "item_type": "Playlist", "driver_id": 1569, "registry_id": "c4recent:playlist-1", "content_fingerprint": None}]

    monkeypatch.setattr(main, "control4_director", director)
    monkeypatch.setattr(main.Control4MediaConnector, "recently_played", history)
    client = TestClient(create_app())
    payload = {"room_id": 51, "proxy_id": 1569}
    first = client.post("/api/control4/favorites/current-spotify-playlist", json=payload)
    assert first.status_code == 200
    assert first.json()["title"] == "Big Boom In The Room"
    assert first.json()["items"][0]["id"] == "recent:playlist-1"
    second = client.post("/api/control4/favorites/current-spotify-playlist", json=payload)
    assert second.status_code == 200
    assert second.json()["items"] == []
