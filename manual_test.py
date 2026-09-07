"""Exercise a real OpenGarage device end-to-end.

Read-only checks (state, capabilities) always run. Pass --actions to also
toggle light/lock (only if the device reports support for them). Pass
--door to additionally cycle the door open/close -- this physically moves
your garage door, so only use it if that's safe to do right now.

Not part of the test suite -- for interactive verification only.
"""
import argparse
import asyncio

from opengarage import OpenGarage

# Fields that naturally fluctuate between polls and aren't part of the
# device's controllable state, so they're excluded from before/after diffs.
_VOLATILE_FIELDS = {"rcnt", "dist", "rssi"}


def _diff_raw(before, after):
    keys = (set(before) | set(after)) - _VOLATILE_FIELDS
    return {k: (before.get(k), after.get(k)) for k in keys if before.get(k) != after.get(k)}


async def check_state(client):
    print("--- state ---")
    state = await client.get_state()
    print("door_state:", state.door_state)
    print("capabilities:", state.capabilities)
    print("raw:", state.raw)
    return state


async def _toggle_and_verify(client, action_name, toggle_fn, expected_field):
    before = (await client.get_state()).raw
    result = await toggle_fn()
    after = (await client.get_state()).raw
    diff = _diff_raw(before, after)
    print(f"{action_name} result: {result}, changed fields: {diff}")
    unexpected = set(diff) - {expected_field}
    if unexpected:
        print(f"  WARNING: unexpected fields changed: {unexpected}")
    if expected_field not in diff:
        print(f"  WARNING: expected '{expected_field}' to change, but it didn't")
    return after


async def check_actions(client, state):
    print("--- actions ---")
    original = state.raw

    if state.capabilities.get("light_control"):
        await _toggle_and_verify(client, "toggle_light", client.toggle_light, "light")
    else:
        print("toggle_light: not supported, skipping")

    if state.capabilities.get("lock_control"):
        await _toggle_and_verify(client, "toggle_lock", client.toggle_lock, "lock")
    else:
        print("toggle_lock: not supported, skipping")

    print("--- reverting toggles ---")
    if state.capabilities.get("lock_control"):
        await _toggle_and_verify(client, "toggle_lock (revert)", client.toggle_lock, "lock")
    if state.capabilities.get("light_control"):
        await _toggle_and_verify(client, "toggle_light (revert)", client.toggle_light, "light")

    final = (await client.get_state()).raw
    diff = _diff_raw(original, final)
    if diff:
        print(f"  WARNING: state did not fully revert to original: {diff}")
    else:
        print("  confirmed: state matches original after reverting toggles")


async def _wait_for_door_value(client, expected_value, timeout=30, interval=1):
    """Poll until the door reaches expected_value, recording every state seen along the way."""
    elapsed = 0
    state = await client.get_state()
    observed = [state.door_state]
    while state.door_value != expected_value and elapsed < timeout:
        await asyncio.sleep(interval)
        elapsed += interval
        state = await client.get_state()
        observed.append(state.door_state)
    return state, observed


async def check_door(client):
    print("--- door cycle ---")
    before = (await client.get_state()).raw

    print("push_open_button result:", await client.push_open_button())
    opened, observed_opening = await _wait_for_door_value(client, 1)
    diff = _diff_raw(before, opened.raw)
    print(f"door_state after open: {opened.door_state}, changed fields: {diff}")
    print(f"  observed states while opening: {observed_opening}")
    if "opening" not in observed_opening:
        print("  NOTE: never observed 'opening' -- door may move faster than the poll interval")
    # nopenings increments on open (secv=2 devices); not a bug, just expected.
    unexpected = set(diff) - {"door", "nopenings"}
    if unexpected:
        print(f"  WARNING: unexpected fields changed: {unexpected}")
    if opened.door_value != 1:
        print("  WARNING: door did not reach 'open' within timeout")

    print("push_close_button result:", await client.push_close_button())
    closed, observed_closing = await _wait_for_door_value(client, 0)
    diff = _diff_raw(opened.raw, closed.raw)
    print(f"door_state after close: {closed.door_state}, changed fields: {diff}")
    print(f"  observed states while closing: {observed_closing}")
    if "closing" not in observed_closing:
        print("  NOTE: never observed 'closing' -- door may move faster than the poll interval")
    unexpected = set(diff) - {"door"}
    if unexpected:
        print(f"  WARNING: unexpected fields changed: {unexpected}")
    if closed.door_value != 0:
        print("  WARNING: door did not reach 'closed' within timeout")

    # nopenings is cumulative and won't revert -- excluded from the final check.
    final_diff = {k: v for k, v in _diff_raw(before, closed.raw).items() if k != "nopenings"}
    if final_diff:
        print(f"  WARNING: state did not fully revert to original: {final_diff}")
    else:
        print("  confirmed: door state matches original after open/close cycle")


async def main(devip, devkey, run_actions, run_door):
    client = OpenGarage(devip, devkey)  # no websession passed
    try:
        state = await check_state(client)
        if run_actions:
            await check_actions(client, state)
        if run_door:
            await check_door(client)
    finally:
        await client.close_connection()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("devip", help="Device IP/host, e.g. 192.168.1.5 or http://192.168.1.5")
    parser.add_argument("devkey", help="Device key (default is 'opendoor')")
    parser.add_argument(
        "--actions", action="store_true", help="Also toggle light/lock (if supported)"
    )
    parser.add_argument(
        "--door", action="store_true", help="Also cycle the door open/close (moves the door!)"
    )
    parsed_args = parser.parse_args()
    asyncio.run(main(parsed_args.devip, parsed_args.devkey, parsed_args.actions, parsed_args.door))
