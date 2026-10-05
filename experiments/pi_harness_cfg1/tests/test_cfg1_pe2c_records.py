"""PE-2c: the v3 classifier, item 1A and the v3 halt precedence, the v3 record
family, and the static wording / version-comparison audits.

PE-1 (``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``) Sec. 26.3
rows C-7, C-8, C-9, C-10, C-13, C-16 and C-18. Every payload is synthetic and
every rule is exercised on the payload ALONE (validity is coherence, never
provenance). Nothing runs Node or Pi or reads a credential.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import re
from pathlib import Path

import pytest
from cfg1_builders import (
    happy_observations,
    happy_observations_v2,
    refusal_payload,
    stage_closure_payload,
    stage_closure_payload_v3,
    v2_refusal_payload,
    v2_run_payload,
)

from pi_harness_cfg1 import classification, halt, records
from pi_harness_cfg1.classification import (
    CLASSIFICATION_INDETERMINATE_PI_PROFILE,
    RUN_CLASSIFICATIONS,
    RUN_CLASSIFICATIONS_V3,
    classify_cfg1_run,
    classify_cfg1_run_v3,
)
from pi_harness_cfg1.halt import (
    HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN,
    HALT_REASON_CODES,
    HALT_REASON_CODES_V3,
    _pi_profile_item_1a_holds,
    _resolve_halt_reason_code,
    _resolve_halt_reason_code_v3,
)
from pi_harness_cfg1.lifecycle import compute_lifecycle_closure_v2
from pi_harness_cfg1.pi_identity import (
    ALLOWED_PAYLOAD_OBSERVATION_COMPLETE,
    PI_IDENTITY_FAILURE_CODES_V3,
    PI_PROFILE_CHANGED_WITHIN_STAGE,
)
from pi_harness_cfg1.records import (
    Cfg1RecordValidationError,
    _require_valid_cfg1_refusal_payload_v2,
    _require_valid_cfg1_refusal_payload_v3,
    _require_valid_cfg1_run_payload_v2,
    _require_valid_cfg1_run_payload_v3,
    _require_valid_cfg1_stage_closure_payload,
    _require_valid_cfg1_stage_closure_payload_v3,
    build_cfg1_run_payload,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_PID = "a" * 64


def _v3(**overrides) -> dict:
    observations = happy_observations(runtime_reported_compat_shape="ABSENT")
    observations.update(overrides)
    closed, steps = compute_lifecycle_closure_v2(observations)
    observations["lifecycle_all_closed"] = closed
    observations["lifecycle_failure_steps"] = list(steps)
    return build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )


_L1_SHAPE = dict(
    base_url_compat_detection_clear=False,
    route_reachable=False,
    route_configured_model_served=False,
    broker_reached_ready=False,
    h1_extension_identity_matched=False,
    h2_provider_model_identity_matched=False,
    runtime_reported_compat_shape="NOT_OBSERVED",
    runtime_reported_model_reasoning="NOT_OBSERVED",
    runtime_reported_thinking_level="NOT_OBSERVED",
    manipulation_check_agrees=False,
    dispatch_state="NOT_ATTEMPTED",
    prompt_writes=0,
    runtime_wait_outcome="NOT_OBSERVED",
    stop_reasons_available=False,
    broker_recorded_activity_available=False,
    runtime_created=False,
    runtime_exit_observed=False,
    runtime_transport_eof_observed=False,
    broker_resource_created=False,
    broker_state_closed=False,
    broker_pending_unreaped_zero=False,
    broker_worker_terminated_or_absent=False,
    workspace_authority_reproved=False,
    workspace_removed_verified=False,
    workspace_mint_state="NOT_ATTEMPTED",
    git_observation_1_performed=False,
    git_observation_2_performed=False,
    verification_attempted=False,
    verification_skip_reason="PRE_DISPATCH_REFUSAL",
    verification_started=False,
    verification_completed=False,
    verification_return_code=None,
    verification_counts={"passed": 0, "failed": 0, "error": 0},
    pi_profile_post_runtime_reobservation="NOT_APPLICABLE",
)


def _l1(*, code="OFFLINE_PREFLIGHT_FAILED", failure=None, complete=True, profile_id=_PID, declared="1.0.0", **extra):
    from pi_harness_cfg1 import obs1

    shape = dict(_L1_SHAPE)
    shape.update(obs1.unavailable_activity_fields(None))
    shape.update(
        pre_dispatch_refusal_code=code,
        refused_at_step="L1",
        pi_identity_failure_code=failure,
        pi_payload_observation_complete=complete,
        pi_profile_id=profile_id,
        pi_profile_declared_package_version=declared,
    )
    shape.update(extra)
    return _v3(**shape)


def _refused_past_l1(step="L7", code="ROUTE_UNAVAILABLE", **extra):
    from pi_harness_cfg1 import obs1

    shape = dict(_L1_SHAPE)
    shape.update(obs1.unavailable_activity_fields(None))
    shape.update(
        workspace_mint_state="AUTHORITY_RETURNED",
        workspace_authority_reproved=True,
        workspace_removed_verified=True,
        pre_dispatch_refusal_code=code,
        refused_at_step=step,
    )
    shape.update(extra)
    return _v3(**shape)


def _refuses(payload, reason=None, validator=_require_valid_cfg1_run_payload_v3):
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        validator(json.loads(json.dumps(payload)))
    if reason is not None:
        assert excinfo.value.reason_code == reason, excinfo.value.reason_code


# ---------------------------------------------------------------------------
# C-7 -- the v3 classification row; v2 byte-identical
# ---------------------------------------------------------------------------

_HEAD_SOURCE_DIGESTS = {
    ("classification", "classify_cfg1_run"): "3e639b357d81b9897838eb3134e16c4e11a5cef4b6f8be22581ba0341a425ae3",
    ("classification", "observation_disagreement_predicates"): "8849d5806d1b1ce58b2c5105891208b1a6b1b47cc36875887d8104f70ea2a0d0",
    ("halt", "_resolve_halt_reason_code"): "f34851f7698a0205008daed4724a14fec320e16cf0530a6009488d201dc80081",
    ("halt", "_admission_conditions_hold"): "6c3a3dd45c7ddb8656b78c037f6d74a53d2743d225accfdc99e5f8138cb62ee4",
    ("records", "_require_valid_cfg1_run_payload_v2"): "01725358f0d22a51e4701209e43e3edeed3fb524a4b93228f6f6886fcd1d4406",
    ("records", "_require_valid_cfg1_refusal_payload_v2"): "df326fefea5d6e9497ecceb3e5ac2ac319f59980aac325878bf4876b876770a9",
    ("records", "_require_pi_identity_rules_v2"): "8b6ed8d0ba2ae7b41ad92c3648b89a3bd37358033af9ee95c3cada87541511c4",
    ("records", "_require_valid_cfg1_stage_closure_payload"): "a9fd905f0a9ee5a042c66692accf92238045070cf8f82a6f1f0ab6ed884600e3",
    ("lifecycle", "compute_lifecycle_closure_v2"): "cdf4239eca3291a7dc5d663952473899f68b25c47aa0fddedd2b00e8d8134105",
}


@pytest.mark.parametrize("module,name", sorted(_HEAD_SOURCE_DIGESTS))
def test_c7_c8_the_historical_v2_and_v1_functions_are_byte_for_byte_unchanged(module, name):
    """Digests of each function's source as shipped at the PE-2b head
    (87d2adb): the v2 classifier, the six-step precedence, the admission
    decision, the v2 validators and closure, and the v1 stage-closure
    validator keep their exact historical behavior."""
    source = (_PACKAGE_DIR / f"{module}.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert hashlib.sha256(segment.encode("utf-8")).hexdigest() == _HEAD_SOURCE_DIGESTS[(module, name)]
            return
    raise AssertionError(f"{module}.{name} is missing")


def test_c7_the_v3_domain_inserts_exactly_one_row_after_refused_pre_dispatch():
    assert len(RUN_CLASSIFICATIONS) == 12
    assert CLASSIFICATION_INDETERMINATE_PI_PROFILE not in RUN_CLASSIFICATIONS
    assert RUN_CLASSIFICATIONS_V3 == RUN_CLASSIFICATIONS[:2] + (CLASSIFICATION_INDETERMINATE_PI_PROFILE,) + RUN_CLASSIFICATIONS[2:]
    assert CLASSIFICATION_INDETERMINATE_PI_PROFILE not in classification.DETERMINATE_CLASSIFICATIONS
    assert classification.aggregate_arm(((CLASSIFICATION_INDETERMINATE_PI_PROFILE, "RECORD_EMITTED"),)) == "INDETERMINATE"


def test_c7_row_2a_sits_after_lifecycle_and_refusal_and_before_every_dispatch_row():
    base = _v3()
    assert base["run_classification"] == "INACTIVE"
    # 1 wins over 2A
    facts = dict(base, lifecycle_all_closed=False, pi_profile_post_runtime_reobservation="CHANGED")
    assert classify_cfg1_run_v3(facts) == "INDETERMINATE_LIFECYCLE"
    # 2 wins over 2A
    facts = dict(base, pre_dispatch_refusal_code="H1_MISMATCH", pi_profile_post_runtime_reobservation="CHANGED")
    assert classify_cfg1_run_v3(facts) == "REFUSED_PRE_DISPATCH"
    # 2A wins over every later row (3 = INDETERMINATE_DISPATCH ... 9 = ACTIVE)
    for later in (
        {"dispatch_state": "SEND_STATE_INDETERMINATE"},
        {"runtime_wait_outcome": "READ_ERROR"},
        {"broker_recorded_activity_available": False},
        {"runtime_reported_aido_read_call_ids": 1},
        {},
    ):
        for value in ("CHANGED", "UNPROVEN"):
            facts = dict(base, pi_profile_post_runtime_reobservation=value, **later)
            assert classify_cfg1_run_v3(facts) == CLASSIFICATION_INDETERMINATE_PI_PROFILE
    # PROVEN_UNCHANGED falls through to exactly v2's rows.
    for later in ({"dispatch_state": "SEND_STATE_INDETERMINATE"}, {}):
        facts = dict(base, **later)
        assert classify_cfg1_run_v3(facts) == classify_cfg1_run(facts)


@pytest.mark.parametrize("value", ["CHANGED", "UNPROVEN", "NOT_APPLICABLE", "PROVEN_UNCHANGED"])
def test_c7_active_and_inactive_are_impossible_without_proven_unchanged(value):
    from cfg1_builders import active_observation_overrides

    for overrides in ({}, active_observation_overrides()):
        payload_facts = dict(_v3(**overrides), pi_profile_post_runtime_reobservation=value)
        result = classify_cfg1_run_v3(payload_facts)
        if result in ("ACTIVE", "INACTIVE"):
            assert value in ("PROVEN_UNCHANGED", "NOT_APPLICABLE")
    # ...and NOT_APPLICABLE with a determinate class is refused by R3-S8/S10.
    if value == "NOT_APPLICABLE":
        payload = _v3()
        payload["pi_profile_post_runtime_reobservation"] = "NOT_APPLICABLE"
        _refuses(payload)


# ---------------------------------------------------------------------------
# C-8 -- item 1A, the v3 seven-step precedence, the frozen six objects
# ---------------------------------------------------------------------------


class _StrSubclass(str):
    pass


def test_c8_item_1a_is_exact_and_fails_closed():
    holds = {
        (False, "NOT_APPLICABLE"): True,
        (True, "PROVEN_UNCHANGED"): True,
        (True, "CHANGED"): False,
        (True, "UNPROVEN"): False,
        (True, "NOT_APPLICABLE"): False,
        (False, "PROVEN_UNCHANGED"): False,
        (False, "CHANGED"): False,
    }
    for (runtime_created, value), expected in holds.items():
        assert _pi_profile_item_1a_holds(runtime_created=runtime_created, pi_profile_reobservation=value) is expected
    for runtime_created, value in (
        (1, "PROVEN_UNCHANGED"),
        (0, "NOT_APPLICABLE"),
        (None, "NOT_APPLICABLE"),
        (True, _StrSubclass("PROVEN_UNCHANGED")),
        (True, None),
        (True, "proven_unchanged"),
        ("True", "PROVEN_UNCHANGED"),
    ):
        assert _pi_profile_item_1a_holds(runtime_created=runtime_created, pi_profile_reobservation=value) is False


def test_c8_the_v3_vocabulary_is_the_frozen_six_plus_exactly_one():
    assert len(HALT_REASON_CODES) == 6
    assert HALT_REASON_CODES_V3 == HALT_REASON_CODES | {HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN}
    assert len(HALT_REASON_CODES_V3) == 7
    assert HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN not in HALT_REASON_CODES
    assert halt.HALT_REASON_CODES is HALT_REASON_CODES  # the frozen object, unchanged


_V3_CONDITIONS = (
    ("collision", {"emission_status": "EMISSION_COLLISION"}, "RUN_RECORD_EMISSION_COLLISION"),
    ("failed", {"emission_status": "EMISSION_FAILED"}, "RUN_RECORD_EMISSION_FAILED"),
    ("defect", {"halt_triggered_by_this_run": True}, "RUN_RECORD_SELF_VALIDATION_FAILED"),
    ("lifecycle", {"lifecycle_all_closed": False}, "LIFECYCLE_CLOSURE_UNPROVEN"),
    ("refusal", {"run_classification": "REFUSED_PRE_DISPATCH"}, "PRE_DISPATCH_REFUSAL"),
    ("item_1a", {"pi_profile_item_1a_holds": False}, HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN),
    ("registry", {"registries_empty": False}, "RUN_SCOPED_REGISTRY_NOT_EMPTY"),
)


def _v3_facts(*names):
    facts = {
        "emission_status": "RECORD_EMITTED",
        "halt_triggered_by_this_run": False,
        "lifecycle_all_closed": True,
        "run_classification": "INACTIVE",
        "pi_profile_item_1a_holds": True,
        "registries_empty": True,
    }
    for name, overrides, _code in _V3_CONDITIONS:
        if name in names:
            facts.update(overrides)
    return facts


def test_c8_the_v3_precedence_is_seven_steps_first_match_wins():
    assert _resolve_halt_reason_code_v3(**_v3_facts()) is None
    order = [name for name, _o, _c in _V3_CONDITIONS]
    for name, _overrides, code in _V3_CONDITIONS:
        assert _resolve_halt_reason_code_v3(**_v3_facts(name)) == code
    for first, second in itertools.combinations(order, 2):
        if {first, second} == {"collision", "failed"}:
            continue  # one emission status cannot be both
        expected = dict((name, code) for name, _o, code in _V3_CONDITIONS)[first]
        assert _resolve_halt_reason_code_v3(**_v3_facts(first, second)) == expected
    assert halt.HALT_REASON_PRECEDENCE_V3 == tuple(code for _n, _o, code in _V3_CONDITIONS)
    # The frozen six-step function never produces the seventh code.
    assert _resolve_halt_reason_code(
        emission_status="RECORD_EMITTED",
        halt_triggered_by_this_run=False,
        lifecycle_all_closed=True,
        run_classification=CLASSIFICATION_INDETERMINATE_PI_PROFILE,
        registries_empty=True,
    ) is None


def test_c8_a_non_exact_item_1a_value_is_treated_as_failed():
    for value in (1, None, "True"):
        facts = _v3_facts()
        facts["pi_profile_item_1a_holds"] = value
        assert _resolve_halt_reason_code_v3(**facts) == HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN


# ---------------------------------------------------------------------------
# C-9 -- the v3 run validator: every R3-S rule, Allowed_O, B7, forbidden keys
# ---------------------------------------------------------------------------


def test_c9_positive_controls_validate():
    _require_valid_cfg1_run_payload_v3(_v3())
    _require_valid_cfg1_run_payload_v3(_l1())  # R3-S3, the Git-resolution refusal
    _require_valid_cfg1_run_payload_v3(_l1(code="UNEXPECTED_STEP_FAILURE", complete=False, profile_id=None, declared=None))
    _require_valid_cfg1_run_payload_v3(_l1(code="UNEXPECTED_STEP_FAILURE"))
    _require_valid_cfg1_run_payload_v3(_refused_past_l1())
    for value in ("CHANGED", "UNPROVEN"):
        payload = _v3(pi_profile_post_runtime_reobservation=value)
        _require_valid_cfg1_run_payload_v3(payload)
        assert payload["run_classification"] == CLASSIFICATION_INDETERMINATE_PI_PROFILE


@pytest.mark.parametrize("failure", sorted(PI_IDENTITY_FAILURE_CODES_V3))
def test_c9_every_allowed_o_row_validates_and_the_other_o_is_refused(failure):
    allowed = ALLOWED_PAYLOAD_OBSERVATION_COMPLETE[failure]
    _require_valid_cfg1_run_payload_v3(_l1(failure=failure, complete=allowed, profile_id=None, declared=None))
    _refuses(_l1(failure=failure, complete=not allowed, profile_id=None, declared=None),
             "PI_IDENTITY_FAILURE_DISAGREES_WITH_OBSERVATION_COMPLETE")
    _refuses(_l1(failure=failure, complete=allowed), "PI_IDENTITY_FAILURE_CARRIES_PROFILE")
    assert len(PI_IDENTITY_FAILURE_CODES_V3) == 6


def test_c9_r3_s1_domains_and_the_exact_key_set():
    for key, bad in (
        ("pi_profile_id", "A" * 64),
        ("pi_profile_id", "a" * 63),
        ("pi_profile_declared_package_version", "1 0"),
        ("pi_profile_declared_package_version", "x" * 129),
        ("pi_profile_declared_package_version", ""),
        ("pi_profile_post_runtime_reobservation", "MAYBE"),
        ("pi_identity_failure_code", "PI_SEAM_UNPROVEN"),
        ("pi_payload_observation_complete", 1),
        ("pi_profile_set_head_sha256", "Z" * 64),
    ):
        payload = _v3()
        payload[key] = bad
        _refuses(payload)
    extra = _v3()
    extra["pi_profile_matched"] = True
    _refuses(extra, "CLOSED_KEY_SET_VIOLATION")
    for key in ("pi_profile_set_head_sha256", "pi_profile_post_runtime_reobservation"):
        missing = _v3()
        missing.pop(key)
        _refuses(missing, "CLOSED_KEY_SET_VIOLATION")


@pytest.mark.parametrize(
    "key,value",
    [("pi_seam_digests_match", True), ("pi_observed_version", "0.85.1"), ("pi_version_probe_attempted", False)],
)
def test_c9_forbidden_legacy_identity_keys_are_refused(key, value):
    payload = _v3()
    payload[key] = value
    _refuses(payload, "V3_CARRIES_FORBIDDEN_IDENTITY_KEY")


def test_c9_r3_s2_to_s6_the_identity_family_over_k_c_f():
    # S2: F outside an L1 preflight refusal
    forged = _refused_past_l1()
    forged["pi_identity_failure_code"] = "PI_PROFILE_UNAPPROVED"
    forged["pi_profile_id"] = None
    forged["pi_profile_declared_package_version"] = None
    _refuses(forged, "PI_IDENTITY_FAILURE_OUTSIDE_L1_PREFLIGHT_REFUSAL")
    _refuses(_l1(code="UNEXPECTED_STEP_FAILURE", failure="PI_PROFILE_UNAPPROVED", profile_id=None, declared=None),
             "PI_IDENTITY_FAILURE_OUTSIDE_L1_PREFLIGHT_REFUSAL")
    # S3: the Git-resolution refusal needs P's success committed
    _refuses(_l1(complete=False), "L1_PREFLIGHT_REFUSAL_WITHOUT_P_SUCCESS")
    _refuses(_l1(profile_id=None, declared=None), "L1_PREFLIGHT_REFUSAL_WITHOUT_P_SUCCESS")
    # S4: UNEXPECTED at L1 -- before the commit or after it, never between
    _refuses(_l1(code="UNEXPECTED_STEP_FAILURE", complete=True, profile_id=None, declared=None),
             "L1_UNEXPECTED_WITH_PARTIAL_PROFILE_FAMILY")
    _refuses(_l1(code="UNEXPECTED_STEP_FAILURE", complete=False), "L1_UNEXPECTED_WITH_PARTIAL_PROFILE_FAMILY")
    # S5: past L1 or no refusal at all
    _refuses(_v3(pi_profile_id=None, pi_profile_declared_package_version=None), "POST_L1_RECORD_WITHOUT_P_SUCCESS")
    _refuses(_v3(pi_payload_observation_complete=False), "POST_L1_RECORD_WITHOUT_P_SUCCESS")
    _refuses(_refused_past_l1(pi_profile_id=None, pi_profile_declared_package_version=None),
             "POST_L1_RECORD_WITHOUT_P_SUCCESS")
    # S6: an L1 refusal code outside the two (caught by the step/code table)
    _refuses(_l1(code="ROUTE_UNAVAILABLE"))


def test_c9_r3_s7_to_s10():
    _refuses(_v3(pi_profile_declared_package_version=None), "DECLARED_VERSION_DISAGREES_WITH_PROFILE_ID")
    _refuses(_l1(failure="PI_PROFILE_UNAPPROVED", profile_id=None, declared="1.0.0"),
             "DECLARED_VERSION_DISAGREES_WITH_PROFILE_ID")
    # S8
    _refuses(_v3(pi_profile_post_runtime_reobservation="NOT_APPLICABLE"), "L21A_APPLICABILITY_DISAGREES_WITH_RUNTIME_CREATED")
    _refuses(_l1(pi_profile_post_runtime_reobservation="PROVEN_UNCHANGED"), "L21A_APPLICABILITY_DISAGREES_WITH_RUNTIME_CREATED")
    # S9: an L1 refusal never created a runtime
    payload = _l1()
    payload["runtime_created"] = True
    payload["pi_profile_post_runtime_reobservation"] = "PROVEN_UNCHANGED"
    _refuses(payload)
    # S10: every non-refused run launched Pi
    payload = _v3()
    payload["runtime_created"] = False
    payload["pi_profile_post_runtime_reobservation"] = "NOT_APPLICABLE"
    _refuses(payload)


def test_c9_r3_s11_to_s13_the_classification_rules():
    determinate = _v3()
    determinate["pi_profile_post_runtime_reobservation"] = "UNPROVEN"
    _refuses(determinate, "DETERMINATE_CLASSIFICATION_WITHOUT_PROVEN_UNCHANGED_PROFILE")
    profile_indeterminate = _v3(pi_profile_post_runtime_reobservation="CHANGED")
    profile_indeterminate["pi_profile_post_runtime_reobservation"] = "PROVEN_UNCHANGED"
    _refuses(profile_indeterminate, "INDETERMINATE_PI_PROFILE_DISAGREES_WITH_REOBSERVATION")
    not_reproducible = _v3()
    not_reproducible["run_classification"] = "INDETERMINATE_PROVIDER"
    _refuses(not_reproducible, "RUN_CLASSIFICATION_NOT_REPRODUCIBLE")


@pytest.mark.parametrize(
    "key,bad",
    [
        ("pi_payload_contract", "PI-PC2"),
        ("pi_seam_contract", "pi-sc1"),
        ("pi_consumer_contract", "CFG1-CC2"),
        ("pi_profile_policy_revision", "HPP-2"),
        ("pi_profile_authority_scope", "COMPLETE_RUNTIME"),
        ("pi_external_runtime_residual", False),
        ("pi_external_runtime_residual", "IDENTIFIED"),
    ],
)
def test_c9_r3_s14_and_b7_literals_are_mandatory_on_passes_and_refusals(key, bad):
    for payload in (_v3(), _l1(failure="PI_PROFILE_UNAPPROVED", profile_id=None, declared=None)):
        assert payload["pi_profile_authority_scope"] == "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
        assert payload["pi_external_runtime_residual"] == "NOT_IDENTIFIED_BY_PROFILE"
        tampered = dict(payload)
        tampered[key] = bad
        _refuses(tampered)
        removed = dict(payload)
        removed.pop(key)
        _refuses(removed, "CLOSED_KEY_SET_VIOLATION")


def test_c9_v1_v2_and_v3_never_cross_dispatch():
    v3 = _v3()
    v2 = v2_run_payload(observations=happy_observations_v2(runtime_reported_compat_shape="ABSENT"))
    _require_valid_cfg1_run_payload_v2(v2)
    _refuses(v3, validator=_require_valid_cfg1_run_payload_v2)
    _refuses(v2, validator=_require_valid_cfg1_run_payload_v3)
    dispatch = records._RUN_PATH_DISCRIMINATORS
    kind = "harness configuration diagnostic run"
    assert dispatch[("pi-harness-cfg1-run.v3", kind)] is _require_valid_cfg1_run_payload_v3
    assert dispatch[("pi-harness-cfg1-run.v2", kind)] is _require_valid_cfg1_run_payload_v2
    assert records._dispatch_run_path_validator(v3) is _require_valid_cfg1_run_payload_v3
    mixed = dict(v3, record_version="pi-harness-cfg1-run.v2")
    with pytest.raises(Cfg1RecordValidationError):
        records._dispatch_run_path_validator(mixed)(mixed)


def test_c9_the_builder_refuses_any_value_outside_the_six_and_never_serializes_seam_keys():
    for bad in ("PI_SEAM_UNPROVEN", "PI_IDENTITY_PROVEN", "PI_IDENTITY_GATE_UNEXPECTED_FAILURE", 3, True):
        observations = happy_observations(pi_identity_failure_code=bad)
        with pytest.raises(Cfg1RecordValidationError):
            build_cfg1_run_payload(stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations)
    observations = happy_observations()
    observations["pi_seam_digests_match"] = True
    with pytest.raises(Cfg1RecordValidationError):
        build_cfg1_run_payload(stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations)


# ---------------------------------------------------------------------------
# C-10 -- the v3 refusal and stage-closure validators
# ---------------------------------------------------------------------------


def test_c10_the_v3_refusal_record_is_its_own_closed_schema():
    payload = refusal_payload()
    _require_valid_cfg1_refusal_payload_v3(payload)
    assert payload["refused_record_kind"] == "pi-harness-cfg1-run.v3"
    for key in records._PROFILE_POLICY_KEYS_V3:
        removed = dict(payload)
        removed.pop(key)
        _refuses(removed, "CLOSED_KEY_SET_VIOLATION", validator=_require_valid_cfg1_refusal_payload_v3)
    for kind in ("pi-harness-cfg1-run.v2", "pi-harness-cfg1-run.v1"):
        _refuses(dict(payload, refused_record_kind=kind), validator=_require_valid_cfg1_refusal_payload_v3)
    # It carries NO per-run profile field.
    _refuses(dict(payload, pi_profile_id=_PID), "CLOSED_KEY_SET_VIOLATION", validator=_require_valid_cfg1_refusal_payload_v3)
    v2 = v2_refusal_payload()
    _require_valid_cfg1_refusal_payload_v2(v2)
    _refuses(v2, validator=_require_valid_cfg1_refusal_payload_v3)
    _refuses(payload, validator=_require_valid_cfg1_refusal_payload_v2)


def _closure(**kwargs) -> dict:
    return stage_closure_payload_v3(**kwargs)


def _closure_refuses(payload, reason=None):
    _refuses(payload, reason, validator=_require_valid_cfg1_stage_closure_payload_v3)


def _halted(ordinal: int, code: str, *, binding_at=None, status_at="RECORD_EMITTED", **kwargs):
    status = {str(k): ("RECORD_EMITTED" if k < ordinal else status_at if k == ordinal else "NOT_EXECUTED") for k in range(1, 10)}
    payload = _closure(ordinal_status=status, halted_after_ordinal=ordinal, halt_reason_code=code, **kwargs)
    if binding_at is not None:
        payload["ordinal_pi_profile_binding"][str(ordinal)] = binding_at
    return payload


def test_c10_stage_closure_positive_controls():
    _require_valid_cfg1_stage_closure_payload_v3(_closure())
    _require_valid_cfg1_stage_closure_payload_v3(_halted(4, "PRE_DISPATCH_REFUSAL", binding_at="NO_PROFILE"))
    _require_valid_cfg1_stage_closure_payload_v3(
        _halted(5, HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN, pi_profile_attribution_halt=True)
    )
    _require_valid_cfg1_stage_closure_payload_v3(
        _halted(1, "PRE_DISPATCH_REFUSAL", binding_at="NO_PROFILE", stage_pi_profile_id=None,
                stage_pi_profile_declared_package_version=None)
    )
    _require_valid_cfg1_stage_closure_payload_v3(
        _halted(3, "RUN_RECORD_EMISSION_FAILED", status_at="EMISSION_FAILED", pi_profile_attribution_halt=True)
    )


def test_c10_every_section_20_2_invariant_is_enforced():
    # 1
    _closure_refuses(_closure(stage_pi_profile_declared_package_version=None), "STAGE_DECLARED_VERSION_DISAGREES_WITH_STAGE_PROFILE")
    _closure_refuses(
        _halted(1, "PRE_DISPATCH_REFUSAL", binding_at="NO_PROFILE", stage_pi_profile_id=None),
        "STAGE_DECLARED_VERSION_DISAGREES_WITH_STAGE_PROFILE",
    )
    # 2
    _closure_refuses(
        _halted(2, "PRE_DISPATCH_REFUSAL", binding_at="NO_PROFILE", stage_pi_profile_id=None,
                stage_pi_profile_declared_package_version=None),
        "NO_STAGE_PROFILE_OUTSIDE_A_FIRST_ORDINAL_HALT",
    )
    _closure_refuses(
        _halted(1, "PRE_DISPATCH_REFUSAL", binding_at="STAGE_PROFILE", stage_pi_profile_id=None,
                stage_pi_profile_declared_package_version=None),
    )
    # 3 (a STAGE_PROFILE binding with no stage profile)
    payload = _halted(1, "PRE_DISPATCH_REFUSAL", binding_at="NO_PROFILE", stage_pi_profile_id=None,
                      stage_pi_profile_declared_package_version=None)
    payload["ordinal_pi_profile_binding"]["1"] = "STAGE_PROFILE"
    _closure_refuses(payload)
    # 4
    payload = _halted(4, "PRE_DISPATCH_REFUSAL")
    payload["ordinal_pi_profile_binding"]["6"] = "NO_PROFILE"
    _closure_refuses(payload, "NOT_EXECUTED_BINDING_DISAGREES_WITH_STATUS")
    # 5
    payload = _closure()
    payload["ordinal_status"]["3"] = "EVIDENCE_REFUSED"
    _closure_refuses(payload, "NO_RUN_EVIDENCE_BINDING_DISAGREES_WITH_STATUS")
    payload = _closure()
    payload["ordinal_pi_profile_binding"]["3"] = "NO_RUN_EVIDENCE"
    _closure_refuses(payload, "NO_RUN_EVIDENCE_BINDING_DISAGREES_WITH_STATUS")
    # 6 -- NO_PROFILE only at the halt point
    payload = _halted(4, "PRE_DISPATCH_REFUSAL")
    payload["ordinal_pi_profile_binding"]["2"] = "NO_PROFILE"
    _closure_refuses(payload, "NO_PROFILE_ORDINAL_IS_NOT_THE_HALT_POINT")
    # 7
    _closure_refuses(_closure(pi_profile_attribution_halt=True))
    _closure_refuses(
        _halted(4, HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN, binding_at="NO_PROFILE", pi_profile_attribution_halt=True),
        "ATTRIBUTION_HALT_WITHOUT_A_PROFILE_BOUND_HALT_ORDINAL",
    )
    # 8
    _closure_refuses(_halted(4, HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN), "ATTRIBUTION_HALT_CODE_WITHOUT_ATTRIBUTION_HALT")
    # 9 -- a normal completion never co-exists with attribution failure
    _closure_refuses(_closure(pi_profile_attribution_halt=True))
    _closure_refuses(_closure(stage_pi_profile_id=None, stage_pi_profile_declared_package_version=None))


def test_c10_stage_closure_literals_types_and_version_dispatch():
    for key, bad in (
        ("pi_profile_attribution_halt", 1),
        ("pi_profile_attribution_halt", 0),
        ("stage_pi_profile_id", "A" * 64),
        ("pi_profile_set_head_sha256", "x"),
        ("pi_payload_contract", "PI-PC2"),
        ("pi_external_runtime_residual", False),
        ("halt_reason_code", "PI_PROFILE_ATTRIBUTION_PROVEN"),
    ):
        payload = _closure()
        payload[key] = bad
        _closure_refuses(payload)
    payload = _closure()
    payload["ordinal_pi_profile_binding"]["1"] = "PROFILE"
    _closure_refuses(payload, "BAD_ORDINAL_PI_PROFILE_BINDING_VALUE")
    payload = _closure()
    payload["ordinal_pi_profile_binding"].pop("9")
    _closure_refuses(payload, "CLOSED_KEY_SET_VIOLATION_ORDINAL_PI_PROFILE_BINDING")
    # A ".v2" stage-closure literal never existed and is refused everywhere.
    never = dict(_closure(), record_version="pi-harness-cfg1-stage-closure.v2")
    _closure_refuses(never, "BAD_LITERAL_RECORD_VERSION")
    assert records._dispatch_stage_closure_validator(never) is None
    # v1 <-> v3 never cross.
    v1 = stage_closure_payload()
    _require_valid_cfg1_stage_closure_payload(v1)
    _closure_refuses(v1)
    _refuses(_closure(), validator=_require_valid_cfg1_stage_closure_payload)
    # The v1 validator still refuses the seventh code.
    status = {str(k): ("RECORD_EMITTED" if k <= 4 else "NOT_EXECUTED") for k in range(1, 10)}
    _refuses(
        stage_closure_payload(ordinal_status=status, halted_after_ordinal=4,
                              halt_reason_code=HALT_PI_PROFILE_ATTRIBUTION_UNPROVEN),
        validator=_require_valid_cfg1_stage_closure_payload,
    )


def test_c10_the_v1_invariants_are_restated_in_v3():
    status = {str(k): "RECORD_EMITTED" for k in range(1, 10)}
    status["4"] = "EMISSION_COLLISION"
    payload = _closure(ordinal_status=status)
    payload["ordinal_pi_profile_binding"]["4"] = "NO_RUN_EVIDENCE"
    _closure_refuses(payload)  # a failure status on a normal completion
    _closure_refuses(_halted(3, "RUN_RECORD_EMISSION_FAILED", status_at="EMISSION_COLLISION"))
    _closure_refuses(_closure(halted_after_ordinal=3))


# ---------------------------------------------------------------------------
# C-13 / C-18 -- static wording audits
# ---------------------------------------------------------------------------

_FORBIDDEN_IDENTITY_WORDING = re.compile(
    r"(?i)(fully_identified|identity_complete|complete_identity|runtime_identity|node_pinned|runtime_pinned)"
)

_V3_VOCABULARIES = None


def _v3_vocabulary() -> set:
    from pi_harness_cfg1 import execution_namespace, pi_identity, pi_profile_binding_verifier

    vocabulary = set()
    vocabulary |= set(records.CFG1_RUN_RECORD_KEYS_V3)
    vocabulary |= set(records.CFG1_REFUSAL_RECORD_KEYS_V3)
    vocabulary |= set(records.CFG1_STAGE_CLOSURE_RECORD_KEYS_V3)
    vocabulary |= set(RUN_CLASSIFICATIONS_V3)
    vocabulary |= set(HALT_REASON_CODES_V3)
    vocabulary |= set(pi_identity.PI_IDENTITY_GATE_CODES)
    vocabulary |= set(pi_identity.PI_IDENTITY_FAILURE_CODES_V3)
    vocabulary |= set(pi_identity.PI_PROFILE_REOBSERVATION_VALUES)
    vocabulary |= set(halt.ORDINAL_PI_PROFILE_BINDING_VALUES)
    vocabulary |= set(execution_namespace.G9_PRECHECK_CODES)
    vocabulary |= set(pi_profile_binding_verifier.PI_PROFILE_BINDING_RESULTS)
    return vocabulary


def test_c13_no_v3_key_enum_value_halt_code_or_console_code_claims_complete_identity():
    for token in _v3_vocabulary():
        assert _FORBIDDEN_IDENTITY_WORDING.search(token) is None, token
    code_like = re.compile(r"^[A-Za-z0-9_.:-]{3,}$")
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and type(node.value) is str and code_like.match(node.value):
                assert _FORBIDDEN_IDENTITY_WORDING.search(node.value) is None, (path.name, node.value)


_PE2C_MODULES = (
    "__init__.py",
    "pi_identity.py",
    "run_executor.py",
    "run_contract.py",
    "stage_runner.py",
    "stage_decision.py",
    "writers.py",
    "records.py",
    "classification.py",
    "halt.py",
    "binding.py",
    "execution_namespace.py",
    "pi_profile_binding_verifier.py",
)

_REMEDY_WORDING = re.compile(
    r"(?i)(restore[sd]?\s+(the\s+)?(approved\s+)?pi|downgrad|install(ing)?\s+the\s+pinned|reinstall|pinned\s+pi\s+0\.)"
)


@pytest.mark.parametrize("module_name", _PE2C_MODULES)
def test_c18_no_restore_downgrade_or_install_pinned_wording(module_name):
    source = (_PACKAGE_DIR / module_name).read_text(encoding="utf-8")
    assert _REMEDY_WORDING.search(source) is None, _REMEDY_WORDING.search(source)
    assert "0.85.1" not in source and "0.87.0" not in source


# ---------------------------------------------------------------------------
# C-16 -- exactly THREE production comparisons of declared version text
#
# PE-1-C16 (``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_C16_AMENDMENT.md``)
# replaces PE-1 Sec. 26.3 C-16.  Exactly three sites may compare declared
# version text, and none decides authority:
#
#   V1  PE-2b loader integrity   (stored ``declared`` == the recomputed projection)
#   V2  PE-2a PMD delta enumeration (and the loader's integrity consumption of
#       that enumeration, which the amendment records as NOT a fourth site)
#   V3  PE-2c post-hoc binding verifier evidence-integrity equality
#
# The audit below is a small VALUE-FLOW analysis over ``ast``, not a token
# search and not a file allow-list.  It starts from the places a declared
# version value ENTERS the code (a ``package_version``-style key or attribute,
# the ``declared`` projection, the PMD delta enumeration), follows it through
# aliases, derivations (slicing, split, casefold, f-strings, containers,
# comprehensions), pass-through and deriving helpers across modules, and
# reports every operation that relates such a value to another value:
# comparison (equality, ordering, membership, chained), prefix/suffix/search
# methods, pattern matching, ``sorted``/``min``/``max``, numeric parse, a
# lookup keyed by the value, a ``match`` statement, and any semver-style
# import.  What it deliberately does NOT count (PE-1-C16 Sec. 6.3): key-name
# strings, closed key-set checks of the declared projection, length / ASCII
# grammar validation of ONE value, nullness and type-exact checks,
# serialization, copying provenance, comments and docstrings.
# ---------------------------------------------------------------------------

_VF_VERSION_KEYS = frozenset(
    {
        "package_version",
        "pi_ai_version",
        "pi_agent_core_version",
        "version",
        "pi_profile_declared_package_version",
        "stage_pi_profile_declared_package_version",
        "declared_package_version",
    }
)
_VF_DICT_KEYS = frozenset({"declared"})
_VF_VERSION_NAME = re.compile(
    r"(?i)(package_version|pi_ai_version|pi_agent_core_version|pi_observed_version|pinned_pi_version"
    r"|declared_version|(?<![a-z_])versions?(?![a-z_]))"
)
_VF_DECLARED_NAME = re.compile(r"(?i)(declared_dict|declared_projection|(?<![a-z_])declared(?![a-z_]))")
#: Calls whose result carries declared version text from a module-external
#: owner: the accepted loader/floor projection and the PE-2a PMD enumeration.
_VF_SOURCE_CALLS = {
    "_version_value": "TEXT",
    "declared_dict": "DICT",
    "declared_projection": "DICT",
    "compute_pmd_deltas": "TEXT",
}
_VF_SINK_METHODS = frozenset(
    {
        "startswith", "endswith", "find", "rfind", "index", "rindex", "count",
        "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__contains__",
        "match", "fullmatch", "search", "isdisjoint", "issubset", "issuperset",
        "intersection", "difference", "symmetric_difference", "union", "sort",
    }
)
_VF_SINK_FUNCTIONS = frozenset(
    {
        "sorted", "min", "max", "eq", "ne", "lt", "le", "gt", "ge", "contains", "compare_digest",
        "fnmatch", "fnmatchcase", "cmp_to_key", "parse", "Version", "LooseVersion", "StrictVersion",
        "coerce", "int", "float",
    }
)
_VF_TRANSFORMS = frozenset(
    {
        "str", "repr", "bytes", "bytearray", "tuple", "list", "set", "frozenset", "dict", "dumps",
        "policy_file_bytes", "canonical_json_bytes", "format", "join", "encode", "decode", "reversed",
        "iter", "next", "enumerate", "zip", "map", "filter", "copy", "deepcopy", "normalize", "casefold",
    }
)
_VF_KEY_VIEWS = frozenset({"tuple", "list", "set", "frozenset", "sorted", "iter", "reversed", "len"})
_VF_MUTATORS = frozenset({"append", "add", "extend", "update", "insert", "setdefault", "appendleft"})
_VF_TYPE_FUNCTIONS = frozenset({"type", "isinstance", "callable", "bool", "id", "issubclass"})
_VF_BANNED_IMPORT_ROOTS = frozenset(
    {"packaging", "semver", "distutils", "pkg_resources", "looseversion", "natsort"}
)
_VF_CONSTANT_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
_VF_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
_VF_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _vf_callee(call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else None


class _VersionFlow:
    """Kinds: ``TEXT`` a version value (or one derived from it); ``DICT`` the
    declared projection (its KEYS are field names, its values are versions);
    ``MIXED`` a container holding version text among other things; ``MEASURE``
    the length / code point of a version value."""

    def __init__(self, trees):
        self.trees = trees
        self.functions = {}
        self.returns = {}
        self.passthrough = {}
        self.derives = {}
        self.param_kinds = {}
        self.grammar = {}
        for path, tree in trees.items():
            patterns = set()
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    call = node.value
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "compile"
                        and call.args
                        and isinstance(call.args[0], ast.Constant)
                    ):
                        patterns.update(t.id for t in node.targets if isinstance(t, ast.Name))
            self.grammar[path] = patterns
            for node in ast.walk(tree):
                if isinstance(node, _VF_FUNCTIONS):
                    self.functions.setdefault(node.name, []).append((path, node))

    # -- kinds ----------------------------------------------------------------
    def _name_kind(self, identifier, path):
        if _VF_CONSTANT_NAME.match(identifier) or identifier in self.grammar.get(path, ()):
            return None
        if _VF_VERSION_NAME.search(identifier):
            return "TEXT"
        return "DICT" if _VF_DECLARED_NAME.search(identifier) else None

    def kind(self, node, env, path):
        if node is None or isinstance(node, ast.Constant):
            return None
        kind = self.kind
        if isinstance(node, ast.Name):
            return env[node.id] if node.id in env else self._name_kind(node.id, path)
        if isinstance(node, ast.Attribute):
            by_name = self._name_kind(node.attr, path)
            if by_name:
                return by_name
            return "TEXT" if kind(node.value, env, path) == "TEXT" else None
        if isinstance(node, ast.Subscript):
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                if index.value in _VF_VERSION_KEYS:
                    return "TEXT"
                if index.value in _VF_DICT_KEYS:
                    return "DICT"
            base = kind(node.value, env, path)
            if base == "TEXT":
                return "TEXT"
            if base == "DICT":
                return None if isinstance(index, ast.Constant) else "TEXT"
            return None
        if isinstance(node, ast.Call):
            return self._call_kind(node, env, path)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return "MIXED" if any(kind(item, env, path) for item in node.elts) else None
        if isinstance(node, ast.Dict):
            return "MIXED" if any(kind(item, env, path) for item in node.values if item is not None) else None
        if isinstance(node, ast.JoinedStr):
            return "TEXT" if any(kind(item, env, path) for item in node.values) else None
        if isinstance(node, ast.FormattedValue):
            return kind(node.value, env, path)
        if isinstance(node, ast.BinOp):
            return "TEXT" if (kind(node.left, env, path) or kind(node.right, env, path)) else None
        if isinstance(node, ast.IfExp):
            return kind(node.body, env, path) or kind(node.orelse, env, path)
        if isinstance(node, ast.BoolOp):
            return "TEXT" if any(kind(item, env, path) for item in node.values) else None
        if isinstance(node, _VF_COMPREHENSIONS):
            inner = self.comprehension_env(node, env, path)
            if isinstance(node, ast.DictComp):
                return "MIXED" if kind(node.value, inner, path) or kind(node.key, inner, path) else None
            return "MIXED" if kind(node.elt, inner, path) else None
        if isinstance(node, (ast.Starred, ast.NamedExpr, ast.Await)):
            return kind(node.value, env, path)
        if isinstance(node, ast.UnaryOp):
            return kind(node.operand, env, path)
        return None

    def _call_kind(self, node, env, path):
        kind = self.kind
        name = _vf_callee(node)
        args = list(node.args) + [keyword.value for keyword in node.keywords]
        method = isinstance(node.func, ast.Attribute)
        if name in ("len", "ord"):
            return "MEASURE" if any(kind(arg, env, path) == "TEXT" for arg in args) else None
        if name in _VF_TYPE_FUNCTIONS:
            return None
        if name in _VF_SOURCE_CALLS:
            return _VF_SOURCE_CALLS[name]
        if name in self.passthrough and not method:
            index, parameter = self.passthrough[name]
            if index < len(node.args):
                return kind(node.args[index], env, path)
            return next((kind(k.value, env, path) for k in node.keywords if k.arg == parameter), None)
        if name in self.derives and not method:
            for index, parameter in self.derives[name]:
                arg = node.args[index] if index < len(node.args) else next(
                    (k.value for k in node.keywords if k.arg == parameter), None
                )
                arg_kind = kind(arg, env, path)
                if arg_kind in ("TEXT", "DICT"):
                    return "TEXT"
                if arg_kind == "MIXED":
                    return "MIXED"
        if name in self.returns and not method:
            return self.returns[name]
        if method:
            receiver = kind(node.func.value, env, path)
            first = node.args[0] if node.args else None
            if name in ("get", "pop", "setdefault") and isinstance(first, ast.Constant) and isinstance(first.value, str):
                if first.value in _VF_VERSION_KEYS:
                    return "TEXT"
                if first.value in _VF_DICT_KEYS:
                    return "DICT"
                if receiver in ("MIXED", "DICT"):
                    return None
            if name in _VF_SINK_METHODS:
                return None  # a bool / int comparison result, not version text
            if receiver == "TEXT":
                return "TEXT"
            if receiver == "DICT":
                if name == "keys":
                    return None
                return "TEXT" if name in ("items", "values", "get", "pop") else None
            if receiver == "MIXED" and name in ("items", "values", "keys", "copy"):
                return "MIXED"
            if name in self.returns:
                return self.returns[name]
        if name in _VF_TRANSFORMS:
            arg_kinds = [kind(arg, env, path) for arg in args]
            if name in _VF_KEY_VIEWS and arg_kinds and arg_kinds[0] == "DICT":
                return None  # the KEYS of the declared projection, not its values
            if any(item in ("TEXT", "DICT") for item in arg_kinds):
                return "TEXT"
            if "MIXED" in arg_kinds:
                return "MIXED"
        return None

    @staticmethod
    def _yields_values(iterable_kind, iterable):
        if iterable_kind in ("TEXT", "MIXED"):
            return True
        return (
            iterable_kind == "DICT"
            and isinstance(iterable, ast.Call)
            and isinstance(iterable.func, ast.Attribute)
            and iterable.func.attr in ("items", "values")
        )

    def comprehension_env(self, comprehension, env, path):
        inner = dict(env)
        for generator in comprehension.generators:
            values = self._yields_values(self.kind(generator.iter, inner, path), generator.iter)
            for name in ast.walk(generator.target):
                if isinstance(name, ast.Name):
                    inner[name.id] = "TEXT" if values else None
        return inner

    @staticmethod
    def own_nodes(function):
        """Every node of ``function`` outside nested function bodies."""
        stack = list(ast.iter_child_nodes(function))
        while stack:
            node = stack.pop()
            yield node
            if not isinstance(node, (*_VF_FUNCTIONS, ast.Lambda)):
                stack.extend(ast.iter_child_nodes(node))

    def environment(self, function, path, with_params=True):
        env = dict(self.param_kinds.get(id(function), {})) if with_params else {}
        changed = True

        def put(name, kind):
            nonlocal changed
            current = env.get(name)
            if kind is None or current == kind or current == "TEXT":
                return
            if current is None or kind == "TEXT" or (current == "MEASURE" and kind in ("MIXED", "DICT")):
                env[name] = kind
                changed = True

        while changed:
            changed = False
            for node in self.own_nodes(function):
                targets, value = [], None
                if isinstance(node, ast.Assign):
                    targets, value = node.targets, node.value
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
                    targets, value = [node.target], node.value
                elif isinstance(node, (ast.For, ast.AsyncFor)):
                    targets, value = [node.target], node.iter
                elif isinstance(node, ast.With):
                    for item in node.items:
                        if item.optional_vars is not None and self.kind(item.context_expr, env, path):
                            for name in ast.walk(item.optional_vars):
                                if isinstance(name, ast.Name):
                                    put(name.id, "TEXT")
                    continue
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call = node.value
                    if (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr in _VF_MUTATORS
                        and isinstance(call.func.value, ast.Name)
                        and any(
                            self.kind(arg, env, path)
                            for arg in list(call.args) + [keyword.value for keyword in call.keywords]
                        )
                    ):
                        put(call.func.value.id, "MIXED")
                    continue
                if value is None:
                    continue
                kind = self.kind(value, env, path)
                if not kind:
                    continue
                if isinstance(node, (ast.For, ast.AsyncFor)):
                    if not self._yields_values(kind, value):
                        continue
                    kind = "TEXT"
                for target in targets:
                    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                        put(target.value.id, "MIXED")
                        continue
                    for name in ast.walk(target):
                        if isinstance(name, ast.Name):
                            put(name.id, kind)
        return env

    @staticmethod
    def _parameters(function):
        names = [arg.arg for arg in function.args.args]
        return names[1:] if names and names[0] in ("self", "cls") else names

    def propagate(self):
        """Cross-module fixpoint over returns, pass-through and parameters."""
        for _ in range(12):
            changed = False
            for name, definitions in list(self.functions.items()):
                for path, function in definitions:
                    env = self.environment(function, path)
                    intrinsic = self.environment(function, path, with_params=False)
                    parameters = self._parameters(function)
                    for index, parameter in enumerate(parameters):
                        probe = dict(intrinsic)
                        probe[parameter] = "TEXT"
                        grown = True
                        while grown:
                            grown = False
                            for node in self.own_nodes(function):
                                if isinstance(node, ast.Assign) and self.kind(node.value, probe, path):
                                    for target in node.targets:
                                        for leaf in ast.walk(target):
                                            if isinstance(leaf, ast.Name) and probe.get(leaf.id) != "TEXT":
                                                probe[leaf.id] = "TEXT"
                                                grown = True
                        for node in self.own_nodes(function):
                            if (
                                isinstance(node, ast.Return)
                                and node.value is not None
                                and self.kind(node.value, probe, path) in ("TEXT", "MIXED")
                                and (index, parameter) not in self.derives.setdefault(name, set())
                            ):
                                self.derives[name].add((index, parameter))
                                changed = True
                    for node in self.own_nodes(function):
                        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name) and node.value.id in parameters:
                            self.passthrough[name] = (parameters.index(node.value.id), node.value.id)
                        if isinstance(node, ast.Return) and node.value is not None:
                            returned = self.kind(node.value, intrinsic, path)
                            current = self.returns.get(name)
                            if returned in ("TEXT", "MIXED", "DICT") and current != "TEXT" and current != returned:
                                self.returns[name] = returned
                                changed = True
                        if not isinstance(node, ast.Call):
                            continue
                        for _callee_path, callee in self.functions.get(_vf_callee(node), ()):
                            callee_parameters = self._parameters(callee)
                            known = self.param_kinds.setdefault(id(callee), {})
                            pairs = [
                                (callee_parameters[i], arg) for i, arg in enumerate(node.args) if i < len(callee_parameters)
                            ]
                            pairs += [(k.arg, k.value) for k in node.keywords if k.arg in callee_parameters]
                            for parameter, arg in pairs:
                                arg_kind = self.kind(arg, env, path)
                                if arg_kind in ("TEXT", "DICT") and known.get(parameter) not in (arg_kind, "TEXT"):
                                    known[parameter] = arg_kind
                                    changed = True
            if not changed:
                break

    # -- sinks ----------------------------------------------------------------
    @staticmethod
    def _benign_compare(node):
        """Nullness and type-exact checks (PE-1-C16 Sec. 6.3)."""
        operands = [node.left] + list(node.comparators)
        typed = any(isinstance(o, ast.Call) and isinstance(o.func, ast.Name) and o.func.id == "type" for o in operands)
        if typed and all(isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)) for op in node.ops):
            return True
        return all(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops) and any(
            isinstance(o, ast.Constant) and o.value in (None, True, False) for o in operands
        )

    @staticmethod
    def _fixed_bound(node):
        return isinstance(node, ast.Constant) or (isinstance(node, ast.Name) and _VF_CONSTANT_NAME.match(node.id))

    def sink(self, node, env, path):
        kind = self.kind
        if isinstance(node, ast.Compare):
            if self._benign_compare(node):
                return None
            operands = [node.left] + list(node.comparators)
            kinds = [kind(o, env, path) for o in operands]
            if (  # key membership in the declared projection: ``name in declared``
                len(operands) == 2
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and kinds[1] == "DICT"
                and kinds[0] not in ("TEXT", "MIXED")
            ):
                return None
            if any(item in ("TEXT", "MIXED", "DICT") for item in kinds):
                return "compare"
            if "MEASURE" in kinds:  # length / ASCII grammar bounds of ONE value are not a comparison
                others = [o for o, item in zip(operands, kinds) if item != "MEASURE"]
                if kinds.count("MEASURE") >= 2 or not all(self._fixed_bound(o) for o in others):
                    return "compare-measure"
            return None
        if isinstance(node, ast.Call):
            name = _vf_callee(node)
            args = list(node.args) + [keyword.value for keyword in node.keywords]
            arg_kinds = [kind(arg, env, path) for arg in args]
            if isinstance(node.func, ast.Attribute):
                receiver = kind(node.func.value, env, path)
                if name in _VF_SINK_METHODS and (receiver or any(arg_kinds)):
                    if (  # a fixed compiled grammar applied to ONE value
                        name in ("match", "fullmatch", "search")
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in self.grammar[path]
                    ):
                        return None
                    return f"method:{name}"
                if name in ("get", "pop", "setdefault", "index") and args and arg_kinds[0] == "TEXT" and not isinstance(args[0], ast.Constant):
                    return f"lookup:{name}"
            if name in _VF_SINK_FUNCTIONS and any(arg_kinds):
                return f"function:{name}"
            return None
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            if (
                not isinstance(node.slice, (ast.Constant, ast.Slice))
                and kind(node.slice, env, path) == "TEXT"
                and kind(node.value, env, path) is None
            ):
                return "lookup:subscript"
            return None
        if isinstance(node, ast.Match) and kind(node.subject, env, path):
            return "match-statement"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(name.split(".")[0] in _VF_BANNED_IMPORT_ROOTS for name in names):
                return "banned-import"
        return None

    def _visit(self, node, env, path, scope, found):
        hit = self.sink(node, env, path)
        if hit:
            found.append((path.name, scope, hit, ast.unparse(node)))
        if isinstance(node, _VF_COMPREHENSIONS):
            inner = self.comprehension_env(node, env, path)
            for generator in node.generators:
                self._visit(generator.iter, env, path, scope, found)
                for condition in generator.ifs:
                    self._visit(condition, inner, path, scope, found)
            for part in [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]:
                self._visit(part, inner, path, scope, found)
            return
        if isinstance(node, _VF_FUNCTIONS):
            return  # a nested function is its own scope
        for child in ast.iter_child_nodes(node):
            self._visit(child, env, path, scope, found)

    def find(self):
        """``[(module file, enclosing function or None, kind of operation, source)]``."""
        self.propagate()
        found = []
        for path, tree in self.trees.items():
            loose = [n for n in tree.body if not isinstance(n, (*_VF_FUNCTIONS, ast.ClassDef))]
            for node in loose:
                self._visit(node, {}, path, None, found)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for member in node.body:
                        if not isinstance(member, _VF_FUNCTIONS):
                            self._visit(member, {}, path, None, found)
            for name, definitions in self.functions.items():
                for owner, function in definitions:
                    if owner == path:
                        env = self.environment(function, path)
                        for statement in list(function.body) + list(function.decorator_list):
                            self._visit(statement, env, path, name, found)
        return found


def _production_trees():
    """Production modules only: ``tests/`` is a sub-directory and never matched."""
    return {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(_PACKAGE_DIR.glob("*.py"))}


def _audit(sources):
    """Run the audit over ``{file name: source text}``."""
    return _VersionFlow({Path(name): ast.parse(text) for name, text in sources.items()}).find()


#: The complete, mechanically identified set of declared-version comparisons.
_V1_LOADER_INTEGRITY = (
    ("pi_profile_policy_loader.py", "_verify_profile_against_facts", "compare", "record['declared'] != facts.declared_dict()"),
    (
        "pi_profile_policy_loader.py",
        "_verify_profile_against_facts",
        "compare",
        "policy_file_bytes(expected) != policy_file_bytes(record)",
    ),
)
#: PE-1-C16 Sec. 4 SITE V2: the loader's integrity consumption of the V2
#: enumeration "is not a fourth site" -- it is the same accounting as V2.
_V2_PMD_ENUMERATION_CONSUMED = (
    ("pi_profile_policy_loader.py", "_validate_pmd", "compare", "stored != expected"),
)
_V2_PMD_DELTA_ENUMERATION = (
    ("pi_profile_floor.py", "compute_pmd_deltas", "compare", "old_version != new_version"),
)
_V3_POST_HOC_BINDING = (
    ("pi_profile_binding_verifier.py", "_require_bound_profile", "compare", "declared != committed"),
)
_PERMITTED_VERSION_COMPARISONS = (
    set(_V1_LOADER_INTEGRITY)
    | set(_V2_PMD_ENUMERATION_CONSUMED)
    | set(_V2_PMD_DELTA_ENUMERATION)
    | set(_V3_POST_HOC_BINDING)
)


def test_c16_audit_scans_production_modules_only():
    """Test modules are not production comparison sites (PE-1-C16 Sec. 6.3)."""
    scanned = set(_production_trees())
    assert scanned and all(path.parent == _PACKAGE_DIR for path in scanned)
    assert not any("tests" in path.parts[len(_PACKAGE_DIR.parts) :] for path in scanned)
    assert Path(__file__).resolve() not in scanned
    assert (_PACKAGE_DIR / "pi_profile_binding_verifier.py") in scanned


def test_c16_exactly_the_three_permitted_sites_exist_and_no_fourth():
    found = _VersionFlow(_production_trees()).find()
    located = {(module, scope, operation, source) for module, scope, operation, source in found}
    assert located == _PERMITTED_VERSION_COMPARISONS, (
        sorted(located - _PERMITTED_VERSION_COMPARISONS),
        sorted(_PERMITTED_VERSION_COMPARISONS - located),
    )
    # V1, V2 and V3 are each detected where they are implemented (not vacuous).
    for site in (_V1_LOADER_INTEGRITY, _V2_PMD_DELTA_ENUMERATION, _V3_POST_HOC_BINDING):
        assert set(site) <= located


def test_c16_every_permitted_site_is_a_plain_equality_never_ordering_or_compatibility():
    """No semver / version compatibility logic: each site is ``==``/``!=`` only,
    and no semver-style import, numeric parse, prefix/suffix test, sort or
    version-keyed lookup exists anywhere in production."""
    found = _VersionFlow(_production_trees()).find()
    assert {operation for _module, _scope, operation, _source in found} == {"compare"}
    for module_file, scope, _operation, source in _PERMITTED_VERSION_COMPARISONS:
        compares = [
            node
            for node in ast.walk(_function(module_file, scope))
            if isinstance(node, ast.Compare) and ast.unparse(node) == source
        ]
        assert len(compares) == 1, (module_file, scope, source)
        assert all(isinstance(op, (ast.Eq, ast.NotEq)) for op in compares[0].ops), source


def _function(module_file, name):
    tree = ast.parse((_PACKAGE_DIR / module_file).read_text(encoding="utf-8"))
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(matches) == 1, (module_file, name)
    return matches[0]


def _guard_of(function, compare_source):
    """The ``if`` whose test contains the comparison (innermost)."""
    guards = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If) and any(ast.unparse(sub) == compare_source for sub in ast.walk(node.test))
    ]
    assert guards, compare_source
    return min(guards, key=lambda guard: len(ast.unparse(guard.test)))


def _only_raises(guard, exception_name, code=None):
    assert not guard.orelse and len(guard.body) == 1 and isinstance(guard.body[0], ast.Raise)
    call = guard.body[0].exc
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == exception_name
    if code is not None:
        assert [ast.unparse(a) for a in call.args] == [code]


def test_c16_v1_loader_integrity_only_refuses_the_policy_chain():
    function = _function("pi_profile_policy_loader.py", "_verify_profile_against_facts")
    _only_raises(_guard_of(function, "record['declared'] != facts.declared_dict()"), "Cfg1PolicyError", "'POLICY_DECLARED_MISMATCH'")
    _only_raises(
        _guard_of(function, "policy_file_bytes(expected) != policy_file_bytes(record)"),
        "Cfg1PolicyError",
        "'POLICY_PROFILE_RECORD_MISMATCH'",
    )
    assert not [n for n in ast.walk(function) if isinstance(n, ast.Return) and n.value is not None]
    consumed = _function("pi_profile_policy_loader.py", "_validate_pmd")
    _only_raises(_guard_of(consumed, "stored != expected"), "Cfg1PolicyError", "'POLICY_PMD_DELTAS_MISMATCH'")


def test_c16_v2_pmd_enumeration_runs_only_after_c2_and_only_lists_a_fact():
    function = _function("pi_profile_floor.py", "compute_pmd_deltas")
    first = function.body[1]  # body[0] is the docstring
    assert isinstance(first, ast.If) and ast.unparse(first.test) == "not c2_relation(candidate, reference)"
    _only_raises(first, "Cfg1FloorError", "'PMD_REQUIRES_C2'")
    guard = _guard_of(function, "old_version != new_version")
    assert not guard.orelse and len(guard.body) == 1 and isinstance(guard.body[0], ast.Expr)
    call = guard.body[0].value
    assert ast.unparse(call.func) == "deltas.append" and "DELTA_VERSION" in ast.unparse(call.args[0])
    source = ast.unparse(function)
    assert "old_version = _version_value(reference_doc)" in source
    assert "new_version = _version_value(candidate_doc)" in source


def test_c16_v3_only_makes_the_post_hoc_verifier_refuse_and_returns_nothing():
    function = _function("pi_profile_binding_verifier.py", "_require_bound_profile")
    assert [a.arg for a in function.args.args] == ["profile_id", "declared", "eligible", "declared_versions"]
    guard = _guard_of(function, "declared != committed")
    _only_raises(guard, "_Refused", "PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH")
    assert not [n for n in ast.walk(function) if isinstance(n, ast.Return) and n.value is not None]
    # Every call site discards the (None) result: nothing is assigned, branched on or returned.
    tree = ast.parse((_PACKAGE_DIR / "pi_profile_binding_verifier.py").read_text(encoding="utf-8"))
    statements = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _vf_callee(n) == "_require_bound_profile"]
    assert len(calls) == 2 and all(id(call) in statements for call in calls)


_V3_SYMBOLS = ("verify_stage_pi_profile_binding", "_require_bound_profile", "_committed_revision_for_head")


def _internal_imports(tree, module_stems):
    edges, dynamic = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".") if node.module else []
            if node.level == 0:
                if parts[:1] != ["pi_harness_cfg1"]:
                    continue
                parts = parts[1:]
            if parts:
                edges.add(parts[0])
            else:  # ``from . import name``: a sibling module, or a name defined in ``__init__``
                edges.update(a.name if a.name in module_stems else "__init__" for a in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "pi_harness_cfg1":
                    edges.add(parts[1] if len(parts) > 1 else "__init__")
        elif isinstance(node, ast.Call) and _vf_callee(node) in ("__import__", "import_module", "exec", "eval"):
            dynamic = True
    return edges, dynamic


def test_c16_v3_has_no_runtime_importer_direct_transitive_or_dynamic():
    """The verifier is not reachable from any production module, so nothing in
    P, the gate, the executor, the runner, the writers, the classifier, the
    halt logic or the stage output can import, call or consume it."""
    trees = _production_trees()
    stems = {path.stem for path in trees}
    graph = {}
    for path, tree in trees.items():
        edges, dynamic = _internal_imports(tree, stems)
        assert not dynamic, f"{path.name} imports dynamically"
        graph[path.stem] = edges & stems
    verifier = "pi_profile_binding_verifier"
    assert graph[verifier]  # the verifier itself has dependencies (the graph is not vacuous)
    runtime_roots = (
        "pi_identity",  # P
        "run_contract",  # the gate / L1
        "run_executor",
        "stage_runner",
        "stage_decision",
        "writers",
        "classification",
        "halt",
        "stage_output",
        "lifecycle",
        "binding",
        "records",
        "execution_namespace",
    )
    for stem in sorted(stems - {verifier}):
        reachable, frontier = set(), [stem]
        while frontier:
            for target in graph.get(frontier.pop(), ()):
                if target not in reachable:
                    reachable.add(target)
                    frontier.append(target)
        assert verifier not in reachable, (stem, "reaches the post-hoc verifier")
    assert set(runtime_roots) <= stems
    # No name, attribute, import alias or string in any other module even refers to it.
    for path, tree in trees.items():
        if path.stem == verifier:
            continue
        for node in ast.walk(tree):
            identifiers = []
            if isinstance(node, ast.Name):
                identifiers.append(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.append(node.attr)
            elif isinstance(node, ast.alias):
                identifiers.append(node.name.split(".")[-1])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert verifier not in node.value, (path.name, node.value[:60])
                identifiers.append(node.value)
            for identifier in identifiers:
                assert identifier != verifier and identifier not in _V3_SYMBOLS, (path.name, identifier)
                assert not identifier.startswith("PI_PROFILE_BINDING_"), (path.name, identifier)


def test_c16_v3_verifier_is_read_only_and_reads_the_loader_projection_only():
    trees = {path.stem: tree for path, tree in _production_trees().items()}
    verifier = trees["pi_profile_binding_verifier"]
    stems = set(trees)
    edges, dynamic = _internal_imports(verifier, stems)
    assert not dynamic
    assert edges <= {
        "__init__",
        "pi_profile_policy_loader",
        "halt",
        "pi_payload",
        "records",
        "schedule",
    }, edges
    forbidden_calls = {"open", "setattr", "delattr", "exec", "eval", "compile", "__import__", "input"}
    forbidden_methods = {"write", "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "touch", "remove"}
    for node in ast.walk(verifier):
        assert not isinstance(node, (ast.Global, ast.Nonlocal))
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            # Only the verifier's own private exception may set its own field.
            assert isinstance(node.value, ast.Name) and node.value.id == "self", ast.unparse(node)
        if isinstance(node, ast.Call):
            assert _vf_callee(node) not in forbidden_calls | forbidden_methods, ast.unparse(node)
    # The loader-recomputed declared-version projection is consumed by the verifier alone.
    for stem, tree in trees.items():
        if stem in ("pi_profile_policy_loader", "pi_profile_binding_verifier"):
            continue
        for node in ast.walk(tree):
            names = [getattr(node, "id", None), getattr(node, "attr", None)]
            assert "profile_declared_versions" not in names, stem
            assert "_GENUINE_POLICY_LOAD" not in names, stem
            assert "_PolicyLoad" not in names, stem


_C16_EVASIONS = {
    "literal_equality": "def f(declared_package_version):\n    return declared_package_version == '0.85.1'\n",
    "two_records_inequality": "def f(a, b):\n    return a['package_version'] != b['package_version']\n",
    "ordering": "def f(a, b):\n    return a['pi_ai_version'] < b['pi_ai_version']\n",
    "chained_ordering": "def f(r, lo, hi):\n    return lo <= r['package_version'] <= hi\n",
    "membership_in_literal": "def f(version):\n    return version in ('1.0', '2.0')\n",
    "membership_not_in_set": "def f(r):\n    return r['version'] not in {'1'}\n",
    "alias_then_compare": "def f(r, other):\n    v = r['package_version']\n    w = v\n    return w == other\n",
    "slice_derived": "def f(r, other):\n    return r['package_version'][:4] == other\n",
    "split_and_numeric_parse": "def f(r):\n    major = int(r['package_version'].split('.')[0])\n    return major >= 1\n",
    "casefold_derived": "def f(r, other):\n    return r['package_version'].casefold() == other\n",
    "string_wrapper": "def f(r, other):\n    return str(r['package_version']) == other\n",
    "fstring_derived": "def f(r, other):\n    return f\"v{r['package_version']}\" == other\n",
    "concatenation_derived": "def f(r, other):\n    return ('v' + r['package_version']) == other\n",
    "ternary_alias": "def f(r, other):\n    v = r['package_version'] if r else other\n    return v == other\n",
    "startswith": "def f(r):\n    return r['package_version'].startswith('0.')\n",
    "endswith": "def f(r):\n    return r['pi_agent_core_version'].endswith('-rc1')\n",
    "substring_membership": "def f(r):\n    return 'rc' in r['package_version']\n",
    "dunder_eq_method": "def f(r, o):\n    return r['package_version'].__eq__(o)\n",
    "operator_eq": "import operator\n\ndef f(r, o):\n    return operator.eq(r['package_version'], o)\n",
    "regex_version_as_pattern": "import re\n\ndef f(r, o):\n    return re.fullmatch(r['package_version'], o)\n",
    "regex_version_as_subject_with_dynamic_pattern": "import re\n\ndef f(r, p):\n    return re.match(p, r['package_version'])\n",
    "helper_equality": "def same(a, b):\n    return a == b\n\ndef f(r, s):\n    return same(r['package_version'], s['package_version'])\n",
    "helper_returns_derived_value": "def major(v):\n    return v.split('.')[0]\n\ndef f(r, s):\n    return major(r['package_version']) == s\n",
    "nested_function": "def f(r, o):\n    def g(v):\n        return v == o\n    return g(r['package_version'])\n",
    "lookup_subscript": "TABLE = {}\n\ndef f(r):\n    return TABLE[r['package_version']]\n",
    "lookup_get": "TABLE = {}\n\ndef f(r):\n    return TABLE.get(r['pi_ai_version'])\n",
    "sorted_pair": "def f(r, s):\n    return sorted([r['package_version'], s['package_version']])\n",
    "max_pair": "def f(r, s):\n    return max(r['package_version'], s['package_version'])\n",
    "list_equality": "def f(r, s):\n    return [r['package_version']] == [s['package_version']]\n",
    "list_built_by_append": "def f(r, s):\n    seen = []\n    seen.append(r['package_version'])\n    return seen == s\n",
    "for_loop_alias": "def f(rs, o):\n    for r in rs:\n        v = r['package_version']\n        if v > o:\n            return True\n",
    "comprehension_filter": "def f(rs, o):\n    return [x for x in [r['package_version'] for r in rs] if x != o]\n",
    "declared_projection_equality": "def f(r, facts):\n    return r['declared'] != facts.declared_dict()\n",
    "declared_value_via_projection": "def f(r, other):\n    d = r['declared']\n    return d['package_version'] == other\n",
    "whole_record_equality": "def f(r, o):\n    return {'declared': r['declared'], 'x': 1} == o\n",
    "serialized_then_compared": "import json\n\ndef f(r, o):\n    return json.dumps(r['declared']) == o\n",
    "attribute_source": "def f(profile, o):\n    return profile.declared_package_version == o\n",
    "match_statement": "def f(r):\n    match r['package_version']:\n        case '1':\n            return 1\n",
    "semver_import": "import semver\n",
    "packaging_import": "from packaging.version import Version\n",
}
_C16_BENIGN = {
    "key_name_as_dict_key": "def f(x):\n    return {'package_version': x}\n",
    "closed_key_set_of_a_record": "KEYS = frozenset({'package_name', 'package_version'})\n\ndef f(rec):\n    return frozenset(rec) != KEYS\n",
    "closed_key_set_of_declared_projection": "KEYS = frozenset({'package_name'})\n\ndef f(r):\n    return frozenset(r['declared']) != KEYS\n",
    "key_name_comparison": "def f(key):\n    return key == 'version'\n",
    "declared_key_membership": "def f(declared, name):\n    return name in declared\n",
    "length_check": "def f(r):\n    return len(r['package_version']) > 128\n",
    "length_bounds": "MAX = 128\n\ndef f(r):\n    return 1 <= len(r['package_version']) <= MAX\n",
    "type_exact": "def f(r):\n    return type(r['package_version']) is not str\n",
    "isinstance": "def f(r):\n    return isinstance(r['package_version'], str)\n",
    "nullness": "def f(r):\n    return r['package_version'] is None\n",
    "not_nullness": "def f(r):\n    return r['package_version'] is not None\n",
    "nullness_bi_implication": "def f(v, pid):\n    return (v is None) == (pid is None)\n",
    "ascii_grammar_loop": "def f(r):\n    for c in r['package_version']:\n        if not 0x21 <= ord(c) <= 0x7E:\n            return False\n    return True\n",
    "fixed_regex_grammar": "import re\nPAT = re.compile(r'[\\x21-\\x7e]{1,128}')\n\ndef f(r):\n    return PAT.fullmatch(r['package_version']) is not None\n",
    "serialization_only": "import json\n\ndef f(r):\n    return json.dumps({'declared': r['declared']})\n",
    "copy_provenance_into_a_record": "def f(out, profile):\n    out['pi_profile_declared_package_version'] = profile.declared_package_version\n    return out\n",
    "copy_provenance_return": "def f(r):\n    return r['package_version']\n",
    "pass_through_helper": "def keep(x):\n    return x\n\ndef f(r):\n    return keep(r['package_version'])\n",
    "record_version_schema_literal": "def f(a):\n    return a.get('record_version') == 'cfg1.run.v3'\n",
    "schema_name_constant": "RUN_RECORD_VERSION_V3 = 'x'\n\ndef f(a):\n    return a == RUN_RECORD_VERSION_V3\n",
    "unrelated_equality": "def f(a, b):\n    return a == b\n",
    "profile_id_equality": "def f(a, b):\n    return a['profile_id'] != b['profile_id']\n",
    "comment_and_docstring": "def f(a):\n    \"\"\"declared version == other\"\"\"\n    # version == 1\n    return a\n",
}


@pytest.mark.parametrize("name", sorted(_C16_EVASIONS))
def test_c16_audit_detects_the_indirection_form(name):
    assert _audit({"fixture.py": _C16_EVASIONS[name]}), name


@pytest.mark.parametrize("name", sorted(_C16_BENIGN))
def test_c16_audit_does_not_count_a_non_comparison(name):
    assert _audit({"fixture.py": _C16_BENIGN[name]}) == [], name


def test_c16_audit_follows_a_helper_across_modules():
    sources = {
        "helper.py": "def same(a, b):\n    return a == b\n",
        "caller.py": "def f(r, s):\n    return same(r['package_version'], s)\n",
    }
    assert [(module, scope) for module, scope, _o, _s in _audit(sources)] == [("helper.py", "same")]


_C16_INJECTION = "\n\ndef _injected_fourth_comparison(r, s):\n    return r['package_version'] < s['package_version']\n"


@pytest.mark.parametrize(
    "module_file",
    [
        "pi_identity.py",
        "run_contract.py",
        "run_executor.py",
        "stage_runner.py",
        "stage_decision.py",
        "writers.py",
        "classification.py",
        "halt.py",
        "stage_output.py",
        "pi_profile_binding_verifier.py",
        "pi_profile_policy_loader.py",
        "pi_profile_floor.py",
    ],
)
def test_c16_a_fourth_comparison_added_to_a_real_module_is_caught(module_file):
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted(_PACKAGE_DIR.glob("*.py"))}
    sources[module_file] += _C16_INJECTION
    located = {(module, scope, operation, source) for module, scope, operation, source in _audit(sources)}
    assert located - _PERMITTED_VERSION_COMPARISONS == {
        (module_file, "_injected_fourth_comparison", "compare", "r['package_version'] < s['package_version']")
    }


def test_c16_a_second_comparison_inside_a_permitted_function_is_still_a_different_finding():
    """The audit pins the exact operands of each site, so widening a site in place fails."""
    path = _PACKAGE_DIR / "pi_profile_binding_verifier.py"
    source = path.read_text(encoding="utf-8").replace(
        "    committed = declared_versions.get(profile_id)\n",
        "    committed = declared_versions.get(profile_id)\n    if declared.startswith('0.'):\n        raise _Refused(PI_PROFILE_BINDING_REFUSED_DECLARED_VERSION_MISMATCH)\n",
    )
    assert source != path.read_text(encoding="utf-8")
    sources = {p.name: p.read_text(encoding="utf-8") for p in sorted(_PACKAGE_DIR.glob("*.py"))}
    sources[path.name] = source
    located = {(module, scope, operation, text) for module, scope, operation, text in _audit(sources)}
    assert located - _PERMITTED_VERSION_COMPARISONS == {
        (path.name, "_require_bound_profile", "method:startswith", "declared.startswith('0.')")
    }


def test_c16_installed_pi_conformance_tests_compare_no_version():
    """PE-0 Sec. 11.2 / PE-1 Sec. 26.3: the conformance tests never compare a
    version (this is the unchanged, separate rule; V1-V3 are production sites)."""
    path = _PACKAGE_DIR / "tests" / "test_cfg1_pi_conformance.py"
    text = path.read_text(encoding="utf-8")
    assert _audit({path.name: text}) == []
    # Not vacuous: the same audit does catch a comparison added to that file.
    assert _audit({path.name: text + "\n\ndef test_x(r, o):\n    assert r['package_version'] == o\n"})


def test_c16_no_runtime_module_reads_the_pinned_release_literal():
    """PE-1 S-6: PINNED_PI_VERSION is provenance only -- never imported,
    referenced, serialized or compared by any module but its definition."""
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        if path.name == "identity.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name):
                assert node.id != "PINNED_PI_VERSION", path.name
            if isinstance(node, ast.Attribute):
                assert node.attr != "PINNED_PI_VERSION", path.name
            if isinstance(node, ast.ImportFrom):
                assert "PINNED_PI_VERSION" not in {alias.name for alias in node.names}, path.name
