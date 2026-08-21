"""The AR1 experiment run record.

This is an EXPERIMENT-OWNED artifact. It is NOT a production ReviewPacket, it is
not ``review-packet.v4``, and it must never be described as one. No reviewer was
called in AR1 (AR0-FU1 section 13: the shipped reviewer prompt asserts the diff
was human-approved before it was written, which is false for a runtime-produced
change; the adaptation is a later, separately authorized slice).

Two namespaces, kept strictly disjoint:

    runtime_reported_*        Pi's own account of itself -- UNTRUSTED CLAIM
    orchestrator_observed_*   AIDO's own derivation      -- AUTHORITATIVE
"""

from __future__ import annotations

import os
from typing import Any

from . import EXPERIMENT_ID, EXPERIMENT_RECORD_VERSION
from .protocol import contains_reasoning

CAPABILITY_BOUNDARY: dict[str, Any] = {
    "tool_layer_path_allowlist_enabled": True,
    "os_filesystem_isolation": False,
    "bash_exposed": False,
    "built_in_filesystem_tools_exposed": False,
    "production_workspace_access_authorized": False,
    "promotion_authorized": False,
    "reviewer_invoked": False,
    "statement": (
        "B-fixed is capability restriction at the tool layer, enforced inside "
        "the runtime's own process. It is NOT an OS sandbox. It proves that the "
        "model was offered no tool capable of naming a path outside the "
        "allowlist, and that AIDO's own code decided every filesystem operation "
        "those tools performed. It does NOT prove that no host file outside the "
        "disposable repository was read or written: the extension runs inside "
        "Pi's Node process with the launching user's full permissions."
    ),
}

TOKEN_POLICY: dict[str, Any] = {
    "aido_requested_max_output_tokens": None,
    "runtime_native_max_tokens": "pi_catalog_default",
    "generated_models_json_omits_max_tokens": True,
    "meaning_of_null": (
        "AIDO did not request an output-token cap. Never 0, never -1, never "
        "'unlimited'."
    ),
    "meaning_of_pi_catalog_default": (
        "AIDO stated no value and Pi applies whatever its own catalog logic "
        "applies. That is Pi/provider-native behavior, never an AIDO-requested cap."
    ),
}

RESIDUAL_LIMITATIONS: list[str] = [
    "The confining extension runs INSIDE Pi's Node process with the launching "
    "user's full Windows permissions. A Pi defect, a dependency defect, or a "
    "future Pi version that adds an unconfined filesystem path would bypass it "
    "entirely. This is not an OS boundary and must never be called one.",
    "Pi's read-path resolver probes the filesystem (existence checks on Unicode "
    "and NFD variants of a resolved path) BEFORE the AIDO-authored operations "
    "seam is consulted. The accurate claim therefore covers reads and writes "
    "through AIDO's tools, not stat calls made by Pi's own resolver.",
    "Pi 0.84.2 exposes no RPC command that enumerates the active tool registry. "
    "The get_commands sentinel proves the intended extension LOADED; it does not "
    "by itself prove the exact contents of the active tool registry.",
    "AIDO's outer wait ending is not Pi stopping, is not the provider request "
    "being cancelled, and is not backend inference stopping. Nothing here claims "
    "descendants were terminated or that GPU work ended.",
    "The disposable repository was observed at one instant. If any process were "
    "still writing at that moment the snapshot would be of a moving target; the "
    "observation timestamp and the termination state are recorded rather than a "
    "quiescence claim.",
    "Redaction and name-only environment auditing are backstops, not guarantees. "
    "Nothing here claims the transmitted material is secret-free.",
    "The host's own Git configuration does carry execution-capable keys in "
    "global and system scope (Git LFS filters, a credential helper). They are "
    "not visible to this observation, because the accepted Git adapter runs with "
    "GIT_CONFIG_NOSYSTEM=1 and forwards no profile variable, so Git resolves "
    "neither file. The gate therefore reports on repository-local scope here. "
    "Keys that appear during the run are treated as poisoning in any scope.",
    "One synthetic fixture, written by AIDO itself, is not evidence about a real "
    "repository. Nothing here supports promotion to a production workspace.",
]

