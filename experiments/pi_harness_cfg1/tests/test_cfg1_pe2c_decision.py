"""PE-2c (R1, B11): decision authentication of the three stage profile facts.

PE-1 (``PHASE_5F3B_PI_HARNESS_PROFILE_EVOLUTION_PE1_AMENDMENT.md``) Sec. 20.3,
rows C-19 .. C-23. One provenance chain, never paralleled:

    runner-local ledgers -> nested terminal sealer -> _DecisionMintRecord
      -> CFG1StageClosureDecision -> _verify_sealed_decision
      -> emit_cfg1_stage_closure(authority, /, *, decision)

Every stage run is offline over a synthetic executor and a SYNTHETIC sealed
snapshot (a genuine PE-2b load of a synthetic chain).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest
from cfg1_builders import happy_observations, pre_dispatch_refusal_overrides, synthetic_run_executor
from cfg1_doubles import approve_profiles, build_synthetic_pi_tree, session_synthetic_pi_tree
from pe2a_support import synthetic_payload_files

from pi_harness_cfg1 import pi_profile_policy_loader as loader
from pi_harness_cfg1 import stage_decision, stage_runner, writers
from pi_harness_cfg1.stage_decision import (
    CFG1StageClosureDecision,
    Cfg1StageDecisionError,
    _DecisionMintRecord,
    _STAGE_DECISION_SEALED,
    _bound_fields,
    _verify_sealed_decision,
)
from pi_harness_cfg1.writers import Cfg1StageClosureEmissionResult, emit_cfg1_stage_closure

_CONFIRMED = Cfg1StageClosureEmissionResult(confirmed=True, phase_reached="EMISSION_CONFIRMED")


def with_live_decision(authority, callback, monkeypatch, *, executor=None):
    """Hand ``callback`` the LIVE sealed decision, while it is still registered."""
    captured: list = []

    def _stub(stub_authority, /, *, decision):
        captured.append(decision)
        outcome = callback(stub_authority, decision)
        return outcome if outcome is not None else _CONFIRMED

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _stub)
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=executor or synthetic_run_executor()
    )
    return result, captured


# ---------------------------------------------------------------------------
# C-21 -- the bound-field tuple, and both structures carry the three fields
# ---------------------------------------------------------------------------


def test_c21_bound_fields_are_the_frozen_six_followed_by_exactly_the_three():
    names = [field.name for field in dataclasses.fields(_DecisionMintRecord)]
    assert names == [
        "authority_mint_nonce",
        "stage_id",
        "stage_execution_id",
        "ordinal_status",
        "halted_after_ordinal",
        "halt_reason_code",
        "stage_pi_profile_id",
        "ordinal_pi_profile_binding",
        "pi_profile_attribution_halt",
    ]
    decision_names = [field.name for field in dataclasses.fields(CFG1StageClosureDecision)]
    assert decision_names == ["decision_nonce"] + names
    probe = type("Probe", (), {name: name for name in names})()
    assert _bound_fields(probe) == tuple(names)


def test_c21_a_registry_record_omitting_a_profile_field_cannot_be_built():
    with pytest.raises(TypeError):
        _DecisionMintRecord(
            authority_mint_nonce="n",
            stage_id="S1",
            stage_execution_id="S1-X1",
            ordinal_status=(),
            halted_after_ordinal=None,
            halt_reason_code=None,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage_pi_profile_id", "e" * 64),
        ("ordinal_pi_profile_binding", tuple((k, "NO_RUN_EVIDENCE") for k in range(1, 10))),
        ("pi_profile_attribution_halt", True),
    ],
)
def test_c21_a_registry_record_disagreeing_with_the_object_refuses(field, value, make_authority, monkeypatch):
    outcomes: list[str] = []

    def _callback(authority, decision):
        record = _STAGE_DECISION_SEALED[decision.decision_nonce]
        _STAGE_DECISION_SEALED[decision.decision_nonce] = dataclasses.replace(record, **{field: value})
        try:
            _verify_sealed_decision(decision, authority)
        except Cfg1StageDecisionError as exc:
            outcomes.append(exc.reason_code)
        # A FRESH construction against the disagreeing record refuses too.
        try:
            CFG1StageClosureDecision(**{f.name: getattr(decision, f.name) for f in dataclasses.fields(decision)})
        except Cfg1StageDecisionError as exc:
            outcomes.append(exc.reason_code)
        _STAGE_DECISION_SEALED[decision.decision_nonce] = record

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch)
    assert outcomes == ["DECISION_FIELD_MISMATCH", "DECISION_FIELD_MISMATCH"]


# ---------------------------------------------------------------------------
# C-19 / C-20 -- object.__setattr__ mutation of each new field, type-exact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,mutate",
    [
        ("stage_pi_profile_id", lambda value: "e" * 64),
        ("stage_pi_profile_id", lambda value: None),
        ("ordinal_pi_profile_binding", lambda value: tuple((k, "NO_PROFILE") for k, _v in value)),
        ("ordinal_pi_profile_binding", lambda value: tuple((True if k == 1 else k, v) for k, v in value)),
        ("ordinal_pi_profile_binding", lambda value: list(value)),
        ("pi_profile_attribution_halt", lambda value: 0),  # False -> 0
        ("pi_profile_attribution_halt", lambda value: True),
    ],
)
def test_c19_c20_a_mutated_genuine_decision_refuses_at_verification_and_at_the_writer(
    field, mutate, make_authority, monkeypatch
):
    outcomes: list[str] = []

    def _callback(authority, decision):
        original = getattr(decision, field)
        object.__setattr__(decision, field, mutate(original))
        try:
            _verify_sealed_decision(decision, authority)
        except Cfg1StageDecisionError as exc:
            outcomes.append(exc.reason_code)
        try:
            emit_cfg1_stage_closure(authority, decision=decision)
        except Cfg1StageDecisionError as exc:
            outcomes.append(exc.reason_code)
        object.__setattr__(decision, field, original)

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch)
    assert outcomes == ["DECISION_FIELD_MISMATCH", "DECISION_FIELD_MISMATCH"]


def test_c20_true_never_stands_in_for_one_and_one_never_for_true(make_authority, monkeypatch):
    """The halted case: attribution True mutated to 1, and an ordinal int to a bool."""

    def _for(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        observations = happy_observations(runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id])
        if admission.run_ordinal == 1:
            observations["pi_profile_post_runtime_reobservation"] = "CHANGED"
        return observations

    outcomes: list[str] = []

    def _callback(authority, decision):
        assert decision.pi_profile_attribution_halt is True
        for field, value in (
            ("pi_profile_attribution_halt", 1),
            ("halted_after_ordinal", True),
            ("ordinal_status", tuple((True if k == 1 else k, v) for k, v in decision.ordinal_status)),
        ):
            original = getattr(decision, field)
            object.__setattr__(decision, field, value)
            try:
                _verify_sealed_decision(decision, authority)
            except Cfg1StageDecisionError as exc:
                outcomes.append(exc.reason_code)
            object.__setattr__(decision, field, original)

    with_live_decision(
        make_authority("S1-X1"), _callback, monkeypatch, executor=synthetic_run_executor(observations_for=_for)
    )
    assert outcomes == ["DECISION_FIELD_MISMATCH"] * 3


# ---------------------------------------------------------------------------
# The sealer: computed binding, refusal before step 3, no module-level sealer
# ---------------------------------------------------------------------------


def test_the_sealer_refuses_a_malformed_attribution_flag_before_the_history_step(make_authority, monkeypatch):
    """The nested sealer's own refusals, reached through the test-only probe:
    the probe's forced second reach uses ``pi_profile_attribution_halt=False``,
    and a direct AST check proves the two pre-step-3 refusals exist."""
    import ast

    source = Path(stage_runner.__file__).read_text(encoding="utf-8")
    seal = source.split("def _seal_terminal_decision(")[1].split("def _force_second_seal_reach")[0]
    refusal_at = seal.index("MALFORMED_PI_PROFILE_ATTRIBUTION_HALT")
    without_halt_at = seal.index("PI_PROFILE_ATTRIBUTION_HALT_WITHOUT_HALT")
    history_at = seal.index("_STAGE_TERMINAL_SEAL_HISTORY.add(")
    assert refusal_at < history_at and without_halt_at < history_at
    tree = ast.parse(source)
    module_functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "_seal_terminal_decision" not in module_functions


def test_the_binding_is_computed_from_the_ledgers_for_every_declared_ordinal(make_authority, monkeypatch):
    def _for(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE

        if admission.run_ordinal == 4:
            return happy_observations(
                **pre_dispatch_refusal_overrides("ROUTE_UNAVAILABLE", "L7"),
                runtime_created=False,
                runtime_exit_observed=False,
                runtime_transport_eof_observed=False,
                pi_profile_post_runtime_reobservation="NOT_APPLICABLE",
                runtime_reported_compat_shape="NOT_OBSERVED",
                runtime_reported_model_reasoning="NOT_OBSERVED",
                runtime_reported_thinking_level="NOT_OBSERVED",
                manipulation_check_agrees=False,
                h1_extension_identity_matched=False,
                h2_provider_model_identity_matched=False,
                broker_reached_ready=False,
                broker_resource_created=False,
                broker_state_closed=False,
                broker_pending_unreaped_zero=False,
                broker_worker_terminated_or_absent=False,
            )
        return happy_observations(runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id])

    captured: list = []

    def _callback(authority, decision):
        captured.append(decision)

    with_live_decision(
        make_authority("S1-X1"), _callback, monkeypatch, executor=synthetic_run_executor(observations_for=_for)
    )
    decision = captured[0]
    assert decision.halted_after_ordinal == 4
    assert decision.stage_pi_profile_id == session_synthetic_pi_tree().profile_id
    assert dict(decision.ordinal_pi_profile_binding) == {
        1: "STAGE_PROFILE",
        2: "STAGE_PROFILE",
        3: "STAGE_PROFILE",
        4: "STAGE_PROFILE",  # refused past L1: its record still binds the profile
        **{k: "NOT_EXECUTED" for k in range(5, 10)},
    }
    assert decision.pi_profile_attribution_halt is False


# ---------------------------------------------------------------------------
# C-22 -- the writer surface: (authority, /, *, decision), nothing else
# ---------------------------------------------------------------------------


def test_c22_the_writer_signature_is_exactly_authority_positional_then_decision():
    signature = inspect.signature(emit_cfg1_stage_closure)
    parameters = list(signature.parameters.values())
    assert [(p.name, p.kind) for p in parameters] == [
        ("authority", inspect.Parameter.POSITIONAL_ONLY),
        ("decision", inspect.Parameter.KEYWORD_ONLY),
    ]
    assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters)


@pytest.mark.parametrize(
    "kwarg",
    ["profile_id", "ordinal_profile_binding", "profile_attribution_halt", "aps_head", "payload", "declared_version", "binding"],
)
def test_c22_no_caller_selected_profile_fact_can_reach_the_writer(kwarg, make_authority, monkeypatch):
    raised: list[type] = []

    def _callback(authority, decision):
        try:
            emit_cfg1_stage_closure(authority, decision=decision, **{kwarg: "a" * 64})
        except TypeError:
            raised.append(TypeError)

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch)
    assert raised == [TypeError]


def test_c22_the_canonical_payload_comes_only_from_the_decision_and_the_snapshot(make_authority):
    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is True
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    tree = session_synthetic_pi_tree()
    assert closure["record_version"] == "pi-harness-cfg1-stage-closure.v3"
    assert closure["pi_profile_set_head_sha256"] == loader.SEALED_POLICY_SNAPSHOT.aps_head_sha256
    assert closure["stage_pi_profile_id"] == tree.profile_id
    assert closure["stage_pi_profile_declared_package_version"] == tree.declared_package_version
    assert closure["pi_profile_authority_scope"] == "PI_PACKAGE_PAYLOAD_AND_DECLARED_RESOLUTION_BOUNDARY"
    assert closure["pi_external_runtime_residual"] == "NOT_IDENTIFIED_BY_PROFILE"


# ---------------------------------------------------------------------------
# C-23 -- ordering, the unknown-profile PRE_CREATE refusal, design B
# ---------------------------------------------------------------------------


def test_c23_the_payload_is_built_only_after_every_verification_and_revocation(make_authority, monkeypatch):
    order: list[str] = []

    def _wrap(module, name, label):
        real = getattr(module, name)

        def _wrapped(*args, **kwargs):
            order.append(label)
            return real(*args, **kwargs)

        monkeypatch.setattr(module, name, _wrapped)

    _wrap(writers, "verify_stage_output_authority", "authority")
    _wrap(stage_decision, "_verify_sealed_decision", "verify_sealed")
    _wrap(stage_decision, "_revoke_decision_consumability", "revoke")
    _wrap(writers, "_build_stage_closure_payload", "build")
    _wrap(writers, "_serialize_artifact", "bytes")
    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is True
    closure_order = order[order.index("verify_sealed") - 1 :]
    assert closure_order[:5] == ["authority", "verify_sealed", "revoke", "build", "bytes"]


def test_c23_the_exact_type_gate_refuses_before_any_payload_is_built(make_authority, monkeypatch):
    built: list[int] = []
    monkeypatch.setattr(writers, "_build_stage_closure_payload", lambda *a, **k: built.append(1))

    class _LooksLikeADecision:
        stage_pi_profile_id = "a" * 64

    with pytest.raises(writers.Cfg1WriterError):
        emit_cfg1_stage_closure(make_authority("S1-X1"), decision=_LooksLikeADecision())
    assert built == []


def test_c23_an_unknown_stage_profile_in_the_snapshot_is_a_pre_create_failure(tmp_path, make_authority, monkeypatch):
    """The sealed stage profile is not an eligible runtime profile of the
    module-level snapshot at write time: step 5 refuses and the write resolves
    as the existing PRE_CREATE failure -- no fallback, no file."""
    files, empty_dirs = synthetic_payload_files()
    files = dict(files, **{"dist/other.js": b"export const other = 404;\n"})
    other = build_synthetic_pi_tree(str(tmp_path / "other"), files, empty_dirs)
    real_writer = stage_runner.emit_cfg1_stage_closure

    def _swap_then_write(authority, /, *, decision):
        approve_profiles(monkeypatch, other)  # the stage profile is no longer eligible
        return real_writer(authority, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _swap_then_write)
    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert "STAGE_CLOSURE_PRE_CREATE_FAILED" in result.console_codes
    assert not Path(authority.execution_directory, "S1_stage_closure.json").exists()


def test_c23_the_declared_version_is_null_iff_the_sealed_stage_profile_is_null(make_authority):
    def _l1_refusal(admission):
        return happy_observations(
            **pre_dispatch_refusal_overrides("OFFLINE_PREFLIGHT_FAILED", "L1"),
            pi_identity_failure_code="PI_PROFILE_UNAPPROVED",
            pi_payload_observation_complete=True,
            pi_profile_id=None,
            pi_profile_declared_package_version=None,
            pi_profile_post_runtime_reobservation="NOT_APPLICABLE",
            runtime_created=False,
            runtime_exit_observed=False,
            runtime_transport_eof_observed=False,
            broker_reached_ready=False,
            broker_resource_created=False,
            broker_state_closed=False,
            broker_pending_unreaped_zero=False,
            broker_worker_terminated_or_absent=False,
            workspace_mint_state="NOT_ATTEMPTED",
            workspace_authority_reproved=False,
            workspace_removed_verified=False,
            git_observation_1_performed=False,
            runtime_reported_compat_shape="NOT_OBSERVED",
            runtime_reported_model_reasoning="NOT_OBSERVED",
            runtime_reported_thinking_level="NOT_OBSERVED",
            manipulation_check_agrees=False,
            h1_extension_identity_matched=False,
            h2_provider_model_identity_matched=False,
            base_url_compat_detection_clear=False,
            route_reachable=False,
            route_configured_model_served=False,
        )

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(observations_for=_l1_refusal)
    )
    assert result.halted_after_ordinal == 1
    assert result.stage_closure_confirmed is True
    closure = json.loads(Path(authority.execution_directory, "S1_stage_closure.json").read_text(encoding="utf-8"))
    assert closure["stage_pi_profile_id"] is None
    assert closure["stage_pi_profile_declared_package_version"] is None
    assert closure["ordinal_pi_profile_binding"]["1"] == "NO_PROFILE"
