from __future__ import annotations

import asyncio

from app import skyq_settings
from app.connectors import skyq


def test_skyq_settings_are_native_and_validated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EFACE_SKYQ_CONFIG", str(tmp_path / "skyq.json"))
    saved = skyq_settings.save({"enabled": True, "host": "192.168.10.64", "name": "Sky Q Sala", "control4_room_id": 61, "control4_source_id": 244, "command_provider": "control4", "services": ["Netflix", "Unknown"]})
    assert saved["command_provider"] == "native"
    assert saved["services"] == ["Netflix"]
    assert skyq_settings.load()["control4_source_id"] == 244


def test_skyq_overlay_replaces_metadata_and_exposes_native_remote() -> None:
    providers = [{"id": "control4", "items": [{"registry_id": "c4room:61", "kind": "media_player", "source": "Sky Q", "active_source_id": 244, "source_options": [{"source_id": 244, "experience": "watch", "remote_actions": []}], "capabilities": {"artwork": False}}]}]
    data = {"status": "online", "title": "Film", "channel": "Sky Cinema", "channel_number": "301", "description": "Trama", "app": "EPG_UI", "artwork": "https://it.imageservice.sky.com/example.jpg"}
    assert skyq.overlay_control4(providers, data, {"control4_room_id": 61, "control4_source_id": 244, "services": ["Netflix"]})
    item = providers[0]["items"][0]
    assert item["title"] == "Film"
    assert item["description"] == "Trama"
    assert item["skyq_artwork"] is True
    assert "custom:PROGRAM_A" in item["source_options"][0]["remote_actions"]


def test_skyq_command_maps_remote_button(monkeypatch) -> None:
    pressed = []

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
