"""Tests for OpenGarage opener light control."""

import asyncio
import unittest

from opengarage import OpenGarage


class AsyncCallable:
    """Minimal async callable test double compatible with Python 3.7."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.calls = []

    async def __call__(self, *args, **kwargs):
        """Record a call and return the configured value."""
        self.calls.append((args, kwargs))
        return self.return_value


class TestOpenGarageLight(unittest.TestCase):
    """Test OpenGarage opener light methods."""

    def setUp(self):
        """Create an OpenGarage client with a mocked session."""
        self.client = OpenGarage(
            "http://device",
            "abc123&=?/",
            websession=object(),
        )

    def test_toggle_light_uses_firmware_toggle_value(self):
        """Test the firmware receives its required light=toggle value."""
        execute = AsyncCallable(return_value={"result": 1})
        self.client._execute = execute

        self.assertEqual(asyncio.run(self.client.toggle_light()), 1)

        self.assertEqual(
            execute.calls,
            [(("cc?dkey=abc123%26%3D%3F%2F&light=toggle",), {})],
        )

    def test_set_light_is_idempotent(self):
        """Test no toggle is sent when the light is already correct."""
        for current, requested in ((0, False), (1, True)):
            with self.subTest(current=current, requested=requested):
                self.client.update_state = AsyncCallable(
                    return_value={"light": current}
                )
                toggle = AsyncCallable()
                self.client.toggle_light = toggle

                self.assertEqual(asyncio.run(self.client.set_light(requested)), 1)

                self.assertEqual(toggle.calls, [])

    def test_set_light_toggles_when_state_differs(self):
        """Test a toggle is sent when the requested state differs."""
        for current, requested in ((0, True), (1, False)):
            with self.subTest(current=current, requested=requested):
                self.client.update_state = AsyncCallable(
                    return_value={"light": current}
                )
                toggle = AsyncCallable(return_value=1)
                self.client.toggle_light = toggle

                self.assertEqual(asyncio.run(self.client.set_light(requested)), 1)

                self.assertEqual(toggle.calls, [((), {})])

    def test_set_light_returns_none_without_light_capability(self):
        """Test devices without a light field are not controlled."""
        for state in (None, {"door": 0}):
            with self.subTest(state=state):
                self.client.update_state = AsyncCallable(return_value=state)
                toggle = AsyncCallable()
                self.client.toggle_light = toggle

                self.assertIsNone(asyncio.run(self.client.set_light(True)))

                self.assertEqual(toggle.calls, [])


if __name__ == "__main__":
    unittest.main()
