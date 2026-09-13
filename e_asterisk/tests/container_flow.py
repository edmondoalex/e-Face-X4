"""Runs only inside the isolated CI Asterisk container."""

from __future__ import annotations

import http.client
import json
import pathlib
import re
import subprocess
import sys


def request(method: str, path: str, payload: dict | None = None, token: str = "") -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", 8350, timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    connection.request(method, path, body=json.dumps(payload) if payload is not None else None, headers=headers)
    response = connection.getresponse()
    status, value = response.status, json.loads(response.read())
    connection.close()
    return status, value


def endpoint_present() -> bool:
    output = subprocess.run(["asterisk", "-rx", "pjsip show endpoint 8302"], text=True, capture_output=True, check=False)
    return output.returncode == 0 and bool(re.search(r"(?m)^\s*Endpoint:\s+8302(?:/|\s)", output.stdout))


def main() -> None:
    mode = sys.argv[1]
    assert request("GET", "/v1/health")[0] == 200
    if mode == "provision":
        code = json.loads(pathlib.Path("/data/eface-pairing.json").read_text())["code"]
        status, paired = request("POST", "/v1/pair", {"code": code})
        assert status == 200, paired
        token = paired["token"]
        assert len(token) >= 32
        assert request("POST", "/v1/pair", {"code": code})[0] == 403
        phone = {"extension": "8302", "password": "CI_secret_for_8302_only_123456789", "name": "Test User"}
        status, result = request("PUT", "/v1/phones/ciuser", phone, token)
        assert (status, result) == (200, {"extension": "8302", "active": True}), (status, result)
        assert endpoint_present()
        assert pathlib.Path("/config/asterisk/eface/phones.json").is_file()
        print("Provisioning and Asterisk endpoint verified", flush=True)
    elif mode == "verify":
        assert request("GET", "/v1/health")[1]["paired"] is True
        assert endpoint_present()
        assert "8302" in pathlib.Path("/config/asterisk/eface/phones.json").read_text()
        print("Endpoint and credentials survived container recreation", flush=True)
    else:
        raise ValueError(mode)


if __name__ == "__main__":
    main()
