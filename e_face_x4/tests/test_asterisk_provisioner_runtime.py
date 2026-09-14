from __future__ import annotations

import subprocess

import pytest

from asterisk_provisioner import runtime, startup
from asterisk_provisioner.managed_config import ManagedConfig


def prepared(tmp_path, monkeypatch):
    root = tmp_path / "asterisk"
    custom = root / "custom" / "pjsip_custom.conf"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"; existing\n")
    monkeypatch.setattr(startup, "asterisk_is_running", lambda: False)
    monkeypatch.setattr(startup, "assert_asterisk_ports_free", lambda: None)
    startup.prepare_before_asterisk(root)
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "Asterisk has fully booted", ""),
    )
    return root


def test_runtime_accepts_reconciled_empty_state(tmp_path, monkeypatch) -> None:
    root = prepared(tmp_path, monkeypatch)
    assert runtime.assert_ready(root).load() == {}


def test_runtime_refuses_modified_include_or_generated_config(tmp_path, monkeypatch) -> None:
    root = prepared(tmp_path, monkeypatch)
    config = ManagedConfig(root / "eface")
    config.pjsip.write_text("broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="non riconciliata"):
        runtime.assert_ready(root)
    config.reconcile_file()
    custom = root / "custom" / "pjsip_custom.conf"
    custom.write_bytes(custom.read_bytes() + b"; extra\n")
    with pytest.raises(RuntimeError, match="Include"):
        runtime.assert_ready(root)


def test_runtime_refuses_asterisk_not_ready(tmp_path, monkeypatch) -> None:
    root = prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "not ready"),
    )
    with pytest.raises(RuntimeError, match="non pronto"):
        runtime.assert_ready(root)
