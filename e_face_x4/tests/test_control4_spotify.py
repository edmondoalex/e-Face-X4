import asyncio

from app import control4_spotify as spotify
from app.media_favorites import list_favorites


def test_spotify_presets_browse_play_and_eface_favorite(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_MEDIA_FAVORITES", str(tmp_path / "favorites.json"))
    calls = []

    async def command(proxy, room, name, values, wait_response=True):
        calls.append((proxy, room, name, values, wait_response))
        if name == "ListPresets":
            return {"List": {"length": 2, "item": [
                {"title": "Presets", "isHeader": True},
                {"title": "Bob Dominator", "subtitle": "lele55!", "blob": "c3BvdGlmeTphcnRpc3Q=", "default_action": "PresetPlay", "actions_list": "PresetPlay FavoriteToRoom"},
            ]}}
        return None

    monkeypatch.setattr(spotify, "_command", command)
    data = asyncio.run(spotify.spotify_browse(1569, 51, "Presets"))
    assert data["items"][0]["header"] is True
    item = data["items"][1]
    assert item["actions"] == ["PresetPlay", "PinFavorite"]
    assert "c3BvdGlme" not in str(data)
    asyncio.run(spotify.spotify_action(1569, 51, "Presets", item["id"], "PinFavorite"))
    assert list_favorites()[0]["title"] == "Bob Dominator"
    refreshed = asyncio.run(spotify.spotify_browse(1569, 51, "Presets"))
    assert refreshed["items"][1]["actions"] == ["PresetPlay", "UnpinFavorite"]
    asyncio.run(spotify.spotify_action(1569, 51, "Presets", item["id"], "PresetPlay"))
    assert calls[-1][2] == "PresetPlay"
    assert calls[-1][3]["blob"] == "c3BvdGlmeTphcnRpc3Q="
    assert calls[-1][4] is False
