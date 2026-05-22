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