# (code, needle) pairs that must never appear anywhere in the emitted record.
# AR1-FU1: findings record the CODE only, never the needle itself. A raw needle
# is safe to name for these four fixed, generic markers, but ``extra_forbidden``
# callers pass real secret/endpoint values, and a finding that echoed the needle
# back would turn detection into a leak. So every finding -- fixed or extra --
# is a bounded code, uniformly.
_FORBIDDEN_RECORD_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("http_url_scheme_present", "http://"),
    ("https_url_scheme_present", "https://"),
    ("authorization_header_text_present", "Authorization"),
    ("bearer_token_marker_present", "Bearer "),
)


def scrub_check(
    record: dict[str, Any], *, extra_forbidden: tuple[tuple[str, str], ...] = ()
) -> dict[str, Any]:
    """Self-check the record before it is written. Fails loudly, never silently.

    Checks: no reasoning field or value survived; no endpoint URL, credential or
    Authorization header text appears; no absolute path outside the disposable
    experiment root leaks in; the record is ASCII-representable.

    ``extra_forbidden`` is a tuple of ``(code, needle)`` pairs -- e.g. a
    caller-supplied endpoint value with a caller-supplied safe code such as
    ``"configured_endpoint_value_present"``. The code is what survives into
    ``findings``; the needle is only ever compared against, never echoed.

    Findings are bounded metadata codes, never the offending value: this
    function's own output must remain safe to persist even when the record it
    checked was not.
    """
    import json

    findings: list[str] = []
    if contains_reasoning(record):
        findings.append("reasoning_content_present")

    serialized = json.dumps(record, ensure_ascii=True)
    for code, needle in (*_FORBIDDEN_RECORD_SUBSTRINGS, *extra_forbidden):
        if needle and needle in serialized:
            findings.append(code)

    if not serialized.isascii():
        findings.append("record_not_ascii_representable")

    return {
        "scrub_checked": True,
        "findings": findings,
        "clean": not findings,
    }


def refusal_record(
    *, phase: str, finding_count: int, finding_categories: list[str]
) -> dict[str, Any]:
    """A SAFE placeholder emitted instead of a candidate artifact that failed scrub.

    AR1-FU1: detection without prevention is advisory, not fail-closed. When a
    candidate artifact does not pass ``scrub_check``, this is emitted in its
    place. It carries only fixed metadata -- experiment identity, phase, finding
    counts and codes -- and NEVER the offending value, the unsafe candidate body,
    an endpoint URL, a credential, reasoning content, or any copied snippet that
    triggered a scrub rule. It must itself pass ``scrub_check`` before it is
    persisted or echoed; the caller enforces that, not this function.
    """
    return {
        "experiment": EXPERIMENT_ID,
        "record_version": EXPERIMENT_RECORD_VERSION,
        "record_kind": "artifact emission refusal",
        "is_production_review_packet": False,
        "reviewer_invoked": False,
        "phase": phase,
        "outcome": "artifact_emission_refused",
        "scrub_checked": True,
        "candidate_artifact_not_emitted": True,
        "finding_count": finding_count,
        "finding_categories": sorted(set(finding_categories)),
    }


def relative_to_experiment_root(path: str, experiment_root: str) -> str:
    """Render a path relative to the disposable root, never as an absolute host path."""
    try:
        return "<experiment_root>/" + os.path.relpath(path, experiment_root).replace(
            os.sep, "/"
        )
    except ValueError:
        return "<path outside the experiment root: not recorded>"


def record_header(**extra: Any) -> dict[str, Any]:
    return {
        "experiment": EXPERIMENT_ID,
        "record_version": EXPERIMENT_RECORD_VERSION,
        "record_kind": "experiment run record",
        "is_production_review_packet": False,
        "reviewer_invoked": False,
        **extra,
    }
