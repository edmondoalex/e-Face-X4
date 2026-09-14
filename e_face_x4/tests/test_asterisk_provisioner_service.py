from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from asterisk_provisioner.managed_config import ManagedConfig
from asterisk_provisioner.service import make_handler


def test_service_requires_real_token(tmp_path) -> None:
    with pytest.raises(ValueError, match="Token"):
        make_handler(ManagedConfig(tmp_path), "short", lambda: None, lambda _: False)


def test_restricted_service_auth_validation_and_rollback(tmp_path) -> None:
    config = ManagedConfig(tmp_path)
    active: set[str] = set()
    token = "local-test-token-" + "x" * 32

    def reload_pjsip() -> None:
        active.clear()
        active.update(record["extension"] for record in config.load().values())

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(config, token, reload_pjsip, active.__contains__)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def call(method: str, path: str, payload: dict | None = None, auth: bool = True) -> tuple[int, dict]:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    try:
        phone = {
            "username": "ekonex", "extension": "8302",
            "password": "A_secure_personal_secret_123456789", "name": "Ekonex",
        }
        assert call("POST", "/v1/phones", phone, auth=False)[0] == 401
        assert not config.state.exists()
        assert call("POST", "/v1/phones", {**phone, "extension": "8301"})[0] == 400
        assert call("POST", "/v1/phones", {**phone, "file": "/etc/asterisk/pjsip.conf"})[0] == 400
        status, result = call("POST", "/v1/phones", phone)
        assert (status, result) == (200, {"extension": "8302", "provisioned": True})
        assert "8302" in active
        assert call("DELETE", "/v1/phones/../8301")[0] == 404
        assert call("DELETE", "/v1/phones/ekonex") == (200, {"removed": True})
        assert "8302" not in active
        voip = {"username": "voip_8350", "extension": "8350", "password": "A_secure_voip_secret_123456789",
                "name": "Studio", "profile": "voip_video"}
        assert call("POST", "/v1/voip-phones", voip, auth=False)[0] == 401
        assert call("POST", "/v1/voip-phones", {**voip, "profile": "browser"})[0] == 400
        assert call("POST", "/v1/voip-phones", voip) == (200, {"extension": "8350", "provisioned": True})
        assert call("GET", "/v1/voip-phones") == (200, {"phones": [{"extension": "8350", "name": "Studio", "profile": "voip_video"}]})
        assert call("DELETE", "/v1/phones/voip_8350")[0] == 404
        assert call("DELETE", "/v1/voip-phones/voip_8350") == (200, {"removed": True})
        assert config.load() == {}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
