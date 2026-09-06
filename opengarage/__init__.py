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
                connector = aiohttp.TCPConnector(ssl=verify_ssl)
                return aiohttp.ClientSession(connector=connector)

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
                resp = await self.websession.get(url)
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
        except asyncio.TimeoutError:
            if retry > 0:
                return await self._execute(command, retry - 1, wrap_errors=wrap_errors)
            _LOGGER.error("Timed out when connecting to Open garage device")
            if wrap_errors:
                raise TransportError('Timed out when connecting to %s' % url)
            raise

        return result
