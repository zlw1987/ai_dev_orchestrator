"""5F3B-Q1-PRE1-FU2 -- the attempt-level artifact for an INDETERMINATE
semantic dispatch. OFFLINE ONLY; pure, and it writes nothing by itself.

Why this artifact exists
-------------------------

``docs/PHASE_5F3B_Q1_PRE1_DESIGN_FU1_SEMANTIC_DISPATCH_AUTHORITY.md`` Sec. 3
established the second PRE1 acceptance blocker from source: an attempt whose
dispatch send state could not be mechanically established -- the ONE outcome
in which AIDO cannot prove whether the candidate's single authorized prompt
was spent -- was the ONE outcome that left **nothing on disk**. The in-memory
``SemanticTaskAttemptResult`` is not evidence; it dies with the process.

The frozen rule this module implements (Sec. 3.F):

.. code-block:: text

    every INVOKED task attempt leaves EXACTLY ONE immutable retained artifact

        determinate send state    -> pi-implementer-qualification.v1
        indeterminate send state  -> pi-implementer-qualification-attempt.v1

    never zero, and never both.

Why a SIBLING artifact and not a widened primary record (Sec. 3.D/3.E)
-----------------------------------------------------------------------

``qualification.records._validate_run_shape`` admits exactly two shapes, and
both would be FALSE statements here: ``infrastructure_refusal`` asserts the
prompt was **not** sent, and the ordinary shape asserts it **was**. Widening
``semantic_prompts_sent`` to ``int | None`` inside the frozen primary record
would push an unestablished fact into ``_validate_run_shape``,
``resolve_run_validity``, ``classify_cleanup_failure``, ``classify_outcome``,
``evaluate_hard_bar``, ``build_invalidation_evidence`` and the ranking layer
-- every one of which currently gets to assume a determinate count, and every
one of whose new ``None`` branch would be a place an unproven fact could
later be read as a proven one. So ``pi-implementer-qualification.v1`` stays
**exactly as frozen**, and this is a separate artifact kind at its own
version, whose ``record_kind`` makes it unmistakable and unmergeable with a
run record.

**The gap is an ABSENT KEY, never a sentinel.** This artifact carries
``semantic_prompts_sent_established: false`` and **no** ``semantic_prompts_sent``
key anywhere in the payload -- not ``null`` doing double duty, not ``0``, not
``-1``. :func:`build_attempt_record` re-proves that recursively before
returning, so a future nested projection cannot reintroduce the key by
accident.

What this module deliberately does NOT do
------------------------------------------

- It does **not** reuse the artifact-emission-refusal record's MEANING
  (Sec. 3.C). ``safety.build_refusal_record`` means exactly "a candidate
  artifact was built and then withheld because it failed the safety scrub";
  an indeterminate dispatch is not a scrub failure, and emitting one would
  assert a safety finding that never occurred. It *does* reuse the shared
  emission choke point :func:`qualification.safety.emit_evidence_or_refuse`,
  which keeps exclusive-create immutability, the scrub, and the refusal
  fallback identical -- and that fallback correctly applies to THIS artifact
  in its own right, if this payload itself ever failed the scrub.
- It does **not** implement the lineage extension (Sec. 3.I).
  ``lineage._require_run_record_shape`` deliberately demands a primary run
  record's exact ``record_kind``/``record_version`` on both sides, and the
  third invalidation reason ``indeterminate_semantic_dispatch`` is a
  SEPARATELY AUTHORIZED extension. Nothing here calls, extends, or
  pre-empts it. Until it is authorized, an indeterminate attempt is recorded
  and its task simply remains unresolved -- an acceptable state; inventing a
  link is not.
- It records **no** retry authority. ``automatic_semantic_retry`` is
  permanently ``false`` here exactly as in a primary record (Sec. 3.H).
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Mapping

from . import ATTEMPT_RECORD_VERSION, FIXTURE_SCHEMA_VERSION, PACKAGE_ID
from .corpus import TASKS_BY_ID
from .i2_route import RouteDescriptorError, route_descriptor_for_candidate
from .i2b_controller import (
    BrokerShutdownStatus,
    CategoryBFailureCode,
    CompatibilityFacts,
    ResourceClosureState,
    RuntimeTeardownStatus,
)
from .records import (
    CANDIDATE_MODEL_IDS,
    TOKEN_POLICY,
    TRUST_NAMESPACES,
    VALID_TASK_IDS,
)
from .safety import ArtifactSafetyContext, emit_evidence_or_refuse
from .semantic_session import (
    DISPATCH_EVIDENCE_CODE_STATES,
    SemanticDispatchEvidenceCode,
    SemanticPromptDispatchState,
)

#: The artifact's own kind string. Deliberately unmistakable, and
#: deliberately not equal to ``records.RECORD_KIND`` -- a reader (and
#: ``lineage._require_run_record_shape``) can never mistake one for the
#: other.
ATTEMPT_RECORD_KIND = "qualification attempt (indeterminate semantic dispatch)"

#: The single fixed reason string used wherever a frozen 0/1 classifier
#: could not be called for this attempt. One constant, reused for the
#: generated-config cleanup and the semantic-workspace removal alike, so the
#: two closure steps can never drift into two different wordings for the
#: identical honest gap.
CLASSIFICATION_UNAVAILABLE_REASON = "semantic dispatch send state indeterminate"

#: The fixed, bounded claim-scope statement every attempt artifact carries.
#: Uses the accepted vocabulary verbatim: AIDO's wait ended. It is NOT a
#: claim that Pi stopped, that the request was cancelled, or that backend
#: inference stopped.
ATTEMPT_CLAIM_SCOPE = (
    "AIDO attempted its ONE authorized semantic dispatch for this task and cannot "
    "mechanically establish whether the command crossed the send boundary. AIDO's "
    "own wait ended; this is NOT a claim that Pi stopped, that the command was "
    "cancelled, that a descendant process was terminated, or that backend inference "
    "stopped. The attempt is CONSUMED and is never automatically retried. Controlled "
    "invocation is not sandboxed execution."
)

#: The evidence codes that may appear on this artifact -- derived from the
#: ONE authoritative code -> state mapping, never re-listed by hand.
INDETERMINATE_EVIDENCE_CODES: frozenset[SemanticDispatchEvidenceCode] = frozenset(
    code
    for code, state in DISPATCH_EVIDENCE_CODE_STATES.items()
    if state is SemanticPromptDispatchState.SEND_STATE_INDETERMINATE
)

#: The key that must never appear anywhere in this payload, at any depth.
_FORBIDDEN_KEY = "semantic_prompts_sent"


class AttemptRecordInvariantError(ValueError):
    """A proposed attempt artifact describes an impossible attempt. Rejected."""


def _contains_key(value: object, key: str) -> bool:
    """Whether ``key`` appears as a mapping key anywhere inside ``value``."""
    if isinstance(value, Mapping):
        if key in value:
            return True
        return any(_contains_key(entry, key) for entry in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_key(entry, key) for entry in value)
    return False


# ===========================================================================
# 5F3B-Q1-PRE1-FU2A -- the attempt.v1 INVARIANT GATE (Sec. 7/8)
# ===========================================================================
# Independent review proved `build_attempt_record` accepted far more shapes
# than an actual reachable indeterminate semantic-dispatch attempt could
# ever produce -- e.g. `compatibility_gate_passed=False` alongside an
# indeterminate dispatch, which is impossible: phase 1 is only ever entered
# after the SAME-RUN pre-prompt compatibility prefix succeeded. It also
# proved `emit_attempt_or_refuse` accepted ANY caller-built dict, scrub-clean
# or not, that never passed through `build_attempt_record`'s own validation
# at all -- a scrub checks SAFETY, never semantic truth.
#
# The literal gate-name/status strings below are duplicated from
# `qualification.semantic_controller`'s `SemanticGateName`/`PRE_PROMPT_GATES`/
# `POST_PROMPT_GATES`/`CLOSURE_GATES` rather than imported, because that
# module imports THIS one (`semantic_controller` -> `semantic_attempt`) --
# importing back would be circular. `tests/test_semantic_fu2a.py` asserts,
# at the source level, that these never drift from the real enum.

#: PRE_PROMPT_GATES, in order -- every one of these must be PASSED before
#: PHASE 1 (dispatch) is ever entered, so it must be PASSED for ANY genuine
#: indeterminate-dispatch attempt.
_PRE_PROMPT_GATE_NAMES: tuple[str, ...] = (
    "run_correlation",
    "workspace_authority",
    "workspace_baseline",
    "route_descriptor",
    "non_secret_preflight",
    "connection_values",
    "secret_context",
    "pi_config_generation",
    "identity_binding",
    "child_environment",
    "broker_session",
    "broker_ready",
    "runtime_launch",
    "pi_version_observed",
    "rpc_launch_shape",
    "required_launch_flags",
    "lf_jsonl_correlation",
    "get_commands",
    "h1_extension_identity",
    "extension_command_namespace",
    "get_state",
    "h2_provider_model_identity",
    "protocol_integrity",
    "route_check",
)

#: The one gate this artifact kind ever records a FAILURE for.
_SEMANTIC_PROMPT_DISPATCH_GATE_NAME = "semantic_prompt_dispatch"

#: The fixed status text an indeterminate dispatch's own gate always
#: carries -- `SemanticFailureCode.SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE`
#: is the ONE failure code the controller ever assigns there, regardless of
#: which specific indeterminate evidence code established it.
_INDETERMINATE_DISPATCH_GATE_STATUS = "FAILED:SEMANTIC_PROMPT_SEND_STATE_INDETERMINATE"

#: POST_PROMPT_GATES minus SEMANTIC_PROMPT_DISPATCH -- an indeterminate
#: dispatch raises from inside phase 1, so NONE of these is ever entered.
_POST_DISPATCH_UNREACHED_GATE_NAMES: tuple[str, ...] = (
    "turn_completion",
    "broker_activity",
    "repository_observation",
    "authoritative_verification",
    "final_report_claims",
)

#: CLOSURE_GATES minus EVIDENCE_SAFETY -- closure runs unconditionally, on
#: every path, so these always carry a real (non-PASSED, non-NOT_REACHED)
#: closure-status string.
_CLOSURE_GATE_NAMES: tuple[str, ...] = (
    "runtime_teardown",
    "broker_shutdown",
    "generated_config_cleanup",
    "semantic_workspace_removal",
)

_EXPECTED_ATTEMPT_GATE_STATUS_KEYS: frozenset[str] = frozenset(
    (
        *_PRE_PROMPT_GATE_NAMES,
        _SEMANTIC_PROMPT_DISPATCH_GATE_NAME,
        *_POST_DISPATCH_UNREACHED_GATE_NAMES,
        *_CLOSURE_GATE_NAMES,
    )
)

#: 5F3B-Q1-PRE1-FU2A-FU1A: the EXACT, CLOSED top-level key set every
#: attempt.v1 payload carries -- `attempt_record_header`'s own 8 fixed
#: header keys, plus `build_attempt_record`'s own 24 `**extra` keys. An
#: unknown key (`semantic_prompt_definitely_sent`, `provider_request_count`,
#: ...) is refused outright, never silently retained -- a scrub-clean
#: unknown field must never be able to widen this artifact's frozen claim
#: scope.
_EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    (
        # -- attempt_record_header's own fixed header shape --
        "experiment",
        "record_version",
        "fixture_schema_version",
        "record_kind",
        "is_review_packet",
        "reviewer_invoked",
        "external_prior_not_scored",
        "trust_namespaces",
        # -- build_attempt_record's own **extra --
        "candidate",
        "model_id",
        "task_id",
        "task_revision",
        "semantic_dispatch_state",
        "dispatch_evidence_code",
        "semantic_prompts_sent_established",
        "attempt_consumed",
        "qualification_record_emitted",
        "scoring_eligible",
        "run_validity",
        "autonomous_classification",
        "diagnostic_subclassification",
        "hard_bar_evaluable",
        "operator_continuation",
        "automatic_semantic_retry",
        "pi_runtime",
        "route_provenance",
        "gate_statuses",
        "closure",
        "cleanup_classification_unavailable_reason",
        "workspace_removal_classification_unavailable_reason",
        "token_policy",
        "claim_scope",
    )
)

#: `pi_runtime`'s own exact, closed key set -- see ``build_attempt_record``'s
#: own literal dict.
_EXPECTED_PI_RUNTIME_KEYS: frozenset[str] = frozenset(
    ("observed_version", "compatibility_facts", "compatibility_gate_passed")
)

#: The frozen 13 compatibility-fact names, read directly off
#: `CompatibilityFacts` rather than re-listed by hand.
_COMPATIBILITY_FACT_NAMES: frozenset[str] = frozenset(
    spec.name for spec in fields(CompatibilityFacts)
)


#: RuntimeTeardownStatus/BrokerShutdownStatus's own two non-``FAILED``
#: literal texts. Read the shared ``CLOSED_BY_CREATOR_VERIFIED`` text
#: programmatically off ``ResourceClosureState`` rather than duplicating it;
#: only the "SUCCEEDED"/"CLOSED" success words genuinely differ per resource
#: kind (`i2b_controller.RuntimeTeardownStatus`/`BrokerShutdownStatus`'s own
#: ``status_text`` properties -- FROZEN, read there, never redefined here).
_CLOSED_BY_CREATOR_VERIFIED_TEXT = ResourceClosureState.CLOSED_BY_CREATOR_VERIFIED.value
_RUNTIME_TEARDOWN_CLOSED_STATUSES: frozenset[str] = frozenset(
    {"NOT_REQUIRED", "SUCCEEDED", _CLOSED_BY_CREATOR_VERIFIED_TEXT}
)
_BROKER_SHUTDOWN_CLOSED_STATUSES: frozenset[str] = frozenset(
    {"NOT_REQUIRED", "CLOSED", _CLOSED_BY_CREATOR_VERIFIED_TEXT}
)
#: 5F3B-Q1-PRE1-FU2A-FU1A: PER-RESOURCE-KIND failure-code domains, not
#: "any CategoryBFailureCode". Independent review proved the FU2A-FU1
#: version too broad: it accepted `runtime_teardown = "FAILED:ROUTE_CHECK_FAILED"`
#: (not even a resource-closure code at all) and would equally have accepted
#: a broker-only code on `runtime_teardown` or vice versa. Each domain is
#: read directly off the respective FROZEN typed status class's own
#: `_ALLOWED_FAILURE_CODES_BY_STATE` table (i2b_controller.py, never
#: modified here) -- the union, across every UNSATISFIED state, of the codes
#: THAT resource kind's own `_close_runtime`/`_close_broker` producer could
#: ever attach to it. `CLOSED_BY_CREATOR_UNVERIFIED` and
#: `PARTIAL_RESOURCE_STRANDED_NO_CLEANUP_ATTEMPT` are genuinely shared
#: between both tables (i2b_controller.py's own comment on
#: `BrokerShutdownStatus._ALLOWED_FAILURE_CODES_BY_STATE` says so); every
#: other code is resource-kind-exclusive, so a cross-resource substitution
#: (a broker code on `runtime_teardown`, or vice versa) is refused.
_RUNTIME_TEARDOWN_FAILURE_CODE_VALUES: frozenset[str] = frozenset(
    code.value
    for code in frozenset().union(*RuntimeTeardownStatus._ALLOWED_FAILURE_CODES_BY_STATE.values())
)
_BROKER_SHUTDOWN_FAILURE_CODE_VALUES: frozenset[str] = frozenset(
    code.value
    for code in frozenset().union(*BrokerShutdownStatus._ALLOWED_FAILURE_CODES_BY_STATE.values())
)

#: `SemanticCleanupStatus`/`SemanticWorkspaceRemovalStatus.status_text`'s own
#: literal texts, SCOPED to this artifact kind. An indeterminate dispatch's
#: `generated_config_cleanup`/`semantic_workspace_removal` are ALWAYS
#: `attempted=True` (enforced below) -- Pi config generation and workspace
#: mint both precede PHASE 1 in the frozen gate order -- so `status_text` can
#: only ever be "VERIFIED_REMOVED" (`scrub_verified`/`verified` True) or
#: this exact indeterminate-dispatch FAILED code
#: (`qualification.semantic_controller.SemanticFailureCode`, which this
#: module cannot import without a circular dependency; duplicated as ONE
#: literal string each here, with a source-level cross-module drift test).
_GENERATED_CONFIG_CLEANUP_VERIFIED_STATUS = "VERIFIED_REMOVED"
_GENERATED_CONFIG_CLEANUP_FAILED_STATUS = (
    "FAILED:GENERATED_CONFIG_CLEANUP_UNVERIFIED_INDETERMINATE_DISPATCH"
)
_SEMANTIC_WORKSPACE_REMOVAL_VERIFIED_STATUS = "VERIFIED_REMOVED"
_SEMANTIC_WORKSPACE_REMOVAL_FAILED_STATUS = (
    "FAILED:SEMANTIC_WORKSPACE_REMOVAL_UNVERIFIED_INDETERMINATE_DISPATCH"
)

# 5F3B-Q1-PRE1-FU2A-FU1A-FU1: `closure.semantic_workspace_removal.facts`'
# OWN closed, typed shape -- `qualification.semantic_controller._bounded_removal_facts`'
# exact 4-key projection, duplicated as literal key/type domains here rather
# than imported (this module cannot import `semantic_controller` without a
# circular dependency; `tests/test_semantic_fu2a_fu1a_fu1.py` asserts, at the
# source level, that these never drift from the real function). Independent
# review proved the FU2A-FU1A version accepted ANY Mapping here, so a
# scrub-clean unknown nested claim (e.g. `backend_inference_stopped`) rode
# along unexamined, widening this artifact's frozen claim scope.
_REMOVAL_FACTS_KEYS: frozenset[str] = frozenset(
    ("result_shape_recognized", "removed", "residual_file_count", "verified")
)

#: The ONE exact `facts` shape a GENUINELY VERIFIED removal can ever carry.
#: `_bounded_removal_facts`/`workspace_removal_succeeded` are both pure
#: functions of the SAME underlying removal-adapter result object in
#: `_remove_semantic_workspace`, and `workspace_removal_succeeded` returns
#: True IFF that result is exactly `{"removed": True,
#: "residual_file_count": 0, "verified": True}` -- so a verified removal's
#: bounded projection is always exactly this, never the residual, malformed,
#: or removal-exception shape.
_REMOVAL_FACTS_VERIFIED_SHAPE: Mapping[str, Any] = {
    "result_shape_recognized": True,
    "removed": True,
    "residual_file_count": 0,
    "verified": True,
}


def _require_valid_removal_facts(facts: object) -> None:
    """The REAL bounded ``facts`` shape ``_bounded_removal_facts`` can ever
    produce -- covering the genuine successful, residual, malformed-result,
    and removal-exception projections that function actually returns for
    SOME real or malformed removal-adapter result, and nothing wider.
    """
    if not isinstance(facts, Mapping) or set(facts) != _REMOVAL_FACTS_KEYS:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts must carry EXACTLY its own "
            "closed key set -- an unknown or missing field is refused"
        )
    if type(facts["result_shape_recognized"]) is not bool:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts.result_shape_recognized must "
            "be exactly a bool"
        )
    if facts["removed"] is not None and type(facts["removed"]) is not bool:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts.removed must be None or "
            "exactly a bool"
        )
    # `bool` is deliberately excluded even though it is an `int` subclass --
    # `type(x) is int` is False for a bool -- exactly `_bounded_removal_facts`'
    # own `_exact_int` domain.
    if (
        facts["residual_file_count"] is not None
        and type(facts["residual_file_count"]) is not int
    ):
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts.residual_file_count must be "
            "None or exactly an int -- a bool is never accepted here"
        )
    if facts["verified"] is not None and type(facts["verified"]) is not bool:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts.verified must be None or "
            "exactly a bool"
        )
    # 5F3B-Q1-PRE1-FU2A-FU1A-FU1-FU1: the remaining bounded-projection-domain
    # invariant. `_bounded_removal_facts` sets `result_shape_recognized` to
    # False iff at least one of the three required keys ("removed",
    # "residual_file_count", "verified") is ABSENT from the underlying
    # removal-adapter result -- and an absent key's own `.get(...)` always
    # projects to None (`_exact_bool`/`_exact_int` both return None for a
    # missing/None value). So `result_shape_recognized is False` with EVERY
    # ONE of the other three fields non-None is a shape that function can
    # NEVER actually produce: whichever key was absent (the exact reason
    # recognition failed) is guaranteed None in the projection.
    if facts["result_shape_recognized"] is False and (
        facts["removed"] is not None
        and facts["residual_file_count"] is not None
        and facts["verified"] is not None
    ):
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts.result_shape_recognized is "
            "False, but removed/residual_file_count/verified are all non-None -- "
            "_bounded_removal_facts can never produce this: a False "
            "result_shape_recognized means at least one of the three required keys "
            "was absent from the underlying removal result, and that key's own "
            "projected field is always None"
        )


def _require_bounded_resource_closure_status(
    name: str,
    value: object,
    *,
    closed_statuses: frozenset[str],
    failure_code_values: frozenset[str],
) -> bool:
    """Whether ``value`` is a status shape ``RuntimeTeardownStatus``/
    ``BrokerShutdownStatus`` could ACTUALLY produce, per their own frozen
    ``status_text`` property AND their own resource-kind-specific failure
    domain -- never an arbitrary non-blank string like ``"TOTALLY_FINE"``,
    and never a cross-resource failure code (a broker code on
    ``runtime_teardown``, or vice versa). Returns whether the status is a
    CLOSED (satisfied) one; raises for anything outside the real bounded
    vocabulary.
    """
    if type(value) is not str:
        raise AttemptRecordInvariantError(f"gate_statuses[{name!r}] must be a str")
    if value in closed_statuses:
        return True
    if value.startswith("FAILED:") and value[len("FAILED:") :] in failure_code_values:
        return False
    raise AttemptRecordInvariantError(
        f"gate_statuses[{name!r}] = {value!r} is not a status this closure gate's "
        "own frozen typed status object could actually produce for its own "
        "resource kind"
    )


def _require_valid_attempt_payload(record: Mapping[str, Any]) -> None:
    """The REAL invariant gate for a ``pi-implementer-qualification-attempt.v1``
    payload -- re-derived from the payload's OWN declared facts, never
    trusted merely because it reached this function.

    Called at the end of :func:`build_attempt_record` (so that function's
    own output can never violate the rules it demands of others) AND at the
    very start of :func:`emit_attempt_or_refuse` (so an arbitrary,
    scrub-clean-but-semantically-invalid dict that never passed through
    :func:`build_attempt_record` at all is refused before it can ever reach
    the safety scrub or be persisted).
    """
    if not isinstance(record, Mapping):
        raise AttemptRecordInvariantError("an attempt payload must be a Mapping")
    if _contains_key(record, _FORBIDDEN_KEY):
        raise AttemptRecordInvariantError(
            f"an attempt artifact must OMIT {_FORBIDDEN_KEY!r} entirely -- the send "
            "state is unestablished, and an absent key is the only truthful "
            "representation of that. Never null, never 0, never a sentinel."
        )
    # 5F3B-Q1-PRE1-FU2A-FU1A: CLOSED shape -- exactly this key set, never
    # more. A scrub-clean unknown field (`semantic_prompt_definitely_sent`,
    # `provider_request_count`, ...) must never be able to widen this
    # artifact's frozen claim scope by riding along unexamined.
    if set(record) != _EXPECTED_ATTEMPT_RECORD_TOP_LEVEL_KEYS:
        raise AttemptRecordInvariantError(
            "an attempt.v1 payload must carry EXACTLY its own closed top-level "
            "key set -- an unknown or missing field is refused"
        )
    # -- FIXED-SHAPE HEADER/PROVENANCE FIELDS: every one of these is a
    # constant for EVERY attempt.v1 artifact, never caller-variable, and a
    # build-valid record must not be mutable in any of them and still
    # emit successfully (5F3B-Q1-PRE1-FU2A-FU1).
    for key, expected in (
        # bool fields: exact type AND value -- `!=` alone would let a
        # non-bool truthy/falsy value (e.g. `0`/`1`) satisfy Python's own
        # `0 == False`/`1 == True` and slip past an equality-only check.
        ("is_review_packet", False),
        ("reviewer_invoked", False),
        ("external_prior_not_scored", True),
    ):
        actual = record.get(key)
        if type(actual) is not bool or actual is not expected:
            raise AttemptRecordInvariantError(
                f"{key!r} must be exactly {expected!r} for every attempt.v1 artifact"
            )
    for key, expected in (
        ("experiment", PACKAGE_ID),
        ("record_version", ATTEMPT_RECORD_VERSION),
        ("fixture_schema_version", FIXTURE_SCHEMA_VERSION),
        ("record_kind", ATTEMPT_RECORD_KIND),
        ("trust_namespaces", dict(TRUST_NAMESPACES)),
        ("token_policy", dict(TOKEN_POLICY)),
        ("claim_scope", ATTEMPT_CLAIM_SCOPE),
        ("cleanup_classification_unavailable_reason", CLASSIFICATION_UNAVAILABLE_REASON),
        (
            "workspace_removal_classification_unavailable_reason",
            CLASSIFICATION_UNAVAILABLE_REASON,
        ),
    ):
        if record.get(key) != expected:
            raise AttemptRecordInvariantError(
                f"{key!r} must be exactly {expected!r} for every attempt.v1 artifact"
            )

    candidate = record.get("candidate")
    model_id = record.get("model_id")
    task_id = record.get("task_id")
    task_revision = record.get("task_revision")
    if candidate not in CANDIDATE_MODEL_IDS:
        raise AttemptRecordInvariantError(
            f"unknown candidate {candidate!r}; declared: {sorted(CANDIDATE_MODEL_IDS)}"
        )
    if model_id != CANDIDATE_MODEL_IDS[candidate]:
        raise AttemptRecordInvariantError(
            f"model_id {model_id!r} does not match candidate {candidate!r}'s frozen "
            f"pairing {CANDIDATE_MODEL_IDS[candidate]!r}"
        )
    frozen_task = TASKS_BY_ID.get(task_id)
    if frozen_task is None:
        raise AttemptRecordInvariantError(f"unknown task_id {task_id!r}")
    if task_revision != frozen_task.task_revision:
        raise AttemptRecordInvariantError(
            f"task_revision {task_revision!r} does not equal task {task_id!r}'s own "
            "frozen revision -- a revision that merely shares the task's id prefix "
            "is refused"
        )

    dispatch_evidence_code_value = record.get("dispatch_evidence_code")
    valid_evidence_code_values = {code.value for code in INDETERMINATE_EVIDENCE_CODES}
    if dispatch_evidence_code_value not in valid_evidence_code_values:
        raise AttemptRecordInvariantError(
            f"dispatch_evidence_code {dispatch_evidence_code_value!r} does not "
            "establish SEND_STATE_INDETERMINATE"
        )
    if (
        record.get("semantic_dispatch_state")
        != SemanticPromptDispatchState.SEND_STATE_INDETERMINATE.value
    ):
        raise AttemptRecordInvariantError(
            "semantic_dispatch_state must be exactly SEND_STATE_INDETERMINATE"
        )

    for key, expected in (
        ("semantic_prompts_sent_established", False),
        ("attempt_consumed", True),
        ("qualification_record_emitted", False),
        ("scoring_eligible", False),
        ("run_validity", None),
        ("autonomous_classification", None),
        ("diagnostic_subclassification", None),
        ("hard_bar_evaluable", False),
        ("operator_continuation", False),
        ("automatic_semantic_retry", False),
    ):
        if record.get(key) is not expected:
            raise AttemptRecordInvariantError(
                f"{key} must be exactly {expected!r} for an indeterminate-dispatch "
                "attempt artifact"
            )

    # -- PRE-PROMPT COMPATIBILITY: an indeterminate dispatch is reachable
    # ONLY after every one of these succeeded (IDENTITY/DISPATCH/PRE-PROMPT
    # COMPATIBILITY, Sec. 7) --------------------------------------------------
    pi_runtime = record.get("pi_runtime")
    if not isinstance(pi_runtime, Mapping):
        raise AttemptRecordInvariantError("pi_runtime must be a Mapping")
    # CLOSED shape here too: an extra `pi_runtime` field could otherwise ride
    # along unexamined on an artifact whose whole point is a bounded claim
    # about compatibility.
    if set(pi_runtime) != _EXPECTED_PI_RUNTIME_KEYS:
        raise AttemptRecordInvariantError(
            "pi_runtime must carry EXACTLY its own closed key set -- an unknown "
            "or missing field is refused"
        )
    if pi_runtime.get("compatibility_gate_passed") is not True:
        raise AttemptRecordInvariantError(
            "pi_runtime.compatibility_gate_passed must be exactly True -- an "
            "indeterminate semantic dispatch is reachable only after the "
            "same-run pre-prompt compatibility prefix succeeded"
        )
    compatibility_facts = pi_runtime.get("compatibility_facts")
    if (
        not isinstance(compatibility_facts, Mapping)
        or set(compatibility_facts) != _COMPATIBILITY_FACT_NAMES
        or not all(
            compatibility_facts.get(name) is True for name in _COMPATIBILITY_FACT_NAMES
        )
    ):
        raise AttemptRecordInvariantError(
            "pi_runtime.compatibility_facts must carry exactly the frozen 13 "
            "compatibility facts, every one exactly True -- a missing, false, or "
            "incomplete compatibility fact is refused"
        )

    # -- ROUTE: the frozen route identity for this candidate/model, never a
    # cross-candidate/provider/backend substitution -------------------------
    try:
        expected_route = route_descriptor_for_candidate(candidate)
    except RouteDescriptorError as exc:
        raise AttemptRecordInvariantError(
            f"candidate {candidate!r} has no frozen route descriptor"
        ) from exc
    expected_route_provenance = {
        "model_id": expected_route.model_id,
        "provider_route": expected_route.provider_id,
        "backend_gateway_class": expected_route.backend_gateway_class,
    }
    if record.get("route_provenance") != expected_route_provenance:
        raise AttemptRecordInvariantError(
            "route_provenance does not equal the frozen route identity for this "
            "candidate/model -- a cross-candidate/provider/backend route "
            "substitution is refused"
        )

    # -- GATE CHRONOLOGY: only the reachable prefix, and nothing past it ----
    gate_statuses = record.get("gate_statuses")
    if not isinstance(gate_statuses, Mapping):
        raise AttemptRecordInvariantError("gate_statuses must be a Mapping")
    if set(gate_statuses) != _EXPECTED_ATTEMPT_GATE_STATUS_KEYS:
        raise AttemptRecordInvariantError(
            "gate_statuses does not carry exactly the gates a reachable "
            "indeterminate-dispatch attempt could have reached"
        )
    for name in _PRE_PROMPT_GATE_NAMES:
        if gate_statuses[name] != "PASSED":
            raise AttemptRecordInvariantError(
                f"gate_statuses[{name!r}] must be PASSED -- an indeterminate "
                "dispatch is reachable only after every pre-prompt gate passed"
            )
    if gate_statuses[_SEMANTIC_PROMPT_DISPATCH_GATE_NAME] != _INDETERMINATE_DISPATCH_GATE_STATUS:
        raise AttemptRecordInvariantError(
            f"gate_statuses[{_SEMANTIC_PROMPT_DISPATCH_GATE_NAME!r}] must record the "
            "indeterminate dispatch failure"
        )
    for name in _POST_DISPATCH_UNREACHED_GATE_NAMES:
        if gate_statuses[name] != "NOT_REACHED":
            raise AttemptRecordInvariantError(
                f"gate_statuses[{name!r}] must be NOT_REACHED -- nothing after an "
                "indeterminate dispatch is ever entered; a post-turn gate cannot "
                "be fabricated as reached, let alone successful"
            )
    # 5F3B-Q1-PRE1-FU2A-FU1: EXACT bounded closure-status vocabulary, not
    # merely "a non-blank str" -- independent review proved that check
    # accepted `runtime_teardown = "TOTALLY_FINE"` /
    # `broker_shutdown = "LOOKS_CLOSED"`. Each gate now accepts only a
    # status shape its OWN frozen typed status object could actually
    # produce (`RuntimeTeardownStatus`/`BrokerShutdownStatus.status_text` for
    # the first two; the two fixed indeterminate-dispatch-scoped literals for
    # the last two, since `attempted=True` is enforced below and rules out
    # every other shape their own status_text could render).
    runtime_teardown_closed = _require_bounded_resource_closure_status(
        "runtime_teardown",
        gate_statuses["runtime_teardown"],
        closed_statuses=_RUNTIME_TEARDOWN_CLOSED_STATUSES,
        failure_code_values=_RUNTIME_TEARDOWN_FAILURE_CODE_VALUES,
    )
    broker_shutdown_closed = _require_bounded_resource_closure_status(
        "broker_shutdown",
        gate_statuses["broker_shutdown"],
        closed_statuses=_BROKER_SHUTDOWN_CLOSED_STATUSES,
        failure_code_values=_BROKER_SHUTDOWN_FAILURE_CODE_VALUES,
    )
    if gate_statuses["generated_config_cleanup"] not in (
        _GENERATED_CONFIG_CLEANUP_VERIFIED_STATUS,
        _GENERATED_CONFIG_CLEANUP_FAILED_STATUS,
    ):
        raise AttemptRecordInvariantError(
            "gate_statuses['generated_config_cleanup'] "
            f"= {gate_statuses['generated_config_cleanup']!r} is not a status this "
            "artifact kind's generated-config cleanup could actually produce"
        )
    if gate_statuses["semantic_workspace_removal"] not in (
        _SEMANTIC_WORKSPACE_REMOVAL_VERIFIED_STATUS,
        _SEMANTIC_WORKSPACE_REMOVAL_FAILED_STATUS,
    ):
        raise AttemptRecordInvariantError(
            "gate_statuses['semantic_workspace_removal'] "
            f"= {gate_statuses['semantic_workspace_removal']!r} is not a status this "
            "artifact kind's workspace removal could actually produce"
        )

    # -- CLOSURE: coherent with its own gate statuses, and with itself ------
    closure = record.get("closure")
    if not isinstance(closure, Mapping) or set(closure) != {
        "runtime_teardown",
        "broker_shutdown",
        "generated_config_cleanup",
        "semantic_workspace_removal",
        "closure_established",
    }:
        raise AttemptRecordInvariantError("closure must carry exactly its five fixed fields")
    if closure["runtime_teardown"] != gate_statuses["runtime_teardown"]:
        raise AttemptRecordInvariantError(
            "closure.runtime_teardown disagrees with gate_statuses.runtime_teardown"
        )
    if closure["broker_shutdown"] != gate_statuses["broker_shutdown"]:
        raise AttemptRecordInvariantError(
            "closure.broker_shutdown disagrees with gate_statuses.broker_shutdown"
        )

    cleanup = closure["generated_config_cleanup"]
    if not isinstance(cleanup, Mapping) or set(cleanup) != {
        "attempted",
        "scrub_verified",
        "classification",
    }:
        raise AttemptRecordInvariantError(
            "closure.generated_config_cleanup has the wrong shape"
        )
    if cleanup["attempted"] is not True:
        raise AttemptRecordInvariantError(
            "closure.generated_config_cleanup.attempted must be True -- the "
            "generated Pi config always exists by the time an indeterminate "
            "dispatch is reached"
        )
    if type(cleanup["scrub_verified"]) is not bool:
        raise AttemptRecordInvariantError(
            "closure.generated_config_cleanup.scrub_verified must be a bool"
        )
    if cleanup["classification"] is not None:
        raise AttemptRecordInvariantError(
            "closure.generated_config_cleanup.classification must be None for an "
            "indeterminate dispatch -- the frozen 0/1 classifier is never called "
            "for an unestablished semantic_prompts_sent fact"
        )
    cleanup_verified = cleanup["scrub_verified"] is True
    cleanup_gate_verified = (
        gate_statuses["generated_config_cleanup"] == _GENERATED_CONFIG_CLEANUP_VERIFIED_STATUS
    )
    if cleanup_verified != cleanup_gate_verified:
        raise AttemptRecordInvariantError(
            "closure.generated_config_cleanup disagrees with its own gate status"
        )

    removal = closure["semantic_workspace_removal"]
    if not isinstance(removal, Mapping) or set(removal) != {"attempted", "verified", "facts"}:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal has the wrong shape"
        )
    if removal["attempted"] is not True:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.attempted must be True -- this "
            "attempt's own semantic workspace always exists by the time an "
            "indeterminate dispatch is reached"
        )
    if type(removal["verified"]) is not bool:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.verified must be a bool"
        )
    # 5F3B-Q1-PRE1-FU2A-FU1A-FU1: the nested `facts` shape is now CLOSED and
    # typed too -- `removal["attempted"]` is already forced True above, and
    # `_remove_semantic_workspace` never returns `facts=None` when
    # `attempted=True` (only its `run_workspace is None` /
    # `attempted=False` branch does), so a genuine attempt.v1 payload's
    # `facts` is always a Mapping matching this exact bounded shape --
    # never bare `None` here.
    _require_valid_removal_facts(removal["facts"])
    removal_verified = removal["verified"] is True
    removal_gate_verified = (
        gate_statuses["semantic_workspace_removal"]
        == _SEMANTIC_WORKSPACE_REMOVAL_VERIFIED_STATUS
    )
    if removal_verified != removal_gate_verified:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal disagrees with its own gate status"
        )
    # 5F3B-Q1-PRE1-FU2A-FU1A-FU1: coherence between `verified` and `facts` --
    # `workspace_removal_succeeded`/`_bounded_removal_facts` are both pure
    # functions of the SAME underlying result, so `verified is True` IFF
    # `facts` is EXACTLY the one shape a genuine success ever produces. A
    # `verified=True` paired with a residual/malformed/exception `facts`
    # shape (or the reverse: a success-shaped `facts` paired with
    # `verified=False`) is an internally incoherent claim, refused.
    if (dict(removal["facts"]) == _REMOVAL_FACTS_VERIFIED_SHAPE) != removal_verified:
        raise AttemptRecordInvariantError(
            "closure.semantic_workspace_removal.facts disagrees with "
            "closure.semantic_workspace_removal.verified -- a verified removal "
            "always carries exactly the success facts shape, and only a verified "
            "removal ever does"
        )

    expected_closure_established = (
        runtime_teardown_closed and broker_shutdown_closed and cleanup_verified and removal_verified
    )
    if closure["closure_established"] is not expected_closure_established:
        raise AttemptRecordInvariantError(
            "closure.closure_established disagrees with the closure facts it "
            "summarizes"
        )


def attempt_record_header(**extra: Any) -> dict[str, Any]:
    """The attempt artifact's header. Mirrors ``records.record_header``'s
    shape so a reader sees the same provenance fields, with this artifact's
    OWN version and kind -- never the primary record's.
    """
    return {
        "experiment": PACKAGE_ID,
        "record_version": ATTEMPT_RECORD_VERSION,
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "record_kind": ATTEMPT_RECORD_KIND,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "external_prior_not_scored": True,
        "trust_namespaces": dict(TRUST_NAMESPACES),
        **extra,
    }


def build_attempt_record(
    *,
    candidate: str,
    model_id: str,
    task_id: str,
    task_revision: str,
    dispatch_evidence_code: SemanticDispatchEvidenceCode,
    gate_statuses: Mapping[str, str],
    observed_pi_version: str | None,
    compatibility_facts: Mapping[str, bool],
    compatibility_gate_passed: bool,
    route_provenance: Mapping[str, Any],
    closure: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one validated ``pi-implementer-qualification-attempt.v1`` payload.

    Pure; does not write. Raises :class:`AttemptRecordInvariantError` for any
    impossible artifact rather than coercing it into a plausible one --
    exactly the discipline ``records.build_qualification_record`` applies to
    a primary record.

    ``dispatch_evidence_code`` must be one of the codes that actually
    establishes ``SEND_STATE_INDETERMINATE``; that set is DERIVED from
    :data:`~qualification.semantic_session.DISPATCH_EVIDENCE_CODE_STATES`,
    so this validation can never drift from the one authoritative mapping.
    """
    if candidate not in CANDIDATE_MODEL_IDS:
        raise AttemptRecordInvariantError(
            f"unknown candidate {candidate!r}; the first round declares exactly "
            f"{sorted(CANDIDATE_MODEL_IDS)}"
        )
    expected_model = CANDIDATE_MODEL_IDS[candidate]
    if model_id != expected_model:
        raise AttemptRecordInvariantError(
            f"candidate {candidate!r} is bound to model id {expected_model!r}, but the "
            f"attempt artifact proposes {model_id!r}. Evidence belongs to a model x "
            "route tuple, so a mismatched pairing is refused rather than recorded."
        )
    if task_id not in VALID_TASK_IDS:
        raise AttemptRecordInvariantError(
            f"unknown task_id {task_id!r}; declared: {sorted(VALID_TASK_IDS)}"
        )
    if not isinstance(task_revision, str) or not task_revision.startswith(f"{task_id}@"):
        raise AttemptRecordInvariantError(
            f"task_revision {task_revision!r} does not belong to task_id {task_id!r}; "
            "a cross-task revision substitution is refused."
        )
    if type(dispatch_evidence_code) is not SemanticDispatchEvidenceCode:
        raise AttemptRecordInvariantError(
            "dispatch_evidence_code must be exactly a SemanticDispatchEvidenceCode"
        )
    if dispatch_evidence_code not in INDETERMINATE_EVIDENCE_CODES:
        raise AttemptRecordInvariantError(
            f"dispatch_evidence_code {dispatch_evidence_code.value!r} establishes "
            f"{DISPATCH_EVIDENCE_CODE_STATES[dispatch_evidence_code].value!r}, not "
            "SEND_STATE_INDETERMINATE; this artifact kind records ONLY an "
            "indeterminate dispatch"
        )
    if not isinstance(compatibility_gate_passed, bool):
        raise AttemptRecordInvariantError("compatibility_gate_passed must be a bool")

    record = attempt_record_header(
        candidate=candidate,
        model_id=model_id,
        task_id=task_id,
        task_revision=task_revision,
        # -- the dispatch truth, and the honest gap ------------------------
        semantic_dispatch_state=(
            SemanticPromptDispatchState.SEND_STATE_INDETERMINATE.value
        ),
        dispatch_evidence_code=dispatch_evidence_code.value,
        semantic_prompts_sent_established=False,
        # Sec. 3.G: an indeterminate send is not a PROVEN zero, so the
        # one-shot attempt IS consumed. The Sec. 11.5 "attempt not consumed"
        # exemption belongs to INFRASTRUCTURE_REFUSAL alone, which is
        # defined by a proven semantic_prompts_sent == 0.
        attempt_consumed=True,
        # -- explicit, scoped negatives ------------------------------------
        qualification_record_emitted=False,
        scoring_eligible=False,
        run_validity=None,
        autonomous_classification=None,
        diagnostic_subclassification=None,
        hard_bar_evaluable=False,
        operator_continuation=False,
        automatic_semantic_retry=False,
        # -- established compatibility facts up to the dispatch gate -------
        pi_runtime={
            "observed_version": observed_pi_version,
            "compatibility_facts": dict(compatibility_facts),
            "compatibility_gate_passed": compatibility_gate_passed,
        },
        route_provenance=dict(route_provenance),
        gate_statuses=dict(gate_statuses),
        # -- what closure actually produced --------------------------------
        closure=dict(closure),
        cleanup_classification_unavailable_reason=CLASSIFICATION_UNAVAILABLE_REASON,
        workspace_removal_classification_unavailable_reason=(
            CLASSIFICATION_UNAVAILABLE_REASON
        ),
        token_policy=dict(TOKEN_POLICY),
        claim_scope=ATTEMPT_CLAIM_SCOPE,
    )

    # 5F3B-Q1-PRE1-FU2A: the FULL invariant gate -- identity, dispatch,
    # pre-prompt compatibility, route, gate chronology and closure coherence
    # -- re-derived from this record's own declared facts (which includes
    # the ABSENT-KEY check this function always ran). This is a self-check:
    # `build_attempt_record`'s own output can never violate the rules it
    # demands of any other caller.
    _require_valid_attempt_payload(record)
    return record


