"""Exception types raised by the OpenGarage client."""


class OpenGarageError(Exception):
    """Base error for OpenGarage client failures."""


class TransportError(OpenGarageError):
    """Transport-level failures (timeout/network) after retries."""


class ResponseError(OpenGarageError):
    """HTTP response errors with status context."""

    def __init__(self, status, url):
        super().__init__(status, url)
        self.status = status
        self.url = url

    def __str__(self):
        return f"OpenGarage response error: {self.status} for {self.url}"


class UnsupportedFeatureError(OpenGarageError):
    """Raised when a capability-gated action is unavailable."""
