from app.media_favorites import add_favorite, favorite_by_id, list_favorites, remove_favorite


def test_media_favorites_are_persistent_and_unique(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    station = {"id": "station:24:20", "kind": "station", "title": "RTL 102.5", "station_id": 20, "proxy_id": 24}
    recent = {"id": "recent:track-1", "kind": "recent", "title": "Brano", "key": "track-1"}
    assert add_favorite(station) == [station]
    assert add_favorite(station) == [station]
    assert add_favorite(recent) == [station, recent]
    assert list_favorites() == [station, recent]
    assert favorite_by_id(station["id"]) == station
    assert remove_favorite(station["id"]) == [recent]
    assert list_favorites() == [recent]
