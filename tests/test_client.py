import asyncio
import unittest

import aiohttp

from opengarage import OpenGarage
from opengarage.errors import (ResponseError, TransportError,
                               UnsupportedFeatureError)


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
        self.requested_urls = []

    async def get(self, url):
        self.requested_urls.append(url)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def close(self):
        return None


class TestOpenGarageClient(unittest.TestCase):
    def test_get_state_normalizes(self):
        session = FakeSession([FakeResponse(200, {"door": 1, "light": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        state = asyncio.run(client.get_state())
        self.assertEqual(state.door_state, "open")
        self.assertTrue(state.capabilities["light_control"])

    def test_get_state_non_200_raises(self):
        session = FakeSession([FakeResponse(500, {"error": "bad"})])
        client = OpenGarage("http://device", "key", websession=session)
        with self.assertRaises(ResponseError):
            asyncio.run(client.get_state())

    def test_update_state_preserves_backward_behavior(self):
        session = FakeSession([FakeResponse(500, {"error": "bad"})])
        client = OpenGarage("http://device", "key", websession=session)
        result = asyncio.run(client.update_state())
        self.assertIsNone(result)

    def test_toggle_light_unsupported(self):
        session = FakeSession([FakeResponse(200, {"door": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        with self.assertRaises(UnsupportedFeatureError):
            asyncio.run(client.toggle_light())

    def test_toggle_light_supported(self):
        session = FakeSession(
            [
                FakeResponse(200, {"door": 1, "light": 1}),
                FakeResponse(200, {"result": "success"}),
            ]
        )
        client = OpenGarage("http://device", "key", websession=session)
        result = asyncio.run(client.toggle_light())
        self.assertEqual(result, "success")
        self.assertTrue(session.requested_urls[-1].endswith("light=toggle"))

    def test_get_capabilities(self):
        session = FakeSession([FakeResponse(200, {"door": 1, "lock": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        capabilities = asyncio.run(client.get_capabilities())
        self.assertIsInstance(capabilities, dict)
        self.assertTrue(capabilities["lock_control"])

    def test_toggle_lock_unsupported(self):
        session = FakeSession([FakeResponse(200, {"door": 1})])
        client = OpenGarage("http://device", "key", websession=session)
        with self.assertRaises(UnsupportedFeatureError):
            asyncio.run(client.toggle_lock())

    def test_toggle_lock_supported(self):
        session = FakeSession(
            [
                FakeResponse(200, {"door": 1, "lock": 1}),
                FakeResponse(200, {"result": "success"}),
            ]
        )
        client = OpenGarage("http://device", "key", websession=session)
        result = asyncio.run(client.toggle_lock())
        self.assertEqual(result, "success")
        self.assertTrue(session.requested_urls[-1].endswith("lock=toggle"))

    def test_execute_handles_invalid_json_payload(self):
        session = FakeSession(
            [FakeResponse(200, ValueError("bad-json"), text="not-json")]
        )
        client = OpenGarage("http://device", "key", websession=session)
        result = asyncio.run(client._execute("jc"))
        self.assertEqual(result["_error"], "invalid_json")
        self.assertEqual(result["_raw"], "not-json")

    def test_execute_wrap_errors_raises_transport_error_on_client_error(self):
        session = FakeSession([aiohttp.ClientError("boom")])
        client = OpenGarage("http://device", "key", websession=session)
        with self.assertRaises(TransportError):
            asyncio.run(client._execute("jc", retry=0, wrap_errors=True))

    def test_execute_wrap_errors_raises_transport_error_on_timeout(self):
        session = FakeSession([asyncio.TimeoutError()])
        client = OpenGarage("http://device", "key", websession=session)
        with self.assertRaises(TransportError):
            asyncio.run(client._execute("jc", retry=0, wrap_errors=True))


if __name__ == "__main__":
    unittest.main()
