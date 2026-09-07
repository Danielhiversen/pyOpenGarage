# OpenGarage Firmware v1.2.x Expansion Implementation Plan

**Goal:** Add capability-aware state parsing and optional v1.2.x actions while preserving the existing OpenGarage client API.

**Architecture:** Keep the single `OpenGarage` façade but introduce lightweight helper modules (dispatcher, state normalization, error types). Existing methods continue to return raw responses and behavior, while new capability-aware methods use normalized state + structured errors for unsupported features and transport failures. This aligns with the design’s thin compatibility layer and avoids a full rewrite.

**Design:** `thoughts/shared/designs/2026-05-22-opengarage-firmware-1-2-4-design.md`

---

## Dependency Graph

```
Batch 1 (parallel): 1.1, 1.2, 1.3 [foundation - no deps]
Batch 2 (parallel): 2.1 [core - depends on batch 1]
```

---

## Batch 1: Foundation (parallel - 3 implementers)

All tasks in this batch have NO dependencies and run simultaneously.

### Task 1.1: Client Error Types
**File:** `opengarage/errors.py`
**Test:** `tests/test_errors.py`
**Depends:** none

```python
import unittest

from opengarage.errors import (
    OpenGarageError,
    ResponseError,
    TransportError,
    UnsupportedFeatureError,
)


class TestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(TransportError, OpenGarageError))
        self.assertTrue(issubclass(ResponseError, OpenGarageError))
        self.assertTrue(issubclass(UnsupportedFeatureError, OpenGarageError))

    def test_response_error_fields(self):
        err = ResponseError(status=500, url="http://example/jc")
        self.assertEqual(err.status, 500)
        self.assertEqual(err.url, "http://example/jc")
        self.assertIn("500", str(err))

    def test_unsupported_feature_message(self):
        err = UnsupportedFeatureError("Light control not supported")
        self.assertIn("Light control", str(err))


if __name__ == "__main__":
    unittest.main()
```

```python
class OpenGarageError(Exception):
    """Base error for OpenGarage client failures."""


class TransportError(OpenGarageError):
    """Transport-level failures (timeout/network) after retries."""


class ResponseError(OpenGarageError):
    """HTTP response errors with status context."""

    def __init__(self, status, url):
        super().__init__("OpenGarage response error: %s for %s" % (status, url))
        self.status = status
        self.url = url


class UnsupportedFeatureError(OpenGarageError):
    """Raised when a capability-gated action is unavailable."""
```

**Verify:** `python -m unittest tests/test_errors.py`
**Commit:** `feat(core): add OpenGarage error types`

---

### Task 1.2: State Normalizer + Capability Detection
**File:** `opengarage/state.py`
**Test:** `tests/test_state.py`
**Depends:** none

```python
import unittest

from opengarage.state import NormalizedState, normalize_state


class TestStateNormalizer(unittest.TestCase):
    def test_known_door_states(self):
        payload = {"door": 0}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "closed")

        payload = {"door": 1}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "open")

        payload = {"door": 2}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "opening")

        payload = {"door": 3}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "closing")

        payload = {"door": 4}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "stopped")

    def test_unknown_door_state(self):
        payload = {"door": 99}
        state = normalize_state(payload)
        self.assertEqual(state.door_state, "unknown")

    def test_optional_fields_and_capabilities(self):
        payload = {
            "door": 1,
            "secv": 2,
            "has_swrx": 1,
            "light": 1,
            "lock": 0,
            "obstruct": 1,
            "nopenings": 42,
            "pemu": 7,
        }
        state = normalize_state(payload)
        self.assertTrue(state.capabilities["security_plus"])
        self.assertTrue(state.capabilities["light_control"])
        self.assertTrue(state.capabilities["lock_control"])
        self.assertTrue(state.capabilities["obstruction"])
        self.assertTrue(state.capabilities["openings_counter"])
        self.assertTrue(state.capabilities["pemu"])
        self.assertEqual(state.nopenings, 42)
        self.assertEqual(state.pemu, 7)

    def test_non_dict_payload_is_safe(self):
        state = normalize_state("not-a-dict")
        self.assertIsInstance(state, NormalizedState)
        self.assertEqual(state.door_state, "unknown")
        self.assertIn("_raw", state.raw)


if __name__ == "__main__":
    unittest.main()
```

