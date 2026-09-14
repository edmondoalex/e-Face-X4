from __future__ import annotations

from pathlib import Path

import pytest


def test_controlled_addon_is_isolated_and_disabled_by_default() -> None:
    yaml = pytest.importorskip("yaml")
    addon = Path(__file__).resolve().parents[2] / "e_face_asterisk"
    config = yaml.safe_load((addon / "config.yaml").read_text(encoding="utf-8"))
    assert config["slug"] == "asterisk_eface"
    assert config["options"]["eface_provisioner_enabled"] is False
    assert config["host_network"] is True
    assert "image" not in config  # Build local Dockerfile, never fetch upstream by mistake.
    assert "all_addon_configs:rw" not in config["map"]
    assert (addon / "asterisk_provisioner" / "runtime.py").is_file()
    assert (addon / "rootfs" / "etc" / "services.d" / "eface_provisioner" / "down").is_file()
    dockerfile = (addon / "Dockerfile").read_text(encoding="utf-8")
    assert "ghcr.io/tech7fox/asterisk-hass-addon:6.2.0" in dockerfile
    assert "COPY asterisk_provisioner/" in dockerfile
