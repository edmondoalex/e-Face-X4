from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[2] / "e_asterisk" / "provisioner"
    sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("eface_pairing_test", path / "pairing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pairing_code_is_one_use_and_key_survives_restart(tmp_path) -> None:
    module = _module()
    persistent = tmp_path / "config" / "access.json"
    temporary = tmp_path / "data" / "pairing.json"
    pairing = module.Pairing(persistent, temporary)
    code = pairing.ensure_code()
    assert len(code) == 16
    with pytest.raises(ValueError):
        pairing.consume("0" * 16 if code != "0" * 16 else "1" * 16)
    assert pairing.token() == ""
    token = pairing.consume(code)
    assert len(token) >= 32
    assert not temporary.exists()
    assert module.Pairing(persistent, temporary).token() == token
    assert pairing.ensure_code() is None
    with pytest.raises(ValueError, match="associato"):
        pairing.consume(code)


def test_pairing_rejects_expired_code(tmp_path, monkeypatch) -> None:
    module = _module()
    pairing = module.Pairing(tmp_path / "access.json", tmp_path / "pairing.json")
    code = pairing.ensure_code()
    monkeypatch.setattr(module.time, "time", lambda: 10**12)
    with pytest.raises(ValueError, match="scaduto"):
        pairing.consume(code)
    assert pairing.token() == ""
