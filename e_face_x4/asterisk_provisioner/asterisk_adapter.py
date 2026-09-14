"""Narrow Asterisk CLI adapter for e-Face-owned personal SIP extensions.

The commands have fixed argument shapes and never use a shell. This adapter
must run inside the Asterisk add-on after the persistent include is installed.
"""

from __future__ import annotations

import re
import subprocess

_EXTENSION = re.compile(r"83(?:0[2-9]|[1-9][0-9])\Z")


def _check_extension(extension: str) -> None:
    if not _EXTENSION.fullmatch(extension):
        raise ValueError("Interno fuori dalla fascia e-Face")


def reload_pjsip() -> None:
    result = subprocess.run(
        ["asterisk", "-rx", "pjsip reload"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode != 0 or "No such command" in result.stdout + result.stderr:
        raise RuntimeError("Ricarica PJSIP fallita")


def endpoint_exists(extension: str) -> bool:
    _check_extension(extension)
    result = subprocess.run(
        ["asterisk", "-rx", f"pjsip show endpoint {extension}"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Verifica endpoint PJSIP fallita")
    output = result.stdout + result.stderr
    if re.search(rf"(?m)^Unable to find object {re.escape(extension)}\.\s*$", output):
        return False
    if re.search(rf"(?m)^\s*Endpoint:\s+{re.escape(extension)}/{re.escape(extension)}(?:\s|$)", output):
        return True
    raise RuntimeError("Risposta endpoint PJSIP non riconosciuta")
