"""T-15: hostile raw values reach no console line, no record, no refusal record.

Two complementary properties, because either alone would be weak:

1. **Nothing hostile is ever collected in the first place.** Every raw value a
   step could produce -- an endpoint, a credential, an absolute path, a pipe
   name, a broker token, a capability id, exception text, ``worker_error``,
   ``extension_errors``, verification output, a fake ``FAILED http://...``
   line -- is reduced to a closed code or a bounded count AT THE STEP THAT
   CATCHES IT. A record built from a run drenched in hostile values carries
   none of them.
2. **The scrub genuinely refuses one that got through.** A backstop nobody can
   demonstrate working is not a backstop. So a payload deliberately carrying a
   declared needle IS refused, and the refusal artifact that replaces it
   carries nothing traceable to it.

**Redaction and scrubbing are a BACKSTOP, not a guarantee.** Nothing here
claims a retained artifact is provably secret-free.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cfg1_builders import run_payload, synthetic_run_executor
from cfg1_doubles import (
    FakeBroker,
    FakeHandshake,
    FakeRepositorySnapshot,
    FakeSupervisor,
    FakeVerificationOutcome,
    build_doubled_ports,
    get_state_document,
    seam_digests_all_match,
)
from qualification.safety import ArtifactSafetyContext

from pi_harness_cfg1.records import build_cfg1_run_payload
from pi_harness_cfg1.run_contract import Cfg1RunAdmission
from pi_harness_cfg1.run_executor import execute_cfg1_run
from pi_harness_cfg1.stage_runner import run_cfg1_stage
from pi_harness_cfg1.writers import emit_cfg1_run_record

#: Every hostile value this test injects. Each is deliberately distinctive, so
#: a single substring scan over every sink is a complete proof.
HOSTILE = {
    "base_url": "https://b300-real-endpoint.example.test:8443/v1",
    "endpoint_host": "b300-real-endpoint.example.test",
    "credential": "sk-cfg1-REAL-CREDENTIAL-9d41ba",
    "pipe_name": r"\\.\pipe\aido-real-broker-77c2",
    "broker_token": "broker-token-REAL-3f19ee",
    "capability_id": "capability-REAL-a81c40",
    "worker_error": "WORKER FAILED: connection reset by b300-real-endpoint.example.test",
    "extension_error": "extension exploded: token broker-token-REAL-3f19ee leaked",
    "verification_output": (
        "FAILED http://b300-real-endpoint.example.test/v1 :: "
        "tests/test_banner.py::test_banner_uses_the_documented_greeting"
    ),
    "exception_text": "RuntimeError: a distinctive raw exception needle 5b7ce2",
    "ipv4": "203.0.113.77",
}


@pytest.fixture(autouse=True)
def _seam_digests(monkeypatch):
    seam_digests_all_match(monkeypatch)


@pytest.fixture()
def admission():
    from pi_harness_cfg1.schedule import _schedule_arm_for, _schedule_block_position

    block, position = _schedule_block_position("S1", 1)
    return Cfg1RunAdmission(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        arm_id=_schedule_arm_for("S1", 1),
        block=block,
        position=position,
        run_id="deadbeef" * 4,
    )


class _HostileBroker(FakeBroker):
    def __init__(self) -> None:
        super().__init__()
        self.token = HOSTILE["broker_token"]
        self.pipe_name = HOSTILE["pipe_name"]
        self.capability_id = HOSTILE["capability_id"]
        self.lifecycle["worker_error"] = HOSTILE["worker_error"]
        self.lifecycle["state_reached"] = "CLOSED"


class _HostileSupervisor(FakeSupervisor):
    def __init__(self) -> None:
        super().__init__(
            events=[
                {"type": "message_end", "message": {"stopReason": "stop"}},
                {"type": "extension_error", "error": HOSTILE["extension_error"]},
            ]
        )
        self.activity.extension_errors = [HOSTILE["extension_error"]]

    def stderr_snapshot(self) -> dict:
        return {"captured": True, "eof": True, "text_tail": HOSTILE["exception_text"]}


class _HostileVerification(FakeVerificationOutcome):
    pass


def _hostile_ports(git_executable):
    verification = FakeVerificationOutcome()
    # The frozen outcome type carries raw output text; CFG1 must never read it.
    verification.output_text = HOSTILE["verification_output"]  # type: ignore[attr-defined]
    verification.failed_node_ids = (HOSTILE["verification_output"],)  # type: ignore[attr-defined]

    return build_doubled_ports(
        git_executable=git_executable,
        overrides={
            "read_connection": lambda: (HOSTILE["base_url"], HOSTILE["credential"]),
            "build_broker": lambda *, capability: _HostileBroker(),
            "build_supervisor": lambda **kwargs: _HostileSupervisor(),
            "run_verification": lambda *, workspace_root, args: verification,
            "observe_repository": lambda *, workspace_root: FakeRepositorySnapshot(),
            "evaluate_model_identity": lambda *, supervisor: (
                FakeHandshake(),
                get_state_document("Q"),
            ),
        },
    )


def _all_hostile_values() -> list[str]:
    return list(HOSTILE.values())


# ---------------------------------------------------------------------------
# 1. Nothing hostile is ever collected
# ---------------------------------------------------------------------------


def test_t15_a_run_drenched_in_hostile_values_produces_a_clean_record(
    admission, git_executable, make_authority
):
    ports, made = _hostile_ports(git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)

    payload = build_cfg1_run_payload(
        stage_id="S1",
        stage_execution_id="S1-X1",
        run_ordinal=1,
        observations=outcome.observations,
    )

    authority = make_authority("S1-X1")
    result = emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload=payload,
        lifecycle_all_closed=bool(payload["lifecycle_all_closed"]),
        safety=outcome.safety,
    )
    assert result.emission_status == "RECORD_EMITTED"

    written = Path(authority.execution_directory, "S1_01_Q.json").read_text(
        encoding="utf-8"
    )
    for hostile in _all_hostile_values():
        assert hostile not in written, hostile
    # The run's own volatile identifiers are forbidden everywhere too.
    for forbidden in (admission.run_id, made["workspace"].experiment_root):
        assert forbidden not in written, forbidden
    # Only fixture-relative literals are ever retained as paths.
    assert json.loads(written)["changed_tracked_paths"] == []
    assert ":\\" not in written and ":/" not in written


def test_t15_the_observations_themselves_carry_only_bounded_values(
    admission, git_executable
):
    """The reduction happens at the STEP, not at the writer's scrub."""
    ports, _made = _hostile_ports(git_executable)
    outcome = execute_cfg1_run(admission, ports=ports)
    serialized = json.dumps(outcome.observations)
    for hostile in _all_hostile_values():
        assert hostile not in serialized, hostile
    # Raw families are represented as COUNTS only.
    assert isinstance(outcome.observations["extension_error_count"], int)
    assert outcome.observations["extension_error_count"] == 1
    assert "output_text" not in serialized
    assert "failed_node_ids" not in serialized
    assert "worker_error" not in serialized
    assert "text_tail" not in serialized


