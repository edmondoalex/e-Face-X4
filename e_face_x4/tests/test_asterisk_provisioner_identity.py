from __future__ import annotations

import os
import shutil

import pytest

from asterisk_provisioner.identity import SiteIdentity


def test_site_identity_survives_repeated_boot(tmp_path) -> None:
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL unavailable")
    directory = tmp_path / "config" / "asterisk" / "eface"
    directory.mkdir(parents=True)
    first = SiteIdentity(directory).ensure()
    second = SiteIdentity(directory).ensure()
    assert first.certificate_sha256 == second.certificate_sha256
    assert first.token == second.token
    assert len(first.token) >= 48
    assert first.certificate.is_file() and first.private_key.is_file()
    if os.name == "posix":
        assert first.private_key.stat().st_mode & 0o077 == 0
        assert (directory / "provisioner.token").stat().st_mode & 0o077 == 0


def test_partial_identity_fails_closed_without_rotating_cert(tmp_path) -> None:
    directory = tmp_path / "eface"
    directory.mkdir()
    (directory / "provisioner.token").write_text("x" * 64, encoding="ascii")
    with pytest.raises(RuntimeError, match="incompleta"):
        SiteIdentity(directory).ensure()
    assert not (directory / "provisioner.crt").exists()