def emit_attempt_or_refuse(
    record: dict[str, Any], *, path: str, safety: ArtifactSafetyContext
) -> dict[str, Any]:
    """Fail-closed emission of one attempt artifact.

    The SAME choke point every other qualification artifact uses, with this
    artifact's own ``record_kind``: exclusive-create, scrub-checked, and a
    bounded refusal record substituted (never appended, never merged) if this
    payload itself fails the scrub.

    5F3B-Q1-PRE1-FU2A: a scrub checks SAFETY, never semantic truth, so this
    is also the emission-boundary consumption gate. ``record`` is
    re-validated against the FULL attempt.v1 invariant set -- identical to
    :func:`build_attempt_record`'s own self-check -- BEFORE the scrub ever
    runs, so an arbitrary caller-built dict that never passed through
    :func:`build_attempt_record` at all (and would therefore never have been
    checked otherwise) cannot reach persistence merely by being scrub-clean.
    """
    _require_valid_attempt_payload(record)
    return emit_evidence_or_refuse(
        record, path=path, safety=safety, record_kind=ATTEMPT_RECORD_KIND
    )


__all__ = [
    "ATTEMPT_CLAIM_SCOPE",
    "ATTEMPT_RECORD_KIND",
    "ATTEMPT_RECORD_VERSION",
    "AttemptRecordInvariantError",
    "CLASSIFICATION_UNAVAILABLE_REASON",
    "INDETERMINATE_EVIDENCE_CODES",
    "attempt_record_header",
    "build_attempt_record",
    "emit_attempt_or_refuse",
]
