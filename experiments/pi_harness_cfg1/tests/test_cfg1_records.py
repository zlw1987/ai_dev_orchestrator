"""T-13, T-69, T-88 - T-90, T-94, T-115, T-123, T-141: the three closed schemas.

Every validator here proves a payload's declared fields agree WITH EACH OTHER.
None proves where the artifact sits on disk -- that stronger claim belongs to
the post-hoc binding verifier (T-33 - T-37) -- and none proves the payload
equals the live observation or decision it claims to describe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from cfg1_builders import (
    active_observation_overrides,
    happy_observations,
    refusal_payload,
    run_payload,
    stage_closure_payload,
    unavailable_activity_overrides,
)

from pi_harness_cfg1 import (
    PACKAGE_ID,
    REFUSAL_RECORD_VERSION,
    REFUSAL_RECORD_VERSION_V2,
    RUN_RECORD_VERSION,
    RUN_RECORD_VERSION_V2,
    STAGE_CLOSURE_RECORD_VERSION,
    arms,
    classification,
    fixture,
    halt,
    records,
    schedule,
)
from pi_harness_cfg1.records import (
    Cfg1RecordValidationError,
    _require_valid_cfg1_stage_closure_payload,
)

# FU1 (R6 D-1/D-3): the executor emits ``pi-harness-cfg1-run.v2`` and
# ``pi-harness-cfg1-refusal.v2`` ONLY, so these payload-level regressions run
# against the v2 validators -- the schema every newly emitted artifact must
# satisfy. v1's own, unchanged validators are pinned separately against
# independently built v1 payloads (FU1 Test N, test_cfg1_fu1_l1_boundary.py).
from pi_harness_cfg1.records import (  # noqa: E402
    _require_valid_cfg1_refusal_payload_v2 as _require_valid_cfg1_refusal_payload,
    _require_valid_cfg1_run_payload_v2 as _require_valid_cfg1_run_payload,
)

_DESIGN_DOC = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "PHASE_5F3B_HARNESS_CFG1_LAUNCH_CONFIGURATION_ISOLATION_DESIGN.md"
)


# ---------------------------------------------------------------------------
# T-13 -- payload-only record authority (and exactly what it does NOT prove)
# ---------------------------------------------------------------------------


def test_t13_a_genuine_payload_passes_every_payload_only_check():
    _require_valid_cfg1_run_payload(run_payload())
    _require_valid_cfg1_run_payload(run_payload(run_ordinal=5))
    _require_valid_cfg1_run_payload(run_payload(stage_id="S2", run_ordinal=3))
    _require_valid_cfg1_run_payload(run_payload(**active_observation_overrides()))
    _require_valid_cfg1_run_payload(run_payload(**unavailable_activity_overrides()))


def test_t13_an_unrecognized_key_is_a_closed_key_set_violation():
    payload = run_payload()
    payload["an_extra_field"] = True
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "CLOSED_KEY_SET_VIOLATION"


@pytest.mark.parametrize(
    "key,bad_value",
    [
        ("experiment", "pi_implementer_qualification"),
        ("record_version", "pi-harness-cfg1-run.v1"),
        ("record_kind", "qualification run"),
        ("scoring_authority", True),
        ("qualification_credit", True),
        ("is_review_packet", True),
        ("reviewer_invoked", True),
        ("claim_scope", "trust me"),
        ("model_id", "minimax-m2.7"),
        ("provider_id", "aido-ar2-qwen36-direct-vllm"),
        ("backend_gateway_class", "direct_vllm"),
        ("fixture_task_id", "IQ-1"),
        ("fixture_revision", "0" * 64),
        ("automatic_semantic_retry", True),
        ("operator_continuation", True),
    ],
)
def test_t13_every_pinned_literal_is_enforced_exactly(key, bad_value):
    payload = run_payload()
    payload[key] = bad_value
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_run_payload(payload)


def test_t13_a_bool_is_never_accepted_where_an_int_is_required():
    payload = run_payload()
    payload["untracked_path_count"] = True
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "BAD_INT_UNTRACKED_PATH_COUNT"


def test_t13_the_stage_execution_id_grammar_is_re_proven_independently():
    for bad in ("../escape", "S1 X1", "", "x" * 65, "S1/X1"):
        payload = run_payload()
        payload["stage_execution_id"] = bad
        with pytest.raises(Cfg1RecordValidationError) as excinfo:
            _require_valid_cfg1_run_payload(payload)
        assert excinfo.value.reason_code == "BAD_STAGE_EXECUTION_ID"


def test_t13_schedule_block_and_position_relations_are_recomputed():
    payload = run_payload(run_ordinal=4)
    assert (payload["block"], payload["position"]) == (2, 1)
    payload["block"] = 1
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "BLOCK_POSITION_DISAGREE_WITH_SCHEDULE"


def test_t13_the_arm_digest_and_declared_shape_bindings_are_enforced():
    payload = run_payload(run_ordinal=2)  # arm R
    assert payload["declared_compat_shape"] == "DEVELOPER_ROLE_FALSE_ONLY"
    payload["declared_compat_shape"] = "ABSENT"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "DECLARED_SHAPE_DISAGREES_WITH_ARM"

    payload = run_payload(run_ordinal=2)
    payload["models_json_redacted_sha256"] = arms.ARM_REDACTED_DIGEST["Q"]
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "MODELS_DIGEST_DISAGREES_WITH_ARM"

    payload = run_payload(run_ordinal=2)
    payload["derived_system_role"] = "developer"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "DERIVED_EFFECTIVE_DISAGREES_WITH_ARM"


def test_t13_classification_is_recomputed_not_trusted():
    payload = run_payload()
    assert payload["run_classification"] == "INACTIVE"
    payload["run_classification"] = "ACTIVE"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "RUN_CLASSIFICATION_NOT_REPRODUCIBLE"


def test_t13_lifecycle_all_closed_must_agree_with_its_own_components():
    payload = run_payload(
        **happy_observations(
            workspace_removed_verified=False,
            lifecycle_all_closed=True,
            lifecycle_failure_steps=[],
        )
    )
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "LIFECYCLE_ALL_CLOSED_DISAGREES_WITH_COMPONENTS"


def test_t13_an_unavailable_activity_family_may_not_carry_counts_or_a_basis():
    overrides = unavailable_activity_overrides()
    overrides["runtime_reported_aido_read_call_ids"] = 3
    payload = run_payload(**overrides)
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "UNAVAILABLE_ACTIVITY_CARRIES_COUNTS"


def test_t13_an_available_activity_family_is_re_validated_through_the_obs1_snapshot():
    """The frozen snapshot's OWN invariants are re-established, not re-stated."""
    overrides = active_observation_overrides()
    overrides["runtime_reported_aido_read_end_observed"] = 5  # ends > call ids
    payload = run_payload(**overrides)
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "OBS1_SNAPSHOT_INVARIANT_VIOLATED"


