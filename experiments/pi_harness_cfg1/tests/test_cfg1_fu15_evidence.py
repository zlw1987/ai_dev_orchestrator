"""T-156 - T-162: FU15 Findings B1/B2 and the frozen OBS1 disposition.

The single idea these rows share is that a malformed value must never be
LAUNDERED into a plausible one. The three dispositions differ because the
truths they have to tell differ:

``L25`` (B1)
    the observation may not have happened, so the whole observation becomes
    the already-frozen NOT-PERFORMED shape -- all-or-nothing, driven by an
    exactness PREDICATE rather than a reducer;
``L26`` (B2)
    the verification demonstrably DID happen, so "not performed" would be a
    second falsehood. The malformed member becomes a fixed,
    non-content-bearing sentinel that the record's own validator refuses by
    construction, and the run takes the already-frozen Sec. 18 row 15 path;
``OBS1``
    the frozen snapshot already refuses a malformed count AT CONSTRUCTION, so
    there is no CFG1-side window for a second mechanism to guard -- and T-162
    guards against inventing one anyway.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

import pytest

from cfg1_builders import happy_observations, run_payload, synthetic_run_executor
from cfg1_doubles import build_doubled_ports, seam_digests_all_match
from pi_harness_cfg1 import classification, obs1, run_executor
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.run_executor import execute_cfg1_run
from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position
from pi_harness_cfg1.stage_runner import (
    _run_cfg1_stage_with_injected_executor as run_cfg1_stage,
)


class _IndexLookalike:
    """An object ``int(...)`` and ``operator.index`` would happily accept.

    This is the shape that makes ``_exact_count``'s replacement necessary
    rather than merely tidier: a reducer built on ``int(...)`` manufactures a
    perfectly plausible count from this.
    """

    def __int__(self) -> int:  # pragma: no cover - never called by design
        return 7

    def __index__(self) -> int:  # pragma: no cover - never called by design
        return 7


#: The five malformed shapes every count row must cover, independently.
MALFORMED_COUNTS = [True, 1.0, "1", -1, _IndexLookalike()]

#: Every observation-#1 companion, at its frozen not-performed default.
NOT_PERFORMED_COMPANIONS = {
    "head_moved": False,
    "changed_tracked_paths": [],
    "untracked_path_count": 0,
    "staged_path_count": 0,
    "broker_git_cross_check_agrees": True,
}


@dataclass
class _Snapshot:
    """A repository snapshot with every member independently overridable."""

    head: object = "0" * 40
    changed_tracked_paths: object = ()
    untracked_path_count: object = 0
    staged_path_count: object = 0


def _admission(run_id: str) -> Cfg1RunAdmission:
    block, position = _schedule_block_position("S1", 1)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id=run_id,
    )


def _run_with_snapshot(git_executable, monkeypatch, snapshot, *, run_id="d" * 32):
    """One full run whose repository observations return ``snapshot``."""
    seam_digests_all_match(monkeypatch)
    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"observe_repository": lambda *, workspace_root: snapshot},
    )
    return execute_cfg1_run(_admission(run_id), ports=ports).observations


# ---------------------------------------------------------------------------
# T-156 / T-157 -- a malformed repository count makes the whole observation
# not-performed, and never becomes a durable observed zero
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("malformed", MALFORMED_COUNTS, ids=repr)
@pytest.mark.parametrize("field_name", ["untracked_path_count", "staged_path_count"])
def test_t156_t157_one_malformed_count_drives_the_whole_l25_observation_not_performed(
    git_executable, monkeypatch, malformed, field_name
):
    """T-156 (``untracked_path_count``) and T-157 (``staged_path_count``).

    Every OTHER member of the snapshot is well-formed, so the disposition is
    attributable to this one member. The point of the row is the last two
    assertions: the record carries no manufactured ``0`` PRESENTED AS AN
    OBSERVED COUNT, and Sec. 12.2's D-4 predicate is never evaluated.
    """
    snapshot = _Snapshot(**{field_name: malformed})
    observations = _run_with_snapshot(git_executable, monkeypatch, snapshot)

    assert observations["git_observation_1_performed"] is False
    for key, expected in NOT_PERFORMED_COMPANIONS.items():
        assert observations[key] == expected, f"{key} was not left at its default"

    # The zero that IS present is the not-performed default, never an observed
    # count: the two are distinguishable only because `performed` is false, and
    # that is exactly the distinction FU2 missed for this family.
    assert observations["untracked_path_count"] == 0
    assert observations["staged_path_count"] == 0
    payload = run_payload(**{key: observations[key] for key in NOT_PERFORMED_COMPANIONS},
                          git_observation_1_performed=False)
    assert payload["git_observation_1_performed"] is False
    assert "D-4" not in classification.observation_disagreement_predicates(payload)


def test_t156_the_projection_no_longer_applies_a_reducer_to_a_repository_count():
    """A source-of-truth guard. ``_exact_count`` manufacturing a plausible
    value IS the defect, so it must not be applied to a load-bearing repository
    count anywhere on the projection path -- not restored later as a
    "harmless" default either.
    """
    # OC-4: the L25 / L26 projection sites now live in their own step
    # functions; audit exactly the functions that contain them (never the
    # sequencer, which would pass vacuously).
    source = "".join(
        inspect.getsource(function)
        for function in (
            run_executor._closure_l25_git_observation_1,
            run_executor._closure_l26_project_verification,
            run_executor._closure_l26_verification,
        )
    )
    # Non-vacuity: the audited text really contains the projection sites.
    assert source.count("_exact_repository_snapshot(snapshot)") == 2
    for laundered in (
        '_exact_count(\n                getattr(snapshot, "untracked_path_count"',
        'getattr(snapshot, "untracked_path_count", 0)',
        'getattr(snapshot, "staged_path_count", 0)',
        'getattr(snapshot, "changed_tracked_paths", ())',
        'getattr(snapshot, "head", head_before)',
    ):
        assert laundered not in source
    # And the predicate really is a predicate: it raises, it does not return a
    # substitute value.
    predicate = inspect.getsource(run_executor._exact_repository_snapshot)
    assert "raise _MalformedRepositorySnapshot" in predicate
    assert "return 0" not in predicate


# ---------------------------------------------------------------------------
# T-158 -- the two adjacent L25 launderings are closed with the counts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides,what",
    [
        ({"changed_tracked_paths": None}, "changed_tracked_paths missing"),
        ({"changed_tracked_paths": ["src/app.py", 7]}, "non-str member"),
        ({"changed_tracked_paths": "src/app.py"}, "a bare str, not a sequence"),
        ({"head": None}, "head missing"),
        ({"head": 12345}, "head not an exact str"),
    ],
)
def test_t158_a_malformed_changed_paths_or_head_takes_the_same_not_performed_branch(
    git_executable, monkeypatch, overrides, what
):
    """(a) ``changed_tracked_paths`` and (b) ``head``.

    Without this row, a missing ``changed_tracked_paths`` becomes a durable
    empty list meaning "nothing changed", and a missing ``head`` becomes a
    durable ``head_moved = false`` meaning "HEAD did not move" -- two invented
    observations sitting beside ``git_observation_1_performed = true``.
    """
    snapshot = _Snapshot(**overrides)
    observations = _run_with_snapshot(git_executable, monkeypatch, snapshot)

    assert observations["git_observation_1_performed"] is False, what
    assert observations["changed_tracked_paths"] == []
    assert observations["head_moved"] is False
    # ...and the only reason those two are safe is that `performed` is false.
    assert observations["git_observation_2_performed"] is False


def test_t158_a_bare_string_is_not_accepted_as_a_sequence_of_paths():
    """``str`` is iterable, so "anything iterable" would silently decompose it
    into characters and intersect to nothing -- another durable "nothing
    changed". The predicate names the exact container types instead.
    """
    with pytest.raises(run_executor._MalformedRepositorySnapshot):
        run_executor._exact_repository_snapshot(
            _Snapshot(changed_tracked_paths="src/app.py")
        )


# ---------------------------------------------------------------------------
# T-159 -- a genuine zero is still recordable
# ---------------------------------------------------------------------------


def test_t159_an_observed_exact_zero_still_records_as_performed(
    git_executable, monkeypatch
):
    """Without this row, T-156/T-157 could be satisfied by a change that made
    observed zeros unrepresentable -- a different falsehood, not a fix.

    The snapshot reports the run's OWN recorded ``head_before``, so
    ``head_moved`` is a genuine observed "no", not an artifact of the double
    reporting an unrelated hash.
    """
    from pi_harness_cfg1 import run_workspace

    seam_digests_all_match(monkeypatch)
    made: dict[str, object] = {}

    def _observe(*, workspace_root):
        head_before, _tracked = run_workspace.registered_baseline(made["workspace"])
        return _Snapshot(
            head=head_before,
            changed_tracked_paths=(),
            untracked_path_count=0,
            staged_path_count=0,
        )

    ports, made = build_doubled_ports(
        git_executable=git_executable, overrides={"observe_repository": _observe}
    )
    observations = execute_cfg1_run(_admission("e" * 32), ports=ports).observations

    assert observations["git_observation_1_performed"] is True
    assert observations["untracked_path_count"] == 0
    assert observations["staged_path_count"] == 0
    assert observations["head_moved"] is False
    assert observations["changed_tracked_paths"] == []


def test_t159_the_predicate_accepts_exact_zero_and_refuses_its_lookalikes():
    """The same distinction, isolated from the run machinery."""
    head, changed, untracked, staged = run_executor._exact_repository_snapshot(
        _Snapshot(untracked_path_count=0, staged_path_count=0)
    )
    assert (untracked, staged) == (0, 0)
    assert changed == () and head == "0" * 40

    for malformed in MALFORMED_COUNTS:
        with pytest.raises(run_executor._MalformedRepositorySnapshot):
            run_executor._exact_repository_snapshot(
                _Snapshot(untracked_path_count=malformed)
            )


# ---------------------------------------------------------------------------
# T-160 -- a malformed verification count REFUSES the record, never invents one
# ---------------------------------------------------------------------------


@dataclass
class _SeededFailureBaseline:
    """L3's baseline call: CFG1-T1 is a declared SEEDED FAILURE, so this must
    report ``passed = False`` or the run refuses before L26 is ever reached.
    """

    started: bool = True
    completed: bool = True
    timed_out: bool = False
    output_limit_exceeded: bool = False
    return_code: int = 1
    passed: bool = False
    counts: dict = dataclass_field(
        default_factory=lambda: {"passed": 0, "failed": 1, "error": 0}
    )


def _verification_ports(git_executable, *, l26_outcome):
    calls: list[int] = []

    def _run_verification(**_kwargs):
        calls.append(1)
        return _SeededFailureBaseline() if len(calls) == 1 else l26_outcome

    ports, _made = build_doubled_ports(
        git_executable=git_executable,
        overrides={"run_verification": _run_verification},
    )
    return ports, calls


@pytest.mark.parametrize("malformed", MALFORMED_COUNTS + ["<missing>"], ids=repr)
@pytest.mark.parametrize("key", ["passed", "failed", "error"])
def test_t160_a_malformed_verification_count_becomes_the_sentinel_never_a_number(
    git_executable, monkeypatch, malformed, key
):
    """(1) The payload's ``verification_counts`` carries the fixed,
    non-content-bearing sentinel -- never a manufactured integer -- and (5) no
    ``verification_passed: true`` survives.
    """
    seam_digests_all_match(monkeypatch)

    counts = {"passed": 1, "failed": 0, "error": 0}
    if malformed == "<missing>":
        del counts[key]
    else:
        counts[key] = malformed

    @dataclass
    class _MalformedVerification:
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 0
        passed: bool = True
        counts: dict = dataclass_field(default_factory=lambda: dict(counts))

    ports, calls = _verification_ports(git_executable, l26_outcome=_MalformedVerification())
    observations = execute_cfg1_run(_admission("f" * 32), ports=ports).observations

    assert len(calls) == 2, "the test never reached L26's own verification call"
    projected = observations["verification_counts"]
    assert projected[key] is None, "the malformed member did not become the sentinel"
    assert projected[key] is not 0  # noqa: F632 - identity is the point
    for other in ("passed", "failed", "error"):
        if other != key:
            assert type(projected[other]) is int
    # Verification really did run -- this is NOT the not-performed shape.
    assert observations["verification_attempted"] is True
    assert observations["verification_completed"] is True
    assert observations["verification_passed"] is False


def test_t160_the_record_fails_its_own_validator_and_halts_the_stage(
    make_authority, git_executable, monkeypatch
):
    """(2), (3) and (4): ``_require_valid_cfg1_run_payload`` refuses at
    ``verification_counts``; Sec. 18 row 15 fires with a refusal record
    carrying ``refused_record_kind`` and ``RECORD_INVARIANT``; the emission
    status is ``EVIDENCE_REFUSED``; and the stage halts unconditionally.
    """
    from pi_harness_cfg1.records import (
        Cfg1RecordValidationError,
        _require_valid_cfg1_run_payload_v2 as _require_valid_cfg1_run_payload,
    )

    # (2) -- the validator's own refusal, in isolation.
    payload = run_payload(verification_counts={"passed": None, "failed": 0, "error": 0})
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        _require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "BAD_MAPPING_VALUE_VERIFICATION_COUNTS"

    # (3)/(4) -- the whole frozen row-15 path, end to end.
    authority = make_authority("S1-T160")
    observations = happy_observations(
        verification_counts={"passed": None, "failed": 0, "error": 0},
        verification_passed=False,
    )
    result = run_cfg1_stage(
        authority,
        run_executor=synthetic_run_executor(observations_for=lambda a: observations),
    )
    assert dict(result.ordinal_status)[1] == "EVIDENCE_REFUSED"
    assert result.halt_reason_code == "RUN_RECORD_SELF_VALIDATION_FAILED"
    assert result.halted_after_ordinal == 1

    from pi_harness_cfg1 import (
        REFUSAL_RECORD_KIND,
        REFUSAL_RECORD_VERSION_V2 as REFUSAL_RECORD_VERSION,
        RUN_RECORD_VERSION_V2 as RUN_RECORD_VERSION,
    )

    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert written["record_version"] == REFUSAL_RECORD_VERSION
    assert written["record_kind"] == REFUSAL_RECORD_KIND
    assert written["refused_record_kind"] == RUN_RECORD_VERSION
    assert "RECORD_INVARIANT" in written["finding_categories"]

    # (5) -- no durable artifact anywhere carries a passing verification claim
    # or an invented count.
    for artifact_path in Path(authority.execution_directory).glob("*.json"):
        text = artifact_path.read_text(encoding="utf-8")
        assert '"verification_passed": true' not in text
        assert "verification_counts" not in text


# ---------------------------------------------------------------------------
# T-161 -- the malformed value never reaches any sink
# ---------------------------------------------------------------------------


_NEEDLE = "CFG1-FU15-MALFORMED-COUNT-NEEDLE-4b71e9"


class _SelfDescribingMalformedCount:
    """Its own text is the thing that must never escape (T-140's technique)."""

    def __str__(self) -> str:
        return _NEEDLE

    def __repr__(self) -> str:
        return _NEEDLE


def test_t161_the_malformed_verification_value_reaches_no_console_or_artifact(
    make_authority, git_executable, monkeypatch, capsys
):
    """The sentinel substitution -- not the malformed object -- is what reaches
    the payload, so neither the console nor any durable byte can carry the
    value's own text.
    """
    seam_digests_all_match(monkeypatch)

    @dataclass
    class _NeedleVerification:
        started: bool = True
        completed: bool = True
        timed_out: bool = False
        output_limit_exceeded: bool = False
        return_code: int = 0
        passed: bool = True
        counts: dict = dataclass_field(
            default_factory=lambda: {
                "passed": _SelfDescribingMalformedCount(),
                "failed": 0,
                "error": 0,
            }
        )

    ports, calls = _verification_ports(git_executable, l26_outcome=_NeedleVerification())
    observations = execute_cfg1_run(_admission("0" * 32), ports=ports).observations
    assert len(calls) == 2
    assert observations["verification_counts"]["passed"] is None

    # The malformed object is not reachable from the observations at all.
    assert _NEEDLE not in json.dumps(observations, default=str)

    authority = make_authority("S1-T161")
    payload_observations = happy_observations(
        verification_counts=dict(observations["verification_counts"]),
        verification_passed=False,
    )
    result = run_cfg1_stage(
        authority,
        run_executor=synthetic_run_executor(
            observations_for=lambda a: payload_observations
        ),
    )
    assert dict(result.ordinal_status)[1] == "EVIDENCE_REFUSED"

    captured = capsys.readouterr()
    assert _NEEDLE not in captured.out
    assert _NEEDLE not in captured.err
    for artifact_path in Path(authority.execution_directory).rglob("*"):
        if artifact_path.is_file():
            assert _NEEDLE not in artifact_path.read_text(encoding="utf-8")


def test_t161_the_sentinel_is_fixed_and_non_content_bearing():
    """It must be ``None`` -- never the malformed value, and never a number.

    ``0``, ``-1`` and ``"unknown"`` would each be an invented count wearing a
    different costume, and the malformed value itself would defeat the
    containment guarantee this sentinel exists to preserve.
    """
    assert run_executor._MALFORMED_VERIFICATION_COUNT is None


# ---------------------------------------------------------------------------
# T-162 -- OBS1's frozen boundary already owns count integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malformed",
    [True, 1.0, -1, _IndexLookalike()],
    ids=["bool", "float", "negative", "index_lookalike"],
)
def test_t162a_a_malformed_count_cannot_reach_a_constructed_obs1_snapshot(malformed):
    """Through the snapshot's ACTUAL frozen public boundary -- its own
    ``__post_init__`` -- not through a CFG1 re-implementation of it.
    """
    from qualification.runtime_activity import (
        ActivityRecordInvariantError,
        RuntimeToolActivitySnapshot,
    )

    fields = {
        name: 0
        for name in obs1._UNAVAILABLE_COUNTS
        if not name.startswith("runtime_reported_")
    }
    # Build the snapshot's own kwargs from its real signature, so this row
    # cannot drift into testing a shape the frozen type no longer has.
    kwargs: dict[str, object] = {}
    for name, parameter in inspect.signature(RuntimeToolActivitySnapshot).parameters.items():
        annotation = str(parameter.annotation)
        if "int" in annotation:
            kwargs[name] = 0
        elif "bool" in annotation:
            kwargs[name] = False
        elif parameter.default is not inspect.Parameter.empty:
            kwargs[name] = parameter.default
        else:
            kwargs[name] = "agent_settled"
    assert fields is not None

    count_fields = [
        name
        for name, parameter in inspect.signature(RuntimeToolActivitySnapshot).parameters.items()
        if "int" in str(parameter.annotation)
    ]
    assert count_fields, "the frozen snapshot no longer exposes int count fields"

    for name in count_fields:
        attempt = dict(kwargs)
        attempt[name] = malformed
        with pytest.raises(ActivityRecordInvariantError):
            RuntimeToolActivitySnapshot(**attempt)


