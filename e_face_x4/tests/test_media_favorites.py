from app.media_favorites import add_favorite, enrich_recent_favorites, favorite_by_id, list_favorites, load_favorite_artwork, remove_favorite, save_favorite_artwork


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


def test_favorite_artwork_survives_reload_and_is_removed_with_favorite(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    item = {"id": "recent:track/1", "kind": "recent", "title": "Brano", "key": "track/1"}
    add_favorite(item)
    save_favorite_artwork(item["id"], b"image-bytes")
    assert load_favorite_artwork(item["id"]) == b"image-bytes"
    assert list_favorites() == [item]
    remove_favorite(item["id"])
    assert load_favorite_artwork(item["id"]) is None


def test_old_spotify_favorite_recovers_persistent_service_id(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    item = {"id": "recent:track-1", "kind": "recent", "title": "Brano", "key": "track-1", "item_type": "Track"}
    add_favorite(item)
    assert enrich_recent_favorites([{"key": "track-1", "driver_id": 1569}]) is True
    assert list_favorites()[0]["driver_id"] == 1569
    assert enrich_recent_favorites([{"key": "track-1", "driver_id": 615}]) is False
    assert list_favorites()[0]["driver_id"] == 1569
