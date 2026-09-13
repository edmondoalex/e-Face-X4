import asyncio

import pytest

from app.asterisk_ami import AMIError, AMIActionError, _request, action


def test_ami_request_rejects_header_injection() -> None:
    with pytest.raises(ValueError):
        _request({"Action": "GetConfig\r\nSecret: stolen"})
    with pytest.raises(ValueError):
        _request({"Bad\nHeader": "value"})


def test_ami_action_error_classifies_without_exposing_server_message() -> None:
    error = AMIActionError("Category not found")
    assert error.reason == "category"
    assert "Category not found" not in str(error)


def test_ami_login_and_action() -> None:
    async def run() -> None:
        received = []

        async def handler(reader, writer):
            writer.write(b"Asterisk Call Manager/5.0.0\r\n")
            await writer.drain()
            received.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"Response: Success\r\nMessage: Authentication accepted\r\n\r\n")
            await writer.drain()
            received.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"Response: Success\r\nLine-000000: username=8301\r\n\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            result = await action("127.0.0.1", port, "eface", "private", {"Action": "GetConfig", "Filename": "pjsip_custom.conf"})
            assert result["Line-000000"] == "username=8301"
            assert b"Secret: private" in received[0]
            assert b"Secret: private" not in received[1]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_ami_rejects_failed_login() -> None:
    async def run() -> None:
        async def handler(reader, writer):
            writer.write(b"Asterisk Call Manager/5.0.0\r\n")
            await writer.drain()
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"Response: Error\r\nMessage: Authentication failed\r\n\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        try:
            with pytest.raises(AMIError, match="Autenticazione"):
                await action("127.0.0.1", server.sockets[0].getsockname()[1], "eface", "private", {"Action": "GetConfig"})
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