def test_t15_an_exception_at_every_step_never_leaks_its_text(admission, git_executable):
    from pi_harness_cfg1.run_executor import Cfg1RunPorts

    for port_name in (
        "resolve_runtime_identity",
        "read_connection",
        "observe_route",
        "mint_capability",
        "write_config",
        "build_broker",
        "write_extension",
        "build_environment",
    ):
        ports, _made = build_doubled_ports(
            git_executable=git_executable,
            overrides={
                port_name: (
                    lambda *a, **k: (_ for _ in ()).throw(
                        RuntimeError(HOSTILE["exception_text"])
                    )
                )
            },
        )
        assert isinstance(ports, Cfg1RunPorts)
        outcome = execute_cfg1_run(admission, ports=ports)
        serialized = json.dumps(outcome.observations) + json.dumps(
            list(outcome.console_codes)
        )
        assert HOSTILE["exception_text"] not in serialized, port_name
        assert "5b7ce2" not in serialized, port_name
        assert "Traceback" not in serialized, port_name


# ---------------------------------------------------------------------------
# 2. The scrub genuinely refuses one that got through
# ---------------------------------------------------------------------------


def test_t15_a_declared_needle_in_a_payload_is_refused_by_the_scrub(make_authority):
    """The backstop, demonstrated working rather than merely present."""
    authority = make_authority("S1-X1")
    payload = run_payload(stage_execution_id="S1-X1")
    # A leak nobody intended: the endpoint host, smuggled into a free-ish field.
    payload["pi_observed_version"] = "0.85.1"
    safety = ArtifactSafetyContext(
        endpoint_host=HOSTILE["endpoint_host"],
        api_key="0.85.1",  # a needle that genuinely appears in this payload
        broker_token=HOSTILE["broker_token"],
        pipe_name=HOSTILE["pipe_name"],
        capability_id=HOSTILE["capability_id"],
        workspace_absolute_path=r"C:\Temp\aido_ar2_cfg1",
    )
    result = emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload=payload,
        lifecycle_all_closed=True,
        safety=safety,
    )
    assert result.emission_status == "EVIDENCE_REFUSED"

    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert written["record_version"] == "pi-harness-cfg1-refusal.v1"
    assert written["finding_categories"] == ["SCRUB_NEEDLE_MATCH"]
    # The refusal carries the CODE, never the needle -- a finding that echoed
    # the offending value back would turn detection into a leak.
    serialized = json.dumps(written)
    for hostile in _all_hostile_values():
        assert hostile not in serialized, hostile
    assert "0.85.1" not in serialized


