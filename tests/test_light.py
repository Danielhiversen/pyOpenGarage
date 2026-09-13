"""Tests for OpenGarage opener light control."""

import asyncio
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest

from opengarage import OpenGarage


@pytest.fixture
def client():
    """Create a client without connecting to a device."""
    return OpenGarage("http://device", "abc123&=?/", websession=object())


@pytest.mark.parametrize(
    "response,expected",
    [({"result": 1}, 1), ({"result": 2}, 2), ({}, None), (None, None)],
)
async def test_toggle_light(client, response, expected):
    """Encode the key, preserve result codes, and never retry a toggle."""
    client._execute = AsyncMock(return_value=response)

    assert await client.toggle_light() == expected

    client._execute.assert_awaited_once_with(
        "cc?dkey=abc123%26%3D%3F%2F&light=toggle", retry=0
    )


@pytest.mark.parametrize("current,requested", [(0, False), (1, True)])
async def test_set_light_is_idempotent(client, current, requested):
    """Do not toggle a light that already has the requested state."""
    client._execute = AsyncMock(return_value={"light": current})

    assert await client.set_light(requested) == 1

    client._execute.assert_awaited_once_with("jc")


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
        "cc?dkey=abc123%26%3D%3F%2F&light=toggle", retry=0
    )


@pytest.mark.parametrize(
    "state", [None, {"door": 0}, {"light": None}, {"light": -1}, {"light": "0"}]
)
async def test_set_light_without_valid_state(client, state):
    """An absent or unknown light state must never trigger a toggle."""
    client._execute = AsyncMock(return_value=state)

    assert await client.set_light(True) is None

    client._execute.assert_awaited_once_with("jc")


@pytest.mark.parametrize("initial,requested", [(0, True), (1, False)])
async def test_concurrent_set_light(client, initial, requested):
    """Two same-state commands must not toggle twice from one snapshot."""
    state = initial

    async def read_state():
        snapshot = {"light": state}
        await asyncio.sleep(0)
        return snapshot

    async def execute(command, retry):
        nonlocal state
        state = 1 - state
        await asyncio.sleep(0)
        return {"result": 1}

    client.update_state = AsyncMock(side_effect=read_state)
    client._execute = AsyncMock(side_effect=execute)

    results = await asyncio.gather(
        client.set_light(requested), client.set_light(requested)
    )

    assert results == [1, 1]

    assert state == int(requested)
    assert client.update_state.await_count == 2
    client._execute.assert_awaited_once()


@pytest.mark.parametrize("error", [aiohttp.ClientError, asyncio.TimeoutError])
async def test_toggle_does_not_retry_network_failure(client, error):
    """An uncertain command outcome must not cause a second toggle."""
    client.websession = SimpleNamespace(get=AsyncMock(side_effect=error))

    with pytest.raises(error):
        await client.toggle_light()

    client.websession.get.assert_awaited_once()


async def test_set_light_lock_released_after_error(client):
    """A failed state read must not block subsequent commands."""
    client._execute = AsyncMock(side_effect=[aiohttp.ClientError(), {"light": 1}])

    with pytest.raises(aiohttp.ClientError):
        await client.set_light(True)

    assert await asyncio.wait_for(client.set_light(True), timeout=1) == 1


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
        snapshot = {"light": state}
        await asyncio.sleep(0)
        return snapshot

    async def execute(command, retry):
        nonlocal state
        state = 1 - state
        await asyncio.sleep(0)
        return {"result": 1}

    connection.update_state = AsyncMock(side_effect=read_state)
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

    assert asyncio.run(run_commands()) == [1, 1]
    assert state == expected_state
    assert connection._execute.await_count == expected_toggles
