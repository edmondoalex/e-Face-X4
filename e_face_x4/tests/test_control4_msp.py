import asyncio

import app.control4_msp as msp


def test_xml_args_escaped_and_empty_root():
    assert msp._args({}) == "<args></args>"
    assert msp._args({"search": 'a<&"b'}) == '<args><arg name="search">a&lt;&amp;&quot;b</arg></args>'


def test_browse_uses_opaque_ids_and_preserves_private_driver_fields(monkeypatch):
    async def command(proxy, room, name, values):
        assert (proxy, room, name) == (615, 51, "GetBrowseScreen")
        assert values["offset"] == 0 and values["limit"] == 30
        return {"List": {"length": 1, "item": [{"Title": "Local Radio", "Url": "secret-driver-url", "actions_list": "Browse", "default_action": "Browse", "isLink": "true"}]}}

    monkeypatch.setattr(msp, "_command", command)
    result = asyncio.run(msp.tunein_browse(615, 51, "Browse"))
    assert result["items"][0]["title"] == "Local Radio"
    assert result["items"][0]["link"] is True
    assert "secret-driver-url" not in str(result)
    assert msp._ITEMS[result["items"][0]["id"]][4]["Url"] == "secret-driver-url"


def test_settings_never_expose_driver_password(monkeypatch):
    async def command(proxy, room, name, values):
        return {"Settings": {"username": "edmondoalex", "status": "Free", "password": "secret"}}

    monkeypatch.setattr(msp, "_command", command)
    result = asyncio.run(msp.tunein_settings(615, 51))
    assert result == {"username": "edmondoalex", "status": "Free"}
    assert "secret" not in str(result)


def test_tunein_actions_are_space_separated_and_default_play_is_allowed(monkeypatch):
    assert msp._item_actions({"actions_list": "Play FavoriteToRoom Follow Profile"}) == ["Play", "FavoriteToRoom", "Follow", "Profile"]
    assert msp._item_actions({"actions_list": "Play,Unfollow"}) == ["Play", "Unfollow"]

    async def command(proxy, room, name, values, wait_response=True):
        assert name == "Play"
        assert values["Title"] == "Radio"
        return None

    monkeypatch.setattr(msp, "_command", command)
    msp._ITEMS["radio"] = (msp.time.monotonic() + 60, 615, 51, "Home", {"Title": "Radio", "default_action": "Play", "actions_list": ""})
    assert asyncio.run(msp.tunein_action(615, 51, "Home", "radio", "Play")) == {"ok": True}
