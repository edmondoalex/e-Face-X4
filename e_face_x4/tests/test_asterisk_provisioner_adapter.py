from __future__ import annotations

import subprocess

import pytest

from asterisk_provisioner import asterisk_adapter as adapter


def test_endpoint_parser_uses_real_asterisk_response_shape(monkeypatch) -> None:
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(
            args, 0,
            "Endpoint:  <Endpoint/CID.....................................>  <State.....>\n"
            "Endpoint:  8302/8302                                      Unavailable\n", "",
        )

    monkeypatch.setattr(adapter.subprocess, "run", run)
    assert adapter.endpoint_exists("8302") is True
    assert commands == [["asterisk", "-rx", "pjsip show endpoint 8302"]]


def test_missing_endpoint_is_distinct_from_unrecognized_output(monkeypatch) -> None:
    def missing(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "Unable to find object 8302.\n", "")

    monkeypatch.setattr(adapter.subprocess, "run", missing)
    assert adapter.endpoint_exists("8302") is False

    def unexpected(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "Something else\n", "")

    monkeypatch.setattr(adapter.subprocess, "run", unexpected)
    with pytest.raises(RuntimeError, match="non riconosciuta"):
        adapter.endpoint_exists("8302")


@pytest.mark.parametrize("extension", ["8301", "8290", "8400", "8302;reload", "../8302"])
def test_adapter_rejects_unmanaged_extension_before_cli(extension, monkeypatch) -> None:
    monkeypatch.setattr(adapter.subprocess, "run", lambda *args, **kwargs: pytest.fail("CLI called"))
    with pytest.raises(ValueError):
        adapter.endpoint_exists(extension)


def test_reload_uses_fixed_command_and_checks_failure(monkeypatch) -> None:
    calls = []

    def good(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "Module reloaded successfully", "")

    monkeypatch.setattr(adapter.subprocess, "run", good)
    adapter.reload_pjsip()
    assert calls == [["asterisk", "-rx", "pjsip reload"]]

    def bad(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "No such command 'pjsip reload'", "")

    monkeypatch.setattr(adapter.subprocess, "run", bad)
    with pytest.raises(RuntimeError, match="fallita"):
        adapter.reload_pjsip()
