from __future__ import annotations

import httpx
import pytest

from app import sip_provisioner


def test_settings_reject_public_or_unpaired_destination(monkeypatch) -> None:
    monkeypatch.delenv("EFACE_PROVISION_URL", raising=False)
    monkeypatch.delenv("EFACE_PROVISION_TOKEN", raising=False)
    assert sip_provisioner.settings() is None
    monkeypatch.setenv("EFACE_PROVISION_TOKEN", "a" * 48)
    for url in ("https://example.com:8350", "http://192.168.3.24:8350", "http://172.30.32.1:8130", "http://127.0.0.1:8350/path"):
        monkeypatch.setenv("EFACE_PROVISION_URL", url)
        assert sip_provisioner.settings() is None
    monkeypatch.setenv("EFACE_PROVISION_URL", "http://172.30.32.1:8350")
    assert sip_provisioner.settings() == ("http://172.30.32.1:8350", "a" * 48)


@pytest.mark.asyncio
async def test_activate_needs_positive_response(monkeypatch) -> None:
    monkeypatch.setenv("EFACE_PROVISION_URL", "http://127.0.0.1:8350")
    monkeypatch.setenv("EFACE_PROVISION_TOKEN", "a" * 48)
    received = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(200, json={"extension": "8303", "active": True})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(sip_provisioner.httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(RuntimeError, match="non ha confermato"):
        await sip_provisioner.activate("mario", "8302", "secret", "Mario")
    assert received[0].headers["Authorization"] == "Bearer " + "a" * 48
    assert received[0].url.path == "/v1/phones/mario"


@pytest.mark.asyncio
async def test_pair_saves_key_only_after_valid_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_PROVISION_SECRET_PATH", str(tmp_path / "provisioner.json"))
    monkeypatch.delenv("EFACE_PROVISION_TOKEN", raising=False)
    monkeypatch.setenv("EFACE_PROVISION_URL", "http://127.0.0.1:8350")
    response_value = {"token": "short"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pair"
        return httpx.Response(200, json=response_value)

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(sip_provisioner.httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(RuntimeError, match="non valida"):
        await sip_provisioner.pair("A" * 16)
    assert not (tmp_path / "provisioner.json").exists()
    response_value["token"] = "k" * 48
    await sip_provisioner.pair("A" * 16)
    assert sip_provisioner.settings() == ("http://127.0.0.1:8350", "k" * 48)
