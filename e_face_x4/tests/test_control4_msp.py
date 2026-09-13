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