def test_t13_dispatch_and_manipulation_cross_field_rules():
    payload = run_payload()
    payload["prompt_writes"] = 0
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "PROMPT_WRITES_DISAGREE_WITH_DISPATCH_STATE"

    payload = run_payload(runtime_reported_thinking_level="high")
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "MANIPULATION_CHECK_DISAGREES_WITH_PROJECTION"


def test_t13_changed_paths_must_be_a_sorted_subset_of_the_fixture():
    payload = run_payload(changed_tracked_paths=["nowhere/else.py"])
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "UNKNOWN_LIST_ENTRY_CHANGED_TRACKED_PATHS"

    payload = run_payload(
        changed_tracked_paths=["tests/test_banner.py", "greeting/banner.py"]
    )
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "UNSORTED_OR_DUPLICATED_CHANGED_TRACKED_PATHS"


def test_t13_proves_nothing_about_where_the_record_sits_on_disk(tmp_path):
    """The explicit FU3 correction: payload validity is not location binding."""
    payload = run_payload()
    _require_valid_cfg1_run_payload(payload)
    stray = tmp_path / "somewhere_entirely_else" / "S1_01_Q.json"
    stray.parent.mkdir(parents=True)
    stray.write_text(json.dumps(payload), encoding="utf-8")

    # Still perfectly valid as a PAYLOAD...
    _require_valid_cfg1_run_payload(json.loads(stray.read_text(encoding="utf-8")))
    # ...and the location claim is a different question entirely (T-36).
    from pi_harness_cfg1.binding import verify_cfg1_run_artifact_binding

    assert verify_cfg1_run_artifact_binding(str(stray)) is False