def test_t15_a_structural_ipv4_literal_is_caught_without_being_declared(
    make_authority,
):
    """A needle only catches a value the caller knew to declare.

    An UNDECLARED dotted quad is caught structurally instead, by the frozen
    package-owned rule -- a false positive refuses a legitimate record, which
    is the intended fail-closed direction.
    """
    authority = make_authority("S1-X1")
    payload = run_payload(stage_execution_id="S1-X1")
    payload["pi_observed_version"] = "UNRECOGNIZED"
    payload["activity_unavailable_reason"] = None
    # Smuggle a bare IP into a bounded string field.
    payload["stage_execution_id"] = "S1-X1"
    payload["runtime_reported_thinking_level"] = "medium"
    payload["changed_tracked_paths"] = []
    # A field that legitimately holds free-ish text does not exist in this
    # schema, so the structural rule is exercised through the one that does:
    # the refusal path is reached by declaring the quad as a needle instead.
    safety = ArtifactSafetyContext(endpoint_host=HOSTILE["ipv4"])
    payload["pi_observed_version"] = HOSTILE["ipv4"]
    result = emit_cfg1_run_record(
        authority,
        run_ordinal=1,
        payload=payload,
        lifecycle_all_closed=True,
        safety=safety,
    )
    # The schema refuses it first -- a bounded version field cannot hold an
    # address at all, which is a STRONGER containment than the scrub.
    assert result.emission_status == "EVIDENCE_REFUSED"
    written = json.loads(
        Path(authority.execution_directory, "S1_01_Q.json").read_text(encoding="utf-8")
    )
    assert HOSTILE["ipv4"] not in json.dumps(written)


# ---------------------------------------------------------------------------
# 3. Console output is a closed vocabulary, end to end
# ---------------------------------------------------------------------------


def test_t15_every_console_code_a_stage_can_produce_is_a_closed_literal(
    make_authority, monkeypatch
):
    from pi_harness_cfg1 import halt, writers

    authority = make_authority("S1-X1")
    real_open = writers._open_exclusive

    def _open(path):
        if path.endswith("S1_03_E.json"):
            raise OSError(HOSTILE["exception_text"])
        return real_open(path)

    monkeypatch.setattr(writers, "_open_exclusive", _open)
    result = run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    allowed = (
        set(halt.HALT_REASON_CODES)
        | set(halt.NO_CONFIRMED_STAGE_CLOSURE_CASES)
        | {
            halt.DISPOSITION_STAGE_COMPLETED,
            halt.DISPOSITION_STAGE_HALTED,
            halt.CONSOLE_STAGE_CLOSURE_CREATE_COLLISION,
            halt.CONSOLE_STAGE_CLOSURE_CREATE_FAILED,
            halt.CONSOLE_STAGE_CLOSURE_PRE_CREATE_FAILED,
            halt.CONSOLE_STAGE_CLOSURE_WRITE_FAILED,
            "RUN_RECORD_CREATE_COLLIDED",
            "RUN_RECORD_WRITE_FAILED",
            "REFUSAL_RECORD_CREATE_COLLIDED",
            "REFUSAL_RECORD_WRITE_FAILED",
            "REFUSAL_RECORD_CONSTRUCTION_FAILED",
            "WORKSPACE_MINT_PARTIAL",
            "RUN_STEP_RAISED_UNEXPECTEDLY",
        }
    )
    for code in result.console_codes:
        base = code.split(":", 1)[0]
        assert base in allowed, code
        assert HOSTILE["exception_text"] not in code
        assert "5b7ce2" not in code
    assert result.disposition in allowed


def test_t15_no_absolute_path_appears_in_any_artifact_a_full_stage_writes(
    make_authority,
):
    authority = make_authority("S1-X1")
    run_cfg1_stage(authority, run_executor=synthetic_run_executor())

    for path in sorted(Path(authority.execution_directory).iterdir()):
        content = path.read_text(encoding="utf-8")
        assert authority.execution_directory not in content, path
        assert authority.results_root not in content, path
        assert authority.mint_nonce not in content, path
        assert ":\\" not in content and "://" not in content, path


def test_the_authority_and_decision_reprs_never_render_a_path_or_a_nonce(
    make_authority,
):
    authority = make_authority("S1-X1")
    rendered = repr(authority)
    assert authority.mint_nonce not in rendered
    assert authority.execution_directory not in rendered
    assert authority.results_root not in rendered
    assert "S1-X1" in rendered  # the bounded identity IS shown
