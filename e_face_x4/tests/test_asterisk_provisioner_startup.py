from __future__ import annotations

import json
import socket

import pytest

from asterisk_provisioner.managed_config import ManagedConfig, render
from asterisk_provisioner import startup
from asterisk_provisioner.startup import assert_asterisk_ports_free, prepare_before_asterisk


@pytest.fixture(autouse=True)
def stopped_asterisk(monkeypatch) -> None:
    monkeypatch.setattr(startup, "asterisk_is_running", lambda: False)
    monkeypatch.setattr(startup, "assert_asterisk_ports_free", lambda: None)


def test_prepare_rejects_running_asterisk_before_writing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(startup, "asterisk_is_running", lambda: True)
    with pytest.raises(RuntimeError, match="già avviato"):
        prepare_before_asterisk(tmp_path / "asterisk")
    assert not (tmp_path / "asterisk").exists()


def test_port_guard_rejects_another_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(RuntimeError, match="altro PBX"):
            assert_asterisk_ports_free(((socket.SOCK_STREAM, listener.getsockname()[1]),))


def test_startup_requires_explicit_private_non_loopback_bind() -> None:
    startup.assert_private_bind_host("192.168.3.24")
    for host in ("", "0.0.0.0", "127.0.0.1", "8.8.8.8"):
        with pytest.raises(ValueError):
            startup.assert_private_bind_host(host)


def test_prepare_bootstraps_persistent_files_before_include_and_repeats(tmp_path) -> None:
    root = tmp_path / "config" / "asterisk"
    custom = root / "custom" / "pjsip_custom.conf"
    custom.parent.mkdir(parents=True)
    original = b"[8301]\ntype=endpoint\n"
    custom.write_bytes(original)

    assert prepare_before_asterisk(root) is True
    managed = ManagedConfig(root / "eface")
    assert managed.pjsip.read_text(encoding="utf-8") == render({})
    assert managed.load() == {}
    assert custom.read_bytes() == original + f"#include {managed.pjsip.as_posix()}\n".encode()
    assert prepare_before_asterisk(root) is False
    assert custom.read_bytes().count(b"#include ") == 1


def test_prepare_restores_interrupted_transaction_without_losing_include(tmp_path) -> None:
    root = tmp_path / "config" / "asterisk"
    custom = root / "custom" / "pjsip_custom.conf"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"; pre-existing\n")
    prepare_before_asterisk(root)
    managed = ManagedConfig(root / "eface")
    managed.state_backup.write_text("{}", encoding="utf-8")
    managed.pjsip_backup.write_text(render({}), encoding="utf-8")
    managed.state.write_text(json.dumps({"broken": {"extension": "8302"}}), encoding="utf-8")
    managed.pjsip.write_text("broken", encoding="utf-8")
    managed.pending.write_text("pending", encoding="utf-8")

    assert prepare_before_asterisk(root) is False
    assert managed.load() == {}
    assert managed.pjsip.read_text(encoding="utf-8") == render({})
    assert not managed.pending.exists()
    assert custom.read_bytes().count(b"#include ") == 1


def test_prepare_preserves_later_custom_changes_when_include_is_unique(tmp_path) -> None:
    root = tmp_path / "config" / "asterisk"
    custom = root / "custom" / "pjsip_custom.conf"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"; pre-existing\n")
    prepare_before_asterisk(root)
    custom.write_bytes(custom.read_bytes() + b"; user edit\n")
    assert prepare_before_asterisk(root) is False
    assert custom.read_bytes().endswith(b"; user edit\n")