# ---------------------------------------------------------------------------
# T-69 -- three validators, six cross-calls, all refused on the KEY SET
# ---------------------------------------------------------------------------


def test_t69_each_validator_accepts_only_its_own_exact_schema():
    genuine = {
        "run": run_payload(),
        "refusal": refusal_payload(),
        "stage_closure": stage_closure_payload(),
    }
    validators = {
        "run": _require_valid_cfg1_run_payload,
        "refusal": _require_valid_cfg1_refusal_payload,
        "stage_closure": _require_valid_cfg1_stage_closure_payload,
    }
    for kind, payload in genuine.items():
        validators[kind](payload)  # its own validator accepts it
        for other_kind, validator in validators.items():
            if other_kind == kind:
                continue
            with pytest.raises(Cfg1RecordValidationError) as excinfo:
                validator(payload)
            # Refused on the CLOSED KEY SET, not on a coincidental literal --
            # proving no validator is a wrapper that also happens to accept a
            # foreign schema's shape.
            assert excinfo.value.reason_code == "CLOSED_KEY_SET_VIOLATION", (
                kind,
                other_kind,
            )


def test_no_validator_is_implemented_as_a_wrapper_around_another():
    source = (Path(records.__file__)).read_text(encoding="utf-8")
    body = source.split("def _require_valid_cfg1_refusal_payload")[1].split(
        "def _require_valid_cfg1_stage_closure_payload"
    )[0]
    assert "_require_valid_cfg1_run_payload(" not in body
    closure_body = source.split("def _require_valid_cfg1_stage_closure_payload")[1].split(
        "# ---------------------------------------------------------------------------\n"
        "# Sec. 22.4.3"
    )[0]
    assert "_require_valid_cfg1_run_payload(" not in closure_body
    assert "_require_valid_cfg1_refusal_payload(" not in closure_body


# ---------------------------------------------------------------------------
# T-88 / T-89 / T-115 -- the stage-closure schema's own invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failure_status", ["EMISSION_COLLISION", "EMISSION_FAILED"])
def test_t88_a_successful_stage_cannot_carry_a_failure_status(failure_status):
    status = {str(k): "RECORD_EMITTED" for k in range(1, 10)}
    status["4"] = failure_status
    payload = stage_closure_payload(
        ordinal_status=status, halted_after_ordinal=None, halt_reason_code=None
    )
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_stage_closure_payload(payload)
    assert excinfo.value.reason_code in (
        "FAILED_ORDINAL_IS_NOT_THE_HALT_POINT",
        "SUCCESSFUL_STAGE_CARRIES_NON_ADMITTING_STATUS",
    )


def _halted_status(k: int, status_at_k: str) -> dict[str, str]:
    status = {}
    for ordinal in range(1, 10):
        if ordinal < k:
            status[str(ordinal)] = "RECORD_EMITTED"
        elif ordinal == k:
            status[str(ordinal)] = status_at_k
        else:
            status[str(ordinal)] = "NOT_EXECUTED"
    return status


def test_t89a_collision_at_the_halt_point_with_the_matching_code_is_accepted():
    _require_valid_cfg1_stage_closure_payload(
        stage_closure_payload(
            ordinal_status=_halted_status(4, "EMISSION_COLLISION"),
            halted_after_ordinal=4,
            halt_reason_code="RUN_RECORD_EMISSION_COLLISION",
        )
    )


def test_t89b_a_failure_status_at_a_different_ordinal_is_refused():
    status = _halted_status(4, "EMISSION_COLLISION")
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_stage_closure_payload(
            stage_closure_payload(
                ordinal_status=status,
                halted_after_ordinal=3,
                halt_reason_code="RUN_RECORD_EMISSION_COLLISION",
            )
        )
    assert excinfo.value.reason_code in (
        "POST_HALT_ORDINAL_NOT_MARKED_NOT_EXECUTED",
        "FAILED_ORDINAL_IS_NOT_THE_HALT_POINT",
    )


def test_t89c_a_mismatched_halt_code_for_the_same_status_is_refused():
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_stage_closure_payload(
            stage_closure_payload(
                ordinal_status=_halted_status(4, "EMISSION_COLLISION"),
                halted_after_ordinal=4,
                halt_reason_code="RUN_RECORD_EMISSION_FAILED",
            )
        )
    assert excinfo.value.reason_code == "HALT_CODE_DISAGREES_WITH_EMISSION_OUTCOME"


