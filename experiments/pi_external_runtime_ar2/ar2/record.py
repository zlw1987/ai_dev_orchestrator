"""The AR2 experiment run record and the fail-closed emission choke point.

This is an EXPERIMENT-OWNED artifact. It is NOT a production ReviewPacket, it is
not ``review-packet.v4``, and it must never be described as one. **No reviewer is
called in AR2**, no packet is emitted, no ``ApprovedDiffProposalArtifact`` is
fabricated, and no packet version is bumped.

THREE namespaces, kept strictly disjoint:

    runtime_reported_*        Pi's own account of itself   UNTRUSTED CLAIM
    broker_recorded_*         AIDO's own broker activity   AIDO-AUTHORED, DIAGNOSTIC
    orchestrator_observed_*   AIDO's independent Git and
                              filesystem derivation        AUTHORITATIVE

A broker log is **not** repository truth even though AIDO wrote it. It records
the operations AIDO performed *through the broker*: it cannot see a write that
happened another way, it does not know what the filesystem did afterwards, and it
is a record of intent and return value, not of final state.

AR2 adds to AR1-FU1's scrub denylist: the per-run broker token, the capability id,
the pipe name, the endpoint value, ``Authorization``/``Bearer`` material, and any
surviving reasoning content. Detection alone is advisory; :func:`emit_or_refuse`
is what makes it fail closed.
"""

from __future__ import annotations

import json
import os
from typing import Any

from . import EXPERIMENT_ID, EXPERIMENT_RECORD_VERSION
from .protocol import contains_reasoning

CAPABILITY_BOUNDARY: dict[str, Any] = {
    "delegated_broker_enabled": True,
    "path_authority": "AIDO Python broker only; never TypeScript",
    "operations_available_to_the_runtime": ["read_file", "edit_file"],
    "os_filesystem_isolation": False,
    "bash_exposed": False,
    "verify_tool_exposed": False,
    "list_search_or_glob_tool_exposed": False,
    "built_in_filesystem_tools_exposed": False,
    "production_workspace_access_authorized": False,
    "promotion_authorized": False,
    "reviewer_invoked": False,
    "statement": (
        "AIDO minted a delegated implementation capability over one canonical "
        "disposable root, admitting exactly two operation classes, over a read "
        "domain of tracked regular text files and a write domain that is a proper "
        "subset of it, under stated byte and count caps, for the lifetime of one "
        "runtime process. The runtime NOMINATED candidates; AIDO AUTHORIZED some "
        "and refused the rest. This is a capability boundary for operations AIDO "
        "performs on the runtime's behalf. It is NOT an OS sandbox and NOT a "
        "privilege boundary: the extension still runs inside Pi's Node process "
        "with the launching user's full Windows permissions, and a Pi defect, a "
        "dependency defect, an out-of-seam path probe, or a future Pi version "
        "adding an unconfined filesystem path would bypass the broker entirely."
    ),
}

TOKEN_POLICY: dict[str, Any] = {
    "aido_requested_max_output_tokens": None,
    "runtime_native_max_tokens": "pi_catalog_default_unless_reported_by_get_state",
    "generated_models_json_omits_max_tokens": True,
    "meaning_of_null": (
        "AIDO did not request an output-token cap. Never 0, never -1, never "
        "'unlimited'."
    ),
    "process_ipc_and_teardown_limits_are_not_token_limits": True,
}

RESIDUAL_LIMITATIONS: list[str] = [
    "The broker is a capability boundary for operations AIDO performs on the "
    "runtime's behalf. It is NOT an OS sandbox and NOT a privilege boundary. The "
    "extension runs inside Pi's Node process with the launching user's full "
    "Windows permissions. Never write 'sandboxed', 'isolated', 'OS-confined', or "
    "'no host file outside the workspace was touched'.",
    "The per-run pipe name, DACL and token are INTEGRITY AND ATTRIBUTION "
    "controls, not access control against a same-user adversary. That adversary "
    "can read the generated extension config, or the disposable repository "
    "itself, without the broker at all.",
    "Overlapped cancellation bounds NAMED-PIPE I/O only. It does not prove that a "
    "synchronous local filesystem call (stat, open, read, write, fstat) can be "
    "cancelled from the controller. That residual is accepted here because the "
    "root is local disposable scratch, the files are small and AIDO-authored, and "
    "every reparse path is refused.",
    "AIDO's wait ending is not Pi stopping, is not the provider request being "
    "cancelled, and is not backend inference stopping. Nothing here claims "
    "descendants were terminated or that GPU work ended.",
    "Pi 0.84.2 exposes no RPC command that enumerates the active tool registry. "
    "The get_commands identity gate proves the intended extension LOADED at the "
    "expected path; it does not prove the exact contents of the active registry. "
    "Equally, a broker that received only read_file and edit_file frames is "
    "evidence about what was REQUESTED through the broker, never proof of what "
    "the registry contained.",
    "Pi's own path resolver may touch the filesystem before the tool seam is "
    "reached. The accurate claim covers operations performed THROUGH the broker, "
    "not every stat call Pi's internals make.",
    "The read capability is also an INJECTION surface: content read through the "
    "broker is data to AIDO and reads as instructions to the model. AR2's "
    "fixtures are AIDO-authored and free of hostile content by construction. A "
    "real repository is not, which is a second independent reason an OS boundary "
    "is required before real-project use.",
    "Redaction, the response host-detail self-check, and name-only environment "
    "auditing are BACKSTOPS, not guarantees. Nothing here claims the transmitted "
    "material is secret-free.",
    "The disposable repository was observed at one instant. The observation "
    "timestamp and the termination state are recorded rather than a quiescence "
    "claim.",
    "Four synthetic fixtures AIDO wrote itself are not evidence about a real "
    "repository. Nothing here supports promotion to a production workspace, and "
    "authorization inside the capability is never an input to promotion "
    "authority.",
]

