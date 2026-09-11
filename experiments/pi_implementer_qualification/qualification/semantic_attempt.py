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

        determinate send state    -> pi-implementer-qualification.v2
        indeterminate send state  -> pi-implementer-qualification-attempt.v2

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
later be read as a proven one. So ``pi-implementer-qualification.v2`` stays
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

import json
from dataclasses import fields
from typing import Any, Mapping

from . import (
    ATTEMPT_RECORD_VERSION,
    FIXTURE_SCHEMA_VERSION,
    PACKAGE_ID,
    QUALIFICATION_POLICY_REVISION,
)
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
# 5F3B-LIVE1-C4: the SAME protected-key set the primary header uses, imported
# rather than re-listed -- two listings is exactly how the two artifact kinds
# could come to protect different fields.
from .records import _CALLER_FORBIDDEN_HEADER_KEYS, _is_exact_declared_mapping
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
# 5F3B-Q1-PRE1-FU2A -- the attempt.v2 INVARIANT GATE (Sec. 7/8)
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
#: attempt.v2 payload carries -- `attempt_record_header`'s own 9 fixed
#: header keys, plus `build_attempt_record`'s own 24 `**extra` keys. An
#: unknown key (`semantic_prompt_definitely_sent`, `provider_request_count`,
#: ...) is refused outright, never silently retained -- a scrub-clean
#: unknown field must never be able to widen this artifact's frozen claim
#: scope.
#:
#: 5F3B-LIVE1-C4 admits EXACTLY ONE new member, `qualification_policy_revision`
#: (the ninth fixed header key). The set stays exact and closed: this is an
#: enumeration of one further permitted field, never a relaxation of the rule.
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
        "qualification_policy_revision",
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