def test_t89d_and_t89e_emission_failed_is_accepted_under_the_one_renamed_code():
    """All three underlying causes produce this ONE payload shape, by design.

    The schema does not -- and must not -- attempt to distinguish a direct
    post-create primary failure, a ``PRE_CREATE`` fallback that itself later
    failed, and a refusal writer's own post-create failure. T-96 proves the
    live runner produces the identical code for structurally different causes;
    this proves the schema accepts exactly that one shape for all of them.
    """
    payload = stage_closure_payload(
        ordinal_status=_halted_status(4, "EMISSION_FAILED"),
        halted_after_ordinal=4,
        halt_reason_code="RUN_RECORD_EMISSION_FAILED",
    )
    for _cause in ("direct_post_create", "pre_create_fallback_failed", "refusal_post_create"):
        _require_valid_cfg1_stage_closure_payload(payload)
    assert "RUN_RECORD_REFUSAL_FALLBACK_FAILED" not in halt.HALT_REASON_CODES


@pytest.mark.parametrize(
    "code",
    [
        "PRE_DISPATCH_REFUSAL",
        "LIFECYCLE_CLOSURE_UNPROVEN",
        "RUN_SCOPED_REGISTRY_NOT_EMPTY",
        "RUN_RECORD_SELF_VALIDATION_FAILED",
    ],
)
def test_t115_the_four_non_mechanical_codes_are_membership_checked_only(code):
    """The validator has no mechanism to check these against ``ordinal_status``.

    Their live provenance is the sealed L30 decision alone. A payload carrying
    one of them beside an ``ordinal_status`` that is not independently
    indicative of that cause is ACCEPTED -- which is the honest behaviour, not
    a gap.
    """
    _require_valid_cfg1_stage_closure_payload(
        stage_closure_payload(
            ordinal_status=_halted_status(4, "RECORD_EMITTED"),
            halted_after_ordinal=4,
            halt_reason_code=code,
        )
    )


def test_a_halt_code_outside_the_closed_set_is_refused():
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_stage_closure_payload(
            stage_closure_payload(
                ordinal_status=_halted_status(4, "RECORD_EMITTED"),
                halted_after_ordinal=4,
                halt_reason_code="A_SEVENTH_CODE",
            )
        )


def test_the_ordinal_status_key_set_is_exact_per_stage():
    for stage_id, expected in (("S1", 9), ("S2", 6)):
        payload = stage_closure_payload(stage_id=stage_id)
        _require_valid_cfg1_stage_closure_payload(payload)
        assert sorted(int(k) for k in payload["ordinal_status"]) == list(
            range(1, expected + 1)
        )
        payload["ordinal_status"][str(expected + 1)] = "RECORD_EMITTED"
        with pytest.raises(Cfg1RecordValidationError) as excinfo:
            _require_valid_cfg1_stage_closure_payload(payload)
        assert excinfo.value.reason_code == "CLOSED_KEY_SET_VIOLATION_ORDINAL_STATUS"


def test_an_ordinal_status_entry_shaped_as_an_object_is_refused():
    payload = stage_closure_payload()
    payload["ordinal_status"]["1"] = {"status": "RECORD_EMITTED", "arm_id": "Q"}
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_stage_closure_payload(payload)
    assert excinfo.value.reason_code == "BAD_ORDINAL_STATUS_VALUE"


# ---------------------------------------------------------------------------
# T-90 / T-94 -- the halt vocabulary's scope, and what the run record dropped
# ---------------------------------------------------------------------------


def test_t90_the_halt_vocabulary_is_exactly_six_members_and_one_shared_object():
    assert halt.HALT_REASON_CODES == frozenset(
        {
            "PRE_DISPATCH_REFUSAL",
            "LIFECYCLE_CLOSURE_UNPROVEN",
            "RUN_RECORD_SELF_VALIDATION_FAILED",
            "RUN_RECORD_EMISSION_COLLISION",
            "RUN_RECORD_EMISSION_FAILED",
            "RUN_SCOPED_REGISTRY_NOT_EMPTY",
        }
    )
    assert len(halt.HALT_REASON_CODES) == 6

    # BY IDENTITY: the stage-closure validator and the L30 admission-decision
    # logic reference the SAME object, not two lists that agree today.
    from pi_harness_cfg1 import stage_runner

    assert records.HALT_REASON_CODES is halt.HALT_REASON_CODES
    assert stage_runner.HALT_REASON_CODES is halt.HALT_REASON_CODES

    # And the RUN-record validator has no halt_reason_code domain to audit,
    # because the field does not exist there at all.
    assert "halt_reason_code" not in records.CFG1_RUN_RECORD_KEYS


