"""Command construction helpers for the OpenGarage device API."""


class CommandDispatcher:  # pylint: disable=too-few-public-methods
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
        """Build the `cc` query string for the given action."""
        if action not in cls._ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported action: {action}")
        return f"cc?dkey={devkey}&{action}=1"
