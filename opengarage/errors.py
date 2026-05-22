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