def test_t94_the_run_record_schema_carries_no_unrecomputable_final_l30_state():
    assert "halt_triggered_by_this_run" not in records.CFG1_RUN_RECORD_KEYS
    assert "halt_reason_code" not in records.CFG1_RUN_RECORD_KEYS
    assert "halt_triggered_by_this_run" not in records.CFG1_RUN_RECORD_KEYS_V2
    assert "halt_reason_code" not in records.CFG1_RUN_RECORD_KEYS_V2

    for key, value in (
        ("halt_triggered_by_this_run", False),
        ("halt_triggered_by_this_run", True),
        ("halt_reason_code", None),
        ("halt_reason_code", "PRE_DISPATCH_REFUSAL"),
    ):
        payload = run_payload()
        payload[key] = value
        with pytest.raises(Cfg1RecordValidationError) as excinfo:
            _require_valid_cfg1_run_payload(payload)
        assert excinfo.value.reason_code == "CLOSED_KEY_SET_VIOLATION"


def test_t94_run_classification_stays_payload_only_recomputable():
    """Two payloads differing only in pre-L29 facts, both recomputed identically."""
    inactive = run_payload()
    active = run_payload(**active_observation_overrides())
    assert inactive["run_classification"] == "INACTIVE"
    assert active["run_classification"] == "ACTIVE"
    for payload in (inactive, active):
        assert classification.classify_cfg1_run(payload) == payload["run_classification"]
        _require_valid_cfg1_run_payload(payload)


# ---------------------------------------------------------------------------
# T-123 / T-141 -- normative-text audits, one level up
# ---------------------------------------------------------------------------


def _design_section(start_marker: str, end_marker: str) -> str:
    text = _DESIGN_DOC.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


_NO_CLOSURE_MARKERS = (
    "16.3.7",
    "row 17",
    "OUTPUT_NAMESPACE_PREOCCUPIED",
    "STAGE_DECISION_MINT_FAILED",
)


def test_t123_and_t141_both_sections_enumerate_exactly_the_same_four_cases():
    section_19_4 = _design_section("### 19.4", "### 19.5")
    exclusion = section_19_4[section_19_4.index("Four cases are explicitly excluded") :]
    bullets = [line for line in exclusion.splitlines() if line.startswith("- ")]
    assert len(bullets) == 4, bullets
    normalized_exclusion = _normalize(exclusion)
    for marker in _NO_CLOSURE_MARKERS:
        assert marker in normalized_exclusion, marker

    # Normalize FIRST: the markdown wraps this sentence across a line break, so
    # indexing the raw text would only ever find it by accident of formatting.
    normalized_22_4_2 = _normalize(_design_section("### 22.4.2", "### 22.4.3"))
    normalized_closure = normalized_22_4_2[
        normalized_22_4_2.index("explicit exclusion of exactly four stage-ending cases") :
    ]
    for index in ("(1)", "(2)", "(3)", "(4)"):
        assert index in normalized_closure, index
    assert "(5)" not in normalized_closure
    for marker in _NO_CLOSURE_MARKERS:
        assert marker in normalized_closure, marker

    # The shared constant both sections describe, as one object.
    assert len(halt.NO_CONFIRMED_STAGE_CLOSURE_CASES) == 4


def test_t123_section_22_4_2_makes_no_run_record_sharing_claim():
    """A POSITIVE assertion check, deliberately.

    A naive negative substring scan would fail here: the section quotes the
    old, false "shared identically" wording in order to correct it. So the
    audit asserts the CORRECTED claims are present rather than that a phrase
    is absent.
    """
    normalized = _normalize(_design_section("### 22.4.2", "### 22.4.3"))
    assert "`HALT_REASON_CODES` is accepted only by the stage-closure record" in normalized
    assert (
        "The run-record schema contains no `halt_reason_code` field at all" in normalized
    )


