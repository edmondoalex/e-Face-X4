import asyncio

from app import control4_msp_catalog as catalog


def test_amazon_catalog_uses_driver_screen_fields_and_opaque_items(monkeypatch):
    calls = []

    async def fake_command(proxy, room, name, values, wait_response=True):
        calls.append((proxy, room, name, values, wait_response))
        if name == "Browse" and values["screenId"] == "HomeScreen":
            return {"List": {"length": 1, "item": {"title": "Playlist", "id": "catalog/playlists/", "parentId": "", "itemType": "link", "isPlayable": False, "default_action": "SelectItem"}}}
        if name == "SelectItem":
            return {"NextScreen": "ListScreen"}
        return {"List": {"length": 1, "item": {"title": "Hit", "id": "private-track-id", "itemType": "track", "isPlayable": True, "default_action": "SelectItem", "image_list": {"$t": "https://example.com/cover.png"}}}}

    monkeypatch.setattr(catalog, "_command", fake_command)
    root = asyncio.run(catalog.catalog_browse("amazon", 1644, 51, "Home"))
    assert root["items"][0]["title"] == "Playlist"
    assert "catalog/playlists/" not in str(root)
    child = asyncio.run(catalog.catalog_browse("amazon", 1644, 51, "Home", root["items"][0]["id"]))
    assert child["items"][0]["actions"] == ["PlayNow"]
    assert child["items"][0]["image"] == "https://example.com/cover.png"
    assert calls[-1][2:4] == ("Browse", {"screenId": "ListScreen", "id": "catalog/playlists/", "parentId": "", "itemType": "link", "isPlayable": False})
    assert asyncio.run(catalog.catalog_action("amazon", 1644, 51, "Home", child["items"][0]["id"], "PlayNow")) == {"ok": True}
    assert calls[-1][2:5] == ("Play", {"id": "private-track-id", "itemType": "track", "playOption": "NOW"}, False)


def test_tidal_tabs_and_settings_do_not_expose_password(monkeypatch):
    async def fake_command(proxy, room, name, values, wait_response=True):
        if name == "GetTabList":
            return {"Tabs": {"Tab": [{"Id": "Library", "Name": "Library"}, {"Id": "Settings", "Name": "Settings"}, {"Id": "Unexpected", "Name": "Unexpected"}]}}
        return {"Settings": {"status": "Logged Out", "username": "test", "password": "secret"}}

    monkeypatch.setattr(catalog, "_command", fake_command)
    assert asyncio.run(catalog.catalog_tabs("tidal", 1650, 51)) == {"tabs": [{"id": "Library", "name": "Library"}, {"id": "Settings", "name": "Settings"}]}
    assert asyncio.run(catalog.catalog_settings(1650, 51)) == {"status": "Logged Out", "username": "test"}
