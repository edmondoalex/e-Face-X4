from __future__ import annotations

import http.client
import importlib.util
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path


def _server_module():
    path = Path(__file__).resolve().parents[2] / "e_asterisk" / "provisioner"
    sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("eface_provisioner_server_test", path / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provisioner_api_rejects_unauthorized_and_limits_actions(monkeypatch) -> None:
    module = _server_module()
    monkeypatch.setattr(module, "_token", lambda: "a" * 48)
    monkeypatch.setattr(module, "_include_ready", lambda: True)
    calls = []

    class FakeConfig:
        def upsert(self, *args):
            calls.append(args[:4])

        def revoke(self, *args):
            calls.append(("revoke", args[0]))
            return True

    monkeypatch.setattr(module, "CONFIG", FakeConfig())
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        def call(method, path, payload=None, token=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            body = json.dumps(payload).encode() if payload is not None else None
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            result = response.status, json.loads(response.read())
            connection.close()
            return result

        phone = {"extension": "8302", "password": "A_secure_personal_secret_123456789", "name": "Ekonex"}
        assert call("PUT", "/v1/phones/ekonex", phone)[0] == 401
        assert call("PUT", "/v1/phones/../../etc/passwd", phone, "a" * 48)[0] == 404
        assert call("PUT", "/v1/phones/ekonex", {"extension": "8302"}, "a" * 48)[0] == 400
        status, result = call("PUT", "/v1/phones/ekonex", phone, "a" * 48)
        assert (status, result) == (200, {"extension": "8302", "active": True})
        assert phone["password"] not in json.dumps(result)
        assert calls[0] == ("ekonex", "8302", phone["password"], "Ekonex")
        assert call("DELETE", "/v1/phones/ekonex", token="a" * 48) == (200, {"removed": True})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
