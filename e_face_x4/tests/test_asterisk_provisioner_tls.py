from __future__ import annotations

import hashlib
import shutil
import ssl
import subprocess
import threading

import pytest

from app.asterisk_provisioner_client import ProvisionerClient
from asterisk_provisioner.managed_config import ManagedConfig
from asterisk_provisioner.service import make_https_server


def certificate(tmp_path):
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL unavailable for local TLS fixture")
    cert = tmp_path / "test.crt"
    key = tmp_path / "test.key"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost", "-days", "1"],
        check=True, capture_output=True, timeout=15,
    )
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
    return cert, key, hashlib.sha256(der).hexdigest()


def test_pinned_tls_rejects_wrong_certificate_before_sending_secret(tmp_path) -> None:
    cert, key, fingerprint = certificate(tmp_path)
    config = ManagedConfig(tmp_path / "state")
    active: set[str] = set()
    token = "site-specific-test-token-" + "x" * 32

    def reload_pjsip() -> None:
        active.clear()
        active.update(record["extension"] for record in config.load().values())

    server = make_https_server(
        config, token, reload_pjsip, active.__contains__, "127.0.0.1", 0, cert, key,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        wrong = ProvisionerClient("127.0.0.1", server.server_port, "0" * 64, token)
        with pytest.raises(RuntimeError, match="Certificato"):
            wrong.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex")
        assert not config.state.exists()

        client = ProvisionerClient("127.0.0.1", server.server_port, fingerprint, token)
        client.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex")
        assert config.load()["ekonex"]["extension"] == "8302"
        assert client.revoke("ekonex") is True
        assert config.load() == {}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_tls_client_rejects_public_target_and_bad_pin() -> None:
    with pytest.raises(ValueError, match="non locale"):
        ProvisionerClient("8.8.8.8", 9443, "a" * 64, "x" * 32)
    with pytest.raises(ValueError, match="Impronta"):
        ProvisionerClient("192.168.3.24", 9443, "not-a-pin", "x" * 32)
