import asyncio

import httpx
import pytest

from app.doorbird_api import check_identity, history_image, live_image, live_video


@pytest.mark.asyncio
async def test_doorbird_sip_setup_backs_up_and_verifies(monkeypatch, tmp_path) -> None:
    from app import doorbird_api
    monkeypatch.setenv("EFACE_DOORBIRD_SIP_BACKUPS", str(tmp_path))
    states = [{"ENABLE": "1", "INCOMING_CALL_ENABLE": "1", "INCOMING_CALL_USER": "192.168.3.10", "AUTOCALL_DOORBELL_URL": "none"},
              {"ENABLE": "1", "INCOMING_CALL_ENABLE": "1", "INCOMING_CALL_USER": "192.168.3.24", "AUTOCALL_DOORBELL_URL": "sip:8290@192.168.3.24"}]
    changes = []
    async def status(*args):
        return states.pop(0)
    async def settings(*args):
        changes.append(args[-1])
    monkeypatch.setattr(doorbird_api, "sip_status", status)
    monkeypatch.setattr(doorbird_api, "_sip_settings", settings)
    previous = await doorbird_api.ensure_incoming_sip("cancello", "192.168.2.31", 80, "user", "password", "192.168.3.24")
    assert previous["incoming_call_user"] == "192.168.3.10"
    assert changes[0]["incoming_call_user"] == "192.168.3.24"
    assert changes[0]["autocall_doorbell_url"] == "sip:8290@192.168.3.24"
    assert len(list(tmp_path.glob("cancello.*.json"))) == 1


def test_doorbird_check_requires_challenge(monkeypatch) -> None:
    requests = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            requests.append((url, kwargs))
            return httpx.Response(200, json={"BHA": {"RETURNCODE": "1"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(check_identity("192.168.2.30", 80, "user", "private"))
    assert result == {"reachable": True, "authenticated": False, "reason": "no_auth_challenge"}
    assert len(requests) == 1
    assert "private" not in requests[0][0]


def test_doorbird_check_uses_digest_after_challenge(monkeypatch) -> None:
    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            calls.append(kwargs)
            status = 401 if len(calls) == 1 else 200
            return httpx.Response(status, json={"BHA": {"RETURNCODE": "1"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(check_identity("192.168.2.30", 80, "user", "private"))
    assert result == {"reachable": True, "authenticated": True, "reason": "ok"}
    assert calls[0] == {}
    assert isinstance(calls[1]["auth"], httpx.DigestAuth)


def test_live_image_uses_digest_and_rejects_non_jpeg(monkeypatch) -> None:
    original = httpx.AsyncClient
    requests = []

    def handle(request):
        requests.append(request)
        if "authorization" not in request.headers:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest realm="DoorBird", nonce="abc", qop="auth"'})
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=b"\xff\xd8\xffimage")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert asyncio.run(live_image("192.168.2.30", 80, "user", "private")) == b"\xff\xd8\xffimage"
    assert len(requests) == 2
    assert all("private" not in str(request.url) for request in requests)

    def invalid(_request):
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"<html>")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(invalid), **kwargs))
    try:
        asyncio.run(live_image("192.168.2.30", 80, "user", "private"))
    except RuntimeError:
        pass
    else:
        assert False, "HTML must not be exposed as an image"


@pytest.mark.parametrize("event", ["doorbell", "motionsensor"])
def test_history_image_preserves_official_doorbird_event(monkeypatch, event) -> None:
    original = httpx.AsyncClient
    requests = []

    def handle(request):
        requests.append(request)
        if "authorization" not in request.headers:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest realm="DoorBird", nonce="abc", qop="auth"'})
        return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=b"\xff\xd8\xffhistory")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert asyncio.run(history_image("192.168.2.30", 80, "user", "private", event)) == b"\xff\xd8\xffhistory"
    assert len(requests) == 2
    assert all(request.url.params["event"] == event for request in requests)
    assert all(request.url.params["index"] == "1" for request in requests)


def test_live_video_uses_digest_and_checks_multipart_type(monkeypatch) -> None:
    original = httpx.AsyncClient
    requests = []

    def handle(request):
        requests.append(request)
        if "authorization" not in request.headers:
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest realm="DoorBird", nonce="abc", qop="auth"'})
        return httpx.Response(200, headers={"Content-Type": "multipart/x-mixed-replace; boundary=my-boundary"}, content=b"--my-boundary\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\xff")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))

    async def read_video():
        client, response, content_type = await live_video("192.168.2.30", 80, "user", "private")
        try:
            return content_type, response.status_code
        finally:
            await response.aclose()
            await client.aclose()

    content_type, status = asyncio.run(read_video())
    assert content_type == "multipart/x-mixed-replace; boundary=my-boundary"
    assert status == 200
    assert len(requests) == 2
    assert all("private" not in str(request.url) for request in requests)

    def invalid(_request):
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"<html>")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(invalid), **kwargs))
    try:
        asyncio.run(live_video("192.168.2.30", 80, "user", "private"))
    except RuntimeError:
        pass
    else:
        assert False, "Non-MJPEG response must be rejected"
