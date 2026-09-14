import asyncio

import pytest

from app import control4_bridge as bridge


def test_bridge_browse_and_connect_use_async_proxy_command(monkeypatch):
    calls = []

    async def command(proxy, room, name, values, wait_response=True, is_async=False):
        calls.append((proxy, room, name, values, wait_response, is_async))
        if name == "PairedDeviceList":
            return {"Collection": {"title": "DEVICES"}, "List": {"item": [
                {"Name": "POCO F7 Pro", "Title": "POCO F7 Pro", "Addr": "20995234CB80", "Connected": False},
                {"Name": "Fire Tablet", "Addr": "244CE3E5E083", "Connected": True},
            ]}}
        return {"RefreshScreen": True}

    monkeypatch.setattr(bridge, "_command", command)
    items = asyncio.run(bridge.bridge_browse(210, 51))["items"]
    assert [item["title"] for item in items] == ["POCO F7 Pro", "Fire Tablet"]
    assert items[1]["connected"] is True
    assert "20995234CB80" not in str(items)
    asyncio.run(bridge.bridge_action(210, 51, items[0]["id"], "BtConnectDisconnect"))
    assert calls[-1] == (210, 51, "BtConnectDisconnect", {"Name": "POCO F7 Pro", "Addr": "20995234CB80", "Paired": "", "Connected": "false"}, True, True)
    with pytest.raises(ValueError):
        asyncio.run(bridge.bridge_action(210, 54, items[0]["id"], "BtRemoveDevice"))


def test_bridge_add_refuses_full_device_list(monkeypatch):
    async def browse(proxy, room):
        return {"items": [{"id": str(index)} for index in range(5)]}

    monkeypatch.setattr(bridge, "bridge_browse", browse)
    with pytest.raises(ValueError, match="massimo 5"):
        asyncio.run(bridge.bridge_action(210, 51, "", "BtAddDevice"))
