"""T-21, T-38 - T-42, T-51 - T-61, T-70 - T-77, T-83 - T-87, T-95 - T-99,
T-116 - T-122: the writer boundary, the emission phases, and the byte pipeline.

Pure Python, ``tmp_path``-scoped, no live Pi/network/model/credential activity.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from cfg1_builders import refusal_payload, run_payload
from qualification.safety import ArtifactSafetyContext

from pi_harness_cfg1 import MAX_CFG1_ARTIFACT_BYTES, binding, records, schedule, writers
from pi_harness_cfg1.records import Cfg1RecordValidationError
from pi_harness_cfg1.writers import (
    Cfg1WriterError,
    emit_cfg1_refusal_record,
    emit_cfg1_run_record,
    emit_cfg1_stage_closure,
)

NO_NEEDLES = ArtifactSafetyContext.none_declared()

_PACKAGE_DIR = Path(__file__).resolve().parent.parent

_EMISSION_WRITERS = (
    emit_cfg1_run_record,
    emit_cfg1_refusal_record,
    emit_cfg1_stage_closure,
)

_FORBIDDEN_WRITER_PARAMETER_NAMES = frozenset(
    {
        "path",
        "actual_path",
        "output_path",
        "filename",
        "file_name",
        "record_filename",
        "directory",
        "execution_directory",
        "results_root",
        "root",
        "arm_id",
        "arm",
    }
)


def _emit_run(authority, *, ordinal=1, payload=None, lifecycle=True, safety=NO_NEEDLES):
    """Emit one run record, with a payload bound to THIS authority by default."""
    if payload is None:
        payload = run_payload(
            stage_execution_id=authority.stage_execution_id, run_ordinal=ordinal
        )
    return emit_cfg1_run_record(
        authority,
        run_ordinal=ordinal,
        payload=payload,
        lifecycle_all_closed=lifecycle,
        safety=safety,
    )


# ---------------------------------------------------------------------------
# T-21 / T-38 / T-39 -- the API surface itself forbids a caller-selected path
# ---------------------------------------------------------------------------


def test_t38_no_emission_writer_declares_a_path_filename_directory_or_arm_parameter():
    """Audits the WRITE/EMISSION surface -- not every public CFG1 function.

    The read-only ``verify_cfg1_*_binding`` functions' one ``actual_path``
    parameter is an intentional, frozen exception: location is the object being
    verified, and accepting it grants no write authority. Including them here
    would make this audit fail against the design's own accepted API, which is
    exactly the wording error FU6 corrected.
    """
    for writer in _EMISSION_WRITERS:
        parameters = inspect.signature(writer).parameters
        offending = sorted(set(parameters) & _FORBIDDEN_WRITER_PARAMETER_NAMES)
        assert offending == [], f"{writer.__name__} declares {offending}"


def test_t21_no_write_or_emission_api_accepts_a_caller_selected_output_location():
    """The whole public write/emission surface is exactly three functions."""
    public_emitters = sorted(
        name
        for name in dir(writers)
        if name.startswith("emit_cfg1_") and callable(getattr(writers, name))
    )
    assert public_emitters == [
        "emit_cfg1_refusal_record",
        "emit_cfg1_run_record",
        "emit_cfg1_stage_closure",
    ]
    # No timestamp, fallback, or replacement output path exists anywhere in the
    # write/emission surface.
    source = (_PACKAGE_DIR / "writers.py").read_text(encoding="utf-8")
    for forbidden in ("strftime", "time.time(", "uuid", "_alternate_path", "_replacement"):
        assert forbidden not in source


@pytest.mark.parametrize("writer", _EMISSION_WRITERS, ids=lambda w: w.__name__)
def test_t39_an_additional_positional_argument_raises_typeerror(writer, make_authority):
    """Python's own argument binding refuses it -- before a line of the body runs."""
    authority = make_authority("S1-X1")
    with pytest.raises(TypeError):
        writer(authority, "C:\\anywhere\\forged.json")


def test_t108_the_stage_closure_writer_has_exactly_two_parameters(make_authority):
    parameters = inspect.signature(emit_cfg1_stage_closure).parameters
    assert list(parameters) == ["authority", "decision"]
    for forbidden in (
        "ordinal_status",
        "halted_after_ordinal",
        "halt_reason_code",
        "record_filename",
        "stage_id",
        "stage_execution_id",
        "payload",
    ):
        assert forbidden not in parameters
    authority = make_authority("S1-X1")
    with pytest.raises(TypeError):
        emit_cfg1_stage_closure(authority, object(), object())


