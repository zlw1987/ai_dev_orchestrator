"""``pi-implementer-qualification.v2`` record schema and safe emission (Sec. 26).

This is an EXPERIMENT-OWNED artifact. It is NOT a ``ReviewPacket``, never
``review-packet.v4``, and never emitted through the reviewer path, and no
reviewer is called anywhere in this package.

**The builder is an invariant GATE, not a formatter** (Phase 5F3B-I1-FU1,
extended by 5F3B-I1-FU2). ``pi-implementer-qualification.v2`` must not be
able to express an internally impossible run, because an impossible record
that reaches disk is indistinguishable from a real one afterwards -- and
these artifacts are immutable, so there is no later opportunity to correct
it. Every cross-field rule the design fixes is therefore enforced here, at
construction, and a violating record is **rejected, never coerced**:

    candidate <-> model id     the frozen candidate <-> model pairing (Sec. 5;
                               extended across rounds by 5F3B-Q3-PRE1)
    prompt/run shape           pre-prompt refusal vs. post-prompt primary run
    validity                   scoring_eligible IFF run_validity == VALID
    classification coherence   Sec. 8's subclassification containment
    identity coherence         task_revision belongs to task_id;
                               route_provenance.model_id == model_id
    AUTONOMOUS_PASS shape      (FU2) the full cross-field bundle Sec. 9's
                               one-shot policy requires for a genuine pass
    primary vs. recovery       (FU2) THIS builder emits only PRIMARY
                               evidence; supervised recovery is REJECTED here

**This builder emits PRIMARY qualification evidence only** (Sec. 10, Layer
3). Supervised recovery is, by design, a SEPARATE child evidence item that
may exist only after the primary record is sealed, and it must never
annotate, upgrade, or be embedded inside the primary record it followed.
This function therefore accepts only ``supervised_recovery ==
"NOT_ATTEMPTED"`` -- a future recovery slice records ``PASS``/``FAIL``
in its own, separate child schema, not here.

Emission goes through :mod:`qualification.safety`'s single choke point,
which requires an explicit :class:`~qualification.safety.ArtifactSafetyContext`
and writes with ``O_CREAT | O_EXCL`` so an emitted artifact can never be
overwritten. See :mod:`qualification.lineage` for how a fixture defect or an
infrastructure-contamination finding is represented afterward -- as
separate, NEW, linked evidence, never as an edit -- and for how that lineage
now (FU2) reads and verifies the OLD and REPLACEMENT records it references,
rather than trusting caller-supplied identifiers about them.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from . import (
    FIXTURE_SCHEMA_VERSION,
    PACKAGE_ID,
    QUALIFICATION_POLICY_REVISION,
    RECORD_VERSION,
)
from .safety import (
    ArtifactSafetyContext,
    build_refusal_record,
    emit_evidence_or_refuse,
)

EXPERIMENT_ID = PACKAGE_ID

RECORD_KIND = "qualification run record"

#: The frozen candidate <-> served-model-id pairing (Sec. 5; extended by
#: 5F3B-Q3-PRE1 with a second-round candidate, per
#: ``docs/PHASE_5F3B_Q3_DESIGN_SECOND_ROUND_CANDIDATE_C_AUTHORIZATION.md``).
#: Identity/schema data only. No candidate-specific behavior exists anywhere
#: in this package -- every candidate shares one corpus, one hard bar, one
#: ranking evaluator, one token policy and one prompt-count policy. Adding a
#: new key entering qualification from scratch is additive: it does not
#: alter A's or B's existing pairing, evidence, or disposition.
CANDIDATE_MODEL_IDS: dict[str, str] = {
    "A": "qwen3-coder-next",
    "B": "minimax-m2.7",
    "C": "qwen3.6-27b",
}

#: ``IQ-4T`` is declared by the design's Sec. 26 schema as the CONDITIONAL
#: tie-break task id. Accepting the identifier in this enum is not the same
#: as implementing it: I1 ships no IQ-4T fixture, prompt, or contract, and
#: Sec. 21's tie-break case remains unauthorized.
VALID_TASK_IDS: frozenset[str] = frozenset({"IQ-1", "IQ-2", "IQ-3", "IQ-4T"})

VALID_RUN_VALIDITY: frozenset[str] = frozenset(
    {
        "VALID",
        "INFRASTRUCTURE_CONTAMINATED",
        "ATTRIBUTION_UNDETERMINED",
        "INVALIDATED_BY_FIXTURE_DEFECT",
    }
)

VALID_AUTONOMOUS_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"AUTONOMOUS_PASS", "AUTONOMOUS_FAIL", "INFRASTRUCTURE_REFUSAL"}
)

#: Sec. 8's diagnostic subclassifications. Every one of these except
#: ``NONE`` is a strict subclassification OF ``AUTONOMOUS_FAIL`` -- never a
#: peer of the top-level taxonomy.
VALID_DIAGNOSTIC_SUBCLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "NONE",
        "PREMATURE_SETTLE",
        "RUNTIME_TIMEOUT",
        "RUNTIME_STALLED",
        "COMPLETED_BUT_WRONG",
        "UNTRUSTED_REPOSITORY_STATE",
    }
)

_FAIL_ONLY_SUBCLASSIFICATIONS: frozenset[str] = VALID_DIAGNOSTIC_SUBCLASSIFICATIONS - {"NONE"}

#: The full schema enum (Sec. 26). Kept for documentation of the eventual
#: shape a SEPARATE future recovery child artifact will use -- NOT accepted
#: by this primary-record builder, which enforces the narrower
#: :data:`PRIMARY_RECORD_SUPERVISED_RECOVERY` below.
VALID_SUPERVISED_RECOVERY: frozenset[str] = frozenset({"PASS", "FAIL", "NOT_ATTEMPTED"})

#: (FU2) A PRIMARY qualification run record is sealed before any supervised-
#: recovery probe may even be attempted (Sec. 10), so no primary record can
#: truthfully carry ``PASS`` or ``FAIL`` here -- that evidence, if it is ever
#: gathered, belongs in a separate child artifact this slice does not
#: implement.
PRIMARY_RECORD_SUPERVISED_RECOVERY: frozenset[str] = frozenset({"NOT_ATTEMPTED"})

#: (FU2) Sec. 16/H-1: within a VALID, scoring-eligible primary run, the model
#: outcome is one of exactly these two -- never absent, and never the
#: pre-prompt-only ``INFRASTRUCTURE_REFUSAL`` shape.
_VALID_SCORING_ELIGIBLE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"AUTONOMOUS_PASS", "AUTONOMOUS_FAIL"}
)

TOKEN_POLICY: dict[str, Any] = {
    "aido_requested_max_output_tokens": None,
    "runtime_native_max_tokens": "backend_capability_limit_never_an_aido_requested_cap",
    "generated_pi_model_config_omits_max_tokens": True,
    "meaning_of_null": (
        "AIDO did not request an output-token cap. Never 0, never -1, never 'unlimited'."
    ),
}

TRUST_NAMESPACES: dict[str, str] = {
    "runtime_reported_*": "UNTRUSTED CLAIM (the runtime's own account of itself)",
    "broker_recorded_*": "AIDO-AUTHORED, DIAGNOSTIC ONLY (never repository truth)",
    "orchestrator_observed_*": "AUTHORITATIVE (AIDO's independent derivation)",
}


class RecordInvariantError(ValueError):
    """A proposed record describes an internally impossible run. Rejected."""


#: 5F3B-LIVE1-C4, extended by C4-FU1: the header keys whose value is FIXED
#: AIDO METADATA of the ``.v2`` schema and is never a caller's to supply.
#: ``record_header(**extra)`` merges caller extras, so a caller-supplied key
#: of either name would otherwise WIN the merge and stamp a policy revision or
#: a schema version AIDO never declared onto a retained, immutable artifact.
#:
#: C4-FU1 added ``record_version``. C4 made the bump and the policy field ONE
#: fact -- ``.v2`` MEANS "carries a policy binding" -- so a caller able to
#: supply the version through ``**extra`` could manufacture an internally
#: inconsistent header (the declared revision beside a stale ``.v1``) without
#: ever touching the revision itself. Both halves of that one fact are fixed,
#: or neither is. This set is deliberately NOT every historical fixed header
#: key: it is exactly the C4 ``.v2`` metadata pair.
_FIXED_HEADER_METADATA_KEYS: tuple[str, str] = (
    "record_version",
    "qualification_policy_revision",
)
_CALLER_FORBIDDEN_HEADER_KEYS: frozenset[str] = frozenset(_FIXED_HEADER_METADATA_KEYS)

#: The primary record's own values for those two keys. The attempt artifact
#: has the same key NAMES (it imports the set above) and its own version
#: value, which is exactly why the names and the values are declared apart.
_FIXED_PRIMARY_HEADER_METADATA: dict[str, str] = {
    "record_version": RECORD_VERSION,
    "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
}


def _reject_caller_supplied_fixed_metadata(extra: dict[str, Any]) -> None:
    """Refuse a caller attempting to supply a FIXED-metadata header key.

    Layer 1 of two independent defences (see :func:`record_header`). Refusal
    rather than silent replacement, because a caller passing either key is
    either forging provenance or badly confused, and both deserve to fail
    loudly rather than be quietly corrected.
    """
    forged = sorted(_CALLER_FORBIDDEN_HEADER_KEYS.intersection(extra))
    if forged:
        raise RecordInvariantError(
            f"{forged!r} is FIXED AIDO metadata on every qualification record and "
            "is not a caller-supplied field; it is stamped from this package's "
            "own declaration sites. A record whose schema version or policy "
            "revision came from its caller would prove nothing about the schema "
            "it satisfies or the policy that produced it."
        )


def record_header(**extra: Any) -> dict[str, Any]:
    """The primary record's header.

    ``record_version`` and ``qualification_policy_revision`` (5F3B-LIVE1-C4,
    C4-FU1) are FIXED AIDO metadata, protected by TWO independent mechanisms
    here and a THIRD at the emission boundary:

    1. a caller supplying either is REFUSED outright, above;
    2. even if that guard were bypassed, both authoritative constants are
       re-stamped AFTER ``**extra`` is merged, so the last write -- AIDO's --
       wins the merge. A forged value cannot survive.
    3. :func:`_require_valid_primary_payload` re-derives both from the
       declaration sites at emission, so a hand-built dict that never came
       through this function is refused too.

    The re-stamp is an ``update`` of an already-merged mapping rather than a
    trailing literal, so each key keeps its canonical position in the header
    while taking AIDO's value.
    """
    _reject_caller_supplied_fixed_metadata(extra)
    header = {
        "experiment": EXPERIMENT_ID,
        "record_version": RECORD_VERSION,
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "external_prior_not_scored": True,
        "trust_namespaces": dict(TRUST_NAMESPACES),
        "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        **extra,
    }
    # -- FIXED AIDO METADATA: re-stamped LAST, after **extra, deliberately.
    header.update(_FIXED_PRIMARY_HEADER_METADATA)
    return header


def _validate_identity(candidate: str, model_id: str, task_id: str, task_revision: str) -> None:
    if candidate not in CANDIDATE_MODEL_IDS:
        raise RecordInvariantError(
            f"unknown candidate {candidate!r}; the declared candidate domain is "
            f"exactly {sorted(CANDIDATE_MODEL_IDS)}"
        )
    expected_model = CANDIDATE_MODEL_IDS[candidate]
    if model_id != expected_model:
        raise RecordInvariantError(
            f"candidate {candidate!r} is bound to model id {expected_model!r}, but the "
            f"record proposes {model_id!r}. Evidence belongs to a model x route tuple, "
            "so a mismatched pairing is refused rather than recorded."
        )
    if task_id not in VALID_TASK_IDS:
        raise RecordInvariantError(f"unknown task_id {task_id!r}; declared: {sorted(VALID_TASK_IDS)}")
    if not task_revision.startswith(f"{task_id}@"):
        raise RecordInvariantError(
            f"task_revision {task_revision!r} does not belong to task_id {task_id!r}; "
            "a cross-task revision substitution is refused."
        )


def _validate_run_shape(
    *,
    infrastructure_refusal: bool,
    semantic_prompts_sent: int,
    run_validity: str | None,
    scoring_eligible: bool,
) -> None:
    if not isinstance(infrastructure_refusal, bool):
        raise RecordInvariantError("infrastructure_refusal must be a bool")
    if not isinstance(scoring_eligible, bool):
        raise RecordInvariantError("scoring_eligible must be a bool")
    if not isinstance(semantic_prompts_sent, int) or isinstance(semantic_prompts_sent, bool):
        raise RecordInvariantError("semantic_prompts_sent must be an int")

    if infrastructure_refusal:
        # Sec. 11.5 / Sec. 17.3: a PRE-prompt gate outcome. No primary run
        # occurred, so there is no run to assign a run_validity value to.
        if semantic_prompts_sent != 0:
            raise RecordInvariantError(
                "a pre-prompt infrastructure_refusal requires semantic_prompts_sent == 0"
            )
        if run_validity is not None:
            raise RecordInvariantError(
                "a pre-prompt infrastructure_refusal has no run to validate; "
                "run_validity must be absent"
            )
        if scoring_eligible:
            raise RecordInvariantError(
                "a pre-prompt infrastructure_refusal is trivially not scoring_eligible"
            )
        return

    # Sec. 17.3: a post-prompt run truthfully retains semantic_prompts_sent == 1
    # even when contaminated or attribution-undetermined. It is never described
    # as though no attempt occurred.
    if semantic_prompts_sent != 1:
        raise RecordInvariantError(
            "a primary run record requires semantic_prompts_sent == 1; the one "
            "authorized prompt for that task genuinely was spent"
        )
    if run_validity is None:
        raise RecordInvariantError("a post-prompt run record requires a run_validity value")
    if run_validity not in VALID_RUN_VALIDITY:
        raise RecordInvariantError(
            f"unknown run_validity {run_validity!r}; declared: {sorted(VALID_RUN_VALIDITY)}"
        )
    if scoring_eligible != (run_validity == "VALID"):
        raise RecordInvariantError(
            f"scoring_eligible must be true if and only if run_validity == VALID; got "
            f"run_validity={run_validity!r} with scoring_eligible={scoring_eligible!r}"
        )


def _validate_classification(
    *,
    autonomous_classification: str | None,
    diagnostic_subclassification: str | None,
    infrastructure_refusal: bool,
) -> None:
    if (
        autonomous_classification is not None
        and autonomous_classification not in VALID_AUTONOMOUS_CLASSIFICATIONS
    ):
        raise RecordInvariantError(
            f"unknown autonomous_classification {autonomous_classification!r}; declared: "
            f"{sorted(VALID_AUTONOMOUS_CLASSIFICATIONS)}"
        )
    if (
        diagnostic_subclassification is not None
        and diagnostic_subclassification not in VALID_DIAGNOSTIC_SUBCLASSIFICATIONS
    ):
        raise RecordInvariantError(
            f"unknown diagnostic_subclassification {diagnostic_subclassification!r}; declared: "
            f"{sorted(VALID_DIAGNOSTIC_SUBCLASSIFICATIONS)}"
        )

    is_infra_classification = autonomous_classification == "INFRASTRUCTURE_REFUSAL"
    if is_infra_classification and not infrastructure_refusal:
        raise RecordInvariantError(
            "an INFRASTRUCTURE_REFUSAL classification requires infrastructure_refusal == true"
        )
    if infrastructure_refusal and autonomous_classification not in (None, "INFRASTRUCTURE_REFUSAL"):
        raise RecordInvariantError(
            "a pre-prompt infrastructure refusal cannot also carry the model "
            f"classification {autonomous_classification!r}; it is not scored as a model outcome"
        )

    # Sec. 8: PREMATURE_SETTLE / RUNTIME_TIMEOUT / RUNTIME_STALLED and the
    # remaining diagnostic shapes are subclassifications OF AUTONOMOUS_FAIL.
    if diagnostic_subclassification in _FAIL_ONLY_SUBCLASSIFICATIONS:
        if autonomous_classification != "AUTONOMOUS_FAIL":
            raise RecordInvariantError(
                f"{diagnostic_subclassification!r} is a subclassification of AUTONOMOUS_FAIL, "
                f"but the record proposes autonomous_classification="
                f"{autonomous_classification!r}"
            )


def _validate_autonomous_pass_shape(
    *,
    run_validity: str | None,
    scoring_eligible: bool,
    autonomous_classification: str | None,
    diagnostic_subclassification: str | None,
    operator_continuation: bool,
    automatic_semantic_retry: bool,
    semantic_prompts_sent: int,
    infrastructure_refusal: bool,
) -> None:
    """(FU2) The cross-field bundle a genuine ``AUTONOMOUS_PASS`` requires,
    and the constraint on every ``VALID``, scoring-eligible run's
    classification field.

    Closes two previously-permitted impossible records: ``AUTONOMOUS_PASS``
    co-occurring with ``operator_continuation`` or
    ``automatic_semantic_retry`` (Sec. 9: "No operator continuation inside
    the primary result" / "No automatic semantic retry, for any reason"),
    and a ``VALID`` + scoring-eligible run left with no model classification
    at all, or mislabelled with the pre-prompt-only
    ``INFRASTRUCTURE_REFUSAL`` shape.
    """
    if run_validity == "VALID" and scoring_eligible:
        if autonomous_classification not in _VALID_SCORING_ELIGIBLE_CLASSIFICATIONS:
            raise RecordInvariantError(
                "a VALID, scoring_eligible primary run must be classified "
                f"AUTONOMOUS_PASS or AUTONOMOUS_FAIL, not "
                f"{autonomous_classification!r}"
            )

    if autonomous_classification != "AUTONOMOUS_PASS":
        return

    if infrastructure_refusal:
        raise RecordInvariantError("AUTONOMOUS_PASS requires infrastructure_refusal == false")
    if semantic_prompts_sent != 1:
        raise RecordInvariantError("AUTONOMOUS_PASS requires semantic_prompts_sent == 1")
    if run_validity != "VALID":
        raise RecordInvariantError(
            f"AUTONOMOUS_PASS requires run_validity == VALID, got {run_validity!r}"
        )
    if not scoring_eligible:
        raise RecordInvariantError("AUTONOMOUS_PASS requires scoring_eligible == true")
    if operator_continuation:
        raise RecordInvariantError(
            "AUTONOMOUS_PASS cannot coexist with operator_continuation == true "
            "(Sec. 9); a run with operator continuation is truthfully representable "
            "only as AUTONOMOUS_FAIL"
        )
    if automatic_semantic_retry:
        raise RecordInvariantError(
            "AUTONOMOUS_PASS cannot coexist with automatic_semantic_retry == true "
            "(Sec. 9); a run with an automatic semantic retry is truthfully "
            "representable only as AUTONOMOUS_FAIL"
        )
    if diagnostic_subclassification != "NONE":
        raise RecordInvariantError(
            f"AUTONOMOUS_PASS requires diagnostic_subclassification == NONE, got "
            f"{diagnostic_subclassification!r}"
        )


def _validate_route_provenance(route_provenance: dict[str, Any], model_id: str) -> None:
    # (5F3B-LIVE1-C4-FU2) An exact `dict`, not merely `isinstance(..., dict)`:
    # a `dict` SUBCLASS can override `.get()` to report the expected model id
    # while its real underlying storage -- the storage `json.dump` actually
    # serializes from (via `.items()`, never `.get()`) -- holds a different
    # one. `isinstance` alone let such an object satisfy the comparison below
    # and still persist the substituted model. Every call site reachable from
    # a genuine caller already hands over an ordinary dict, so this refuses
    # only a shape that was never honestly reachable.
    if type(route_provenance) is not dict:
        raise RecordInvariantError(
            "route_provenance must be an ordinary dict; a Mapping of another "
            "type -- including a dict subclass -- is refused, because what it "
            "reports through `.get()` and what would be serialized from its "
            "real storage need not agree"
        )
    recorded = route_provenance.get("model_id")
    # (C4-FU1) An ordinary str or nothing: an equality-forging `str` subclass
    # would otherwise satisfy the comparison below while serializing a
    # substituted model id into the immutable artifact.
    if recorded is not None and type(recorded) is not str:
        raise RecordInvariantError(
            "route_provenance.model_id must be exactly None or an ordinary str, "
            f"got {type(recorded).__name__}"
        )
    if recorded is not None and recorded != model_id:
        raise RecordInvariantError(
            f"route_provenance.model_id {recorded!r} disagrees with the record's model_id "
            f"{model_id!r}; qualification evidence belongs to a model x route tuple"
        )


def _validate_primary_invariants(
    *,
    candidate: str,
    model_id: str,
    task_id: str,
    task_revision: str,
    semantic_prompts_sent: int,
    infrastructure_refusal: bool,
    run_validity: str | None,
    scoring_eligible: bool,
    autonomous_classification: str | None,
    diagnostic_subclassification: str | None,
    operator_continuation: bool,
    automatic_semantic_retry: bool,
    route_provenance: dict[str, Any],
    supervised_recovery: str,
    supersedes_task_revision: str | None,
) -> None:
    """THE frozen primary-record invariant contract, in one place.

    5F3B-LIVE1-C4-FU1 extracted this from :func:`build_qualification_record`
    unchanged -- same rules, same order, same messages -- so that the durable
    emission boundary can re-derive the SAME contract from a payload's own
    declared facts instead of trusting that the builder was called. Two
    copies of these rules is exactly how the builder and the emission gate
    could come to accept different records.
    """
    _validate_identity(candidate, model_id, task_id, task_revision)
    _validate_run_shape(
        infrastructure_refusal=infrastructure_refusal,
        semantic_prompts_sent=semantic_prompts_sent,
        run_validity=run_validity,
        scoring_eligible=scoring_eligible,
    )
    _validate_classification(
        autonomous_classification=autonomous_classification,
        diagnostic_subclassification=diagnostic_subclassification,
        infrastructure_refusal=infrastructure_refusal,
    )
    _validate_autonomous_pass_shape(
        run_validity=run_validity,
        scoring_eligible=scoring_eligible,
        autonomous_classification=autonomous_classification,
        diagnostic_subclassification=diagnostic_subclassification,
        operator_continuation=operator_continuation,
        automatic_semantic_retry=automatic_semantic_retry,
        semantic_prompts_sent=semantic_prompts_sent,
        infrastructure_refusal=infrastructure_refusal,
    )
    _validate_route_provenance(route_provenance, model_id)

    if supervised_recovery not in PRIMARY_RECORD_SUPERVISED_RECOVERY:
        raise RecordInvariantError(
            f"invalid supervised_recovery {supervised_recovery!r} for a PRIMARY "
            "qualification run record; this builder accepts only "
            f"{sorted(PRIMARY_RECORD_SUPERVISED_RECOVERY)} -- a PASS/FAIL recovery "
            "outcome belongs in a separate child evidence item created after this "
            "primary record is sealed (Sec. 10), never embedded in it"
        )
    if not isinstance(operator_continuation, bool):
        raise RecordInvariantError("operator_continuation must be a bool")
    if not isinstance(automatic_semantic_retry, bool):
        raise RecordInvariantError("automatic_semantic_retry must be a bool")
    if supersedes_task_revision is not None and not supersedes_task_revision.startswith(
        f"{task_id}@"
    ):
        raise RecordInvariantError(
            f"supersedes_task_revision {supersedes_task_revision!r} does not belong to "
            f"task_id {task_id!r}; a replacement record supersedes the SAME task's "
            "earlier revision, never a different task's"
        )


def build_qualification_record(
    *,
    candidate: str,
    model_id: str,
    task_id: str,
    task_revision: str,
    semantic_prompts_sent: int,
    infrastructure_refusal: bool,
    run_validity: str | None,
    scoring_eligible: bool,
    autonomous_classification: str | None,
    diagnostic_subclassification: str | None,
    operator_continuation: bool,
    automatic_semantic_retry: bool,
    pi_runtime: dict[str, Any],
    route_provenance: dict[str, Any],
    verification: dict[str, Any],
    scope_result: dict[str, Any],
    report_accuracy: dict[str, Any],
    supervised_recovery: str = "NOT_ATTEMPTED",
    supersedes_task_revision: str | None = None,
) -> dict[str, Any]:
    """Build one validated ``pi-implementer-qualification.v2`` record.

    Pure; does not write. Raises :class:`RecordInvariantError` for any
    internally impossible record rather than coercing it into a plausible
    one.
    """
    _validate_primary_invariants(
        candidate=candidate,
        model_id=model_id,
        task_id=task_id,
        task_revision=task_revision,
        semantic_prompts_sent=semantic_prompts_sent,
        infrastructure_refusal=infrastructure_refusal,
        run_validity=run_validity,
        scoring_eligible=scoring_eligible,
        autonomous_classification=autonomous_classification,
        diagnostic_subclassification=diagnostic_subclassification,
        operator_continuation=operator_continuation,
        automatic_semantic_retry=automatic_semantic_retry,
        route_provenance=route_provenance,
        supervised_recovery=supervised_recovery,
        supersedes_task_revision=supersedes_task_revision,
    )

    record = record_header(
        candidate=candidate,
        model_id=model_id,
        task_id=task_id,
        task_revision=task_revision,
        semantic_prompts_sent=semantic_prompts_sent,
        infrastructure_refusal=infrastructure_refusal,
        run_validity=run_validity,
        scoring_eligible=scoring_eligible,
        autonomous_classification=autonomous_classification,
        diagnostic_subclassification=diagnostic_subclassification,
        operator_continuation=operator_continuation,
        automatic_semantic_retry=automatic_semantic_retry,
        pi_runtime=pi_runtime,
        route_provenance=route_provenance,
        verification=verification,
        scope_result=scope_result,
        report_accuracy=report_accuracy,
        token_policy=dict(TOKEN_POLICY),
        supervised_recovery=supervised_recovery,
    )
    if supersedes_task_revision is not None:
        record["supersedes_task_revision"] = supersedes_task_revision
    # (C4-FU1) This builder's own output must satisfy the very contract the
    # emission boundary re-derives, so the two can never drift apart in the
    # direction that matters: a builder-produced record that the boundary
    # would refuse.
    #
    # (C4-FU4) The value RETURNED is the validated canonical snapshot the
    # gate itself produced and checked, never the local `record` variable
    # built above -- which still holds live references to this function's
    # own `pi_runtime`/`route_provenance`/`verification`/`scope_result`/
    # `report_accuracy` parameters exactly as the caller supplied them. The
    # two are equal in content for every genuine call, but returning the
    # gate's own output is what keeps this function's contract identical to
    # `emit_or_refuse`'s: the object a caller receives (or that reaches the
    # writer) is always exactly the one object the invariant gate validated,
    # never a second, independently-serializing account of it.
    return _require_valid_primary_payload(record)


# ===========================================================================
# 5F3B-LIVE1-C4-FU1 -- the PRIMARY record's durable consumption gate
# ===========================================================================
# Independent review found that `emit_or_refuse` accepted any scrub-clean
# hand-built dict that merely carried the accepted revision and version, so a
# supported caller could bypass `build_qualification_record` -- the module's
# declared invariant gate for this artifact -- entirely. AIDO's standing rule
# is that a caller convention to invoke the correct helper first is not an
# authority invariant when the consumption boundary can mechanically enforce
# the condition itself. So it does, below, by RE-DERIVING the same contract
# from the payload's own declared facts. Nothing here trusts a provenance
# flag, a "validated" marker, or the fact that the payload arrived at all.

#: The EXACT, CLOSED required top-level key set of a primary record: the 9
#: fixed `record_header` keys plus `build_qualification_record`'s own 19
#: `**extra` keys. Enumerated from the frozen builder shape, so an unknown
#: scrub-clean field can never widen this artifact's claim scope by riding
#: along unexamined.
_REQUIRED_PRIMARY_RECORD_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    (
        # -- record_header's own fixed header shape --
        "experiment",
        "record_version",
        "fixture_schema_version",
        "record_kind",
        "is_review_packet",
        "reviewer_invoked",
        "external_prior_not_scored",
        "trust_namespaces",
        "qualification_policy_revision",
        # -- build_qualification_record's own **extra --
        "candidate",
        "model_id",
        "task_id",
        "task_revision",
        "semantic_prompts_sent",
        "infrastructure_refusal",
        "run_validity",
        "scoring_eligible",
        "autonomous_classification",
        "diagnostic_subclassification",
        "operator_continuation",
        "automatic_semantic_retry",
        "pi_runtime",
        "route_provenance",
        "verification",
        "scope_result",
        "report_accuracy",
        "token_policy",
        "supervised_recovery",
    )
)

#: The ONE conditionally-present key the frozen builder can add.
_OPTIONAL_PRIMARY_RECORD_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"supersedes_task_revision"})


def _canonicalize_or_refuse(payload: object) -> object:
    """The EXACT structure ``json.dump`` would persist for ``payload``, at
    every depth.

    5F3B-LIVE1-C4-FU4. Independent review reproduced the primary-record
    counterpart of the gap :func:`~qualification.semantic_attempt._canonicalize_or_refuse`
    closes for the attempt artifact: the top-level record was exact-`dict`
    gated, and ``route_provenance`` was compared by serialized form, but the
    other retained nested objects -- ``pi_runtime``, ``verification``,
    ``scope_result``, ``report_accuracy`` -- were caller-owned Mapping values
    consulted independently by the invariant gate, the safety scrub, and the
    exclusive-create writer. A nested `dict` subclass whose ``.items()``
    reports one shape on an early call and a different (e.g. secret-bearing)
    shape on a later call could therefore pass every check here and still
    have the later shape reach disk, because each of those three stages is
    its own independent serialization of the SAME caller object.

    The fix is the identical mechanism FU3 established for the attempt
    artifact: collapse the WHOLE payload through the one serialization call
    the writer uses -- ``json.dumps(..., ensure_ascii=True, sort_keys=True)``
    -- and read it back with ``json.loads``, which can only ever produce
    ordinary ``dict`` / ``list`` / ``str`` / ``int`` / ``float`` / ``bool`` /
    ``None`` objects. No subclass of any of those survives the round trip:
    whatever ``json.dumps`` chose to walk is exactly what comes back, and it
    is also exactly what a genuine write would have persisted. Every check
    that runs afterward -- in this gate, in the safety scrub, and in the
    writer -- therefore examines the SAME concrete value, and the caller's
    original object is never read again after this one call.

    Using the writer's own ``sort_keys=True`` configuration here (rather than
    a plain ``json.dumps(payload)``) additionally surfaces a
    writer-incompatible payload (e.g. a nested dict with heterogeneous key
    types) as a refusal here, before any file is created, rather than as a
    bare ``TypeError`` inside ``write_evidence_exclusively`` after an
    exclusive-created destination already exists.

    A payload that cannot be serialized at all could never be durably
    emitted either, so that is refused here too, with the same exception the
    rest of the gate raises.
    """
    try:
        return json.loads(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    except (TypeError, ValueError, RecursionError) as exc:
        raise RecordInvariantError(
            "a primary qualification record must be JSON-serializable -- by the "
            "SAME serialization configuration the writer uses -- to ever be "
            "durably emitted; refused before any check trusted its reported "
            "shape, and before any file was created"
        ) from exc


def _is_exact_declared_str(value: Any, expected: str) -> bool:
    """``value`` is an ORDINARY ``str`` carrying exactly ``expected``.

    ``type(...) is str``, never ``isinstance``: a ``str`` subclass may define
    ``__eq__``/``__ne__`` that compare equal to anything while its actual
    underlying content -- the content that gets serialized into the immutable
    artifact -- is something else entirely. That is the same class of bypass
    an equality-only bool check has with ``0``/``1``. No coercion, no
    ``str(value)``, no normalization: a lookalike is REFUSED, never repaired.
    """
    return type(value) is str and value == expected


def _is_exact_declared_mapping(value: Any, expected: Mapping[str, Any]) -> bool:
    """``value`` is an ordinary ``dict`` whose SERIALIZED form is exactly the
    declared mapping's.

    Compared through ``json.dumps`` rather than ``==``, because ``dict.__eq__``
    compares its values with ``==`` too: a nested equality-forging ``str``
    subclass satisfies an ordinary mapping comparison while writing a forged
    claim into the immutable artifact. What is compared here is exactly what
    gets written. An unserializable value could not be written at all, so it
    is a mismatch rather than an exception.
    """
    if type(value) is not dict:
        return False
    try:
        return json.dumps(value, sort_keys=True) == json.dumps(dict(expected), sort_keys=True)
    except (TypeError, ValueError):
        return False


def _require_exact_declared_str(record: dict[str, Any], key: str, expected: str) -> None:
    if not _is_exact_declared_str(record.get(key), expected):
        raise RecordInvariantError(
            f"{key!r} must be an ordinary str carrying exactly {expected!r} on every "
            "primary qualification record; a value of another type -- including a "
            "str subclass that merely compares equal -- is refused, never coerced. "
            "Nothing was written."
        )


def _require_exact_optional_str(record: dict[str, Any], key: str) -> None:
    """A ``str | None`` field must be exactly ``None`` or an ordinary ``str``.

    Type-guarding these BEFORE the frozen contract runs is what stops a
    lookalike from subverting the contract's own equality and membership
    tests (``run_validity == "VALID"``, ``task_revision.startswith(...)``).
    """
    value = record.get(key)
    if value is not None and type(value) is not str:
        raise RecordInvariantError(
            f"{key!r} must be exactly None or an ordinary str on a primary "
            f"qualification record, got {type(value).__name__}. Nothing was written."
        )


def _require_valid_primary_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """THE invariant gate for a ``pi-implementer-qualification.v2`` payload,
    re-derived from the payload's OWN declared facts.

    Called at the end of :func:`build_qualification_record` (so that
    function's output can never violate the rules it demands of others) AND
    at the very start of :func:`emit_or_refuse` (so a hand-built dict that
    never passed through the builder at all is refused before the scrub ever
    runs, and before anything is persisted).

    The property this establishes:

        Any record accepted for primary durable emission satisfies the same
        primary-record invariant contract ``build_qualification_record``
        enforces. A caller cannot bypass that contract by constructing a
        dict directly.

    **5F3B-LIVE1-C4-FU4 -- RETURNS the validated snapshot.** Every check
    below runs against ``record`` AFTER it is rebound, at the top of this
    function, to :func:`_canonicalize_or_refuse`'s output -- an AIDO-owned
    plain ``dict`` built fresh by a ``json.dumps``/``json.loads`` round trip,
    never the caller's original object, and never any of its original nested
    objects (``pi_runtime``, ``route_provenance``, ``verification``,
    ``scope_result``, ``report_accuracy``). Independent review found that a
    caller-owned nested object whose serialization changes between calls (a
    stateful ``dict`` subclass, or a mutation performed after this function
    returns) could have a genuinely valid shape checked here while a
    completely different, forged shape reached the safety scrub and the
    writer -- each of which is its own independent serialization of whatever
    object it is handed. Returning the exact validated snapshot -- and every
    caller below using ONLY that return value from this point on -- closes
    that gap: the caller's original record and every one of its original
    nested objects are consulted exactly once, ever, and never again after
    this function returns.
    """
    # (5F3B-LIVE1-C4-FU4) Canonicalize FIRST, before ANY other check runs.
    # Every check in this function, at every depth -- including inside
    # nested `pi_runtime`/`verification`/`scope_result`/`report_accuracy`,
    # which this gate does not itself walk field-by-field -- operates on
    # `record` as rebound here: the exact concrete structure `json.dump`
    # would persist, never a Mapping/dict/str subclass's own account of
    # itself. See `_canonicalize_or_refuse` for why this is airtight rather
    # than merely another special case.
    record = _canonicalize_or_refuse(record)
    # An exact `dict`, not merely a Mapping: `json.dump` serializes a dict
    # subclass from its real underlying storage, so a subclass whose `get`
    # returned AIDO's declared values while its storage held forged ones
    # would satisfy every check below and still persist the forgery. (After
    # canonicalization this can only fail for a payload that does not even
    # serialize to a JSON object at its top level -- e.g. a list handed in
    # directly -- since `json.loads` of a JSON object always yields a plain
    # `dict`.)
    if type(record) is not dict:
        raise RecordInvariantError(
            "a primary qualification record must be an ordinary dict; a Mapping "
            "of another type -- including a dict subclass -- is refused, because "
            "what it reports and what it serializes need not agree. Nothing was "
            "written."
        )
    keys = set(record)
    missing = _REQUIRED_PRIMARY_RECORD_TOP_LEVEL_KEYS - keys
    unknown = keys - (
        _REQUIRED_PRIMARY_RECORD_TOP_LEVEL_KEYS | _OPTIONAL_PRIMARY_RECORD_TOP_LEVEL_KEYS
    )
    if missing or unknown:
        raise RecordInvariantError(
            "a primary qualification record must carry EXACTLY its own closed "
            f"top-level key set; missing={sorted(missing)} unknown={sorted(unknown)}. "
            "Nothing was written."
        )

    # -- FIXED-SHAPE HEADER/PROVENANCE FIELDS: constant for EVERY primary
    # artifact, never caller-variable.
    for key, expected_flag in (
        # bool fields: exact type AND identity -- `!=` alone would let a
        # non-bool truthy/falsy value (`0`/`1`) satisfy Python's own
        # `0 == False`/`1 == True` and slip past an equality-only check.
        ("is_review_packet", False),
        ("reviewer_invoked", False),
        ("external_prior_not_scored", True),
    ):
        actual = record.get(key)
        if type(actual) is not bool or actual is not expected_flag:
            raise RecordInvariantError(
                f"{key!r} must be exactly {expected_flag!r} on every primary "
                "qualification record. Nothing was written."
            )
    _require_exact_declared_str(record, "experiment", EXPERIMENT_ID)
    _require_exact_declared_str(record, "record_kind", RECORD_KIND)
    _require_exact_declared_str(record, "fixture_schema_version", FIXTURE_SCHEMA_VERSION)
    # The C4 `.v2` metadata pair. `record_version` is checked here as an exact
    # ordinary str, not by `!=`, because the bump and the policy binding are
    # ONE fact: `.v2` MEANS "carries a policy binding", and `.v1`'s frozen
    # meaning is "carries no such binding". A payload may not pair the
    # declared revision with a stale version that merely compares equal to the
    # new one.
    for key, expected_metadata in _FIXED_PRIMARY_HEADER_METADATA.items():
        _require_exact_declared_str(record, key, expected_metadata)
    for key, expected_mapping in (
        ("trust_namespaces", TRUST_NAMESPACES),
        ("token_policy", TOKEN_POLICY),
    ):
        if not _is_exact_declared_mapping(record.get(key), expected_mapping):
            raise RecordInvariantError(
                f"{key!r} must be exactly the declared {key} mapping on every "
                "primary qualification record; a mapping of another type, or one "
                "whose nested values merely compare equal, is refused. Nothing "
                "was written."
            )

    # -- TYPE PRELUDE for the contract's own fields. The frozen contract
    # compares and slices these; a lookalike must be refused BEFORE it can
    # subvert one of those comparisons.
    for key in ("candidate", "model_id", "task_id", "task_revision", "supervised_recovery"):
        if type(record.get(key)) is not str:
            raise RecordInvariantError(
                f"{key!r} must be an ordinary str on a primary qualification "
                f"record, got {type(record.get(key)).__name__}. Nothing was written."
            )
    for key in (
        "run_validity",
        "autonomous_classification",
        "diagnostic_subclassification",
        "supersedes_task_revision",
    ):
        _require_exact_optional_str(record, key)
    if type(record.get("semantic_prompts_sent")) is not int:
        raise RecordInvariantError(
            "semantic_prompts_sent must be an ordinary int on a primary "
            "qualification record. Nothing was written."
        )

    _validate_primary_invariants(
        candidate=record["candidate"],
        model_id=record["model_id"],
        task_id=record["task_id"],
        task_revision=record["task_revision"],
        semantic_prompts_sent=record["semantic_prompts_sent"],
        infrastructure_refusal=record["infrastructure_refusal"],
        run_validity=record["run_validity"],
        scoring_eligible=record["scoring_eligible"],
        autonomous_classification=record["autonomous_classification"],
        diagnostic_subclassification=record["diagnostic_subclassification"],
        operator_continuation=record["operator_continuation"],
        automatic_semantic_retry=record["automatic_semantic_retry"],
        route_provenance=record["route_provenance"],
        supervised_recovery=record["supervised_recovery"],
        supersedes_task_revision=record.get("supersedes_task_revision"),
    )

    # 5F3B-LIVE1-C4-FU4: every check above ran against `record` as rebound
    # at the top of this function -- the canonical snapshot, never the
    # caller's original object or any of its original nested objects.
    # Returning it (rather than `None`) is what lets every caller below bind
    # ONE AIDO-owned concrete object all the way from validation through the
    # safety scrub to persistence.
    return record


def emit_or_refuse(
    record: dict[str, Any], *, path: str, safety: ArtifactSafetyContext
) -> dict[str, Any]:
    """Fail-closed emission of one qualification run record.

    ``safety`` is REQUIRED and has no default: a caller with nothing to
    declare says so explicitly with
    :meth:`~qualification.safety.ArtifactSafetyContext.none_declared`. The
    write is exclusive-create, so this can never overwrite an earlier
    emitted artifact -- not with the record, and not with a refusal.

    **5F3B-LIVE1-C4-FU1 emission-boundary re-derivation.** A scrub checks
    SAFETY, never semantic truth or provenance truth, so a hand-built dict
    that never passed through :func:`build_qualification_record` -- and
    therefore never met that builder's invariant gate or
    :func:`record_header`'s protected-key guard -- would otherwise be
    persisted verbatim, forged ``qualification_policy_revision``, stale
    ``.v1`` version and internally impossible run alike.

    :func:`_require_valid_primary_payload` therefore re-derives the FULL
    frozen primary-record contract here, from the payload's own declared
    facts. A caller convention to invoke the builder first is not an
    authority invariant when this boundary can enforce the condition itself;
    nothing here trusts a provenance flag or a "validated" marker, because a
    forger supplies those as readily as anything else.

    This is the primary artifact's counterpart to the gate
    :func:`~qualification.semantic_attempt._require_valid_attempt_payload`
    already performs for the attempt artifact.

    **5F3B-LIVE1-C4-FU4.** The parameter named ``record`` is the caller's
    object and is used for exactly ONE thing: as the input to
    :func:`_require_valid_primary_payload`. Its RETURN value -- an AIDO-owned
    plain ``dict`` produced by a ``json.dumps``/``json.loads`` round trip of
    ``record``, including every nested ``pi_runtime``/``route_provenance``/
    ``verification``/``scope_result``/``report_accuracy`` value -- is what is
    handed to :func:`~qualification.safety.emit_evidence_or_refuse` for both
    the safety scrub and the exclusive-create write. The caller's original
    ``record`` object, and every one of its original nested objects, is never
    read again after the line below: not by the scrub, not by the writer. A
    stateful or subclassed caller object whose serialized shape could change
    between calls (a stateful ``dict`` subclass's ``.items()``, or a plain
    mutation performed by the caller after this call returns) therefore
    cannot affect what is persisted -- only the ONE validated snapshot can
    ever reach disk.
    """
    validated = _require_valid_primary_payload(record)
    return emit_evidence_or_refuse(validated, path=path, safety=safety, record_kind=RECORD_KIND)


__all__ = [
    "ArtifactSafetyContext",
    "CANDIDATE_MODEL_IDS",
    "EXPERIMENT_ID",
    "PRIMARY_RECORD_SUPERVISED_RECOVERY",
    "QUALIFICATION_POLICY_REVISION",
    "RECORD_KIND",
    "RECORD_VERSION",
    "RecordInvariantError",
    "TOKEN_POLICY",
    "TRUST_NAMESPACES",
    "VALID_SUPERVISED_RECOVERY",
    "build_qualification_record",
    "build_refusal_record",
    "emit_or_refuse",
    "record_header",
]
