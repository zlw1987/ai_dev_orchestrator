"""T-102 - T-110, T-124 - T-141: the terminal decision's issuance boundary.

The property this whole file exists to prove: **no supported caller holding
only a genuine, ACTIVE ``CFG1StageOutputAuthority`` has any name, attribute
path, or object-graph edge leading to the sealing step.** That is strictly
stronger than "there happens to be one call site": a single call site is a fact
about how correct code behaves; no reachable name is a fact about what code
holding only an authority is CAPABLE of, regardless of intent.

The harness reaches genuine, live decisions the only way anything can -- by
standing in for the one writer the stage runner calls, from inside that
runner's own invocation. After the invocation returns, the bounded cleanup has
removed both registry facts, exactly as T-136 and T-139 require, so a live
decision simply does not exist to be tested from outside.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from cfg1_builders import (
    happy_observations,
    pre_dispatch_refusal_overrides,
    synthetic_run_executor,
)

from pi_harness_cfg1 import stage_decision, stage_runner, writers
from pi_harness_cfg1.stage_decision import (
    CFG1StageClosureDecision,
    Cfg1StageDecisionError,
    _STAGE_DECISION_SEALED,
    _STAGE_TERMINAL_SEAL_HISTORY,
)
from pi_harness_cfg1.stage_output import (
    CFG1StageOutputAuthority,
    stage_output_authority_is_active,
)
from pi_harness_cfg1.writers import (
    Cfg1StageClosureEmissionResult,
    Cfg1WriterError,
    emit_cfg1_stage_closure,
)

_CONFIRMED = Cfg1StageClosureEmissionResult(
    confirmed=True, phase_reached="EMISSION_CONFIRMED"
)


def with_live_decision(authority, callback, *, executor=None, monkeypatch=None):
    """Drive a genuine stage run and hand ``callback`` the LIVE sealed decision.

    Stands in for the one writer the stage runner calls, so the callback runs
    while the decision is still registered and the runner frame is still alive.
    There is no way to obtain one afterwards, and that is the point.
    """
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
# T-102 -- the positive control, and the exact decision type gate
# ---------------------------------------------------------------------------


def test_t102_a_genuine_sealed_decision_produces_a_valid_written_closure(make_authority):
    from pi_harness_cfg1.binding import verify_cfg1_stage_closure_binding

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=synthetic_run_executor())
    assert result.disposition == "STAGE_COMPLETED"
    assert result.stage_closure_confirmed is True
    closure_path = Path(authority.execution_directory, "S1_stage_closure.json")
    assert verify_cfg1_stage_closure_binding(str(closure_path)) is True


class _LooksLikeADecision:
    """Same attribute names, same ``__class__.__name__``. Not the same type."""

    __name__ = "CFG1StageClosureDecision"

    def __init__(self) -> None:
        self.reads: list[str] = []

    def __getattr__(self, name):
        self.reads.append(name)
        raise AttributeError(name)


_LooksLikeADecision.__qualname__ = "CFG1StageClosureDecision"


def test_t102_the_decision_type_gate_is_exact_and_reads_zero_fields(make_authority):
    authority = make_authority("S1-X1")
    lookalike = _LooksLikeADecision()
    with pytest.raises(Cfg1WriterError) as excinfo:
        emit_cfg1_stage_closure(authority, decision=lookalike)
    assert excinfo.value.reason_code == "NOT_A_STAGE_CLOSURE_DECISION"
    assert lookalike.reads == []

    for impostor in (
        None,
        {
            "stage_id": "S1",
            "stage_execution_id": "S1-X1",
            "ordinal_status": (),
            "halted_after_ordinal": None,
            "halt_reason_code": None,
        },
        object(),
    ):
        with pytest.raises(Cfg1WriterError) as excinfo:
            emit_cfg1_stage_closure(authority, decision=impostor)
        assert excinfo.value.reason_code == "NOT_A_STAGE_CLOSURE_DECISION"


# ---------------------------------------------------------------------------
# T-103 -- a directly constructed or forged decision, with zero I/O
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nonce", ["", "not-registered", "0" * 32, "deadbeef" * 4, "S1-X1"]
)
def test_t103_direct_construction_with_an_unregistered_nonce_is_refused(
    nonce, make_authority, filesystem_spy
):
    authority = make_authority("S1-X1")
    # The mint itself legitimately creates the execution directory, so the
    # zero-I/O claim is measured from AFTER it -- exactly the calls the refused
    # construction would have to make, and does not.
    baseline = filesystem_spy.total_mutations
    with pytest.raises(Cfg1StageDecisionError) as excinfo:
        CFG1StageClosureDecision(
            decision_nonce=nonce,
            authority_mint_nonce=authority.mint_nonce,
            stage_id="S1",
            stage_execution_id="S1-X1",
            ordinal_status=tuple((k, "RECORD_EMITTED") for k in range(1, 10)),
            halted_after_ordinal=None,
            halt_reason_code=None,
        )
    assert excinfo.value.reason_code == "UNKNOWN_DECISION_NONCE"
    assert filesystem_spy.total_mutations == baseline


# ---------------------------------------------------------------------------
# T-104 / T-105 -- mutation and rebinding, caught at the writer's own re-proof
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name,new_value",
    [
        ("ordinal_status", ()),
        ("halted_after_ordinal", 3),
        ("halt_reason_code", "PRE_DISPATCH_REFUSAL"),
        ("stage_id", "S2"),
        ("stage_execution_id", "S1-X9"),
    ],
)
def test_t104_a_mutated_genuine_decision_is_refused_at_the_next_consumption(
    field_name, new_value, make_authority, monkeypatch
):
    seen: list = []

    def _callback(authority, decision):
        object.__setattr__(decision, field_name, new_value)
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority, decision=decision)
        assert excinfo.value.reason_code == "DECISION_FIELD_MISMATCH"
        seen.append(field_name)
        return None

    authority = make_authority("S1-X1")
    with_live_decision(authority, _callback, monkeypatch=monkeypatch)
    assert seen == [field_name]


def test_t105_a_genuine_decision_cannot_be_rebound_to_another_genuine_authority(
    make_authority, monkeypatch
):
    seen: list = []

    def _callback(authority_a, decision):
        authority_b = make_authority("S1-X2")
        assert stage_output_authority_is_active(authority_b) is True
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority_b, decision=decision)
        assert excinfo.value.reason_code == "DECISION_AUTHORITY_MISMATCH"
        assert not Path(
            authority_b.execution_directory, "S1_stage_closure.json"
        ).exists()
        seen.append(True)
        return None

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    assert seen == [True]


# ---------------------------------------------------------------------------
# T-106 -- sealing cannot precede the ordinal's own L29 result
# ---------------------------------------------------------------------------


def test_t106_the_sealing_step_is_never_reached_before_l29_is_in_the_ledger():
    """A source-level/statement-ordering proof over the runner's own routine.

    Mirrors T-101's technique, applied to a lexically-scoped step rather than a
    call to a separately-nameable function -- because FU10 removed the latter.
    """
    source = inspect.getsource(stage_runner._run_cfg1_stage_with_injected_executor)

    record_at = source.index("_record_ordinal_result(run_ordinal, emission.emission_status)")
    l30_at = source.index('_fire("l30:enter"')
    terminate_at = source.index("return _terminate(")
    assert record_at < l30_at < terminate_at

    # And the sealing step itself re-checks the ledger before doing anything.
    seal_body = source.split("def _seal_terminal_decision(")[1].split("def _force_second")[0]
    guard_at = seal_body.index("current_ordinal not in _ordinal_ledger")
    history_at = seal_body.index("_terminal_seal_recorded")
    assert guard_at < history_at


# ---------------------------------------------------------------------------
# T-107 -- L30 cardinality, branch B's non-sealing, and the seal-once backstop
# ---------------------------------------------------------------------------


def test_t107_l30_runs_once_per_admitted_ordinal_and_only_terminal_ones_seal(
    make_authority, monkeypatch
):
    l30_ordinals: list[int] = []
    registry_snapshots: list[tuple[int, int]] = []
    closure_calls: list = []

    real_closure = stage_runner.emit_cfg1_stage_closure

    def _counting_closure(authority, /, *, decision):
        closure_calls.append(decision)
        return real_closure(authority, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _counting_closure)

    def _probe(context):
        if context.event == "l30:enter":
            l30_ordinals.append(context.run_ordinal)
            # (2) Before the terminal branch is selected for the final ordinal,
            # NEITHER registry has gained anything.
            registry_snapshots.append(
                (len(_STAGE_DECISION_SEALED), len(_STAGE_TERMINAL_SEAL_HISTORY))
            )

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )

    # (1) L30 runs once per ADMITTED ORDINAL -- nine times, not once.
    assert l30_ordinals == list(range(1, 10))
    assert len(l30_ordinals) > 1
    # (2) Every branch-B evaluation left both registries untouched.
    assert registry_snapshots == [(0, 0)] * 9
    # Exactly one closure, from exactly one sealed decision.
    assert len(closure_calls) == 1
    assert result.disposition == "STAGE_COMPLETED"


def test_t107a_a_second_seal_before_any_consumption_is_refused(
    make_authority, monkeypatch
):
    reports: list[dict] = []

    def _probe(context):
        if context.event == "seal:after":
            reports.append(context.force_second_seal_reach())

    authority = make_authority("S1-X1")
    stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert len(reports) == 1
    assert reports[0]["refused_by"] == "seal_history"
    assert reports[0]["second_decision_registered"] is False
    assert reports[0]["seal_history_present"] is True


def test_t107b_a_second_seal_after_consumption_revocation_is_refused_identically(
    make_authority, monkeypatch
):
    """The regression FU11 lacked, and the one FU11's mechanism would have failed.

    By this point the consumed decision's own ``_STAGE_DECISION_SEALED`` entry
    has been revoked, so a seal-once proof resting on THAT registry would find
    it empty and happily mint a second decision. Refusal must come from the
    independent seal-history fact instead -- and it does.
    """
    reports: list[dict] = []
    decision_registry_sizes: list[int] = []

    def _probe(context):
        # Immediately after the one permitted write, and BEFORE the authority is
        # retired -- the exact point at which the only thing that can still
        # refuse a second seal is the independent seal-history fact.
        if context.event == "closure:after_write":
            decision_registry_sizes.append(len(_STAGE_DECISION_SEALED))
            reports.append(context.force_second_seal_reach())

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert result.stage_closure_confirmed is True
    # The decision registry holds NO trace of the consumed decision...
    assert decision_registry_sizes == [0]
    # ...and the second reach is refused anyway.
    assert reports[0]["refused_by"] == "seal_history"
    assert reports[0]["second_decision_registered"] is False
    assert reports[0]["seal_history_present"] is True


# ---------------------------------------------------------------------------
# T-109 / T-110 -- the written bytes, and every avenue to alternate facts
# ---------------------------------------------------------------------------


def test_t109_the_written_closure_bytes_are_exactly_the_sealed_decision(
    make_authority, monkeypatch
):
    captured: list = []

    def _callback(authority, decision):
        captured.append(decision)
        return writers.emit_cfg1_stage_closure(authority, decision=decision)

    authority = make_authority("S1-X1")
    with_live_decision(authority, _callback, monkeypatch=monkeypatch)

    decision = captured[0]
    written = json.loads(
        Path(authority.execution_directory, "S1_stage_closure.json").read_text(
            encoding="utf-8"
        )
    )
    # Field for field, with no transformation, substitution, or default-value
    # fallback. The decimal-string keys are JSON's own required key form for the
    # decision's ``(ordinal, status)`` pairs -- the same data, never stored twice.
    assert written["ordinal_status"] == {
        str(ordinal): status for ordinal, status in decision.ordinal_status
    }
    assert written["halted_after_ordinal"] == decision.halted_after_ordinal
    assert written["halt_reason_code"] == decision.halt_reason_code
    assert written["stage_id"] == decision.stage_id
    assert written["stage_execution_id"] == decision.stage_execution_id


def test_t110_no_avenue_yields_an_alternate_fact_closure_record(
    make_authority, monkeypatch
):
    """Every avenue reduces to one of T-102 - T-105, or does not exist at all."""
    attempts: list[str] = []

    def _callback(authority, decision):
        alternate_status = tuple((k, "EVIDENCE_REFUSED") for k in range(1, 10))

        # (1) Direct construction of an alternate-fact decision.
        with pytest.raises(Cfg1StageDecisionError):
            CFG1StageClosureDecision(
                decision_nonce="forged",
                authority_mint_nonce=authority.mint_nonce,
                stage_id="S1",
                stage_execution_id=authority.stage_execution_id,
                ordinal_status=alternate_status,
                halted_after_ordinal=4,
                halt_reason_code="PRE_DISPATCH_REFUSAL",
            )
        attempts.append("direct_construction")

        # (2) A mutated copy of the genuine object.
        object.__setattr__(decision, "ordinal_status", alternate_status)
        with pytest.raises(Cfg1StageDecisionError):
            writers.emit_cfg1_stage_closure(authority, decision=decision)
        object.__setattr__(
            decision,
            "ordinal_status",
            tuple((k, "RECORD_EMITTED") for k in range(1, 10)),
        )
        attempts.append("mutated_copy")

        # (3) A hand-rolled object exposing the same attribute names.
        with pytest.raises(Cfg1WriterError):
            writers.emit_cfg1_stage_closure(authority, decision=_LooksLikeADecision())
        attempts.append("hand_rolled")

        # (4) Every enumerable module-level callable reachable while holding
        # only the genuine authority -- proven absent by T-124 itself.
        assert _reachable_decision_issuers(authority) == []
        attempts.append("reachable_callables")
        return None

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    assert attempts == [
        "direct_construction",
        "mutated_copy",
        "hand_rolled",
        "reachable_callables",
    ]


# ---------------------------------------------------------------------------
# T-124 / T-125 -- the required adversarial proof, in its strongest form
# ---------------------------------------------------------------------------


def _cfg1_modules():
    import importlib
    import pkgutil

    import pi_harness_cfg1

    modules = [pi_harness_cfg1]
    for info in pkgutil.iter_modules(pi_harness_cfg1.__path__):
        modules.append(importlib.import_module(f"pi_harness_cfg1.{info.name}"))
    return modules


_DECISION_FACT_PARAMETERS = frozenset(
    {"ordinal_status", "halted_after_ordinal", "halt_reason_code"}
)


def _reachable_decision_issuers(authority) -> list[str]:
    """Every module-level FUNCTION that could plausibly ISSUE a decision.

    Classes are swept separately, below, rather than here. A frozen value type
    whose constructor names its own fields --
    :class:`~pi_harness_cfg1.stage_decision.CFG1StageClosureDecision` itself,
    its private registry record, and the console-facing
    :class:`~pi_harness_cfg1.stage_runner.Cfg1StageResult` -- is not an issuer,
    and the design's own T-103 REQUIRES the decision constructor to exist and be
    callable so that its refusal can be proven. What matters is that no class
    can be turned into a genuine decision, which
    :func:`test_t124_no_value_type_constructor_yields_a_genuine_decision`
    proves directly.
    """
    offenders: list[str] = []
    for module in _cfg1_modules():
        for name, value in inspect.getmembers(module, inspect.isfunction):
            try:
                parameters = frozenset(inspect.signature(value).parameters)
            except (TypeError, ValueError):
                continue
            if parameters & _DECISION_FACT_PARAMETERS:
                offenders.append(f"{module.__name__}.{name}")
    return sorted(set(offenders))


def test_t124_no_value_type_constructor_yields_a_genuine_decision(make_authority):
    """Every module-level CLASS that names a decision fact, constructed directly.

    None of them produces an object satisfying
    ``type(x) is CFG1StageClosureDecision`` -- the decision type itself refuses
    without an already-registered nonce, and the others are simply different
    types that no writer accepts.
    """
    authority = make_authority("S1-X1")
    facts = {
        "ordinal_status": tuple((k, "RECORD_EMITTED") for k in range(1, 10)),
        "halted_after_ordinal": None,
        "halt_reason_code": None,
    }
    inspected: list[str] = []
    for module in _cfg1_modules():
        for name, value in inspect.getmembers(module, inspect.isclass):
            try:
                parameters = frozenset(inspect.signature(value).parameters)
            except (TypeError, ValueError):
                continue
            if not (parameters & _DECISION_FACT_PARAMETERS):
                continue
            inspected.append(f"{module.__name__}.{name}")
            kwargs = {k: v for k, v in facts.items() if k in parameters}
            for extra, extra_value in (
                ("decision_nonce", "forged"),
                ("authority_mint_nonce", authority.mint_nonce),
                ("stage_id", "S1"),
                ("stage_execution_id", "S1-X1"),
                ("record_filename", "S1_stage_closure.json"),
                ("disposition", "STAGE_COMPLETED"),
                ("ordinals_attempted", ()),
                ("stage_closure_confirmed", True),
            ):
                if extra in parameters:
                    kwargs[extra] = extra_value
            try:
                produced = value(**kwargs)
            except Exception:  # noqa: BLE001 - a refusal is the expected outcome
                continue
            assert type(produced) is not CFG1StageClosureDecision, name
    # The sweep found something to check -- it is not vacuously empty.
    assert inspected, "the class sweep matched nothing; the audit would be vacuous"


def test_t124_no_reachable_callable_accepts_decision_facts_or_returns_a_decision(
    make_authority,
):
    authority = make_authority("S1-X1")
    assert _reachable_decision_issuers(authority) == []

    # And no callable, given ONLY the authority, returns a genuine decision.
    produced: list[str] = []
    for module in _cfg1_modules():
        for name, value in inspect.getmembers(module):
            if not callable(value) or value is CFG1StageClosureDecision:
                continue
            try:
                parameters = inspect.signature(value).parameters
            except (TypeError, ValueError):
                continue
            required = [
                parameter
                for parameter in parameters.values()
                if parameter.default is inspect.Parameter.empty
                and parameter.kind
                in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
            ]
            if len(required) != 1:
                continue
            try:
                result = value(authority)
            except Exception:  # noqa: BLE001 - a refusal is the expected outcome
                continue
            if type(result) is CFG1StageClosureDecision:  # pragma: no cover - a defect
                produced.append(f"{module.__name__}.{name}")
    assert produced == []


def test_t124_nothing_reachable_from_the_authority_object_leads_to_the_sealer(
    make_authority,
):
    authority = make_authority("S1-X1")
    reachable = set(vars(authority)) | set(type(authority).__dict__)
    for name in reachable:
        value = getattr(authority, name, None)
        if not callable(value):
            continue
        try:
            parameters = frozenset(inspect.signature(value).parameters)
        except (TypeError, ValueError):
            continue
        assert not (parameters & _DECISION_FACT_PARAMETERS), name
    # The authority gains no field pointing at the runner's own nested step.
    assert set(CFG1StageOutputAuthority.__dataclass_fields__) == {
        "mint_nonce",
        "stage_id",
        "stage_execution_id",
        "results_root",
        "execution_directory",
    }


def test_t125_an_invented_ledger_or_tuple_cannot_reach_the_genuine_issuer(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")

    # (2) No supported API accepts, returns, or exposes the runner-local ledger.
    ledger_names = frozenset({"ledger", "ordinal_ledger", "stage_progress", "_ordinal_ledger"})
    for module in _cfg1_modules():
        for name, value in inspect.getmembers(module):
            if not callable(value):
                continue
            try:
                parameters = frozenset(inspect.signature(value).parameters)
            except (TypeError, ValueError):
                continue
            assert not (parameters & ledger_names), f"{module.__name__}.{name}"
    for name in set(vars(authority)) | set(type(authority).__dict__):
        assert name not in ledger_names

    # (3) The real terminal decision reflects only runner-recorded L29 entries,
    # never an invented tuple held in the same process at the same time.
    invented = tuple((k, "EVIDENCE_REFUSED") for k in range(1, 10))
    captured: list = []

    def _callback(_authority, decision):
        captured.append(decision.ordinal_status)
        return None

    with_live_decision(authority, _callback, monkeypatch=monkeypatch)
    assert captured[0] == tuple((k, "RECORD_EMITTED") for k in range(1, 10))
    assert captured[0] != invented


def test_t125_does_not_claim_registry_memory_is_tamper_proof():
    """Explicitly out of scope, per FU11's own threat-model note.

    ``_STAGE_DECISION_SEALED`` is an internal authenticity/revocation registry,
    not an issuance API. Defending against arbitrary same-user in-process memory
    manipulation is outside this design's threat model, and this suite does not
    pretend otherwise.
    """
    assert isinstance(_STAGE_DECISION_SEALED, dict)
    assert isinstance(_STAGE_TERMINAL_SEAL_HISTORY, set)


# ---------------------------------------------------------------------------
# T-126 - T-132 -- the three-way terminal transition
# ---------------------------------------------------------------------------


def test_t126_a_non_final_successful_ordinal_admits_without_sealing_anything(
    make_authority, monkeypatch
):
    closure_calls: list = []
    monkeypatch.setattr(
        stage_runner,
        "emit_cfg1_stage_closure",
        lambda authority, /, *, decision: closure_calls.append(decision) or _CONFIRMED,
    )
    sealed_at_branch_b: list[int] = []

    def _probe(context):
        if context.event == "l30:enter" and context.run_ordinal < 9:
            sealed_at_branch_b.append(len(_STAGE_DECISION_SEALED))

    authority = make_authority("S1-X1")
    stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert sealed_at_branch_b == [0] * 8
    assert len(closure_calls) == 1  # only the terminal ordinal sealed


@pytest.mark.parametrize(
    "stage_id,last_ordinal", [("S1", 9), ("S2", 6)], ids=["S1", "S2"]
)
def test_t127_and_t128_the_final_ordinal_succeeding_seals_success_and_issues_no_token(
    stage_id, last_ordinal, make_authority, monkeypatch
):
    admitted: list[int] = []
    sealed: list = []

    def _executor(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE
        from pi_harness_cfg1.run_contract import Cfg1RunOutcome
        from qualification.safety import ArtifactSafetyContext

        admitted.append(admission.run_ordinal)
        return Cfg1RunOutcome(
            observations=happy_observations(
                runtime_reported_compat_shape=ARM_SHAPE[admission.arm_id]
            ),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    real_closure = stage_runner.emit_cfg1_stage_closure

    def _capture(authority, /, *, decision):
        sealed.append(decision)
        return real_closure(authority, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _capture)

    authority = make_authority(f"{stage_id}-X1", stage_id=stage_id)
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=_executor)

    # (1) no admission token for LAST_ORDINAL + 1 was ever issued.
    assert admitted == list(range(1, last_ordinal + 1))
    assert last_ordinal + 1 not in admitted
    # (2) exactly ONE decision was sealed, with the success shape.
    assert len(sealed) == 1
    decision = sealed[0]
    assert [ordinal for ordinal, _ in decision.ordinal_status] == list(
        range(1, last_ordinal + 1)
    )
    assert decision.halted_after_ordinal is None
    assert decision.halt_reason_code is None
    # (3) the closure was emitted exactly once and is schema-valid on disk.
    from pi_harness_cfg1.records import _require_valid_cfg1_stage_closure_payload

    written = json.loads(
        Path(authority.execution_directory, f"{stage_id}_stage_closure.json").read_text(
            encoding="utf-8"
        )
    )
    _require_valid_cfg1_stage_closure_payload(written)
    # (4) retirement happened AFTER that emission was confirmed.
    assert result.stage_closure_confirmed is True
    assert stage_output_authority_is_active(authority) is False


def test_t130_a_halted_ordinal_seals_a_halted_decision_from_the_same_ledger(
    make_authority, monkeypatch
):
    sealed: list = []
    real_closure = stage_runner.emit_cfg1_stage_closure

    def _capture(authority, /, *, decision):
        sealed.append(decision)
        return real_closure(authority, decision=decision)

    monkeypatch.setattr(stage_runner, "emit_cfg1_stage_closure", _capture)

    def _executor(admission):
        from pi_harness_cfg1.arms import ARM_SHAPE
        from pi_harness_cfg1.run_contract import Cfg1RunOutcome
        from qualification.safety import ArtifactSafetyContext

        overrides = {"runtime_reported_compat_shape": ARM_SHAPE[admission.arm_id]}
        if admission.run_ordinal == 3:
            overrides.update(
                pre_dispatch_refusal_overrides("ROUTE_UNAVAILABLE", "L7")
            )
            overrides["route_reachable"] = False
        return Cfg1RunOutcome(
            observations=happy_observations(**overrides),
            safety=ArtifactSafetyContext.none_declared(),
            live_references_released=True,
        )

    authority = make_authority("S1-X1")
    result = stage_runner._run_cfg1_stage_with_injected_executor(authority, run_executor=_executor)

    assert result.disposition == "STAGE_HALTED"
    assert result.halted_after_ordinal == 3
    assert result.halt_reason_code == "PRE_DISPATCH_REFUSAL"
    decision = sealed[0]
    status = dict(decision.ordinal_status)
    assert status[1] == "RECORD_EMITTED"
    # The refused run's own RECORD was still emitted successfully -- the halt
    # comes from its CLASSIFICATION, not from its emission outcome.
    assert status[3] == "RECORD_EMITTED"
    for ordinal in range(4, 10):
        assert status[ordinal] == "NOT_EXECUTED"


def test_t131_the_successful_decision_carries_the_invariant_itself(
    make_authority, monkeypatch
):
    captured: list = []

    def _callback(_authority, decision):
        captured.append(decision)
        return None

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    decision = captured[0]
    assert decision.halted_after_ordinal is None
    assert decision.halt_reason_code is None
    for _ordinal, status in decision.ordinal_status:
        assert status in ("RECORD_EMITTED", "EVIDENCE_REFUSED")
        assert status not in ("EMISSION_COLLISION", "EMISSION_FAILED", "NOT_EXECUTED")


def test_t132_a_sealed_decision_cannot_be_consumed_twice(make_authority, monkeypatch):
    outcomes: list[str] = []

    def _callback(authority, decision):
        first = writers.emit_cfg1_stage_closure(authority, decision=decision)
        assert first.confirmed is True
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority, decision=decision)
        outcomes.append(excinfo.value.reason_code)
        return first

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    # Identical to a never-sealed decision's refusal: it does not merely become
    # useless, it becomes mechanically indistinguishable from one that never was.
    assert outcomes == ["UNKNOWN_DECISION_NONCE"]


def test_t132_revocation_is_unconditional_on_the_ensuing_writes_outcome(
    make_authority, monkeypatch
):
    outcomes: list[str] = []

    def _callback(authority, decision):
        # Pre-occupy the closure path so the FIRST attempt itself fails.
        Path(authority.execution_directory, "S1_stage_closure.json").write_text(
            "occupant", encoding="utf-8"
        )
        first = writers.emit_cfg1_stage_closure(authority, decision=decision)
        assert first.confirmed is False
        with pytest.raises(Cfg1StageDecisionError) as excinfo:
            writers.emit_cfg1_stage_closure(authority, decision=decision)
        outcomes.append(excinfo.value.reason_code)
        return first

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    assert outcomes == ["UNKNOWN_DECISION_NONCE"]


# ---------------------------------------------------------------------------
# T-133 / T-134 / T-136 -- the seal-history fact's own independent lifetime
# ---------------------------------------------------------------------------


def test_t133_seal_history_survives_decision_consumability_revocation(
    make_authority, monkeypatch
):
    """Both registries inspected AT ONCE, immediately after step 4a."""
    snapshots: list[tuple[int, bool]] = []

    def _callback(authority, decision):
        result = writers.emit_cfg1_stage_closure(authority, decision=decision)
        snapshots.append(
            (
                len(_STAGE_DECISION_SEALED),
                authority.mint_nonce in _STAGE_TERMINAL_SEAL_HISTORY,
            )
        )
        return result

    with_live_decision(make_authority("S1-X1"), _callback, monkeypatch=monkeypatch)
    assert snapshots == [(0, True)]


@pytest.mark.parametrize("failure", ["collision", "non_collision"])
def test_t134_seal_history_survives_a_failed_write_and_authority_retirement(
    failure, make_authority, monkeypatch
):
    observations: list[tuple[bool, bool]] = []

    def _probe(context):
        if context.event == "closure:after_emit":
            observations.append(
                (
                    context.force_second_seal_reach()["seal_history_present"],
                    stage_output_authority_is_active(authority),
                )
            )

    authority = make_authority("S1-X1")
    if failure == "collision":
        Path(authority.execution_directory, "S1_stage_closure.json").write_text(
            "occupant", encoding="utf-8"
        )
    else:
        real_open = writers._open_exclusive

        def _open(path):
            if path.endswith("S1_stage_closure.json"):
                raise OSError("injected non-collision create failure")
            return real_open(path)

        monkeypatch.setattr(writers, "_open_exclusive", _open)

    result = stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    assert result.stage_closure_confirmed is False
    # Present after the failed write AND after retirement -- its lifetime is
    # independent of both.
    assert observations == [(True, False)]


def test_t136_seal_history_lives_for_the_whole_invocation_and_no_longer(
    make_authority, monkeypatch
):
    during: list[bool] = []

    def _probe(context):
        if context.event in ("seal:after", "closure:after_emit", "stage:before_return"):
            during.append(context.force_second_seal_reach()["seal_history_present"])

    authority = make_authority("S1-X1")
    stage_runner._run_cfg1_stage_with_injected_executor(
        authority, run_executor=synthetic_run_executor(), _internal_probe=_probe
    )
    # Present through sealing, the write, and authority retirement...
    assert during == [True, True, True]
    # ...and absent only after the invocation itself has returned.
    assert authority.mint_nonce not in _STAGE_TERMINAL_SEAL_HISTORY
    assert _STAGE_DECISION_SEALED == {}
