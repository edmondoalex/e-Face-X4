"""Persistent per-installation TLS identity and API token for Asterisk.

Never copy these files into an image or repository. Pairing the fingerprint
and token with e-Face is a separate authenticated installation step.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import ssl
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .managed_config import _atomic_write

_TOKEN = re.compile(r"[A-Za-z0-9_-]{48,128}\Z")


@dataclass(frozen=True)
class Identity:
    certificate: Path
    private_key: Path
    token: str
    certificate_sha256: str


class SiteIdentity:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.certificate = directory / "provisioner.crt"
        self.private_key = directory / "provisioner.key"
        self.token_file = directory / "provisioner.token"

    def ensure(self) -> Identity:
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise RuntimeError("Directory identità persistente non disponibile")
        files = (self.certificate, self.private_key, self.token_file)
        if any(path.is_symlink() for path in files):
            raise RuntimeError("Identità provisioner non valida")
        existing = tuple(path.is_file() for path in files)
        if any(existing) and not all(existing):
            raise RuntimeError("Identità provisioner incompleta: recupero manuale necessario")
        if not any(existing):
            self._generate()
        if os.name == "posix" and any(
            stat.S_IMODE(path.stat().st_mode) & 0o077
            for path in (self.private_key, self.token_file)
        ):
            raise RuntimeError("Permessi identità provisioner troppo ampi")
        token = self.token_file.read_text(encoding="ascii").strip()
        if not _TOKEN.fullmatch(token):
            raise RuntimeError("Token provisioner non valido")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.certificate), str(self.private_key))
        pem = self.certificate.read_text(encoding="ascii")
        der = ssl.PEM_cert_to_DER_cert(pem)
        return Identity(self.certificate, self.private_key, token, hashlib.sha256(der).hexdigest())

    def _generate(self) -> None:
        suffix = secrets.token_hex(8)
        temporary_cert = self.directory / f".provisioner.{suffix}.crt"
        temporary_key = self.directory / f".provisioner.{suffix}.key"
        try:
            descriptor = os.open(temporary_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)
            subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes",
                 "-keyout", str(temporary_key), "-out", str(temporary_cert),
                 "-subj", "/CN=e-Face-Asterisk", "-days", "3650"],
                capture_output=True, check=True, timeout=30,
            )
            os.chmod(temporary_key, 0o600)
            os.chmod(temporary_cert, 0o600)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(temporary_cert), str(temporary_key))
            temporary_cert.replace(self.certificate)
            temporary_key.replace(self.private_key)
            _atomic_write(self.token_file, secrets.token_urlsafe(48) + "\n")
        finally:
            temporary_cert.unlink(missing_ok=True)
            temporary_key.unlink(missing_ok=True)
