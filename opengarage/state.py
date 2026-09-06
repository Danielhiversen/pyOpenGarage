"""Normalization of raw OpenGarage device state payloads."""

DOOR_STATE_MAP = {
    0: "closed",
    1: "open",
    2: "opening",
    3: "closing",
    4: "stopped",
}


def _coerce_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value):
    if value is None:
        return None
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


class NormalizedState:  # pylint: disable=too-few-public-methods
    """Normalized, capability-aware view of a raw OpenGarage state payload."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-instance-attributes
    def __init__(
        self,
        door_state,
        door_value,
        light_on=None,
        lock_engaged=None,
        obstruction=None,
        nopenings=None,
        secv=None,
        has_swrx=None,
        pemu=None,
        raw=None,
    ):
        self.door_state = door_state
        self.door_value = door_value
        self.light_on = light_on
        self.lock_engaged = lock_engaged
        self.obstruction = obstruction
        self.nopenings = nopenings
        self.secv = secv
        self.has_swrx = has_swrx
        self.pemu = pemu
        self.raw = raw if raw is not None else {}
        self.capabilities = {
            "security_plus": secv is not None or has_swrx is not None,
            "light_control": light_on is not None,
            "lock_control": lock_engaged is not None,
            "obstruction": obstruction is not None,
            "openings_counter": nopenings is not None,
            "pemu": pemu is not None,
        }

    def to_dict(self):
        """Return a plain-dict representation of this state."""
        return {
            "door_state": self.door_state,
            "door_value": self.door_value,
            "light_on": self.light_on,
            "lock_engaged": self.lock_engaged,
            "obstruction": self.obstruction,
            "nopenings": self.nopenings,
            "secv": self.secv,
            "has_swrx": self.has_swrx,
            "pemu": self.pemu,
            "capabilities": dict(self.capabilities),
            "raw": dict(self.raw) if isinstance(self.raw, dict) else self.raw,
        }


def normalize_state(payload):
    """Normalize a raw OpenGarage device payload into a `NormalizedState`."""
    if not isinstance(payload, dict):
        return NormalizedState("unknown", None, raw={"_raw": payload})

    door_value = _coerce_int(payload.get("door"))
    door_state = DOOR_STATE_MAP.get(door_value, "unknown")

    secv = _coerce_int(payload.get("secv"))
    has_swrx = _coerce_bool(payload.get("has_swrx"))
    light_on = _coerce_bool(payload.get("light"))
    lock_engaged = _coerce_bool(payload.get("lock"))
    obstruction = _coerce_bool(payload.get("obstruct"))
    nopenings = _coerce_int(payload.get("nopenings"))
    pemu = _coerce_int(payload.get("pemu"))

    return NormalizedState(
        door_state=door_state,
        door_value=door_value,
        light_on=light_on,
        lock_engaged=lock_engaged,
        obstruction=obstruction,
        nopenings=nopenings,
        secv=secv,
        has_swrx=has_swrx,
        pemu=pemu,
        raw=payload,
    )