```python
DOOR_STATE_MAP = {
    0: "closed",
    1: "open",
    2: "opening",
    3: "closing",
    4: "stopped",
}


def _coerce_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value):
    if value is None:
        return None
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


class NormalizedState:
    def __init__(
        self,
        door_state,
        door_value,
        light_on=None,
        lock_engaged=None,
        obstruction=None,
        nopenings=None,
        secv=None,
        has_swrx=None,
        pemu=None,
        raw=None,
    ):
        self.door_state = door_state
        self.door_value = door_value
        self.light_on = light_on
        self.lock_engaged = lock_engaged
        self.obstruction = obstruction
        self.nopenings = nopenings
        self.secv = secv
        self.has_swrx = has_swrx
        self.pemu = pemu
        self.raw = raw if raw is not None else {}
        self.capabilities = {
            "security_plus": secv is not None or has_swrx is not None,
            "light_control": light_on is not None,
            "lock_control": lock_engaged is not None,
            "obstruction": obstruction is not None,
            "openings_counter": nopenings is not None,
            "pemu": pemu is not None,
        }

    def to_dict(self):
        return {
            "door_state": self.door_state,
            "door_value": self.door_value,
            "light_on": self.light_on,
            "lock_engaged": self.lock_engaged,
            "obstruction": self.obstruction,
            "nopenings": self.nopenings,
            "secv": self.secv,
            "has_swrx": self.has_swrx,
            "pemu": self.pemu,
            "capabilities": dict(self.capabilities),
            "raw": dict(self.raw) if isinstance(self.raw, dict) else self.raw,
        }


def normalize_state(payload):
    if not isinstance(payload, dict):
        return NormalizedState("unknown", None, raw={"_raw": payload})

    door_value = _coerce_int(payload.get("door"))
    door_state = DOOR_STATE_MAP.get(door_value, "unknown")

    secv = _coerce_int(payload.get("secv"))
    has_swrx = _coerce_bool(payload.get("has_swrx"))
    light_on = _coerce_bool(payload.get("light"))
    lock_engaged = _coerce_bool(payload.get("lock"))
    obstruction = _coerce_bool(payload.get("obstruct"))
    nopenings = _coerce_int(payload.get("nopenings"))
    pemu = _coerce_int(payload.get("pemu"))

    return NormalizedState(
        door_state=door_state,
        door_value=door_value,
        light_on=light_on,
        lock_engaged=lock_engaged,
        obstruction=obstruction,
        nopenings=nopenings,
        secv=secv,
        has_swrx=has_swrx,
        pemu=pemu,
        raw=payload,
    )
```

**Verify:** `python -m unittest tests/test_state.py`
**Commit:** `feat(state): add normalized state and capabilities`

---

### Task 1.3: Command Dispatcher
**File:** `opengarage/dispatcher.py`
**Test:** `tests/test_dispatcher.py`
**Depends:** none

```python
import unittest

from opengarage.dispatcher import CommandDispatcher


class TestCommandDispatcher(unittest.TestCase):
    def test_build_command(self):
        command = CommandDispatcher.build_command("open", "abc123")
        self.assertEqual(command, "cc?dkey=abc123&open=1")

    def test_invalid_action_raises(self):
        with self.assertRaises(ValueError):
            CommandDispatcher.build_command("invalid", "abc123")


if __name__ == "__main__":
    unittest.main()
```

```python
class CommandDispatcher:
    """Centralized cc command construction."""

    _ALLOWED_ACTIONS = {
        "click",
        "close",
        "open",
        "reboot",
        "apmode",
        "light",
        "lock",
    }

    @classmethod
    def build_command(cls, action, devkey):
        if action not in cls._ALLOWED_ACTIONS:
            raise ValueError("Unsupported action: %s" % action)
        return "cc?dkey=%s&%s=1" % (devkey, action)
```

**Verify:** `python -m unittest tests/test_dispatcher.py`
**Commit:** `feat(core): add command dispatcher`

---

## Batch 2: Core Client Updates (parallel - 1 implementer)

All tasks in this batch depend on Batch 1 completing.

### Task 2.1: OpenGarage Client Enhancements
**File:** `opengarage/__init__.py`
**Test:** `tests/test_client.py`
**Depends:** 1.1, 1.2, 1.3 (imports errors, state, dispatcher)

```python
import asyncio
import unittest

from opengarage import OpenGarage
from opengarage.errors import ResponseError, UnsupportedFeatureError


class FakeResponse:
    def __init__(self, status, payload=None, text=None):
        self.status = status
        self._payload = payload
        self._text = text or ""

    async def json(self, content_type=None):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def text(self):
        return self._text


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def get(self, url, verify_ssl=False):
        return self._responses.pop(0)

    async def close(self):
        return None


class TestOpenGarageClient(unittest.TestCase):
    def test_get_state_normalizes(self):
        session = FakeSession([FakeResponse(200, {"door": 1, "light": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        loop = asyncio.get_event_loop()
        state = loop.run_until_complete(client.get_state())
        self.assertEqual(state.door_state, "open")
        self.assertTrue(state.capabilities["light_control"])

    def test_get_state_non_200_raises(self):
        session = FakeSession([FakeResponse(500, {"error": "bad"})])
        client = OpenGarage("http://device", "key", websession=session)
        loop = asyncio.get_event_loop()
        with self.assertRaises(ResponseError):
            loop.run_until_complete(client.get_state())

    def test_update_state_preserves_backward_behavior(self):
        session = FakeSession([FakeResponse(500, {"error": "bad"})])
        client = OpenGarage("http://device", "key", websession=session)
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.update_state())
        self.assertIsNone(result)

    def test_toggle_light_unsupported(self):
        session = FakeSession([FakeResponse(200, {"door": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        loop = asyncio.get_event_loop()
        with self.assertRaises(UnsupportedFeatureError):
            loop.run_until_complete(client.toggle_light())

    def test_toggle_light_supported(self):
        session = FakeSession(
            [
                FakeResponse(200, {"door": 1, "light": 1}),
                FakeResponse(200, {"result": "success"}),
            ]
        )
        client = OpenGarage("http://device", "key", websession=session)
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(client.toggle_light())
        self.assertEqual(result, "success")


if __name__ == "__main__":
    unittest.main()
```