# ---------------------------------------------------------------------------
# T-40 / T-41 / T-42 / T-91 -- schedule identity is derived, never accepted
# ---------------------------------------------------------------------------


def test_t40_an_off_schedule_arm_is_refused_at_step_6_not_step_7(make_authority):
    """FU7's own correction: this payload is NOT internally self-consistent.

    Sec. 22.3 already makes ``arm_id`` a pure function of the payload's own
    ``(stage_id, run_ordinal)``, so a payload claiming a different arm for the
    same ordinal is refused by the payload validator itself, with no authority
    object needed to state or check it -- step 7 never runs.
    """
    assert schedule._schedule_arm_for("S1", 1) == "Q"
    for wrong_arm in ("E", "R"):
        payload = run_payload(run_ordinal=1)
        payload["arm_id"] = wrong_arm
        with pytest.raises(Cfg1RecordValidationError) as excinfo:
            records._require_valid_cfg1_run_payload(payload)
        assert excinfo.value.reason_code == "ARM_DISAGREES_WITH_SCHEDULE"

        authority = make_authority(f"S1-arm{wrong_arm}")
        result = _emit_run(authority, payload=payload)
        # The step-6 refusal fired first: the outcome carries the RECORD_INVARIANT
        # finding class, never the step-7 AUTHORITY_BINDING one.
        assert result.emission_status == "EVIDENCE_REFUSED"
        written = json.loads(
            Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
        )
        assert "AUTHORITY_BINDING" not in written["finding_categories"]
        assert "RECORD_INVARIANT" in written["finding_categories"]


@pytest.mark.parametrize("ordinal", [0, 10, -1, True, False, "1", 1.0, None])
def test_t41_malformed_ordinals_are_refused_before_any_schedule_lookup(
    ordinal, make_authority
):
    authority = make_authority("S1-X1")
    with pytest.raises(Cfg1WriterError) as excinfo:
        emit_cfg1_run_record(
            authority,
            run_ordinal=ordinal,
            payload={},
            lifecycle_all_closed=True,
            safety=NO_NEEDLES,
        )
    assert excinfo.value.reason_code in (
        "MALFORMED_RUN_ORDINAL",
        "RUN_ORDINAL_OUT_OF_RANGE",
    )


def test_t42_s1_ordinals_derive_the_real_schedule_and_one_shared_callable():
    assert [schedule._schedule_arm_for("S1", k) for k in range(1, 10)] == [
        "Q", "R", "E", "R", "E", "Q", "E", "Q", "R",
    ]
    _assert_one_shared_schedule_callable()


