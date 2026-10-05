"""The read-only, post-hoc HPP-1 profile binding verifier (PE-2c, PE-1 Sec. 21).

**Never in the runtime path, and it grants nothing.** Nothing in P, the gate,
L1, L14, L21A, the executor, the runner or any writer imports or calls this
module. It is review tooling: given ONE stage execution's v3 artifacts it
answers whether their profile claims bind to the committed policy chain of the
verifying checkout, and returns one closed code. It never repairs, rewrites,
moves or reinterprets anything, and a verified result recreates no authority.

**The policy is the accepted PE-2b load, never a second parser.** The committed
chain is the one the strict loader already loaded and sealed at import
(``pi_profile_policy_loader._GENUINE_POLICY_LOAD``): its per-revision
``(revision, file SHA-256, eligible set)`` summaries and its loader-recomputed
``(profile_id, declared package_version)`` pairs. Earlier heads keep their
eligible sets (append-only chain), so an artifact bound to an earlier head is
checked against THAT revision, never against the current head.

**What it checks, exactly (PE-1 Sec. 21).**

1. every artifact is v3: a v1 or v2 artifact is refused outright -- HPP-1 is
   never applied to historical evidence;
2. every v3 artifact of the stage carries the same APS head and the same
   contract/B7 literals as the stage closure;
3. a committed revision whose file SHA-256 equals that head exists;
4. at that revision, ``stage_pi_profile_id`` and every non-null run
   ``pi_profile_id`` are eligible and equal the stage profile, and every
   declared version equals that profile's loader-bound declared version (an
   integrity binding of recorded provenance to committed bytes; it decides
   no authority);
5. ``ordinal_pi_profile_binding`` agrees with every ``RECORD_EMITTED`` run
   record (``STAGE_PROFILE`` iff that record's ``pi_profile_id`` equals the
   stage profile). Nothing at all is inferred for a ``NO_RUN_EVIDENCE`` or
   ``NOT_EXECUTED`` ordinal, and a refusal record is NEVER read as profile
   evidence -- only its head and literals are checked (rule 2).
"""

from __future__ import annotations

from typing import Any, Mapping

from . import (
    REFUSAL_RECORD_KIND,
    REFUSAL_RECORD_VERSION_V3,
    RUN_RECORD_KIND,
    RUN_RECORD_VERSION_V3,
    STAGE_CLOSURE_RECORD_KIND,
    STAGE_CLOSURE_RECORD_VERSION_V3,
)
from . import pi_profile_policy_loader as _loader
from .halt import (
    EMISSION_EVIDENCE_REFUSED,
    EMISSION_RECORD_EMITTED,
    ORDINAL_PI_PROFILE_STAGE_PROFILE,
)
from .pi_payload import is_lowercase_hex64
from .records import (
    _require_valid_cfg1_refusal_payload_v3,
    _require_valid_cfg1_run_payload_v3,
    _require_valid_cfg1_stage_closure_payload_v3,
)
from .schedule import declared_ordinals

PI_PROFILE_BINDING_VERIFIED = "PI_PROFILE_BINDING_VERIFIED"
PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT = "PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT"
PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT = "PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT"
PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT = "PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT"
PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH = "PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH"
PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH = (
    "PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH"
)
PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN = (
    "PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN"
)
PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD = (
    "PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD"
)
PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH = (
    "PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH"
)
PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH = "PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH"
PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH = "PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH"
PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD = "PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD"
PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT = (
    "PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT"
)
PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE = "PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE"

#: The closed result vocabulary. Exactly one pass code.
PI_PROFILE_BINDING_RESULTS: frozenset[str] = frozenset(
    {
        PI_PROFILE_BINDING_VERIFIED,
        PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT,
        PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT,
        PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT,
        PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH,
        PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH,
        PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN,
        PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD,
        PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH,
        PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH,
        PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH,
        PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD,
        PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT,
        PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE,
    }
)

