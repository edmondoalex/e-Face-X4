from app.media_favorites import add_favorite, enrich_recent_favorites, favorite_by_id, list_favorites, load_favorite_artwork, remove_favorite, save_favorite_artwork


def without_saved_at(items):
    return [{key: value for key, value in item.items() if key != "saved_at"} for item in items]


def test_media_favorites_are_persistent_and_unique(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    station = {"id": "station:24:20", "kind": "station", "title": "RTL 102.5", "station_id": 20, "proxy_id": 24}
    recent = {"id": "recent:track-1", "kind": "recent", "title": "Brano", "key": "track-1"}
    assert without_saved_at(add_favorite(station)) == [station]
    assert without_saved_at(add_favorite(station)) == [station]
    assert without_saved_at(add_favorite(recent)) == [station, recent]
    assert without_saved_at(list_favorites()) == [station, recent]
    assert without_saved_at([favorite_by_id(station["id"])]) == [station]
    assert without_saved_at(remove_favorite(station["id"])) == [recent]
    assert without_saved_at(list_favorites()) == [recent]


def test_wiim_track_favorite_is_persistent(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    item = {"id": "wiim:track:6:tracks/abc", "kind": "wiim_track", "title": "Titolo", "track_id": "tracks/abc", "preset_index": 6}
    assert without_saved_at(add_favorite(item)) == [item]
    assert favorite_by_id(item["id"])["track_id"] == "tracks/abc"


def test_favorite_artwork_survives_reload_and_is_removed_with_favorite(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    item = {"id": "recent:track/1", "kind": "recent", "title": "Brano", "key": "track/1"}
    add_favorite(item)
    save_favorite_artwork(item["id"], b"image-bytes")
    assert load_favorite_artwork(item["id"]) == b"image-bytes"
    assert without_saved_at(list_favorites()) == [item]
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
