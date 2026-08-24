"""The two pre-prompt handshakes, H1 and H2. EXPERIMENT ONLY.

Both are carried forward from AR1-FU1 unchanged in strictness, and both are
terminal: a failure means **zero prompts** for that case, not a retry and not a
weaker check.

H1 -- exact intended extension identity. A sentinel command merely EXISTING is
not sufficient (that was the pre-FU1 gate). H1 proves, in order:

1. a command with the sentinel name was reported at all;
2. its reported ``source`` is exactly ``"extension"``;
3. its reported path resolves to exactly the extension entry point AIDO itself
   passed via ``--extension``;
4. when Pi also reports a source-origin field, it does not contradict the one
   known-expected value for a CLI-loaded extension.

Any missing, wrong, or malformed piece fails the whole gate. There is no partial
credit and no path repair.

H2 -- exact provider/model identity via ``get_state``. Neither handshake triggers
inference, and neither sends a prompt.
"""

from __future__ import annotations

import os
from typing import Any

from .pi_config import EXPECTED_EXTENSION_SOURCE_KIND, SENTINEL_COMMAND_NAME


def evaluate_extension_identity(
    commands: list[Any],
    *,
    extension_entry: str,
    sentinel_command_name: str = SENTINEL_COMMAND_NAME,
    expected_source_kind: str = EXPECTED_EXTENSION_SOURCE_KIND,
) -> dict[str, Any]:
    """H1. Fails closed on ambiguity, a wrong path, or malformed metadata."""
    same_name = [
        c for c in commands if isinstance(c, dict) and c.get("name") == sentinel_command_name
    ]
    sentinel_name_matched = bool(same_name)
    sentinel = next((c for c in same_name if c.get("source") == "extension"), None)
    extension_source_matched = sentinel is not None

    extension_path_matched = False
    noncontradictory_source_origin = True
    malformed_source_metadata = False
    reported_source_kind: Any = None
    failure_reasons: list[str] = []

    if not sentinel_name_matched:
        failure_reasons.append(f"no command named {sentinel_command_name!r} was reported")
    elif not extension_source_matched:
        failure_reasons.append(
            f"a command named {sentinel_command_name!r} exists but its reported "
            "source is not 'extension'"
        )
    else:
        source_info = sentinel.get("sourceInfo")
        if source_info is not None and not isinstance(source_info, dict):
            malformed_source_metadata = True
            failure_reasons.append("sourceInfo is present but not an object")
            source_info = None

        reported_path: Any = None
        if isinstance(source_info, dict):
            reported_source_kind = source_info.get("source")
            candidate = source_info.get("path")
            if candidate is not None and not isinstance(candidate, str):
                malformed_source_metadata = True
                failure_reasons.append("sourceInfo.path is present but not a string")
            elif isinstance(candidate, str):
                reported_path = candidate

        flat_path = sentinel.get("path")
        if flat_path is not None and not isinstance(flat_path, str):
            malformed_source_metadata = True
            failure_reasons.append("the flat 'path' field is present but not a string")
        elif reported_path is None and isinstance(flat_path, str):
            reported_path = flat_path

        if reported_path is None:
            failure_reasons.append(
                "neither sourceInfo.path nor the flat 'path' field is a usable "
                "string; extension identity cannot be proven"
            )
        else:
            try:
                extension_path_matched = os.path.normcase(
                    os.path.realpath(reported_path)
                ) == os.path.normcase(os.path.realpath(extension_entry))
            except OSError:  # pragma: no cover - defensive
                extension_path_matched = False
            if not extension_path_matched:
                failure_reasons.append(
                    "the reported extension path does not resolve to the expected "
                    "extension entry point"
                )

        if reported_source_kind is not None and reported_source_kind != expected_source_kind:
            noncontradictory_source_origin = False
            failure_reasons.append(
                f"sourceInfo.source reported {reported_source_kind!r}, contradicting "
                f"the expected {expected_source_kind!r} for a CLI-loaded extension"
            )

    passed = (
        sentinel_name_matched
        and extension_source_matched
        and extension_path_matched
        and noncontradictory_source_origin
        and not malformed_source_metadata
    )
    return {
        "sentinel_command_name": sentinel_command_name,
        "sentinel_name_matched": sentinel_name_matched,
        "extension_source_matched": extension_source_matched,
        "extension_path_matched": extension_path_matched,
        "noncontradictory_source_origin": noncontradictory_source_origin,
        "malformed_source_metadata": malformed_source_metadata,
        "expected_source_kind": expected_source_kind,
        "sentinel_source_kind": reported_source_kind,
        "failure_reasons": failure_reasons,
        "proves": (
            "the intended extension loaded, at the expected path, with a "
            "noncontradictory reported source origin"
        ),
        "does_not_prove": (
            "the exact contents of the active tool registry; Pi 0.84.2 has no RPC "
            "command that enumerates tools"
        ),
        "passed": passed,
    }


def evaluate_model_identity(
    response: dict[str, Any] | None, *, expected_provider: str, expected_model: str
) -> dict[str, Any]:
    """H2. Exact provider and model identity, from ``get_state``. No inference."""
    model_obj: dict[str, Any] = {}
    if response and isinstance(response.get("data"), dict):
        candidate = response["data"].get("model")
        if isinstance(candidate, dict):
            model_obj = candidate
    provider_matches = model_obj.get("provider") == expected_provider
    model_matches = model_obj.get("id") == expected_model
    return {
        "command": "get_state",
        "response_success": bool(response and response.get("success")),
        "expected_provider": expected_provider,
        "expected_model": expected_model,
        "reported_provider": model_obj.get("provider"),
        "reported_model": model_obj.get("id"),
        "reported_api": model_obj.get("api"),
        "reported_base_url_recorded": False,
        "runtime_native_max_tokens_reported": model_obj.get("maxTokens"),
        "provider_matches": provider_matches,
        "model_matches": model_matches,
        "triggered_inference": False,
        "passed": bool(provider_matches and model_matches),
    }