def test_t93_s2_ordinals_derive_the_frozen_schedule_and_the_same_callable():
    assert [schedule._schedule_arm_for("S2", k) for k in range(1, 7)] == [
        "Q", "H", "H", "Q", "Q", "H",
    ]
    for ordinal in range(1, 7):
        assert schedule._schedule_block_position("S2", ordinal) == (
            ((ordinal - 1) // 2) + 1,
            ((ordinal - 1) % 2) + 1,
        )
    _assert_one_shared_schedule_callable()


def _assert_one_shared_schedule_callable():
    """Identity of the underlying callable at every consumption site.

    A future refactor that accidentally reimplements the lookup somewhere fails
    this even if the reimplementation happens to agree today.
    """
    from pi_harness_cfg1 import stage_runner

    canonical = schedule._schedule_arm_for
    for module in (records, writers, binding, stage_runner):
        assert module._schedule_arm_for is canonical, module.__name__

    # And no module outside ``schedule`` carries an ordinal->arm table of its own.
    table_pattern = re.compile(r"\{\s*1\s*:\s*[\"'][QREH][\"']")
    for source_path in sorted(_PACKAGE_DIR.glob("*.py")):
        if source_path.name == "schedule.py":
            continue
        assert not table_pattern.search(source_path.read_text(encoding="utf-8")), source_path


def test_t129_last_ordinal_is_derived_from_the_shared_schedule_mapping(monkeypatch):
    assert schedule.LAST_ORDINAL("S1") == 9
    assert schedule.LAST_ORDINAL("S2") == 6
    assert schedule.LAST_ORDINAL("S1") == max(schedule.SCHEDULE["S1"])

    # A synthetic, differently-sized schedule proves the derivation is genuinely
    # computed rather than two integers that happen to equal 9 and 6 today.
    monkeypatch.setitem(schedule.SCHEDULE, "S1", {1: "Q", 2: "R", 3: "E", 4: "Q"})
    assert schedule.LAST_ORDINAL("S1") == 4


def test_t91_step_6_refusals_never_reach_step_7(make_authority):
    """Off-schedule arm, wrong run filename, wrong closure filename."""
    payload = run_payload(run_ordinal=1)
    payload["arm_id"] = "E"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        records._require_valid_cfg1_run_payload(payload)
    assert excinfo.value.category == "CROSS_FIELD_INVARIANT"

    payload = run_payload(run_ordinal=1)
    payload["record_filename"] = "S1_02_R.json"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        records._require_valid_cfg1_run_payload(payload)
    assert excinfo.value.reason_code == "RECORD_FILENAME_DISAGREES_WITH_DERIVATION"

    from cfg1_builders import stage_closure_payload

    closure = stage_closure_payload()
    closure["record_filename"] = "S2_stage_closure.json"
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        records._require_valid_cfg1_stage_closure_payload(closure)
    assert excinfo.value.reason_code == "RECORD_FILENAME_DISAGREES_WITH_DERIVATION"


# ---------------------------------------------------------------------------
# T-51 - T-57 -- the writer's input ordering: type-gate, canonicalize, never re-read
# ---------------------------------------------------------------------------


class _HostileMapping:
    """A hand-rolled Mapping. Records every field read it is asked for."""

    def __init__(self, backing: dict) -> None:
        self._backing = backing
        self.reads: list[str] = []

    def __getitem__(self, key):
        self.reads.append(key)
        return self._backing[key]

    def get(self, key, default=None):
        self.reads.append(key)
        return self._backing.get(key, default)

    def keys(self):
        return self._backing.keys()

    def __iter__(self):
        return iter(self._backing)

    def __len__(self):
        return len(self._backing)


class _DictSubclass(dict):
    """A genuine ``dict`` subclass -- still not exactly ``dict``."""


def test_t55_hostile_mapping_and_dict_subclass_are_refused_with_zero_field_reads(
    make_authority,
):
    authority = make_authority("S1-X1")
    hostile = _HostileMapping(run_payload())
    with pytest.raises(Cfg1WriterError) as excinfo:
        _emit_run(authority, payload=hostile)
    assert excinfo.value.reason_code == "PAYLOAD_NOT_A_DICT"
    assert hostile.reads == []

    with pytest.raises(Cfg1WriterError):
        _emit_run(authority, payload=_DictSubclass(run_payload()))

    hostile_refusal = _HostileMapping(refusal_payload())
    with pytest.raises(Cfg1WriterError) as excinfo:
        emit_cfg1_refusal_record(
            authority, run_ordinal=1, refusal_payload=hostile_refusal, safety=NO_NEEDLES
        )
    assert excinfo.value.reason_code == "PAYLOAD_NOT_A_DICT"
    assert hostile_refusal.reads == []

    with pytest.raises(Cfg1WriterError):
        emit_cfg1_refusal_record(
            authority,
            run_ordinal=1,
            refusal_payload=_DictSubclass(refusal_payload()),
            safety=NO_NEEDLES,
        )


def test_t51_marks_its_own_retarget_to_the_writer_boundary():
    """T-51 originally tested the removed ``parsed_record`` gate (FU5).

    The hostile-Mapping / dict-subclass concern now lives at the WRITER
    boundary, which T-55 above proves. This row exists so the retarget is
    explicit rather than a silently dropped test id.
    """
    assert "parsed_record" not in inspect.signature(
        binding.verify_cfg1_run_artifact_binding
    ).parameters


def test_t56_uncanonicalizable_and_incomplete_payloads_never_reach_step_7(make_authority):
    class _NotSerializable:
        pass

    authority = make_authority("S1-X1")
    payload = run_payload()
    payload["head_moved"] = _NotSerializable()
    result = _emit_run(authority, payload=payload)
    assert result.emission_status == "EVIDENCE_REFUSED"
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert "AUTHORITY_BINDING" not in written["finding_categories"]
    # No exception text of any kind was retained.
    assert "_NotSerializable" not in json.dumps(written)

    incomplete = run_payload(run_ordinal=2)
    del incomplete["head_moved"]
    with pytest.raises(Cfg1RecordValidationError) as excinfo:
        records._require_valid_cfg1_run_payload(incomplete)
    assert excinfo.value.reason_code == "CLOSED_KEY_SET_VIOLATION"


def test_t57_the_original_payload_is_read_exactly_once(make_authority, monkeypatch):
    """The writer's outcome is provably a function of the one canonical snapshot."""
    authority = make_authority("S1-X1")
    payload = run_payload()

    seen: list[object] = []
    real_dumps = json.dumps

    def _counting_dumps(obj, *args, **kwargs):
        seen.append(obj)
        return real_dumps(obj, *args, **kwargs)

    monkeypatch.setattr(writers.json, "dumps", _counting_dumps)
    result = _emit_run(authority, payload=payload)
    assert result.emission_status == "RECORD_EMITTED"
    # Exactly one of the dumps calls saw the ORIGINAL payload object (step 4);
    # every later one saw the canonical snapshot instead.
    assert sum(1 for obj in seen if obj is payload) == 1


def test_t52_and_t53_mark_their_own_retargets():
    """T-52/T-53 pointed at the removed second verifier parameter (FU5)."""
    for verifier in (
        binding.verify_cfg1_run_artifact_binding,
        binding.verify_cfg1_stage_closure_binding,
    ):
        assert list(inspect.signature(verifier).parameters) == ["actual_path"]


# ---------------------------------------------------------------------------
# T-58 / T-59 / T-60 / T-61 / T-92 -- step 7, the authority-binding boundary
# ---------------------------------------------------------------------------


def _valid_other_identity_run_payloads():
    """The three genuinely constructible valid-other-identity cases."""
    return {
        # Case A -- same valid S1 identity, a DIFFERENT execution id.
        "A": run_payload(stage_execution_id="S1-X2", run_ordinal=1),
        # Case B -- a complete, fully-valid record for a DIFFERENT S1 ordinal.
        "B": run_payload(stage_execution_id="S1-X1", run_ordinal=4),
        # Case C -- a complete, fully-valid S2 identity.
        "C": run_payload(stage_id="S2", stage_execution_id="S1-X1", run_ordinal=2),
    }


def test_t92_every_step_7_candidate_first_passes_its_own_validator():
    """The meta-test: a step-7 regression is vacuous unless step 6 accepts it."""
    for case, payload in _valid_other_identity_run_payloads().items():
        records._require_valid_cfg1_run_payload(payload), case
    for case in ("A", "B", "C"):
        records._require_valid_cfg1_refusal_payload(_refusal_case(case))
    for closure in _stage_closure_cases().values():
        records._require_valid_cfg1_stage_closure_payload(closure)


def _refusal_case(case: str) -> dict:
    if case == "A":
        return refusal_payload(stage_execution_id="S1-X2", run_ordinal=1)
    if case == "B":
        return refusal_payload(stage_execution_id="S1-X1", run_ordinal=4)
    return refusal_payload(stage_id="S2", stage_execution_id="S1-X1", run_ordinal=2)


def _stage_closure_cases() -> dict:
    from cfg1_builders import stage_closure_payload

    return {
        "other_execution_id": stage_closure_payload(stage_execution_id="S1-X2"),
        "other_stage": stage_closure_payload(stage_id="S2", stage_execution_id="S1-X1"),
    }


@pytest.mark.parametrize("case", ["A", "B", "C"])
def test_t58_valid_other_identity_run_payloads_are_refused_at_step_7(case, make_authority):
    authority = make_authority("S1-X1")
    payload = _valid_other_identity_run_payloads()[case]
    result = _emit_run(authority, ordinal=1, payload=payload)
    assert result.emission_status == "EVIDENCE_REFUSED"
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert written["finding_categories"] == ["AUTHORITY_BINDING"]
    assert written["stage_execution_id"] == "S1-X1"


@pytest.mark.parametrize("case", ["A", "B", "C"])
def test_t59_valid_other_identity_refusal_payloads_are_refused_at_step_7(
    case, make_authority
):
    authority = make_authority("S1-X1")
    result = emit_cfg1_refusal_record(
        authority, run_ordinal=1, refusal_payload=_refusal_case(case), safety=NO_NEEDLES
    )
    assert result.emission_status == "EMISSION_FAILED"
    assert "AUTHORITY_BINDING_MISMATCH" in (result.console_code or "")
    assert not Path(authority.execution_directory, "S1_01_Q.json").exists()


def test_t60_stage_closure_valid_other_identity_cases_cannot_reach_the_writer(
    make_authority,
):
    """The stage-closure writer has no payload parameter at all (FU9).

    So the FU7-era "valid other identity" constructions are provable only at the
    validator, which accepts them under their OWN claimed identity -- and a
    decision sealed for a different authority is what the writer refuses (T-105).
    """
    for closure in _stage_closure_cases().values():
        records._require_valid_cfg1_stage_closure_payload(closure)
    assert "payload" not in inspect.signature(emit_cfg1_stage_closure).parameters


def test_t61_a_fully_bound_canonical_payload_is_accepted_and_written(make_authority):
    """Positive control for the full ten-step sequence."""
    authority = make_authority("S1-X1")
    result = _emit_run(authority)
    assert result.emission_status == "RECORD_EMITTED"
    assert result.phase_reached == "EMISSION_CONFIRMED"
    assert result.fallback_attempted is False
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    records._require_valid_cfg1_run_payload(written)


# ---------------------------------------------------------------------------
# T-70 / T-71 / T-72 -- the exact byte bound, and the one-serialization pipeline
# ---------------------------------------------------------------------------


def _padded_serializer(total: int, *, only_record_version: str | None = None):
    """Pad one record kind's serialized bytes to an exact length.

    Trailing whitespace is valid JSON, so the padded bytes remain a genuine,
    parseable artifact -- which is what lets the boundary case be exercised at
    BOTH the writer's size check and the verifier's bounded read.
    """
    real = writers._serialize_artifact

    def _serialize(canonical):
        produced = real(canonical)
        if only_record_version and canonical.get("record_version") != only_record_version:
            return produced
        assert len(produced) < total
        return produced + b" " * (total - len(produced))

    return _serialize


def test_t70_exactly_the_bound_is_accepted_by_writer_and_verifier(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    monkeypatch.setattr(
        writers, "_serialize_artifact", _padded_serializer(MAX_CFG1_ARTIFACT_BYTES)
    )
    result = _emit_run(authority)
    assert result.emission_status == "RECORD_EMITTED"

    path = Path(authority.execution_directory, "S1_01_Q.json")
    assert path.stat().st_size == MAX_CFG1_ARTIFACT_BYTES
    assert binding.verify_cfg1_run_artifact_binding(str(path)) is True


def test_t71_one_byte_over_the_bound_is_refused_at_both_boundaries(
    make_authority, monkeypatch
):
    authority = make_authority("S1-X1")
    creates: list[str] = []
    real_open = writers._open_exclusive
    monkeypatch.setattr(
        writers, "_open_exclusive", lambda path: (creates.append(path), real_open(path))[1]
    )
    monkeypatch.setattr(
        writers,
        "_serialize_artifact",
        _padded_serializer(
            MAX_CFG1_ARTIFACT_BYTES + 1, only_record_version="pi-harness-cfg1-run.v1"
        ),
    )
    result = _emit_run(authority)
    # The size refusal is PRE_CREATE, so the one permitted fallback runs -- and
    # the ONLY exclusive-create that ever happens is the refusal artifact's.
    # The oversized primary artifact never reached a create at all.
    assert result.fallback_attempted is True
    assert result.emission_status == "EVIDENCE_REFUSED"
    run_path = str(Path(authority.execution_directory, "S1_01_Q.json"))
    assert creates == [run_path]
    assert Path(run_path).stat().st_size <= MAX_CFG1_ARTIFACT_BYTES
    written = json.loads(Path(run_path).read_text(encoding="utf-8"))
    assert written["finding_categories"] == ["SIZE_BOUND_EXCEEDED"]

    # And, independently, an on-disk oversized artifact is refused by the
    # verifier's bounded read BEFORE any JSON parse.
    oversized = Path(authority.execution_directory, "S1_02_R.json")
    oversized.write_bytes(b"{}" + b" " * MAX_CFG1_ARTIFACT_BYTES)
    assert binding.verify_cfg1_run_artifact_binding(str(oversized)) is False


def test_t72_exactly_one_serialization_and_the_same_bytes_are_written(
    make_authority, monkeypatch
):
    """For all three record kinds."""
    from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor as run_cfg1_stage

    from cfg1_builders import synthetic_run_executor

    serialized: list[bytes] = []
    written: list[bytes] = []
    real_serialize = writers._serialize_artifact
    real_write = writers._write_all

    def _serialize(canonical):
        produced = real_serialize(canonical)
        serialized.append(produced)
        return produced

    def _write(handle, data):
        written.append(data)
        return real_write(handle, data)

    monkeypatch.setattr(writers, "_serialize_artifact", _serialize)
    monkeypatch.setattr(writers, "_write_all", _write)

    authority = make_authority("S1-X1")
    run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    assert len(serialized) == len(written) >= 10  # 9 run records + 1 stage closure
    for produced, emitted in zip(serialized, written):
        assert emitted is produced

    # And a refusal record, through the same pipeline.
    serialized.clear()
    written.clear()
    other = make_authority("S1-X2")
    emit_cfg1_refusal_record(
        other, run_ordinal=1, refusal_payload=refusal_payload(stage_execution_id="S1-X2"),
        safety=NO_NEEDLES,
    )
    assert len(serialized) == 1
    assert written[0] is serialized[0]


# ---------------------------------------------------------------------------
# T-73 / T-74 / T-120 -- non-recursion, at every phase, for every cause
# ---------------------------------------------------------------------------


@pytest.fixture()
def refusal_writer_spy(monkeypatch):
    """Counts every entry into the refusal writer, wherever it came from."""
    calls: list[tuple] = []
    real = writers.emit_cfg1_refusal_record

    def _spy(authority, /, **kwargs):
        calls.append((authority, kwargs))
        return real(authority, **kwargs)

    monkeypatch.setattr(writers, "emit_cfg1_refusal_record", _spy)
    return calls


_REFUSAL_WRITER_FAILURE_POINTS = (
    "canonicalization",
    "schema_validation",
    "authority_binding",
    "scrub",
    "size_check",
    "write",
    "construction",
)


@pytest.mark.parametrize("failure_point", _REFUSAL_WRITER_FAILURE_POINTS)
def test_t73_the_refusal_writer_never_calls_itself(
    failure_point, make_authority, monkeypatch, refusal_writer_spy
):
    authority = make_authority(f"S1-{failure_point[:8]}")
    _inject_refusal_writer_failure(monkeypatch, failure_point)

    if failure_point == "construction":
        # Construction happens in the PRIMARY writer's fallback block, so the
        # refusal writer is never entered at all -- which is the strongest
        # possible form of "it did not call itself".
        result = _emit_run(authority, payload=_scrub_tripping_payload())
        assert result.emission_status == "EMISSION_FAILED"
        assert len(refusal_writer_spy) == 0
        return

    result = emit_cfg1_refusal_record(
        authority,
        run_ordinal=1,
        refusal_payload=refusal_payload(stage_execution_id=authority.stage_execution_id),
        safety=NO_NEEDLES,
    )
    assert result.emission_status in ("EMISSION_FAILED", "EMISSION_COLLISION")
    assert refusal_writer_spy == []  # zero RE-entries through the spied name


def _inject_refusal_writer_failure(monkeypatch, failure_point: str) -> None:
    if failure_point == "canonicalization":
        monkeypatch.setattr(
            writers, "_canonicalize", _raiser(Cfg1WriterError("PAYLOAD_NOT_CANONICALIZABLE"))
        )
    elif failure_point == "schema_validation":
        monkeypatch.setattr(
            writers,
            "_require_valid_cfg1_refusal_payload",
            _raiser(Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED")),
        )
    elif failure_point == "authority_binding":
        monkeypatch.setattr(
            writers, "_bind_refusal_identity", _raiser(Cfg1WriterError("AUTHORITY_BINDING_MISMATCH"))
        )
    elif failure_point == "scrub":
        monkeypatch.setattr(writers, "_scrub", _raiser(Cfg1WriterError("SCRUB_NEEDLE_MATCH")))
    elif failure_point == "size_check":
        monkeypatch.setattr(
            writers, "_size_check", _raiser(Cfg1WriterError("ARTIFACT_SIZE_BOUND_EXCEEDED"))
        )
    elif failure_point == "write":
        monkeypatch.setattr(writers, "_write_all", _raiser(OSError("injected write failure")))
    elif failure_point == "construction":
        monkeypatch.setattr(
            writers, "_build_refusal_payload", _raiser(RuntimeError("injected construction"))
        )
    else:  # pragma: no cover - the parametrize list is closed
        raise AssertionError(failure_point)


def _raiser(error):
    def _raise(*_args, **_kwargs):
        raise error

    return _raise


def _scrub_tripping_payload():
    """A payload whose scrub will trip, so the primary writer takes its fallback."""
    return run_payload()


_STAGE_CLOSURE_FAILURE_POINTS = (
    "pre_create_validation",
    "pre_create_scrub",
    "pre_create_size",
    "create_collision",
    "create_error",
    "write",
    "flush",
    "close",
)


@pytest.mark.parametrize("failure_point", _STAGE_CLOSURE_FAILURE_POINTS)
def test_t74_the_stage_closure_writer_never_calls_the_refusal_writer(
    failure_point, make_authority, monkeypatch, refusal_writer_spy
):
    from cfg1_builders import synthetic_run_executor

    from pi_harness_cfg1.stage_runner import _run_cfg1_stage_with_injected_executor as run_cfg1_stage

    authority = make_authority("S1-X1")
    if failure_point == "create_collision":
        Path(authority.execution_directory, "S1_stage_closure.json").write_text(
            "occupant", encoding="utf-8"
        )
    else:
        _inject_stage_closure_failure(monkeypatch, failure_point)

    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())
    assert result.stage_closure_confirmed is False
    assert result.disposition == "STAGE_CLOSURE_EMISSION_FAILED"
    assert refusal_writer_spy == []


def _inject_stage_closure_failure(monkeypatch, failure_point: str) -> None:
    real_validator = writers._require_valid_cfg1_stage_closure_payload
    real_scrub = writers._scrub
    real_size = writers._size_check
    real_open = writers._open_exclusive
    real_write = writers._write_all
    real_flush = writers._flush_handle
    real_close = writers._close_handle

    def _only_for_closure(real, raise_when_closure, error):
        def _wrapped(*args, **kwargs):
            if raise_when_closure(*args, **kwargs):
                raise error
            return real(*args, **kwargs)

        return _wrapped

    is_closure_payload = lambda payload, *a, **k: True  # noqa: E731 - only the closure validator is patched

    if failure_point == "pre_create_validation":
        monkeypatch.setattr(
            writers,
            "_require_valid_cfg1_stage_closure_payload",
            _only_for_closure(
                real_validator,
                is_closure_payload,
                Cfg1RecordValidationError("SCHEMA_VIOLATION", "INJECTED"),
            ),
        )
    elif failure_point == "pre_create_scrub":
        monkeypatch.setattr(
            writers,
            "_scrub",
            _only_for_closure(
                real_scrub,
                lambda canonical, *a, **k: canonical.get("record_kind") == "cfg1 stage closure",
                Cfg1WriterError("SCRUB_NEEDLE_MATCH"),
            ),
        )
    elif failure_point == "pre_create_size":
        monkeypatch.setattr(
            writers,
            "_size_check",
            _only_for_closure(
                real_size,
                lambda data: b"cfg1 stage closure" in data,
                Cfg1WriterError("ARTIFACT_SIZE_BOUND_EXCEEDED"),
            ),
        )
    elif failure_point == "create_error":
        monkeypatch.setattr(
            writers,
            "_open_exclusive",
            _only_for_closure(
                real_open,
                lambda path: path.endswith("_stage_closure.json"),
                OSError("injected non-collision create failure"),
            ),
        )
    elif failure_point in ("write", "flush", "close"):
        marker = {"closure_handle": None}

        def _open(path):
            handle = real_open(path)
            if path.endswith("_stage_closure.json"):
                marker["closure_handle"] = handle
            return handle

        monkeypatch.setattr(writers, "_open_exclusive", _open)
        target = {"write": real_write, "flush": real_flush, "close": real_close}[failure_point]
        name = {"write": "_write_all", "flush": "_flush_handle", "close": "_close_handle"}[
            failure_point
        ]

        def _fail(handle, *args, **kwargs):
            if handle is marker["closure_handle"]:
                if failure_point != "write":
                    target(handle, *args, **kwargs)
                raise OSError(f"injected {failure_point} failure")
            return target(handle, *args, **kwargs)

        monkeypatch.setattr(writers, name, _fail)
    else:  # pragma: no cover
        raise AssertionError(failure_point)
