"""O1's Pi compatibility policy: version is PROVENANCE, never an authorization gate.

Corrects a harness-policy defect the first O1 invocation inherited unchanged
from AR2: calling ``ar2.launch.resolve_runtime_identity(expected_version=
ar2.PINNED_PI_VERSION)`` made an EXACT Pi version match (``"0.84.2"``) a
precondition for sending any prompt. The operator has since upgraded Pi, and
the installed runtime now reports ``"0.84.3"``. AR2 itself is frozen and its
historical pin/records stay exactly as they are -- this module changes
nothing under ``experiments/pi_external_runtime_ar2/`` and never imports
``ar2.PINNED_PI_VERSION`` or ``ar2.launch.PINNED_PI_VERSION`` as a gate value.

The corrected policy, for O1 only, from now on:

    Pi version = provenance / diagnostic evidence, always recorded truthfully
    Pi version = NEVER authorization by itself

A different Pi version is allowed to proceed when a **zero-prompt
compatibility gate** mechanically demonstrates that the exact runtime seam
and capability behaviors O1 depends on are still present: Node-direct
launch, LF-framed JSONL RPC correlation, RPC startup with no inference, H1
extension identity, H2 provider/model identity, the exact CLI launch shape
AR2's own ``ar2.launch.build_pi_argv`` constructs, absence of any protocol
violation or extension error during that non-inference exchange, and the
non-inference ``/models`` route check. If ANY of those fails, O1 fails
closed for that EXACT reason -- never generically as "version mismatch" --
and sends zero prompts. This is deliberately NOT a semver range: there is no
version-string comparison of any kind left in the gate, in either direction.

Node/Pi LOCATION resolution is reused from ``ar2.launch`` unmodified (its
private ``_resolve_node_executable`` / ``_resolve_pi_package_root`` helpers,
and its ``RuntimeIdentity`` data shape, and its ``LaunchIdentityError``
exception type for a genuine launch failure that has nothing to do with
version authorization -- Node/Pi missing, ``dist/cli.js`` absent, or the
``--version`` probe itself failing to start or exiting non-zero). Only the
version-EQUALITY comparison in ``ar2.launch.resolve_runtime_identity`` is
not called.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ar2.launch import (
    LaunchIdentityError,
    RuntimeIdentity,
    _resolve_node_executable,  # noqa: F401 -- deliberate reuse of AR2's own helper
    _resolve_pi_package_root,  # noqa: F401 -- deliberate reuse of AR2's own helper
)


def resolve_pi_identity_provenance_only() -> RuntimeIdentity:
    """Locate Node + Pi and OBSERVE Pi's version. Never gates on the value.

    Raises :class:`LaunchIdentityError` only for a launch-time failure that
    is true regardless of what version is installed: Node or Pi not found,
    ``dist/cli.js`` missing, the direct-launch ``--version`` probe failing to
    start, exiting non-zero, or reporting an empty string (a version must be
    OBSERVABLE even though it is not an authorization gate). There is no
    comparison against any pin, exact or ranged, anywhere in this function.
    """
    node_executable = _resolve_node_executable()
    package_root = _resolve_pi_package_root()
    cli_js = os.path.realpath(os.path.join(package_root, "dist", "cli.js"))
    if not os.path.isfile(cli_js):
        raise LaunchIdentityError(
            "launch error: the resolved Pi dist/cli.js does not exist"
        )

    try:
        completed = subprocess.run(  # noqa: S603 - resolved absolute argv, shell=False
            [node_executable, cli_js, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except OSError as exc:
        raise LaunchIdentityError(
            f"launch error: Node-direct Pi launch failed to start: {exc}"
        ) from exc

    if completed.returncode != 0:
        raise LaunchIdentityError(
            "launch error: Node-direct Pi launch exited "
            f"{completed.returncode}; no fallback launch architecture is attempted"
        )

    reported = completed.stdout.decode("utf-8", "replace").strip()
    if not reported:
        raise LaunchIdentityError(
            "launch error: Pi reported an empty version string; a version "
            "must be observable even though it is never an authorization gate"
        )

    return RuntimeIdentity(
        node_executable=node_executable,
        pi_cli_js=cli_js,
        pi_package_root=package_root,
        reported_version=reported,
        launch_shape="node_direct",
    )


# The named, mechanically-evaluated compatibility checks (brief items 1-12).
# Every key here maps 1:1 to a boolean actually computed from an observed
# fact -- never from the version string.
COMPATIBILITY_CHECK_NAMES: tuple[str, ...] = (
    "pi_version_observable",
    "node_direct_launch_constructed",
    "rpc_process_launched_and_alive",
    "jsonl_request_response_correlation_h1_worked",
    "get_commands_response_shape_understood",
    "h1_extension_identity_passed",
    "jsonl_request_response_correlation_h2_worked",
    "get_state_response_shape_understood",
    "h2_model_identity_passed",
    "required_launch_flags_accepted",
    "no_protocol_violation_during_handshake",
    "no_extension_errors_during_handshake",
    "route_serves_configured_model",
)


def build_pi_runtime_provenance(
    *,
    identity: RuntimeIdentity,
    checks: dict[str, bool],
) -> dict[str, Any]:
    """The ``pi_runtime`` record block. Truthful provenance, never authorization."""
    missing = [name for name in COMPATIBILITY_CHECK_NAMES if name not in checks]
    if missing:  # pragma: no cover - a harness-internal wiring bug, not a runtime fact
        raise AssertionError(f"compatibility_checks is missing required keys: {missing}")
    return {
        "observed_version": identity.reported_version,
        "version_recorded_as_provenance": True,
        "exact_version_is_authorization_gate": False,
        "version_pin_policy": (
            "O1 does not compare the observed Pi version against any pin, exact "
            "or ranged. A different version proceeds only when every named "
            "compatibility check below passes against the ACTUAL launched "
            "runtime seam."
        ),
        "compatibility_gate_passed": all(checks.values()),
        "compatibility_checks": dict(checks),
        "no_semver_range_authorization": True,
        "future_version_support_claim": (
            "NONE. This block records only that THIS observed Pi version "
            "passed or failed the required compatibility gate for THIS run. "
            "It is not a claim that any other Pi version is supported."
        ),
    }
