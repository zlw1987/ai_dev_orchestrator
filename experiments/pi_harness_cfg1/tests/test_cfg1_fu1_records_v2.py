"""FU1 (R6 + AMEND1): run record v2, refusal record v2, and v1 unchanged.

Tests N, O, T and AE, plus the W invariants and the v2 closure predicate, of
``PHASE_5F3B_HARNESS_CFG1_L1_BOUNDARY_FU1_DESIGN.md`` Sec. 10/11 as reconciled
by ``..._OC3_AMEND1_DESIGN.md`` Sec. 8/15/16. Every payload here is
SYNTHETIC; no real results file is read, and every v2 rule is exercised on the
serialized payload ALONE (a pure function of durable fields).
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from cfg1_builders import a3_shaped_v1_payload, happy_observations, refusal_payload, v1_run_payload

from pi_harness_cfg1 import binding, lifecycle, records, writers
from pi_harness_cfg1.arms import ARM_SHAPE
from pi_harness_cfg1.lifecycle import compute_lifecycle_closure, compute_lifecycle_closure_v2
from pi_harness_cfg1.pi_identity import PI_IDENTITY_FAILURE_CODES
from pi_harness_cfg1.records import (
    Cfg1RecordValidationError,
    _require_valid_cfg1_refusal_payload,
    _require_valid_cfg1_refusal_payload_v2,
    _require_valid_cfg1_run_payload,
    _require_valid_cfg1_run_payload_v2,
    build_cfg1_run_payload,
)

_PACKAGE_DIR = Path(__file__).resolve().parents[1]

#: The four R6 codes AMEND1 Sec. 8.1 deletes (or replaces).
DELETED_R6_CODES = (
    "PI_PROBE_FAILED",
    "PI_SEAM_CHANGED_DURING_PROBE",
    "PI_VERSION_MISMATCH",
    "PI_IDENTITY_DRIFTED_BEFORE_PROBE",
)


def _v2(**overrides) -> dict:
    """A v2 payload from happy observations plus overrides, lifecycle recomputed."""
    observations = happy_observations(runtime_reported_compat_shape=ARM_SHAPE["Q"])
    observations.update(overrides)
    closed, steps = compute_lifecycle_closure_v2(observations)
    observations["lifecycle_all_closed"] = closed
    observations["lifecycle_failure_steps"] = list(steps)
    return build_cfg1_run_payload(
        stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
    )


#: Everything an L1 refusal leaves at its fail-closed initial value.
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
)


def _l1(*, code="OFFLINE_PREFLIGHT_FAILED", failure=None, seam=True, **extra) -> dict:
    from pi_harness_cfg1 import obs1

    return _v2(
        **_L1_SHAPE,
        **obs1.unavailable_activity_fields(None),
        pre_dispatch_refusal_code=code,
        refused_at_step="L1",
        pi_identity_failure_code=failure,
        pi_seam_digests_match=seam,
        **extra,
    )


def _refused_at(step: str, code: str, **extra) -> dict:
    """A REFUSAL-mode v2 payload past L1 (W = AUTHORITY_RETURNED, all closed)."""
    from pi_harness_cfg1 import obs1

    shape = dict(_L1_SHAPE)
    shape.update(
        workspace_mint_state="AUTHORITY_RETURNED",
        workspace_authority_reproved=True,
        workspace_removed_verified=True,
    )
    shape.update(extra)
    return _v2(
        **shape,
        **obs1.unavailable_activity_fields(None),
        pre_dispatch_refusal_code=code,
        refused_at_step=step,
    )


def _refuses(payload, reason: str | None = None) -> None:
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload_v2(json.loads(json.dumps(payload)))
    if reason is not None:
        assert excinfo.value.reason_code == reason, excinfo.value.reason_code


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_the_builder_emits_exactly_v2_and_every_mode_validates():
    clean = _v2()
    assert clean["record_version"] == "pi-harness-cfg1-run.v2"
    assert "pi_observed_version" not in clean
    assert "pi_version_probe_attempted" not in clean
    _require_valid_cfg1_run_payload_v2(clean)
    for failure, seam in (
        ("PI_RESOLUTION_FAILED", False),
        ("PI_SEAM_UNPROVEN", False),
        ("PI_IDENTITY_DRIFTED_DURING_PROOF", True),
    ):
        _require_valid_cfg1_run_payload_v2(_l1(failure=failure, seam=seam))
    # R-S3: the Git-resolution refusal, P's success committed.
    _require_valid_cfg1_run_payload_v2(_l1(failure=None, seam=True))
    # R-S4: UNEXPECTED at L1, S free.
    _require_valid_cfg1_run_payload_v2(_l1(code="UNEXPECTED_STEP_FAILURE", seam=False))
    _require_valid_cfg1_run_payload_v2(_l1(code="UNEXPECTED_STEP_FAILURE", seam=True))
    _require_valid_cfg1_run_payload_v2(_refused_at("L7", "ROUTE_UNAVAILABLE"))
    _require_valid_cfg1_run_payload_v2(_refused_at("L9", "UNEXPECTED_STEP_FAILURE"))


def test_the_v2_refusal_record_names_run_v2_and_refusal_v1_is_unchanged():
    payload = refusal_payload()
    assert payload["record_version"] == "pi-harness-cfg1-refusal.v2"
    assert payload["refused_record_kind"] == "pi-harness-cfg1-run.v2"
    _require_valid_cfg1_refusal_payload_v2(payload)
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_refusal_payload(payload)
    legacy = dict(payload)
    legacy["record_version"] = "pi-harness-cfg1-refusal.v1"
    legacy["refused_record_kind"] = "pi-harness-cfg1-run.v1"
    _require_valid_cfg1_refusal_payload(legacy)
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_refusal_payload_v2(legacy)


# ---------------------------------------------------------------------------
# AE -- the three-code domain, everywhere
# ---------------------------------------------------------------------------


def test_ae_the_domain_is_exactly_three_codes_and_the_builder_refuses_others():
    assert PI_IDENTITY_FAILURE_CODES == {
        "PI_RESOLUTION_FAILED",
        "PI_SEAM_UNPROVEN",
        "PI_IDENTITY_DRIFTED_DURING_PROOF",
    }
    assert not (PI_IDENTITY_FAILURE_CODES & records.PRE_DISPATCH_REFUSAL_CODES_V2)
    for bad in DELETED_R6_CODES + ("", "pi_resolution_failed", 3, True):
        observations = happy_observations(pi_identity_failure_code=bad)
        with pytest.raises(Cfg1RecordValidationError):
            build_cfg1_run_payload(
                stage_id="S1", stage_execution_id="S1-X1", run_ordinal=1, observations=observations
            )


@pytest.mark.parametrize("code", DELETED_R6_CODES)
def test_ae_the_validator_refuses_every_deleted_r6_code(code):
    payload = _l1(failure="PI_SEAM_UNPROVEN", seam=False)
    payload["pi_identity_failure_code"] = code
    _refuses(payload, "BAD_ENUM_PI_IDENTITY_FAILURE_CODE")


def test_ae_no_production_module_names_a_deleted_code():
    for path in sorted(_PACKAGE_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for code in DELETED_R6_CODES:
            assert code not in text, (path.name, code)


# ---------------------------------------------------------------------------
# O -- forged records fail by DURABLE fields alone
# ---------------------------------------------------------------------------


def test_o_forged_identity_and_step_combinations_are_refused():
    # F set at K = "L7"
    forged = _refused_at("L7", "ROUTE_UNAVAILABLE")
    forged["pi_identity_failure_code"] = "PI_SEAM_UNPROVEN"
    forged["pi_seam_digests_match"] = False
    _refuses(forged, "PI_IDENTITY_FAILURE_OUTSIDE_L1_PREFLIGHT_REFUSAL")
    # (L1, OFFLINE_PREFLIGHT_FAILED, F = null, S = false)
    _refuses(_l1(failure=None, seam=False), "L1_PREFLIGHT_REFUSAL_WITHOUT_P_SUCCESS")
    # F = DRIFTED with S = false; F = SEAM_UNPROVEN with S = true;
    # F = RESOLUTION_FAILED with S = true
    _refuses(_l1(failure="PI_IDENTITY_DRIFTED_DURING_PROOF", seam=False),
             "PI_IDENTITY_FAILURE_DISAGREES_WITH_SEAM_MATCH")
    _refuses(_l1(failure="PI_SEAM_UNPROVEN", seam=True),
             "PI_IDENTITY_FAILURE_DISAGREES_WITH_SEAM_MATCH")
    _refuses(_l1(failure="PI_RESOLUTION_FAILED", seam=True),
             "PI_IDENTITY_FAILURE_DISAGREES_WITH_SEAM_MATCH")
    # (L1, UNEXPECTED_STEP_FAILURE, F != null)
    _refuses(_l1(code="UNEXPECTED_STEP_FAILURE", failure="PI_SEAM_UNPROVEN", seam=False),
             "PI_IDENTITY_FAILURE_OUTSIDE_L1_PREFLIGHT_REFUSAL")
    # a post-L1 record with S = false, and a clean record with S = false
    post_l1 = _refused_at("L7", "ROUTE_UNAVAILABLE")
    post_l1["pi_seam_digests_match"] = False
    _refuses(post_l1, "POST_L1_RECORD_WITHOUT_P_SUCCESS")
    clean = _v2()
    clean["pi_seam_digests_match"] = False
    _refuses(clean, "POST_L1_RECORD_WITHOUT_P_SUCCESS")
    # a P code written into the refusal-code field (B7)
    wrong_field = _l1(failure="PI_SEAM_UNPROVEN", seam=False)
    wrong_field["pre_dispatch_refusal_code"] = "PI_SEAM_UNPROVEN"
    _refuses(wrong_field, "BAD_ENUM_PRE_DISPATCH_REFUSAL_CODE")
    # (L1, ROUTE_UNAVAILABLE)
    _refuses(_l1(code="ROUTE_UNAVAILABLE"), "REFUSAL_CODE_DISAGREES_WITH_STEP")
    # a refusal code without a step, and a step without a code
    no_step = _refused_at("L7", "ROUTE_UNAVAILABLE")
    no_step["refused_at_step"] = None
    _refuses(no_step)
    no_code = _refused_at("L7", "ROUTE_UNAVAILABLE")
    no_code["pre_dispatch_refusal_code"] = None
    _refuses(no_code)


@pytest.mark.parametrize("key,value", [
    ("pi_observed_version", "0.85.1"),
    ("pi_observed_version", "NOT_OBSERVED"),
    ("pi_version_probe_attempted", False),
    ("pi_version_probe_attempted", True),
])
def test_o_a_v2_payload_carrying_a_removed_key_is_refused(key, value):
    payload = _v2()
    payload[key] = value
    _refuses(payload, "V2_CARRIES_REMOVED_IDENTITY_KEY")


@pytest.mark.parametrize("step", [f"L{n}" for n in range(1, 19)])
def test_o_the_step_code_table_admits_exactly_the_shipped_codes_plus_unexpected(step):
    table = records.REFUSAL_CODES_BY_STEP
    assert "UNEXPECTED_STEP_FAILURE" in table[step]
    foreign = sorted(records.PRE_DISPATCH_REFUSAL_CODES - table[step])
    assert foreign  # every step has codes it may NOT carry
    if step == "L1":
        payload = _l1(code=foreign[0])
    else:
        payload = _refused_at(step, sorted(table[step] - {"UNEXPECTED_STEP_FAILURE"})[0])
        payload["pre_dispatch_refusal_code"] = foreign[0]
    _refuses(payload)


# ---------------------------------------------------------------------------
# T -- the three exact modes, checked as a whole triple
# ---------------------------------------------------------------------------


def _post_dispatch(step: str, dispatch_state: str = "SEND_STATE_INDETERMINATE", **extra) -> dict:
    from pi_harness_cfg1 import obs1

    if step == "L18":
        # L19 never ran: no wait outcome and no activity observation.
        extra = {
            **obs1.unavailable_activity_fields(None),
            "runtime_wait_outcome": "NOT_OBSERVED",
            "stop_reasons_available": False,
            **extra,
        }
    return _v2(unexpected_failure_step=step, dispatch_state=dispatch_state, **extra)


def test_t_every_mode_validates_and_no_mixture_does():
    # NO_DISPATCH_FAILURE: all three absent (the case R2 wrongly rejected).
    _require_valid_cfg1_run_payload_v2(_v2())
    # POST_DISPATCH_UNEXPECTED at each admissible step.
    for step in ("L18", "L19", "L20"):
        payload = _post_dispatch(step)
        _require_valid_cfg1_run_payload_v2(payload)
        assert payload["run_classification"] == "INDETERMINATE_DISPATCH"
    _require_valid_cfg1_run_payload_v2(_post_dispatch("L20", dispatch_state="CONFIRMED_SENT"))
    # Two families at once.
    mixed = _refused_at("L9", "CONFIG_GENERATION_FAILED")
    mixed["unexpected_failure_step"] = "L18"
    _refuses(mixed, "REFUSAL_AND_POST_DISPATCH_UNEXPECTED_TOGETHER")
    # Outside the closed domain (a closure-phase step is NOT folded in).
    for step in ("L17", "L21", "L27"):
        payload = _post_dispatch("L19")
        payload["unexpected_failure_step"] = step
        _refuses(payload, "BAD_ENUM_UNEXPECTED_FAILURE_STEP")
    # POST mode is genuinely post-dispatch: never with NOT_ATTEMPTED.
    no_dispatch = _v2(unexpected_failure_step="L19", dispatch_state="NOT_ATTEMPTED", prompt_writes=0)
    _refuses(no_dispatch)


# ---------------------------------------------------------------------------
# W -- the workspace mint state and the v2 closure predicate
# ---------------------------------------------------------------------------


def test_w_the_v2_closure_predicate_conditions_only_the_workspace_conjunct():
    base = happy_observations()
    for state, facts, expected in (
        ("NOT_ATTEMPTED", (False, False, 0), (True, ())),
        ("ATTEMPTED_NO_AUTHORITY", (False, False, 0), (False, ("L27",))),
        ("ATTEMPTED_NO_AUTHORITY", (True, True, 0), (False, ("L27",))),
        ("AUTHORITY_RETURNED", (True, True, 0), (True, ())),
        ("AUTHORITY_RETURNED", (False, True, 0), (False, ("L27",))),
        ("AUTHORITY_RETURNED", (True, True, 3), (False, ("L27",))),
        ("SOMETHING_ELSE", (True, True, 0), (False, ("L27",))),
        (None, (True, True, 0), (False, ("L27",))),
    ):
        facts_map = dict(base)
        facts_map["workspace_mint_state"] = state
        (
            facts_map["workspace_authority_reproved"],
            facts_map["workspace_removed_verified"],
            facts_map["workspace_residual_file_count"],
        ) = facts
        assert compute_lifecycle_closure_v2(facts_map) == expected, state
    assert lifecycle.WORKSPACE_MINT_STATES == {
        "NOT_ATTEMPTED",
        "ATTEMPTED_NO_AUTHORITY",
        "AUTHORITY_RETURNED",
    }


def test_w_the_mint_state_is_bound_to_the_step_in_both_directions():
    # NOT_ATTEMPTED past L1
    forged = _refused_at("L2", "WORKSPACE_BASELINE_FAILED")
    forged["workspace_mint_state"] = "NOT_ATTEMPTED"
    forged["workspace_authority_reproved"] = False
    forged["workspace_removed_verified"] = False
    _refuses(forged, "WORKSPACE_MINT_STATE_DISAGREES_WITH_L1")
    # L1 with a returned authority
    forged = _l1(failure=None, seam=True)
    forged["workspace_mint_state"] = "AUTHORITY_RETURNED"
    _refuses(forged, "WORKSPACE_MINT_STATE_DISAGREES_WITH_L1")
    # NOT_ATTEMPTED carrying a resource-creation fact
    for key in ("runtime_created", "broker_resource_created", "git_observation_1_performed",
                "workspace_authority_reproved"):
        forged = _l1(failure="PI_SEAM_UNPROVEN", seam=False)
        forged[key] = True
        with pytest.raises(Cfg1RecordValidationError):
            _require_valid_cfg1_run_payload_v2(forged)
    # A partial mint anywhere but L2, and a partial mint that claims closure
    partial = _refused_at(
        "L3", "WORKSPACE_BASELINE_FAILED",
        workspace_mint_state="ATTEMPTED_NO_AUTHORITY",
        workspace_authority_reproved=False,
        workspace_removed_verified=False,
    )
    _refuses(partial, "PARTIAL_MINT_OUTSIDE_L2")
    genuine_partial = _refused_at(
        "L2", "WORKSPACE_BASELINE_FAILED",
        workspace_mint_state="ATTEMPTED_NO_AUTHORITY",
        workspace_authority_reproved=False,
        workspace_removed_verified=False,
    )
    _require_valid_cfg1_run_payload_v2(genuine_partial)
    assert genuine_partial["lifecycle_failure_steps"] == ["L27"]
    assert genuine_partial["run_classification"] == "INDETERMINATE_LIFECYCLE"


# ---------------------------------------------------------------------------
# N -- v1 compatibility: archived meaning, validator and closure UNCHANGED
# ---------------------------------------------------------------------------

#: SHA-256 of each v1 function's source text as shipped (``bfae384`` lineage,
#: verified identical to HEAD by the FU1 implementation turn). A change to any
#: of them changes what an archived v1 artifact means.
_FROZEN_V1_SOURCES = {
    ("records", "_require_valid_cfg1_run_payload"): (
        "cc69495df8939b8ab059971cffdc65cbcacfcc73d3a05eee469c0e2269c5e347"
    ),
    ("records", "_require_valid_cfg1_refusal_payload"): (
        "6bfd2a5affb5ffca3619422e634673bf3f5dc3d71818c045f077af2bca88d74b"
    ),
    ("records", "_require_activity_family_consistency"): (
        "3831bf2ff092ff2b57c2e226ab38601682e836aa89e201aaabb3f8e8eb372fe7"
    ),
    ("lifecycle", "compute_lifecycle_closure"): (
        "142d3e7e9ceac514058aac03753ae38fdd207b6ebe0bd7f1aaae4cef6249560c"
    ),
}


@pytest.mark.parametrize("module,name", sorted(_FROZEN_V1_SOURCES))
def test_n_the_v1_validator_and_closure_sources_are_byte_for_byte_unchanged(module, name):
    source = (_PACKAGE_DIR / f"{module}.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert hashlib.sha256(segment.encode("utf-8")).hexdigest() == (
                _FROZEN_V1_SOURCES[(module, name)]
            )
            return
    raise AssertionError(f"{module}.{name} is missing")


def test_n_v1_payloads_validate_and_close_exactly_as_before():
    happy = v1_run_payload()
    _require_valid_cfg1_run_payload(happy)
    assert compute_lifecycle_closure(happy) == (True, ())
    a3 = a3_shaped_v1_payload()
    _require_valid_cfg1_run_payload(a3)
    # A3's truthful v1 output: an L1 refusal whose closure v1 cannot prove.
    assert compute_lifecycle_closure(a3) == (False, ("L27",))
    assert a3["run_classification"] == "INDETERMINATE_LIFECYCLE"
    assert a3["pi_observed_version"] == "0.87.0"  # v1 meaning, never re-read
    # v1 keeps refusing exactly what it refused.
    tampered = dict(a3)
    tampered["lifecycle_failure_steps"] = []
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(tampered)
    assert excinfo.value.reason_code == "LIFECYCLE_FAILURE_STEPS_DISAGREE_WITH_COMPONENTS"
    bad_version = dict(happy)
    bad_version["pi_observed_version"] = "not-a-version"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(bad_version)
    assert excinfo.value.reason_code == "BAD_PI_OBSERVED_VERSION"


def test_n_neither_version_is_ever_routed_through_the_other():
    a3 = a3_shaped_v1_payload()
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_run_payload_v2(a3)
    with pytest.raises(Cfg1RecordValidationError):
        _require_valid_cfg1_run_payload(_v2())
    dispatch = records._RUN_PATH_DISCRIMINATORS
    kind = "harness configuration diagnostic run"
    assert dispatch[("pi-harness-cfg1-run.v1", kind)] is _require_valid_cfg1_run_payload
    assert dispatch[("pi-harness-cfg1-run.v2", kind)] is _require_valid_cfg1_run_payload_v2
    assert "pi_observed_version" in records.CFG1_RUN_RECORD_KEYS
    assert "pi_observed_version" not in records.CFG1_RUN_RECORD_KEYS_V2
    assert "UNEXPECTED_STEP_FAILURE" not in records.PRE_DISPATCH_REFUSAL_CODES
    assert records.REFUSABLE_RECORD_KINDS == {"pi-harness-cfg1-run.v1"}


def test_n_an_archived_v1_artifact_still_verifies_at_its_genuine_path(make_authority):
    authority = make_authority("S1-X1")
    for payload in (v1_run_payload(), a3_shaped_v1_payload()):
        path = Path(authority.execution_directory, "S1_01_Q.json")
        if path.exists():
            path.unlink()
        path.write_bytes(writers._serialize_artifact(writers._canonicalize(payload)))
        assert binding.verify_cfg1_run_artifact_binding(str(path)) is True
    # ...and a v2 artifact verifies there too, through ITS validator.
    path.unlink()
    path.write_bytes(writers._serialize_artifact(writers._canonicalize(_v2())))
    assert binding.verify_cfg1_run_artifact_binding(str(path)) is True