```python
"""Open garage"""
import asyncio
import logging

import aiohttp
import async_timeout

from opengarage.dispatcher import CommandDispatcher
from opengarage.errors import ResponseError, TransportError, UnsupportedFeatureError
from opengarage.state import normalize_state

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class OpenGarage:
    """Class to communicate with the Open Garage api."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        devip,
        devkey,
        verify_ssl=False,
        websession=None,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Initialize the Open Garage connection."""
        if websession is None:

            async def _create_session():
                return aiohttp.ClientSession()

            loop = asyncio.get_event_loop()
            self.websession = loop.run_until_complete(_create_session())
        else:
            self.websession = websession
        self._timeout = timeout
        self._devip = devip
        self._devkey = devkey
        self._verify_ssl = verify_ssl

    @property
    def device_url(self):
        """Device url."""
        return self._devip

    async def close_connection(self):
        """Close the connection."""
        await self.websession.close()

    async def update_state(self):
        """Update state (raw jc payload)."""
        return await self._execute("jc")

    async def get_state(self):
        """Get normalized state plus raw payload."""
        raw = await self._execute("jc", wrap_errors=True)
        return normalize_state(raw)

    async def get_capabilities(self):
        """Return capability flags from normalized state."""
        state = await self.get_state()
        return dict(state.capabilities)

    async def push_button(self):
        """Push button."""
        return await self._dispatch_action("click")

    async def push_close_button(self):
        """Push close button.  No-op if already closed."""
        return await self._dispatch_action("close")

    async def push_open_button(self):
        """Push open button.  No-op if already open."""
        return await self._dispatch_action("open")

    async def reboot(self):
        """Reboot device."""
        return await self._dispatch_action("reboot")

    async def ap_mode(self):
        """Reset device in AP mode (to reconfigure WiFi settings)."""
        return await self._dispatch_action("apmode")

    async def toggle_light(self):
        """Toggle light when supported by firmware."""
        state = await self.get_state()
        if not state.capabilities.get("light_control"):
            raise UnsupportedFeatureError("Light control not supported")
        return await self._dispatch_action("light", wrap_errors=True)

    async def toggle_lock(self):
        """Toggle lock when supported by firmware."""
        state = await self.get_state()
        if not state.capabilities.get("lock_control"):
            raise UnsupportedFeatureError("Lock control not supported")
        return await self._dispatch_action("lock", wrap_errors=True)

    async def _dispatch_action(self, action, wrap_errors=False):
        command = CommandDispatcher.build_command(action, self._devkey)
        result = await self._execute(command, wrap_errors=wrap_errors)
        if result is None:
            return None
        return result.get("result")

    async def _execute(self, command, retry=2, wrap_errors=False):
        """Execute command."""
        url = "%s/%s" % (self._devip, command)
        try:
            async with async_timeout.timeout(self._timeout):
                resp = await self.websession.get(url, verify_ssl=self._verify_ssl)
            if resp.status != 200:
                _LOGGER.error(
                    "Error connecting to Open garage, resp code: %s", resp.status
                )
                if wrap_errors:
                    raise ResponseError(resp.status, url)
                return None
            try:
                result = await resp.json(content_type=None)
            except ValueError:
                # Malformed JSON; preserve raw payload for diagnostics
                text = await resp.text()
                result = {"_error": "invalid_json", "_raw": text}
        except aiohttp.ClientError as err:
            if retry > 0:
                return await self._execute(command, retry - 1, wrap_errors=wrap_errors)
            _LOGGER.error("Error connecting to Open garage: %s ", err, exc_info=True)
            if wrap_errors:
                raise TransportError(str(err))
            raise
        except asyncio.TimeoutError as err:
            if retry > 0:
                return await self._execute(command, retry - 1, wrap_errors=wrap_errors)
            _LOGGER.error("Timed out when connecting to Open garage device")
            if wrap_errors:
                raise TransportError(str(err))
            raise

        return result
```

**Verify:** `python -m unittest tests/test_client.py`
**Commit:** `feat(client): add normalized state and capability-gated actions`

---

## Notes / Design-to-Implementation Decisions

- **Backward compatibility preserved:** existing methods (`update_state`, `push_*`) keep returning raw results or `None` for non-200 responses. New capability-aware methods (`get_state`, `get_capabilities`, `toggle_light`, `toggle_lock`) use structured errors without changing legacy behavior.
- **Malformed JSON handling:** `_execute` now captures invalid JSON and returns a safe `{"_error": "invalid_json", "_raw": "..."}` dict. This enables state normalization to proceed without crashing, matching the design’s requirement to preserve diagnostics.
- **Capability detection:** implemented in `NormalizedState.capabilities` based on optional field presence, so older firmware remains “not supported” rather than failing.
- **Door state mapping:** uses a stable mapping for known values and defaults to `"unknown"` for future values to avoid breaking changes.