# (code, needle) pairs that must never appear anywhere in an emitted record.
# Findings record the CODE only, never the needle: a finding that echoed the
# needle back would turn detection into a leak.
_FORBIDDEN_RECORD_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("http_url_scheme_present", "http://"),
    ("https_url_scheme_present", "https://"),
    ("authorization_header_text_present", "Authorization"),
    ("bearer_token_marker_present", "Bearer "),
    ("named_pipe_endpoint_prefix_present", "\\\\.\\pipe\\"),
)


def broker_secret_denylist(
    *,
    token: str | None,
    capability_id: str | None,
    pipe_name: str | None,
    endpoint_host: str | None = None,
) -> tuple[tuple[str, str], ...]:
    """The AR2-specific scrub additions: the per-run binding and the endpoint.

    ``endpoint_host`` is denylisted separately from the base URL because a bare
    host or IP is still an endpoint value under the experiment retention policy,
    and AR2's R1-b run proved a bare host can reach an artifact by a route the
    base-URL needle does not cover.
    """
    entries: list[tuple[str, str]] = []
    if endpoint_host:
        entries.append(("endpoint_host_value_present", endpoint_host))
    if token:
        entries.append(("broker_token_present", token))
    if capability_id:
        entries.append(("broker_capability_id_present", capability_id))
    if pipe_name:
        entries.append(("broker_pipe_name_present", pipe_name))
    return tuple(entries)


def scrub_check(
    record: dict[str, Any], *, extra_forbidden: tuple[tuple[str, str], ...] = ()
) -> dict[str, Any]:
    """Self-check the record before it is written. Fails loudly, never silently.

    Checks: no reasoning field or value survived; no endpoint URL, credential,
    ``Authorization`` header text, broker token, capability id or pipe name
    appears; and the record is ASCII-representable.

    Findings are bounded metadata codes, never the offending value: this
    function's own output must remain safe to persist even when the record it
    checked was not.
    """
    findings: list[str] = []
    if contains_reasoning(record):
        findings.append("reasoning_content_present")

    serialized = json.dumps(record, ensure_ascii=True)
    for code, needle in (*_FORBIDDEN_RECORD_SUBSTRINGS, *extra_forbidden):
        if not needle:
            continue
        # Compare against BOTH the raw needle and its JSON-escaped spelling. A
        # Windows pipe name is all backslashes, and every one of them is doubled
        # once the record is serialized -- so a raw-only comparison would let the
        # endpoint through exactly where it matters most.
        escaped = json.dumps(needle, ensure_ascii=True)[1:-1]
        if needle in serialized or escaped in serialized:
            findings.append(code)

    if not serialized.isascii():
        findings.append("record_not_ascii_representable")

    return {"scrub_checked": True, "findings": findings, "clean": not findings}


def refusal_record(
    *, phase: str, finding_count: int, finding_categories: list[str]
) -> dict[str, Any]:
    """A SAFE placeholder emitted INSTEAD of a candidate that failed scrub.

    Carries only fixed metadata -- experiment identity, phase, finding counts and
    codes -- and NEVER the offending value, the unsafe candidate body, an endpoint,
    a credential, reasoning content, or any copied snippet that triggered a rule.
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
        "trust_namespaces": {
            "runtime_reported_*": "UNTRUSTED CLAIM (the runtime's own account)",
            "broker_recorded_*": "AIDO-AUTHORED, DIAGNOSTIC ONLY (never repository truth)",
            "orchestrator_observed_*": "AUTHORITATIVE (AIDO's independent derivation)",
        },
        **extra,
    }


def redact_value(value: Any, needles: tuple[str, ...]) -> Any:
    """A redaction BACKSTOP, never a guarantee.

    If runtime- or child-produced text happened to echo a secret or an endpoint,
    replace it before the record is written. This does not make the record
    provably secret-free and must never be described as if it did.
    """
    if isinstance(value, str):
        out = value
        for needle in needles:
            if needle:
                out = out.replace(needle, "<redacted>")
        return out
    if isinstance(value, dict):
        return {k: redact_value(v, needles) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v, needles) for v in value]
    return value
