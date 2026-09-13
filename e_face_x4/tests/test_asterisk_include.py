from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[2] / "e_asterisk" / "provisioner" / "ensure_include.py"
    spec = importlib.util.spec_from_file_location("eface_include_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_custom_pjsip_include_is_backed_up_once(tmp_path) -> None:
    module = _module()
    custom = tmp_path / "custom"
    custom.mkdir()
    target = custom / "pjsip.conf"
    target.write_text("[global]\ntype=global\n", encoding="utf-8")
    active = tmp_path / "pjsip.conf"
    active.symlink_to(target)
    assert module.ensure_include(active, custom) is True
    assert module.INCLUDE in target.read_text(encoding="utf-8")
    backup = custom / "pjsip.conf.before-eface.bak"
    assert backup.read_text(encoding="utf-8") == "[global]\ntype=global\n"
    assert module.ensure_include(active, custom) is False
    assert target.read_text(encoding="utf-8").count(module.INCLUDE) == 1


def test_refuses_unmanaged_file_without_include(tmp_path) -> None:
    module = _module()
    custom = tmp_path / "custom"
    custom.mkdir()
    active = tmp_path / "pjsip.conf"
    active.write_text("[global]\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="non gestibile"):
        module.ensure_include(active, custom)
    assert active.read_text(encoding="utf-8") == "[global]\n"
