"""``pi-implementer-qualification.v1`` record schema and safe emission (Sec. 26).

This is an EXPERIMENT-OWNED artifact. It is NOT a ``ReviewPacket``, never
``review-packet.v4``, and never emitted through the reviewer path, and no
reviewer is called anywhere in this package.

**The builder is an invariant GATE, not a formatter** (Phase 5F3B-I1-FU1,
extended by 5F3B-I1-FU2). ``pi-implementer-qualification.v1`` must not be
able to express an internally impossible run, because an impossible record
that reaches disk is indistinguishable from a real one afterwards -- and
these artifacts are immutable, so there is no later opportunity to correct
it. Every cross-field rule the design fixes is therefore enforced here, at
construction, and a violating record is **rejected, never coerced**:

    candidate <-> model id     the frozen first-round pairing (Sec. 5)
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

from typing import Any

from . import FIXTURE_SCHEMA_VERSION, PACKAGE_ID, RECORD_VERSION
from .safety import (
    ArtifactSafetyContext,
    build_refusal_record,
    emit_evidence_or_refuse,
)

EXPERIMENT_ID = PACKAGE_ID

RECORD_KIND = "qualification run record"

#: The frozen first-round candidate <-> served-model-id pairing (Sec. 5).
#: Identity/schema data only. No candidate-specific behavior exists anywhere
#: in this package -- both candidates share one corpus, one hard bar, one
#: ranking evaluator, one token policy and one prompt-count policy.
CANDIDATE_MODEL_IDS: dict[str, str] = {
    "A": "qwen3-coder-next",
    "B": "minimax-m2.7",
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


def record_header(**extra: Any) -> dict[str, Any]:
    return {
        "experiment": EXPERIMENT_ID,
        "record_version": RECORD_VERSION,
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "external_prior_not_scored": True,
        "trust_namespaces": dict(TRUST_NAMESPACES),
        **extra,
    }


def _validate_identity(candidate: str, model_id: str, task_id: str, task_revision: str) -> None:
    if candidate not in CANDIDATE_MODEL_IDS:
        raise RecordInvariantError(
            f"unknown candidate {candidate!r}; the first round declares exactly "
            f"{sorted(CANDIDATE_MODEL_IDS)}"
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
    if not isinstance(route_provenance, dict):
        raise RecordInvariantError("route_provenance must be a dict")
    recorded = route_provenance.get("model_id")
    if recorded is not None and recorded != model_id:
        raise RecordInvariantError(
            f"route_provenance.model_id {recorded!r} disagrees with the record's model_id "
            f"{model_id!r}; qualification evidence belongs to a model x route tuple"
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
    """Build one validated ``pi-implementer-qualification.v1`` record.

    Pure; does not write. Raises :class:`RecordInvariantError` for any
    internally impossible record rather than coercing it into a plausible
    one.
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
    """
    return emit_evidence_or_refuse(record, path=path, safety=safety, record_kind=RECORD_KIND)


__all__ = [
    "ArtifactSafetyContext",
    "CANDIDATE_MODEL_IDS",
    "EXPERIMENT_ID",
    "PRIMARY_RECORD_SUPERVISED_RECOVERY",
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
