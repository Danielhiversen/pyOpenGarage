import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest

from opengarage import OpenGarage


class ResponseStub:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload
        self.json_calls = []

    async def json(self, content_type=None):
        self.json_calls.append(content_type)
        return self._payload


def make_client(session):
    return OpenGarage("http://device", "devkey", verify_ssl=False, websession=session)


def test_init_uses_provided_session():
    session = object()
    client = OpenGarage("http://device", "devkey", websession=session)
    assert client.websession is session


def test_init_does_not_create_session_eagerly():
    client = OpenGarage("http://device", "devkey")
    assert client.websession is None


@pytest.mark.asyncio
async def test_ensure_session_creates_session_lazily(monkeypatch):
    session = object()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda connector=None: session)
    client = OpenGarage("http://device", "devkey")

    await client._ensure_session()

    assert client.websession is session


def test_device_url_returns_devip():
    client = OpenGarage("http://device", "devkey", websession=SimpleNamespace())
    assert client.device_url == "http://device"


@pytest.mark.asyncio
async def test_close_connection_closes_session():
    session = SimpleNamespace(close=AsyncMock())
    client = make_client(session)

    await client.close_connection()

    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_state_calls_execute():
    session = SimpleNamespace()
    client = make_client(session)
    client._execute = AsyncMock(return_value={"door": "open"})

    result = await client.update_state()

    assert result == {"door": "open"}
    client._execute.assert_awaited_once_with("jc")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name,command",
    [
        ("push_button", "cc?dkey=devkey&click=1"),
        ("push_close_button", "cc?dkey=devkey&close=1"),
        ("push_open_button", "cc?dkey=devkey&open=1"),
        ("reboot", "cc?dkey=devkey&reboot=1"),
        ("ap_mode", "cc?dkey=devkey&apmode=1"),
    ],
)
async def test_command_methods_return_result(method_name, command):
    session = SimpleNamespace()
    client = make_client(session)
    client._execute = AsyncMock(return_value={"result": "ok"})

    method = getattr(client, method_name)
    result = await method()

    assert result == "ok"
    client._execute.assert_awaited_once_with(command, wrap_errors=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name,command",
    [
        ("push_button", "cc?dkey=devkey&click=1"),
        ("push_close_button", "cc?dkey=devkey&close=1"),
        ("push_open_button", "cc?dkey=devkey&open=1"),
        ("reboot", "cc?dkey=devkey&reboot=1"),
        ("ap_mode", "cc?dkey=devkey&apmode=1"),
    ],
)
async def test_command_methods_return_none_on_no_result(method_name, command):
    session = SimpleNamespace()
    client = make_client(session)
    client._execute = AsyncMock(return_value=None)

    method = getattr(client, method_name)
    result = await method()

    assert result is None
    client._execute.assert_awaited_once_with(command, wrap_errors=False)


@pytest.mark.asyncio
async def test_execute_success_returns_json():
    response = ResponseStub(200, {"ok": True})
    session = SimpleNamespace(get=AsyncMock(return_value=response))
    client = make_client(session)

    result = await client._execute("jc")

    assert result == {"ok": True}
    session.get.assert_awaited_once_with("http://device/jc")
    assert response.json_calls == [None]


@pytest.mark.asyncio
async def test_execute_non_200_returns_none_and_logs(caplog):
    response = ResponseStub(500, {"ok": False})
    session = SimpleNamespace(get=AsyncMock(return_value=response))
    client = make_client(session)

    caplog.set_level(logging.ERROR)
    result = await client._execute("jc")

    assert result is None
    assert any("resp code: 500" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_execute_retries_on_client_error_then_succeeds():
    response = ResponseStub(200, {"ok": True})
    session = SimpleNamespace(
        get=AsyncMock(side_effect=[aiohttp.ClientError("boom"), response])
    )
    client = make_client(session)

    result = await client._execute("jc")

    assert result == {"ok": True}
    assert session.get.await_count == 2


@pytest.mark.asyncio
async def test_execute_raises_after_client_error_retries_exhausted():
    session = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                aiohttp.ClientError("boom"),
                aiohttp.ClientError("boom"),
                aiohttp.ClientError("boom"),
            ]
        )
    )
    client = make_client(session)

    with pytest.raises(aiohttp.ClientError):
        await client._execute("jc")

    assert session.get.await_count == 3


@pytest.mark.asyncio
async def test_execute_retries_on_timeout_then_succeeds():
    response = ResponseStub(200, {"ok": True})
    session = SimpleNamespace(
        get=AsyncMock(side_effect=[asyncio.TimeoutError(), response])
    )
    client = make_client(session)

    result = await client._execute("jc")

    assert result == {"ok": True}
    assert session.get.await_count == 2


@pytest.mark.asyncio
async def test_execute_raises_after_timeout_retries_exhausted():
    session = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                asyncio.TimeoutError(),
                asyncio.TimeoutError(),
                asyncio.TimeoutError(),
            ]
        )
    )
    client = make_client(session)

    with pytest.raises(asyncio.TimeoutError):
        await client._execute("jc")

    assert session.get.await_count == 3
