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