def _canonicalize_or_refuse(payload: object) -> object:
    """The EXACT structure ``json.dump`` would persist for ``payload``, at
    every depth.

    5F3B-LIVE1-C4-FU2. FU1 closed the TOP-LEVEL lying-``dict`` bypass, but a
    ``dict``/``Mapping`` or ``str`` subclass can play the identical trick at
    any nested depth: override ``get``/``__getitem__``/``__contains__``/
    ``__iter__``/``values``/equality to report one shape to a validator while
    its real underlying storage -- the storage
    :func:`~qualification.safety.write_evidence_exclusively`'s ``json.dump``
    actually walks -- holds another. Patching each nested site individually
    (``pi_runtime``, ``compatibility_facts``, ``gate_statuses``, ``closure``
    and its own nested fields, ...) is an unbounded list of special cases;
    the property that actually needs to hold is that the validator and the
    writer look at the SAME concrete value.

    So this collapses the WHOLE payload through the identical serialization
    call the writer uses -- ``json.dumps`` -- and reads it back with
    ``json.loads``, which can only ever produce ordinary ``dict`` / ``list`` /
    ``str`` / ``int`` / ``float`` / ``bool`` / ``None`` objects. No subclass
    of any of those survives a JSON round trip: whatever ``json.dumps`` chose
    to walk (real storage for an object that does not override ``.items()``;
    its own lie for one that does -- and a lie there is what would genuinely
    be written too, so it is not a bypass) is exactly what comes back. Every
    check that runs afterward, at any depth, is therefore comparing against
    the identical concrete value that can reach disk, never a lookalike.

    A payload that cannot be serialized at all could never be durably
    emitted either, so that is refused here too, with the same exception the
    rest of the gate raises, instead of surfacing a bare ``TypeError`` later
    inside the writer.

    **5F3B-LIVE1-C4-FU3.** The probe call below now uses the SAME
    ``json.dumps`` keyword arguments -- ``ensure_ascii=True`` AND
    ``sort_keys=True`` -- that
    :func:`~qualification.safety.write_evidence_exclusively`'s ``json.dump``
    call actually uses (that call additionally passes ``indent=2``, which
    only affects whitespace and can never affect success or failure).
    Independent review reproduced a payload for which
    ``json.dumps(payload)`` succeeds while ``json.dumps(payload,
    sort_keys=True)`` raises ``TypeError`` -- ``sort_keys`` sorts a dict's
    ``.items()`` BEFORE non-``str`` keys are coerced to text, so a dict with
    heterogeneous key types (e.g. both ``str`` and ``int`` keys) can compare
    them and raise. Using the writer's own configuration here means that
    exact failure now surfaces as a refusal at validation time, before
    ``write_evidence_exclusively`` has opened the destination file --
    instead of after, where it would strand a partial, exclusive-created
    artifact. It also makes the return value's own re-serialization by the
    writer provably safe: every key surviving a ``json.loads`` of ``payload``
    is already an ordinary ``str`` (JSON object keys are always strings), so
    the writer's later ``sort_keys=True`` re-encoding of THIS canonical
    snapshot can never itself raise for a shape that passed here.
    """
    try:
        return json.loads(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    except (TypeError, ValueError, RecursionError) as exc:
        raise AttemptRecordInvariantError(
            "an attempt payload must be JSON-serializable -- by the SAME "
            "serialization configuration the writer uses -- to ever be "
            "durably emitted; refused before any check trusted its reported "
            "shape, and before any file was created"
        ) from exc


def _require_valid_attempt_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """The REAL invariant gate for a ``pi-implementer-qualification-attempt.v2``
    payload -- re-derived from the payload's OWN declared facts, never
    trusted merely because it reached this function.

    Called at the end of :func:`build_attempt_record` (so that function's
    own output can never violate the rules it demands of others) AND at the
    very start of :func:`emit_attempt_or_refuse` (so an arbitrary,
    scrub-clean-but-semantically-invalid dict that never passed through
    :func:`build_attempt_record` at all is refused before it can ever reach
    the safety scrub or be persisted).

    **5F3B-LIVE1-C4-FU3 -- RETURNS the validated snapshot.** Every check
    below runs against ``record`` AFTER it is rebound, at the top of this
    function, to :func:`_canonicalize_or_refuse`'s output -- an AIDO-owned
    plain ``dict`` built fresh by a ``json.dumps``/``json.loads`` round trip,
    never the caller's original object. Independent review found that this
    rebinding was previously LOCAL: the canonical snapshot was validated and
    then discarded, and the caller's original -- possibly stateful or
    subclassed -- object was consulted a SECOND time by the safety scrub and
    the writer. A caller-owned object whose serialization changes between
    calls (a stateful ``dict`` subclass, a mutation performed after this
    function returns) could therefore have a genuinely valid shape checked
    here while a completely different, forged shape reached disk.
    Returning the exact validated snapshot -- and every caller below using
    ONLY that return value from this point on -- closes that gap: the
    caller's original object is never consulted again after this function
    returns.
    """
    # (5F3B-LIVE1-C4-FU2) Canonicalize FIRST, before ANY other check --
    # including the forbidden-key scan below -- runs. Every check in this
    # function, at every depth, operates on `record` as rebound here: the
    # exact concrete structure `json.dump` would persist, never a
    # Mapping/dict/str subclass's own account of itself. See
    # `_canonicalize_or_refuse` for why this is airtight rather than merely
    # another special case.
    record = _canonicalize_or_refuse(record)
    if type(record) is not dict:
        raise AttemptRecordInvariantError(
            "an attempt payload must serialize to a JSON object at its top "
            f"level, got {type(record).__name__}"
        )
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
            "an attempt.v2 payload must carry EXACTLY its own closed top-level "
            "key set -- an unknown or missing field is refused"
        )
    # -- FIXED-SHAPE HEADER/PROVENANCE FIELDS: every one of these is a
    # constant for EVERY attempt.v2 artifact, never caller-variable, and a
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
                f"{key!r} must be exactly {expected!r} for every attempt.v2 artifact"
            )
    # FIXED str fields. `type(...) is str` as well as `==` (5F3B-LIVE1-C4-FU1):
    # a `str` subclass may define `__eq__`/`__ne__` that compare equal to
    # anything while its actual underlying content -- the content that gets
    # serialized into the immutable artifact -- is a forged value entirely.
    # That is the same class of bypass the bool fields above have with
    # `0`/`1`. Refused, never coerced: no `str(value)`, no normalization.
    for key, expected_text in (
        ("experiment", PACKAGE_ID),
        # `record_version` and `qualification_policy_revision` are the C4 `.v2`
        # metadata PAIR, and the bump and the binding are ONE fact: `.v2`
        # MEANS "carries a policy binding", `.v1` MEANS "carries none". Both
        # are re-derived here so a hand-built dict handed straight to
        # `emit_attempt_or_refuse` -- which never passed through
        # `attempt_record_header` and so never met its protected-key guard --
        # can persist neither a forged revision nor a real `.v1` value that
        # merely compares equal to `.v2`.
        ("record_version", ATTEMPT_RECORD_VERSION),
        ("qualification_policy_revision", QUALIFICATION_POLICY_REVISION),
        ("fixture_schema_version", FIXTURE_SCHEMA_VERSION),
        ("record_kind", ATTEMPT_RECORD_KIND),
        ("claim_scope", ATTEMPT_CLAIM_SCOPE),
        ("cleanup_classification_unavailable_reason", CLASSIFICATION_UNAVAILABLE_REASON),
        (
            "workspace_removal_classification_unavailable_reason",
            CLASSIFICATION_UNAVAILABLE_REASON,
        ),
    ):
        actual = record.get(key)
        if type(actual) is not str or actual != expected_text:
            raise AttemptRecordInvariantError(
                f"{key!r} must be an ordinary str carrying exactly "
                f"{expected_text!r} for every attempt.v2 artifact; a value of "
                "another type -- including a str subclass that merely compares "
                "equal -- is refused, never coerced"
            )
    for key, expected_mapping in (
        ("trust_namespaces", TRUST_NAMESPACES),
        ("token_policy", TOKEN_POLICY),
    ):
        if not _is_exact_declared_mapping(record.get(key), expected_mapping):
            raise AttemptRecordInvariantError(
                f"{key!r} must be exactly the declared {key} mapping for every "
                "attempt.v2 artifact; a mapping of another type, or one whose "
                "nested values merely compare equal, is refused"
            )

    candidate = record.get("candidate")
    model_id = record.get("model_id")
    task_id = record.get("task_id")
    task_revision = record.get("task_revision")
    # (5F3B-LIVE1-C4-FU1) Ordinary strs BEFORE the identity comparisons below,
    # so an equality-forging `str` subclass cannot satisfy `model_id !=` or
    # `task_revision !=` while serializing a different underlying value.
    for key, value in (
        ("candidate", candidate),
        ("model_id", model_id),
        ("task_id", task_id),
        ("task_revision", task_revision),
        ("semantic_dispatch_state", record.get("semantic_dispatch_state")),
        ("dispatch_evidence_code", record.get("dispatch_evidence_code")),
    ):
        if type(value) is not str:
            raise AttemptRecordInvariantError(
                f"{key!r} must be an ordinary str on an attempt.v2 artifact, got "
                f"{type(value).__name__}"
            )
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
    # 5F3B-LIVE1-C4-FU3: `observed_pi_version: str | None` is the real
    # builder parameter's own declared domain (see `build_attempt_record`
    # below) -- never a Mapping, list, number, bool, or a `str` subclass
    # whose serialized content need not match what it reports. `type(...) is
    # str`, not `isinstance`, for the same reason every other authority
    # string on this artifact is checked that way: an equality-forging `str`
    # subclass cannot reach here at all (canonicalization already reduced it
    # to an ordinary JSON scalar), but a genuine caller-built dict handed
    # straight to `emit_attempt_or_refuse` could still carry a Mapping, a
    # list, or a bool here -- shapes the real builder can never produce.
    observed_version = pi_runtime.get("observed_version")
    if observed_version is not None and type(observed_version) is not str:
        raise AttemptRecordInvariantError(
            "pi_runtime.observed_version must be exactly None or an ordinary "
            f"str, got {type(observed_version).__name__} -- the real builder "
            "parameter's own domain is `str | None`, and no other shape is a "
            "value the real builder could ever have honestly produced"
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
    # (5F3B-LIVE1-C4-FU1) Compared by SERIALIZED form: an ordinary mapping
    # comparison compares its values with `==` too, so a nested
    # equality-forging `str` subclass would satisfy it while writing a
    # substituted route into the immutable artifact.
    if not _is_exact_declared_mapping(record.get("route_provenance"), expected_route_provenance):
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
    # `attempted=False` branch does), so a genuine attempt.v2 payload's
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

    # 5F3B-LIVE1-C4-FU3: every check above ran against `record` as rebound
    # at the top of this function -- the canonical snapshot, never the
    # caller's original object. Returning it (rather than `None`) is what
    # lets every caller below bind ONE AIDO-owned concrete object all the
    # way from validation through the safety scrub to persistence.
    return record


#: This artifact's own values for the protected key NAMES imported above. The
#: names are shared with the primary record; the ``record_version`` value is
#: emphatically NOT, which is exactly why the two are declared apart.
_FIXED_ATTEMPT_HEADER_METADATA: dict[str, str] = {
    "record_version": ATTEMPT_RECORD_VERSION,
    "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
}


def _reject_caller_supplied_fixed_metadata(extra: dict[str, Any]) -> None:
    """Refuse a caller attempting to supply a FIXED-metadata header key.

    Deliberately checks ``records._CALLER_FORBIDDEN_HEADER_KEYS`` -- the SAME
    set the primary header protects -- rather than a second local listing, so
    the two artifact kinds can never protect different fields.
    """
    forged = sorted(_CALLER_FORBIDDEN_HEADER_KEYS.intersection(extra))
    if forged:
        raise AttemptRecordInvariantError(
            f"{forged!r} is FIXED AIDO metadata on every attempt artifact and is "
            "not a caller-supplied field; it is stamped from this package's own "
            "declaration sites. An attempt artifact whose schema version or "
            "policy revision came from its caller would prove nothing about the "
            "schema it satisfies or the policy under which that one-shot attempt "
            "was made."
        )


def attempt_record_header(**extra: Any) -> dict[str, Any]:
    """The attempt artifact's header. Mirrors ``records.record_header``'s
    shape so a reader sees the same provenance fields, with this artifact's
    OWN version and kind -- never the primary record's.

    ``qualification_policy_revision`` (5F3B-LIVE1-C4) is the SAME constant, from
    the SAME single declaration site, that the primary header stamps -- an
    indeterminate attempt is equally a one-shot result produced under a policy.
    ``record_version`` (C4-FU1) is fixed alongside it, because the bump and the
    binding are one fact. Both are protected by the same TWO independent
    mechanisms:

    1. a caller supplying either is REFUSED outright, above;
    2. even if that guard were bypassed, both authoritative constants are
       re-stamped AFTER ``**extra`` is merged, so the last write -- AIDO's --
       wins the merge.

    A third, independent check re-derives both at the emission boundary, in
    :func:`_require_valid_attempt_payload`.
    """
    _reject_caller_supplied_fixed_metadata(extra)
    header = {
        "experiment": PACKAGE_ID,
        "record_version": ATTEMPT_RECORD_VERSION,
        "fixture_schema_version": FIXTURE_SCHEMA_VERSION,
        "record_kind": ATTEMPT_RECORD_KIND,
        "is_review_packet": False,
        "reviewer_invoked": False,
        "external_prior_not_scored": True,
        "trust_namespaces": dict(TRUST_NAMESPACES),
        "qualification_policy_revision": QUALIFICATION_POLICY_REVISION,
        **extra,
    }
    # -- FIXED AIDO METADATA: re-stamped LAST, after **extra, deliberately.
    header.update(_FIXED_ATTEMPT_HEADER_METADATA)
    return header


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
    """Build one validated ``pi-implementer-qualification-attempt.v2`` payload.

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
            f"unknown candidate {candidate!r}; the declared candidate domain is "
            f"exactly {sorted(CANDIDATE_MODEL_IDS)}"
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
    #
    # 5F3B-LIVE1-C4-FU3: the value RETURNED is the validated snapshot the
    # gate itself produced and checked, never the local `record` variable
    # built above. `record` here is already an ordinary dict built fresh by
    # `attempt_record_header`, so the two are equal in content for every
    # genuine call -- but returning the gate's own output is what keeps this
    # function's contract identical to `emit_attempt_or_refuse`'s: the
    # object a caller receives (or that reaches the writer) is always
    # exactly the one object the invariant gate validated, never a second,
    # independently-serializing account of it.
    return _require_valid_attempt_payload(record)


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
    re-validated against the FULL attempt.v2 invariant set -- identical to
    :func:`build_attempt_record`'s own self-check -- BEFORE the scrub ever
    runs, so an arbitrary caller-built dict that never passed through
    :func:`build_attempt_record` at all (and would therefore never have been
    checked otherwise) cannot reach persistence merely by being scrub-clean.

    **5F3B-LIVE1-C4-FU3.** The parameter named ``record`` is the caller's
    object and is used for exactly ONE thing: as the input to
    :func:`_require_valid_attempt_payload`. Its RETURN value -- an AIDO-owned
    plain ``dict`` produced by a ``json.dumps``/``json.loads`` round trip of
    ``record`` -- is what is handed to :func:`~qualification.safety.emit_evidence_or_refuse`
    for both the safety scrub and the exclusive-create write. The caller's
    original ``record`` object is never read again after the line below:
    not by the scrub, not by the writer. A stateful or subclassed caller
    object whose serialized shape could change between calls (a stateful
    ``dict`` subclass's ``.items()``, or a plain mutation performed by the
    caller after this call returns) therefore cannot affect what is
    persisted -- only the ONE validated snapshot can ever reach disk.
    """
    validated = _require_valid_attempt_payload(record)
    return emit_evidence_or_refuse(
        validated, path=path, safety=safety, record_kind=ATTEMPT_RECORD_KIND
    )


__all__ = [
    "ATTEMPT_CLAIM_SCOPE",
    "ATTEMPT_RECORD_KIND",
    "ATTEMPT_RECORD_VERSION",
    "AttemptRecordInvariantError",
    "CLASSIFICATION_UNAVAILABLE_REASON",
    "INDETERMINATE_EVIDENCE_CODES",
    "QUALIFICATION_POLICY_REVISION",
    "attempt_record_header",
    "build_attempt_record",
    "emit_attempt_or_refuse",
]