def test_t162a_cfg1_converts_that_refusal_into_the_frozen_unavailable_shape(
    monkeypatch,
):
    """And CFG1's consumption is the whole of its handling: availability false,
    one closed reason code, every count zeroed, and no exception text retained.
    """
    from qualification import runtime_activity

    class _DistinctiveProjectionFailure(runtime_activity.ActivityRecordInvariantError):
        pass

    needle = "CFG1-FU15-OBS1-PROJECTION-NEEDLE-2c0dd1"

    def _raise(*_args, **_kwargs):
        raise _DistinctiveProjectionFailure(needle)

    monkeypatch.setattr(runtime_activity, "project_runtime_tool_activity", _raise)

    fields = obs1.project_cfg1_runtime_activity(
        activity=object(), baseline=object(), turn_outcome=object()
    )
    assert fields["runtime_reported_tool_activity_available"] is False
    assert fields["activity_unavailable_reason"] == "PROJECTION_REFUSED"
    assert fields["runtime_reported_tool_activity_capture_basis"] is None
    for name, value in obs1._UNAVAILABLE_COUNTS.items():
        assert fields[name] == 0 and type(fields[name]) is int, name
    assert needle not in json.dumps(fields, default=str)


def test_t162b_cfg1_defines_no_second_availability_mechanism_for_obs1_counts():
    """The half that guards against DUPLICATING OBS1's authority.

    A second, independently-evolving definition of what a valid OBS1 count is
    is the failure mode Sec. 37.5's disposition exists to prevent -- so no
    CFG1 module may define an extra availability flag, predicate or exactness
    gate for a ``runtime_reported_*`` count, and no ``_exact_count``-style
    reduction may be applied to one on the projection path.
    """
    from pi_harness_cfg1 import records

    obs1_source = inspect.getsource(obs1)
    executor_source = inspect.getsource(run_executor)

    # Exactly one availability flag for the family, and it is the frozen one.
    assert obs1_source.count("runtime_reported_tool_activity_available") == 2
    for invented in (
        "runtime_reported_counts_available",
        "runtime_activity_counts_available",
        "_require_exact_activity_count",
        "_exact_activity_count",
    ):
        assert invented not in obs1_source
        assert invented not in executor_source
        assert invented not in inspect.getsource(records)

    # No reduction is applied to a runtime_reported_* count anywhere on the
    # projection path -- the snapshot's attributes are passed straight through.
    for line in obs1_source.splitlines():
        if "runtime_reported_" in line and "snapshot." in line:
            assert "_exact_count" not in line
            assert "int(" not in line
    for line in executor_source.splitlines():
        if "runtime_reported_" in line:
            assert "_exact_count" not in line, line

    # And CFG1 never re-implements or shadows the frozen projection.
    assert "def project_runtime_tool_activity" not in obs1_source
    assert "class RuntimeToolActivitySnapshot" not in obs1_source