#: The literal fields every v3 artifact must carry identically (rule 2).
_COMMON_POLICY_FIELDS: tuple[str, ...] = (
    "pi_payload_contract",
    "pi_seam_contract",
    "pi_consumer_contract",
    "pi_profile_policy_revision",
    "pi_profile_set_head_sha256",
    "pi_profile_authority_scope",
    "pi_external_runtime_residual",
)

_RUN_PAIR = (RUN_RECORD_VERSION_V3, RUN_RECORD_KIND)
_REFUSAL_PAIR = (REFUSAL_RECORD_VERSION_V3, REFUSAL_RECORD_KIND)
_STAGE_CLOSURE_PAIR = (STAGE_CLOSURE_RECORD_VERSION_V3, STAGE_CLOSURE_RECORD_KIND)


class _Refused(Exception):
    """Internal control flow only: one closed refusal code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _pair(artifact: Mapping[str, Any]) -> tuple[object, object]:
    return artifact.get("record_version"), artifact.get("record_kind")


def _committed_revision_for_head(head: str) -> tuple[frozenset[str], dict[str, str]]:
    """The eligible set at the revision whose file SHA-256 equals ``head``,
    and the loader-recomputed declared version of every committed profile."""
    load = _loader._GENUINE_POLICY_LOAD
    if type(load) is not _loader._PolicyLoad:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE)
    revisions = load.revisions
    declared_pairs = load.profile_declared_versions
    if type(revisions) is not tuple or type(declared_pairs) is not tuple:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE)
    eligible: frozenset[str] | None = None
    for summary in revisions:
        if (
            type(summary) is not tuple
            or len(summary) != 3
            or type(summary[1]) is not str
            or type(summary[2]) is not frozenset
        ):
            raise _Refused(PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE)
        if summary[1] == head:
            eligible = summary[2]
            break
    if eligible is None:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_HEAD_NOT_IN_COMMITTED_CHAIN)
    declared_versions: dict[str, str] = {}
    for pair in declared_pairs:
        if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or type(pair[1]) is not str:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_POLICY_UNAVAILABLE)
        declared_versions[pair[0]] = pair[1]
    return eligible, declared_versions


def _require_bound_profile(
    profile_id: str, declared: object, eligible: frozenset[str], declared_versions: dict[str, str]
) -> None:
    """Rule 4 for one non-null profile id and the declared version beside it."""
    if profile_id not in eligible:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_PROFILE_NOT_ELIGIBLE_AT_HEAD)
    committed = declared_versions.get(profile_id)
    if type(committed) is not str or type(declared) is not str or declared != committed:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH)


def _verify(stage_closure: object, run_path_artifacts: object) -> str:
    if type(stage_closure) is not dict or type(run_path_artifacts) is not dict:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT)

    # -- rule 1: v3 only; every artifact validates under ITS OWN v3 validator
    if _pair(stage_closure) != _STAGE_CLOSURE_PAIR:
        raise _Refused(PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT)
    try:
        _require_valid_cfg1_stage_closure_payload_v3(stage_closure)
    except Exception:  # noqa: BLE001 - any schema failure is a refusal
        raise _Refused(PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT) from None
    stage_id = stage_closure["stage_id"]
    stage_execution_id = stage_closure["stage_execution_id"]
    ordinals = declared_ordinals(stage_id)
    status = stage_closure["ordinal_status"]
    binding = stage_closure["ordinal_pi_profile_binding"]

    run_records: dict[int, dict] = {}
    refusal_records: dict[int, dict] = {}
    for ordinal, artifact in run_path_artifacts.items():
        if type(ordinal) is not int or ordinal not in ordinals or type(artifact) is not dict:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT)
        pair = _pair(artifact)
        if pair == _RUN_PAIR:
            validator, bucket = _require_valid_cfg1_run_payload_v3, run_records
        elif pair == _REFUSAL_PAIR:
            validator, bucket = _require_valid_cfg1_refusal_payload_v3, refusal_records
        else:
            # A v1/v2 run or refusal record (or anything else) is never read
            # under HPP-1 semantics.
            raise _Refused(PI_PROFILE_BINDING_REFUSED_HISTORICAL_ARTIFACT)
        try:
            validator(artifact)
        except Exception:  # noqa: BLE001
            raise _Refused(PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT) from None
        if (
            artifact["stage_id"] != stage_id
            or artifact["stage_execution_id"] != stage_execution_id
            or artifact["run_ordinal"] != ordinal
        ):
            raise _Refused(PI_PROFILE_BINDING_REFUSED_STAGE_MISMATCH)
        bucket[ordinal] = artifact

    # Only confirmed occupants are artifacts of the stage: a run record at a
    # RECORD_EMITTED ordinal, a refusal record at an EVIDENCE_REFUSED one.
    for ordinal in run_records:
        if status[str(ordinal)] != EMISSION_RECORD_EMITTED:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT)
    for ordinal in refusal_records:
        if status[str(ordinal)] != EMISSION_EVIDENCE_REFUSED:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_UNCONFIRMED_ORDINAL_ARTIFACT)

    # -- rule 2: one head and one set of literals across every v3 artifact --
    for artifact in list(run_records.values()) + list(refusal_records.values()):
        for field in _COMMON_POLICY_FIELDS:
            left, right = artifact[field], stage_closure[field]
            if type(left) is not type(right) or left != right:
                raise _Refused(PI_PROFILE_BINDING_REFUSED_HEAD_OR_LITERAL_MISMATCH)

    # -- rule 3: the committed revision whose file SHA-256 is that head -----
    head = stage_closure["pi_profile_set_head_sha256"]
    if not is_lowercase_hex64(head):
        raise _Refused(PI_PROFILE_BINDING_REFUSED_INVALID_ARTIFACT)
    eligible, declared_versions = _committed_revision_for_head(head)

    # -- rule 4: eligibility and declared versions AT THAT revision ----------
    stage_profile = stage_closure["stage_pi_profile_id"]
    if stage_profile is not None:
        _require_bound_profile(
            stage_profile,
            stage_closure["stage_pi_profile_declared_package_version"],
            eligible,
            declared_versions,
        )
    for record in run_records.values():
        run_profile = record["pi_profile_id"]
        if run_profile is None:
            continue
        if stage_profile is None or run_profile != stage_profile:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_RUN_PROFILE_MISMATCH)
        _require_bound_profile(
            run_profile, record["pi_profile_declared_package_version"], eligible, declared_versions
        )

    # -- rule 5: the binding vs every RECORD_EMITTED run record -------------
    for ordinal in ordinals:
        key = str(ordinal)
        if status[key] != EMISSION_RECORD_EMITTED:
            continue  # NO_RUN_EVIDENCE / NOT_EXECUTED: nothing is inferred
        record = run_records.get(ordinal)
        if record is None:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_MISSING_RUN_RECORD)
        record_binds_stage = stage_profile is not None and record["pi_profile_id"] == stage_profile
        if (binding[key] == ORDINAL_PI_PROFILE_STAGE_PROFILE) != record_binds_stage:
            raise _Refused(PI_PROFILE_BINDING_REFUSED_BINDING_MISMATCH)
    return PI_PROFILE_BINDING_VERIFIED


def verify_stage_pi_profile_binding(stage_closure: object, run_path_artifacts: object) -> str:
    """Verify ONE stage execution's v3 profile claims against the committed chain.

    ``stage_closure`` is the parsed stage-closure artifact; ``run_path_artifacts``
    maps an exact ``int`` ordinal to the parsed artifact confirmed at that
    ordinal's run path (a ``run.v3`` record at a ``RECORD_EMITTED`` ordinal, a
    ``refusal.v3`` record at an ``EVIDENCE_REFUSED`` one). Returns exactly one
    of :data:`PI_PROFILE_BINDING_RESULTS`. Total: nothing raises out, no text
    of any exception is retained, and nothing is written.
    """
    try:
        return _verify(stage_closure, run_path_artifacts)
    except _Refused as refusal:
        return refusal.code
    except Exception:  # noqa: BLE001 - any other defect is a malformed input
        return PI_PROFILE_BINDING_REFUSED_MALFORMED_INPUT
