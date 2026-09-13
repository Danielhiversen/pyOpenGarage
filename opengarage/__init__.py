"""Open garage"""

import asyncio
import logging

import aiohttp
import async_timeout

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
        self._light_lock = None

    @property
    def device_url(self):
        """Device url."""
        return self._devip

    async def close_connection(self):
        """Close the connection."""
        await self.websession.close()

    async def update_state(self):
        """Update state."""
        return await self._execute("jc")

    async def push_button(self):
        """Push button."""
        result = await self._execute("cc", {"dkey": self._devkey, "click": 1})
        if result is None:
            return None
        return result.get("result")

    async def push_close_button(self):
        """Push close button.  No-op if already closed."""
        result = await self._execute("cc", {"dkey": self._devkey, "close": 1})
        if result is None:
            return None
        return result.get("result")

    async def push_open_button(self):
        """Push open button.  No-op if already open."""
        result = await self._execute("cc", {"dkey": self._devkey, "open": 1})
        if result is None:
            return None
        return result.get("result")

    async def reboot(self):
        """Reboot device."""
        result = await self._execute("cc", {"dkey": self._devkey, "reboot": 1})
        if result is None:
            return None
        return result.get("result")

    async def ap_mode(self):
        """Reset device in AP mode (to reconfigure WiFi settings)."""
        result = await self._execute("cc", {"dkey": self._devkey, "apmode": 1})
        if result is None:
            return None
        return result.get("result")

    async def toggle_light(self):
        """Toggle the opener light."""
        async with self._get_light_lock():
            return await self._toggle_light()

    def _get_light_lock(self):
        """Create the shared lock inside the light command's running loop."""
        if self._light_lock is None:
            self._light_lock = asyncio.Lock()
        return self._light_lock

    async def _toggle_light(self):
        """Send one toggle without retrying an ambiguous response."""
        # A lost response may follow a successful toggle; retrying would undo it.
        result = await self._execute(
            "cc", {"dkey": self._devkey, "light": "toggle"}, retry=0
        )
        if result is None:
            return None
        return result.get("result")

    async def set_light(self, turn_on):
        """Set the opener light without toggling an already-correct state."""
        async with self._get_light_lock():
            state = await self.update_state()
            if state is None or state.get("light") not in (0, 1):
                return None
            if bool(state["light"]) is bool(turn_on):
                return 1
            return await self._toggle_light()

    async def _execute(self, command, params=None, retry=2):
        """Execute command."""
        url = f"{self._devip}/{command}"
        try:
            async with async_timeout.timeout(self._timeout):
                resp = await self.websession.get(
                    url, params=params, verify_ssl=self._verify_ssl
                )
            if resp.status != 200:
                _LOGGER.error(
                    "Error connecting to Open garage, resp code: %s", resp.status
                )
                return None
            result = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            if retry > 0:
                return await self._execute(command, params, retry - 1)
            _LOGGER.error("Error connecting to Open garage: %s ", err, exc_info=True)
            raise
        except asyncio.TimeoutError:
            if retry > 0:
                return await self._execute(command, params, retry - 1)
            _LOGGER.error("Timed out when connecting to Open garage device")
            raise

        return result
