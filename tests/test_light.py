"""Tests for OpenGarage opener light control."""

import asyncio
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest

from opengarage import OpenGarage
from opengarage.errors import TransportError, UnsupportedFeatureError
from opengarage.state import normalize_state


@pytest.fixture
def client():
    """Create a client without connecting to a device."""
    return OpenGarage("http://device", "abc123&=?/", websession=object())


@pytest.mark.parametrize(
    "response,expected",
    [({"result": 1}, 1), ({"result": 2}, 2), ({}, None), (None, None)],
)
async def test_toggle_light(client, response, expected):
    """Pass the key as a query parameter and never retry a toggle."""
    client.get_state = AsyncMock(return_value=normalize_state({"light": 0}))
    client._execute = AsyncMock(return_value=response)

    assert await client.toggle_light() == expected

    client._execute.assert_awaited_once_with(
        "cc?dkey=abc123%26%3D%3F%2F&light=toggle", retry=0, wrap_errors=True
    )


@pytest.mark.parametrize("current,requested", [(0, False), (1, True)])
async def test_set_light_is_idempotent(client, current, requested):
    """Do not toggle a light that already has the requested state."""
    client._execute = AsyncMock(return_value={"light": current})

    assert await client.set_light(requested) is None

    client._execute.assert_awaited_once_with("jc", wrap_errors=True)


@pytest.mark.parametrize("current,requested", [(0, True), (1, False)])
@pytest.mark.parametrize(
    "response,expected",
    [({"result": 1}, 1), ({"result": 2}, 2), ({"result": 3}, 3), (None, None)],
)
async def test_set_light_when_state_differs(client, current, requested, response, expected):
    """Read the state before toggling and preserve command failures."""
    client._execute = AsyncMock(side_effect=[{"light": current}, response])

    assert await client.set_light(requested) == expected

    assert client._execute.await_count == 2
    client._execute.assert_awaited_with(
        "cc?dkey=abc123%26%3D%3F%2F&light=toggle", retry=0, wrap_errors=True
    )


@pytest.mark.parametrize(
    "state", [None, {"door": 0}, {"light": None}, {"light": "unknown"}]
)
async def test_set_light_without_valid_state(client, state):
    """An absent or unknown light state must never trigger a toggle."""
    client._execute = AsyncMock(return_value=state)

    with pytest.raises(UnsupportedFeatureError):
        await client.set_light(True)

    client._execute.assert_awaited_once_with("jc", wrap_errors=True)


@pytest.mark.parametrize("initial,requested", [(0, True), (1, False)])
async def test_concurrent_set_light(client, initial, requested):
    """Two same-state commands must not toggle twice from one snapshot."""
    state = initial

    async def read_state():
        snapshot = normalize_state({"light": state})
        await asyncio.sleep(0)
        return snapshot

    async def execute(command, retry, wrap_errors):
        nonlocal state
        state = 1 - state
        await asyncio.sleep(0)
        return {"result": 1}

    client.get_state = AsyncMock(side_effect=read_state)
    client._execute = AsyncMock(side_effect=execute)

    results = await asyncio.gather(
        client.set_light(requested), client.set_light(requested)
    )

    assert results == [1, None]

    assert state == int(requested)
    assert client.get_state.await_count == 2
    client._execute.assert_awaited_once()


@pytest.mark.parametrize("error", [aiohttp.ClientError, asyncio.TimeoutError])
async def test_toggle_does_not_retry_network_failure(client, error):
    """An uncertain command outcome must not cause a second toggle."""
    client.get_state = AsyncMock(return_value=normalize_state({"light": 0}))
    client.websession = SimpleNamespace(get=AsyncMock(side_effect=error))

    with pytest.raises(TransportError):
        await client.toggle_light()

    client.websession.get.assert_awaited_once_with(
        "http://device/cc?dkey=abc123%26%3D%3F%2F&light=toggle",
    )


async def test_set_light_lock_released_after_error(client):
    """A failed state read must not block subsequent commands."""
    client._execute = AsyncMock(side_effect=[aiohttp.ClientError(), {"light": 1}])

    with pytest.raises(aiohttp.ClientError):
        await client.set_light(True)

    assert await asyncio.wait_for(client.set_light(True), timeout=1) is None


@pytest.mark.parametrize(
    "commands,expected_state,expected_toggles",
    [
        (("on", "on"), 1, 1),
        (("off", "off"), 0, 0),
        (("on", "off"), 0, 2),
        (("off", "on"), 1, 1),
        (("toggle", "on"), 1, 1),
        (("on", "toggle"), 0, 2),
        (("toggle", "toggle"), 0, 2),
    ],
)
def test_light_commands_after_loop_start(commands, expected_state, expected_toggles):
    """A client constructed before the running loop must serialize light calls."""
    construction_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(construction_loop)
    try:
        connection = OpenGarage("http://device", "key", websession=object())
    finally:
        asyncio.set_event_loop(None)
        construction_loop.close()

    state = 0

    async def read_state():
        snapshot = normalize_state({"light": state})
        await asyncio.sleep(0)
        return snapshot

    async def execute(command, retry, wrap_errors):
        nonlocal state
        state = 1 - state
        await asyncio.sleep(0)
        return {"result": 1}

    connection.get_state = AsyncMock(side_effect=read_state)
    connection._execute = AsyncMock(side_effect=execute)
    actions = {
        "on": partial(connection.set_light, True),
        "off": partial(connection.set_light, False),
        "toggle": connection.toggle_light,
    }

    async def run_commands():
        return await asyncio.wait_for(
            asyncio.gather(*(actions[command]() for command in commands)), timeout=1
        )

    results = asyncio.run(run_commands())
    assert results.count(1) == expected_toggles
    assert results.count(None) == 2 - expected_toggles
    assert state == expected_state
    assert connection._execute.await_count == expected_toggles
