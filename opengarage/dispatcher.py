"""Command construction helpers for the OpenGarage device API."""


class CommandDispatcher:  # pylint: disable=too-few-public-methods
    """Centralized cc command construction."""

    # Per the firmware API, most actions are triggered with value "1", but
    # light/lock only accept the literal value "toggle".
    _ACTION_VALUES = {
        "click": "1",
        "close": "1",
        "open": "1",
        "reboot": "1",
        "apmode": "1",
        "light": "toggle",
        "lock": "toggle",
    }

    @classmethod
    def build_command(cls, action, devkey):
        """Build the `cc` query string for the given action."""
        if action not in cls._ACTION_VALUES:
            raise ValueError(f"Unsupported action: {action}")
        return f"cc?dkey={devkey}&{action}={cls._ACTION_VALUES[action]}"
