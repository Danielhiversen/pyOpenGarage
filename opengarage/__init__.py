"""Open garage"""
import asyncio
import logging

import aiohttp
import async_timeout

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class OpenGarage:
    """Class to communicate with the Open Garage api."""

    def __init__(
        self, devip, devkey, verify_ssl=False, websession=None, timeout=DEFAULT_TIMEOUT,
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

    async def close_connection(self):
        """Close the connection."""
        await self.websession.close()

    async def update_state(self):
        """Update state."""
        return await self._execute("jc")

    async def push_button(self):
        """Push button."""
        result = await self._execute(f"cc?dkey={self._devkey}&click=1")
        if result is None:
            return None
        return result.get("result")
    
    async def reboot(self):
        """Reboot device."""
        result = await self._execute(f"cc?dkey={self._devkey}&reboot=1")
        if result is None:
            return None
        return result.get("result")
    
    async def ap_mode(self):
        """Reset device in AP mode (to reconfigure WiFi settings)."""
        result = await self._execute(f"cc?dkey={self._devkey}&apmode=1")
        if result is None:
            return None
        return result.get("result")

    async def _execute(self, command, retry=2):
        """Execute command."""
        url = f"{self._devip}/{command}"
        try:
            with async_timeout.timeout(self._timeout):
                resp = await self.websession.get(url, verify_ssl=self._verify_ssl)
            if resp.status != 200:
                _LOGGER.error(
                    "Error connecting to Open garage, resp code: %s", resp.status
                )
                return None
            result = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            if retry > 0:
                return await self._execute(command, retry - 1)
            _LOGGER.error("Error connecting to Open garage: %s ", err, exc_info=True)
            raise
        except asyncio.TimeoutError:
            if retry > 0:
                return await self._execute(command, retry - 1)
            _LOGGER.error("Timed out when connecting to Open garage device")
            raise

        return result