def test_t141_stage_decision_mint_failed_is_absent_from_every_closed_domain():
    code = halt.DISPOSITION_STAGE_DECISION_MINT_FAILED
    assert code == "STAGE_DECISION_MINT_FAILED"
    assert code in halt.NO_CONFIRMED_STAGE_CLOSURE_CASES
    assert code not in halt.HALT_REASON_CODES
    for key_set in (
        records.CFG1_RUN_RECORD_KEYS,
        records.CFG1_REFUSAL_RECORD_KEYS,
        records.CFG1_STAGE_CLOSURE_RECORD_KEYS,
    ):
        assert code not in key_set
    for domain in (
        records.FINDING_CATEGORIES,
        records.PRE_DISPATCH_REFUSAL_CODES,
        records.VERIFICATION_SKIP_REASONS,
        records.ACTIVITY_UNAVAILABLE_REASONS,
        halt.ORDINAL_STATUS_VALUES,
    ):
        assert code not in domain
    # And the same negative sweep for the OTHER console-only code.
    preoccupied = halt.DISPOSITION_OUTPUT_NAMESPACE_PREOCCUPIED
    assert preoccupied not in halt.HALT_REASON_CODES
    for key_set in (
        records.CFG1_RUN_RECORD_KEYS,
        records.CFG1_REFUSAL_RECORD_KEYS,
        records.CFG1_STAGE_CLOSURE_RECORD_KEYS,
    ):
        assert preoccupied not in key_set


# ---------------------------------------------------------------------------
# Refusal-record schema specifics
# ---------------------------------------------------------------------------


def test_the_refusal_schema_refuses_a_zero_finding_or_uncovered_category():
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_refusal_payload(refusal_payload(finding_count=0))

    payload = refusal_payload(
        finding_count=1, finding_categories=("SCRUB_NEEDLE_MATCH", "RECORD_INVARIANT")
    )
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_refusal_payload(payload)
    assert excinfo.value.reason_code == "FINDING_COUNT_BELOW_CATEGORY_COUNT"


def test_the_refusal_schema_accepts_only_the_one_refusable_record_kind():
    payload = refusal_payload()
    payload["refused_record_kind"] = STAGE_CLOSURE_RECORD_VERSION
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_refusal_payload(payload)
    assert records.REFUSABLE_RECORD_KINDS == frozenset({RUN_RECORD_VERSION})
    assert records.REFUSABLE_RECORD_KINDS_V2 == frozenset({RUN_RECORD_VERSION_V2})
    # A v2 refusal may never stand in for a v1 run record, nor vice versa.
    payload = refusal_payload()
    payload["refused_record_kind"] = RUN_RECORD_VERSION
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_refusal_payload(payload)


def test_the_pinned_fixture_revision_still_matches_the_fixture_content():
    """Fixture drift is a TEST failure, never a silent record redefinition."""
    assert fixture.PINNED_CFG1_T1_REVISION == fixture._compute_fixture_revision()
    assert fixture.CFG1_T1.case_id == "CFG1-T1"
    assert fixture.CFG1_T1.manifest_in_prompt is False
    assert fixture.CFG1_T1.names_the_implementation_file is True
    assert fixture.CFG1_T1.expected_changed_paths == frozenset({"greeting/banner.py"})
    assert "aido_read" not in fixture.CFG1_T1_PROMPT
    assert "aido_edit" not in fixture.CFG1_T1_PROMPT


def test_every_record_header_declares_no_qualification_authority():
    for payload, version in (
        (run_payload(), RUN_RECORD_VERSION_V2),
        (refusal_payload(), REFUSAL_RECORD_VERSION_V2),
        (stage_closure_payload(), STAGE_CLOSURE_RECORD_VERSION),
    ):
        assert payload["experiment"] == PACKAGE_ID
        assert payload["record_version"] == version
    run = run_payload()
    assert run["scoring_authority"] is False
    assert run["qualification_credit"] is False
    assert run["is_review_packet"] is False
    assert run["reviewer_invoked"] is False


def test_schedule_arms_are_scoped_per_stage():
    assert schedule.STAGE_ARMS["S1"] == ("Q", "R", "E")
    assert schedule.STAGE_ARMS["S2"] == ("Q", "H")
    payload = run_payload(stage_id="S1", run_ordinal=1)
    payload["arm_id"] = "H"  # never scheduled in S1
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "BAD_ENUM_ARM_ID"
