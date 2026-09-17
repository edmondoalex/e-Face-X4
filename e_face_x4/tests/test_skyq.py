from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app import skyq_icons, skyq_settings
from app.connectors import skyq


def test_skyq_custom_icon_is_persistent(tmp_path, monkeypatch) -> None:
    import base64

    monkeypatch.setenv("EFACE_SKYQ_ICON_DIR", str(tmp_path / "icons"))
    content = b"\x89PNG\r\n\x1a\n" + b"custom-icon-data"
    skyq_icons.save("prime.video", "image/png", base64.b64encode(content).decode())
    assert skyq_icons.load("prime.video") == ("image/png", content)
    assert skyq_icons.delete("prime.video") is True
    assert skyq_icons.load("prime.video") is None


def test_skyq_settings_are_native_and_validated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EFACE_SKYQ_CONFIG", str(tmp_path / "skyq.json"))
    saved = skyq_settings.save({"enabled": True, "host": "192.168.10.64", "name": "Sky Q Sala", "control4_room_id": 61, "control4_source_id": 244, "command_provider": "control4", "services": ["Netflix", "DAZN", "dazn", ""], "app_order": ["DAZN", "Netflix"]})
    assert saved["command_provider"] == "native"
    assert saved["services"] == ["Netflix", "DAZN"]
    assert saved["app_order"] == ["DAZN", "Netflix"]
    assert skyq_settings.load()["control4_source_id"] == 244


def test_skyq_overlay_replaces_metadata_and_exposes_native_remote() -> None:
    providers = [{"id": "control4", "items": [{"registry_id": "c4room:61", "kind": "media_player", "source": "Sky Q", "active_source_id": 244, "source_options": [{"source_id": 244, "experience": "watch", "remote_actions": []}], "capabilities": {"artwork": False}}]}]
    data = {"status": "online", "title": "Film", "channel": "Sky Cinema", "channel_number": "301", "description": "Trama", "app": "EPG_UI", "artwork": "https://it.imageservice.sky.com/example.jpg", "apps": [{"id": "netflix", "title": "Netflix"}, {"id": "dazn", "title": "DAZN"}]}
    assert skyq.overlay_control4(providers, data, {"control4_room_id": 61, "control4_source_id": 244, "services": ["Netflix"]})
    item = providers[0]["items"][0]
    assert item["title"] == "Film"
    assert item["description"] == "Trama"
    assert item["skyq_artwork"] is True
    assert item["skyq_apps"] == [{"id": "netflix", "title": "Netflix"}]
    assert "custom:PROGRAM_A" in item["source_options"][0]["remote_actions"]


def test_skyq_command_maps_remote_button(monkeypatch) -> None:
    pressed = []
    skyq._remotes.clear()

    class Remote:
        device_setup = True

        def __init__(self, host):
            assert host == "192.168.10.64"

        def press(self, value):
            pressed.append(value)

    import pyskyqremote.skyq_remote
    monkeypatch.setattr(pyskyqremote.skyq_remote, "SkyQRemote", Remote)
    result = asyncio.run(skyq.command({"enabled": True, "host": "192.168.10.64"}, "custom:PROGRAM_A"))
    assert result["provider"] == "skyq"
    assert pressed == ["red"]


def test_skyq_digits_are_aggregated_in_order(monkeypatch) -> None:
    pressed = []
    skyq._remotes.clear()
    skyq._digit_buffers.clear()
    skyq._digit_tasks.clear()

    class Remote:
        device_setup = True

        def __init__(self, host):
            pass

        def press(self, value):
            pressed.append(value)

    import pyskyqremote.skyq_remote
    monkeypatch.setattr(pyskyqremote.skyq_remote, "SkyQRemote", Remote)

    async def run() -> None:
        config = {"enabled": True, "host": "192.168.10.64"}
        await skyq.command(config, "digit_1")
        await skyq.command(config, "digit_0")
        await skyq.command(config, "digit_0")
        await asyncio.sleep(0.7)

    asyncio.run(run())
    assert pressed == [["1", "0", "0"]]


def test_skyq_inventory_serializes_decoder_lists(monkeypatch) -> None:
    class Remote:
        device_setup = True

        def __init__(self, host):
            assert host == "192.168.10.64"

        def get_channel_list(self):
            return SimpleNamespace(channels=[SimpleNamespace(channelno="110")])

        def get_channel_info(self, number):
            return SimpleNamespace(channelno=number, channelname="Sky Cinema Uno", channelsid="203", channeltype="video", sf="hd", channelimageurl="https://images.sky.com/channel.png")

        def get_recordings(self, limit, offset):
            assert (limit, offset) == (1000, 0)
            return SimpleNamespace(recordings=[SimpleNamespace(pvrid="p1", title="Film", channelname="Sky Cinema Uno", synopsis="Trama", summary="", season=1, episode=2, status="RECORDED", source="VOD", starttime=datetime(2026, 9, 17, tzinfo=timezone.utc), endtime=None, image_url="https://images.sky.com/film.jpg")])

        def get_quota(self):
            return SimpleNamespace(quota_max=1000, quota_used=250)

    monkeypatch.setattr(skyq, "_read_box", lambda host: {"apps": [{"id": "netflix", "title": "Netflix"}]})
    import pyskyqremote.skyq_remote
    monkeypatch.setattr(pyskyqremote.skyq_remote, "SkyQRemote", Remote)
    data = skyq._read_inventory("192.168.10.64")
    assert data["summary"] == {"channels": 1, "recordings": 1, "apps": 1, "recording_statuses": {"RECORDED": 1}, "recording_sources": {"VOD": 1}}
    assert data["channels"][0]["name"] == "Sky Cinema Uno"
    assert data["recordings"][0]["artwork_fingerprint"].startswith("skyq-")


def test_skyq_launches_only_an_exposed_decoder_app(monkeypatch) -> None:
    calls = []
    remote = SimpleNamespace(_remote_config=SimpleNamespace(device_access=SimpleNamespace(retrieve_information=lambda path: {"apps": [{"appId": "Netflix", "title": "Netflix", "blocked": False}]})))
    monkeypatch.setattr(skyq, "_remote", lambda host: remote)
    monkeypatch.setattr(skyq.httpx, "post", lambda url, **kwargs: calls.append((url, kwargs)) or SimpleNamespace(status_code=200))
    result = asyncio.run(skyq.launch_app({"enabled": True, "host": "192.168.10.64", "services": ["Netflix"]}, "Netflix"))
    assert result == {"ok": True, "provider": "skyq", "app_id": "Netflix"}
    assert calls[0][1]["params"] == {"appId": "Netflix"}


def test_skyq_rejects_app_not_exposed(monkeypatch) -> None:
    remote = SimpleNamespace(_remote_config=SimpleNamespace(device_access=SimpleNamespace(retrieve_information=lambda path: {"apps": [{"appId": "Netflix", "title": "Netflix", "blocked": False}]})))
    monkeypatch.setattr(skyq, "_remote", lambda host: remote)
    try:
        asyncio.run(skyq.launch_app({"enabled": True, "host": "192.168.10.64", "services": []}, "Netflix"))
    except ValueError as exc:
        assert "non disponibile" in str(exc)
    else:
        raise AssertionError("An app not exposed in admin must not be launched")
