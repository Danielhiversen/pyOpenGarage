"""Command-line control application for OpenGarage devices."""

import argparse
import asyncio
import json
import os
import sys

import aiohttp

from opengarage import OpenGarage
from opengarage.errors import OpenGarageError

DEFAULT_DEVKEY = "opendoor"

_ACTIONS = {
    "state": lambda client, args: client.get_state(),
    "capabilities": lambda client, args: client.get_capabilities(),
    "open": lambda client, args: client.push_open_button(),
    "close": lambda client, args: client.push_close_button(),
    "click": lambda client, args: client.push_button(),
    "toggle-light": lambda client, args: client.toggle_light(),
    "toggle-lock": lambda client, args: client.toggle_lock(),
    "set-light": lambda client, args: client.set_light(args.state == "on"),
    "set-lock": lambda client, args: client.set_lock(args.state == "on"),
    "reboot": lambda client, args: client.reboot(),
    "apmode": lambda client, args: client.ap_mode(),
}

# Actions that require --state {on,off} to be provided.
_STATE_REQUIRED_ACTIONS = {"set-light", "set-lock"}

# Actions with side effects serious enough to warrant an explicit confirmation.
_CONFIRM_MESSAGES = {
    "apmode": "This resets the device's WiFi settings and takes it offline from your "
    "network until reconfigured.",
    "reboot": "This reboots the device, temporarily taking it offline.",
}


def _to_plain(value):
    """Convert client results into a JSON/print-friendly plain value."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _format_dict(data):
    """Render a flat dict as one 'key: value' line per entry, sorted by key."""
    lines = [f"  {key}: {value}" for key, value in sorted(data.items())]
    return "\n".join(lines)


def _format_capabilities(capabilities):
    """Render a capabilities dict as one 'name: yes/no' line per entry."""
    lines = [
        f"  {name}: {'yes' if enabled else 'no'}"
        for name, enabled in sorted(capabilities.items())
    ]
    return "\n".join(lines)


def _print_result(action, value, as_json):
    plain = _to_plain(value)
    if as_json:
        print(json.dumps(plain, indent=2, sort_keys=True))
        return
    if action == "state":
        print("door_state:", plain["door_state"])
        print("capabilities:")
        print(_format_capabilities(plain["capabilities"]))
        print("raw:")
        print(_format_dict(plain["raw"]))
    elif action == "capabilities":
        print("capabilities:")
        print(_format_capabilities(plain))
    else:
        print(f"{action}:", plain)


def _confirm(action):
    """Prompt for confirmation before running a disruptive action."""
    message = _CONFIRM_MESSAGES.get(action)
    if message is None:
        return True
    print(f"warning: {message}", file=sys.stderr)
    try:
        answer = input(f"Continue with '{action}'? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in ("y", "yes")


async def _run(args):
    client = OpenGarage(args.devip, args.devkey, verify_ssl=args.verify_ssl, timeout=args.timeout)
    try:
        result = await _ACTIONS[args.action](client, args)
    finally:
        await client.close_connection()
    _print_result(args.action, result, args.json)


def build_parser():
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="opengarage", description="Control an OpenGarage device from the command line."
    )
    parser.add_argument("devip", help="Device IP/host, e.g. 192.168.1.5 or http://192.168.1.5")
    parser.add_argument(
        "--devkey",
        default=os.environ.get("OPENGARAGE_DEVKEY", DEFAULT_DEVKEY),
        help="Device key. Defaults to $OPENGARAGE_DEVKEY, or 'opendoor' if unset.",
    )
    parser.add_argument("action", choices=sorted(_ACTIONS), help="Action to perform")
    parser.add_argument(
        "--state",
        choices=["on", "off"],
        help="Desired state for set-light/set-lock (required for those actions)",
    )
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    parser.add_argument("--verify-ssl", action="store_true", help="Verify SSL certificates")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation for disruptive actions"
    )
    return parser


def main(argv=None):
    """Entry point for the `opengarage` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action in _STATE_REQUIRED_ACTIONS and args.state is None:
        print(f"error: action '{args.action}' requires --state {{on,off}}", file=sys.stderr)
        return 2
    if args.action not in _STATE_REQUIRED_ACTIONS and args.state is not None:
        print(f"error: --state is not valid for action '{args.action}'", file=sys.stderr)
        return 2
    if not args.yes and not _confirm(args.action):
        print("aborted", file=sys.stderr)
        return 1
    try:
        asyncio.run(_run(args))
    except (OpenGarageError, aiohttp.ClientError, asyncio.TimeoutError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
