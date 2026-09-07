---
date: 2026-05-22
topic: "OpenGarage firmware feature expansion (v1.2.x)"
status: draft
---

## Problem Statement

We need to expand this client so it supports the latest OpenGarage firmware capabilities exposed in v1.2.x, especially new door states and Security+ controls/telemetry.

Today the library only wraps a narrow subset of commands (`jc` read, a few `cc` actions) and exposes raw responses with minimal structure, which makes it hard to safely adopt newer fields and behaviors.

## Constraints

- Keep the public API backward compatible for existing consumers.
- Preserve async behavior and simple client ergonomics.
- Maintain compatibility with older firmware that does not expose new fields.
- Avoid a large architecture rewrite in this repository’s current lightweight structure.
- Do not require MQTT usage for core HTTP functionality.

## Approach

We will evolve from a fixed-command wrapper to a **capability-aware API surface** while keeping the current class model.

The chosen approach is a **thin compatibility layer**: we add richer response parsing, optional feature methods, and runtime capability detection from `/jc` fields.

Why this approach:
- Lowest disruption to current users.
- Fits the current single-class client style.
- Lets us add modern firmware support without forcing version pinning.

Alternatives considered:
- Full multi-module SDK redesign: cleaner long-term, but overkill for this package size.
- Strict firmware-version branching: simpler logic but brittle when fields roll out incrementally.

## Architecture

High-level structure remains a single OpenGarage client, with three explicit layers of responsibility.

1. **Transport Layer**
   - Handles request execution, retries, timeout, and response parsing.
   - Normalizes API errors into stable client-level failure modes.

2. **State/Capability Layer**
   - Converts `/jc` payload into a normalized state model.
   - Detects optional capabilities (Security+, light/lock control, obstruction telemetry) based on field presence.

3. **Action Layer**
   - Exposes current actions plus new optional actions (light toggle, lock toggle).
   - Gates unsupported actions cleanly when device capability is absent.

## Components

### OpenGarage Client (core façade)
- Continues to be the main user entrypoint.
- Adds explicit state retrieval returning normalized status + raw payload.
- Adds capability query helpers for feature detection.

### Command Dispatcher
- Centralizes command/query construction for `cc` actions.
- Supports extending action set without duplicating request logic.

### State Normalizer
- Maps `door` values to stable semantic states including intermediate states (`opening`, `closing`, `stopped`).
- Parses optional v1.2.x fields (`secv`, `has_swrx`, `light`, `lock`, `obstruct`, `nopenings`, `pemu`) when available.

### Compatibility Guard
- Ensures absent fields on older firmware degrade gracefully.
- Avoids raising errors for unknown extra fields from future firmware.

## Data Flow

1. Consumer calls state refresh.
2. Client requests `/jc`.
3. Transport validates HTTP response and parses JSON.
4. State normalizer maps raw values into normalized state + capability flags.
5. Caller receives normalized state (plus optional raw payload for advanced use).

For actions:
1. Consumer calls action method (open/close/click/light/lock/etc.).
2. Action layer validates capability preconditions when required.
3. Dispatcher sends `/cc` with the appropriate control argument.
4. Response result is normalized into a consistent success/failure contract.

## Error Handling

- **Transport failures** (timeout/network): retain retry behavior, then raise a clear client exception.
- **HTTP non-200**: treat as operation failure with structured error context.
- **Invalid JSON / malformed fields**: fail state normalization safely, preserving raw payload for diagnostics.
- **Unsupported feature call** (e.g., lock toggle on non-Security+): return deterministic unsupported-feature error.
- **Backward compatibility path**: missing optional fields are interpreted as “not supported,” not hard failures.

## Testing Strategy

We add focused tests around compatibility boundaries rather than exhaustive firmware emulation.

1. **State mapping tests**
   - Validate all known `door` states and unknown fallback handling.

2. **Optional-field parsing tests**
   - Verify behavior when Security+ fields are present vs absent.

3. **Action capability tests**
   - Ensure light/lock actions succeed when capabilities exist and fail predictably when they do not.

4. **Transport/error tests**
   - Timeout retry behavior.
   - Non-200 and malformed payload handling.

5. **Backward compatibility tests**
   - Existing open/close/click flows remain unchanged for older payload shapes.

## Open Questions

- Whether to expose config-level endpoints (`/jo`) in this phase or keep scope limited to operational control/state.
- Whether OTC cloud-token behavior should be handled in this library now or in a separate cloud-focused client.
- Whether MQTT-facing features should be represented as first-class APIs or documented as out of scope for this package.
